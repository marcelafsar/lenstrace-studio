"""The shared :class:`MetadataEngine` — the single public entry point.

Every interface (desktop backend, Telegram bot, Discord bot) uses this class.
No interface should read or write metadata directly.
"""

from __future__ import annotations

from pathlib import Path

from core import metadata_reader, metadata_writer
from core.audit import write_audit_sidecar
from core.datetime_utils import parse_exif_datetime
from core.exceptions import InvalidCoordinateError, LensTraceError, MetadataWriteError
from core.metadata_models import (
    ChangeDiff,
    ChangePlan,
    DateStrategy,
    ExportResult,
    FieldChange,
    FieldVerification,
    GPSData,
    MetadataSummary,
    MetadataVerification,
)
from core.presets.loader import PresetLoader, get_default_loader
from core.validation import build_output_path, validate_coordinates


class MetadataEngine:
    """Typed, interface-agnostic metadata operations."""

    def __init__(self, preset_loader: PresetLoader | None = None) -> None:
        self._presets = preset_loader or get_default_loader()

    # ---- Inspection -----------------------------------------------------

    def inspect_image(self, path: Path | str) -> MetadataSummary:
        """Read the current metadata of an image without modifying it."""
        return metadata_reader.read_summary(Path(path))

    # ---- Planning -------------------------------------------------------

    def build_change_plan(
        self,
        source_path: Path | str,
        output_dir: Path | str,
        *,
        preset_id: str | None = None,
        lens_id: str | None = None,
        make: str | None = None,
        model: str | None = None,
        lens_model: str | None = None,
        software: str | None = None,
        keep_original_lens: bool = False,
        remove_lens: bool = False,
        date_strategy: DateStrategy = DateStrategy.KEEP_ORIGINAL,
        datetime_original=None,
        create_date=None,
        modify_date=None,
        utc_offset: str | None = None,
        timezone_name: str | None = None,
        gps: GPSData | None = None,
        remove_gps: bool = False,
        strip_all_metadata: bool = False,
        convert_to_jpeg: bool = False,
        write_audit_sidecar: bool = True,
        filename_suffix: str = "_metadata",
        preserve_name: bool = False,
        on_collision: str = "increment",
    ) -> ChangePlan:
        """Assemble a :class:`ChangePlan`, resolving a device preset if given."""
        from core.presets.lens_resolver import resolve_lens_by_id

        source_path = Path(source_path)
        summary = self.inspect_image(source_path)

        focal_length_mm = focal_length_35mm = f_number = None
        lens_specification: list[float] | None = None
        lens_is_generic = False

        if preset_id:
            device = self._presets.get(preset_id)
            make = make or device.manufacturer
            model = model or device.exif_model
            software = software if software is not None else device.software_default
            # Resolve the selected lens to a GUARANTEED non-empty LensModel plus
            # any optical values the preset supplies (never invented). This is
            # the fix for "device model written but lens blank".
            if lens_id and not keep_original_lens and not remove_lens:
                resolved = resolve_lens_by_id(device, lens_id)
                if resolved is None:
                    raise LensTraceError(
                        f"Unknown lens id {lens_id!r} for preset {preset_id!r}",
                        user_message="The selected lens is not available for this device.",
                    )
                lens_model = lens_model or resolved.lens_model
                focal_length_mm = resolved.focal_length_mm
                focal_length_35mm = resolved.focal_length_35mm
                f_number = resolved.f_number
                lens_specification = resolved.lens_specification
                lens_is_generic = resolved.is_generic

        destination = build_output_path(
            source_path,
            Path(output_dir),
            suffix=filename_suffix,
            preserve_name=preserve_name,
            on_collision=on_collision,
        )

        return ChangePlan(
            source_path=source_path,
            destination_path=destination,
            original_summary=summary,
            preset_id=preset_id,
            lens_id=lens_id,
            make=make,
            model=model,
            lens_model=lens_model,
            focal_length_mm=focal_length_mm,
            focal_length_35mm=focal_length_35mm,
            f_number=f_number,
            lens_specification=lens_specification,
            lens_is_generic=lens_is_generic,
            keep_original_lens=keep_original_lens,
            remove_lens=remove_lens,
            software=software,
            date_strategy=date_strategy,
            datetime_original=datetime_original,
            create_date=create_date,
            modify_date=modify_date,
            utc_offset=utc_offset,
            timezone_name=timezone_name,
            gps=gps,
            remove_gps=remove_gps,
            strip_all_metadata=strip_all_metadata,
            convert_to_jpeg=convert_to_jpeg,
            write_audit_sidecar=write_audit_sidecar,
        )

    def validate_change_plan(self, plan: ChangePlan) -> None:
        """Validate a plan before applying. Raises a :class:`LensTraceError`."""
        if plan.gps is not None:
            validate_coordinates(plan.gps.latitude, plan.gps.longitude)
        if plan.gps is not None and plan.remove_gps:
            raise InvalidCoordinateError(
                "Plan both sets and removes GPS",
                user_message="Choose either to set GPS coordinates or to remove them, not both.",
            )
        if Path(plan.source_path).resolve() == Path(plan.destination_path).resolve():
            raise LensTraceError(
                "Destination equals source",
                user_message="The export would overwrite the original; choose a different output.",
            )

    # ---- Diff (for the review screen) ----------------------------------

    def build_diff(self, plan: ChangePlan) -> ChangeDiff:
        """Compute the before/after diff shown on the review screen."""
        rows: list[FieldChange] = []

        def row(field: str, old: str | None, new: str | None) -> None:
            if new is None and old is None:
                return
            if plan.strip_all_metadata:
                status = "removed" if old is not None else "preserved"
                rows.append(FieldChange(field=field, original=old, new=None, status=status))
                return
            if new is None:
                status = "preserved"
                new = old
            elif old is None:
                status = "added"
            elif old != new:
                status = "changed"
            else:
                status = "preserved"
            rows.append(FieldChange(field=field, original=old, new=new, status=status))

        o = plan.original_summary
        row("Make", o.make if o else None, plan.make)
        row("Model", o.model if o else None, plan.model)

        # Lens: reflect keep/remove/new-selection explicitly.
        old_lens = o.lens_model if o else None
        if plan.remove_lens:
            row("Lens model", old_lens, None)
        elif plan.keep_original_lens:
            if old_lens:
                row("Lens model", old_lens, old_lens)
        elif plan.lens_model:
            label = plan.lens_model + ("  (generic)" if plan.lens_is_generic else "")
            row("Lens model", old_lens, label)
            if plan.focal_length_mm is not None:
                row("Focal length", None, f"{plan.focal_length_mm:g} mm")
            if plan.f_number is not None:
                row("Aperture", None, f"f/{plan.f_number:g}")
            if plan.focal_length_35mm is not None:
                row("35mm equivalent", None, f"{plan.focal_length_35mm:g} mm")

        row("Software", o.software if o else None, plan.software)

        if plan.date_strategy == DateStrategy.SET_EXPLICIT and plan.datetime_original:
            row(
                "Date taken",
                o.datetime_original if o else None,
                plan.datetime_original.strftime("%Y:%m:%d %H:%M:%S"),
            )
        elif o and o.datetime_original:
            row("Date taken", o.datetime_original, o.datetime_original)

        if plan.utc_offset:
            row("UTC offset", o.offset_time_original if o else None, plan.utc_offset)

        old_gps = (
            f"{o.gps_latitude:.5f}, {o.gps_longitude:.5f}"
            if o and o.has_gps and o.gps_latitude is not None
            else None
        )
        if plan.remove_gps:
            row("GPS", old_gps, None)
        elif plan.gps is not None:
            row("GPS", old_gps, f"{plan.gps.latitude:.5f}, {plan.gps.longitude:.5f}")
        elif old_gps is not None:
            row("GPS", old_gps, old_gps)

        return ChangeDiff(rows=rows)

    # ---- Applying -------------------------------------------------------

    def apply_metadata(self, plan: ChangePlan) -> ExportResult:
        """Validate, apply, and VERIFY a change plan, writing the exported copy.

        After writing, the exported file is read back and compared against the
        plan. A requested LensModel that is missing from the output is treated as
        an export failure (the caller must not present it as success).
        """
        self.validate_change_plan(plan)
        base_exif = self._load_base_exif(plan)
        result = metadata_writer.write_metadata(base_exif, plan)

        if not plan.strip_all_metadata:
            verification = self.verify_exported_metadata(result.destination_path, plan)
            result.verification = verification
            result.warnings = list(result.warnings) + verification.warnings
            if not verification.lens_model_ok:
                result.success = False
                raise MetadataWriteError(
                    "Requested LensModel missing from exported file",
                    user_message=(
                        "The lens information could not be written to the exported "
                        "file. Try exporting as JPEG for reliable metadata."
                    ),
                )

        result.sha256 = self._sha256(result.destination_path)

        if plan.write_audit_sidecar and not plan.strip_all_metadata:
            diff = self.build_diff(plan)
            result.audit_sidecar_path = write_audit_sidecar(plan, result, diff)
        return result

    def verify_exported_metadata(self, path: Path | str, plan: ChangePlan) -> MetadataVerification:
        """Read an exported file back and confirm it matches the change plan."""
        summary = self.inspect_image(path)
        fields: list[FieldVerification] = []
        warnings: list[str] = []

        def check(name: str, requested: str | None, actual: str | None) -> bool:
            if requested is None:
                return True
            ok = actual is not None and actual.strip() == requested.strip()
            fields.append(FieldVerification(field=name, requested=requested, actual=actual, ok=ok))
            if not ok:
                warnings.append(f"{name} was requested but not verified in the output.")
            return ok

        check("Make", plan.make, summary.make)
        check("Model", plan.model, summary.model)

        # Lens: only a hard requirement when a lens was applied (not kept/removed).
        lens_model_ok = True
        expected_lens = (
            plan.lens_model if (not plan.keep_original_lens and not plan.remove_lens) else None
        )
        if expected_lens:
            lens_model_ok = (
                summary.lens_model is not None
                and summary.lens_model.strip() == expected_lens.strip()
            )
            fields.append(
                FieldVerification(
                    field="LensModel",
                    requested=expected_lens,
                    actual=summary.lens_model,
                    ok=lens_model_ok,
                )
            )
            if not lens_model_ok:
                warnings.append("LensModel was requested but is missing from the output.")

        if plan.date_strategy == DateStrategy.SET_EXPLICIT and plan.datetime_original is not None:
            check(
                "DateTimeOriginal",
                plan.datetime_original.strftime("%Y:%m:%d %H:%M:%S"),
                summary.datetime_original,
            )
        if plan.utc_offset:
            check("OffsetTimeOriginal", plan.utc_offset, summary.offset_time_original)
        if plan.gps is not None:
            gps_ok = summary.has_gps
            fields.append(
                FieldVerification(
                    field="GPS",
                    requested="present",
                    actual="present" if gps_ok else "missing",
                    ok=gps_ok,
                )
            )
            if not gps_ok:
                warnings.append("GPS coordinates were requested but not verified.")

        all_ok = lens_model_ok and all(f.ok for f in fields)
        return MetadataVerification(
            ok=all_ok,
            lens_model_ok=lens_model_ok,
            lens_model_requested=expected_lens,
            lens_model_actual=summary.lens_model,
            fields=fields,
            warnings=warnings,
        )

    @staticmethod
    def _sha256(path: Path | str) -> str:
        import hashlib

        digest = hashlib.sha256()
        with Path(path).open("rb") as fh:
            for block in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def remove_metadata(
        self,
        source_path: Path | str,
        output_dir: Path | str,
        *,
        filename_suffix: str = "_clean",
        write_audit: bool = True,
    ) -> ExportResult:
        """Export a copy with all metadata stripped."""
        plan = self.build_change_plan(
            source_path,
            output_dir,
            strip_all_metadata=True,
            filename_suffix=filename_suffix,
            write_audit_sidecar=write_audit,
        )
        return self.apply_metadata(plan)

    def export_image(self, plan: ChangePlan) -> ExportResult:
        """Alias for :meth:`apply_metadata` reflecting the review→export step."""
        return self.apply_metadata(plan)

    # ---- Internals ------------------------------------------------------

    def _load_base_exif(self, plan: ChangePlan) -> dict:
        from core.metadata_reader import _extract_exif_dict, detect_format

        try:
            return _extract_exif_dict(Path(plan.source_path), detect_format(Path(plan.source_path)))
        except LensTraceError:
            return {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "Interop": {}, "thumbnail": None}

    @staticmethod
    def datetime_from_exif(value: str):
        """Helper exposed for interfaces: parse an EXIF datetime string."""
        return parse_exif_datetime(value)
