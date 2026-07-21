"""The shared :class:`MetadataEngine` — the single public entry point.

Every interface (desktop backend, Telegram bot, Discord bot) uses this class.
No interface should read or write metadata directly.
"""

from __future__ import annotations

from pathlib import Path

from core import metadata_reader, metadata_writer
from core.audit import write_audit_sidecar
from core.datetime_utils import parse_exif_datetime
from core.exceptions import InvalidCoordinateError, LensTraceError
from core.metadata_models import (
    ChangeDiff,
    ChangePlan,
    DateStrategy,
    ExportResult,
    FieldChange,
    GPSData,
    MetadataSummary,
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
        date_strategy: DateStrategy = DateStrategy.KEEP_ORIGINAL,
        datetime_original=None,
        create_date=None,
        modify_date=None,
        utc_offset: str | None = None,
        timezone_name: str | None = None,
        gps: GPSData | None = None,
        remove_gps: bool = False,
        strip_all_metadata: bool = False,
        write_audit_sidecar: bool = True,
        filename_suffix: str = "_metadata",
        preserve_name: bool = False,
        on_collision: str = "increment",
    ) -> ChangePlan:
        """Assemble a :class:`ChangePlan`, resolving a device preset if given."""
        source_path = Path(source_path)
        summary = self.inspect_image(source_path)

        if preset_id:
            device = self._presets.get(preset_id)
            make = make or device.manufacturer
            model = model or device.exif_model
            software = software if software is not None else device.software_default
            if lens_id:
                lens = next((ln for ln in device.lenses if ln.id == lens_id), None)
                if lens and lens.lens_model:
                    lens_model = lens_model or lens.lens_model

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
            make=make,
            model=model,
            lens_model=lens_model,
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
        row("Lens model", o.lens_model if o else None, plan.lens_model or None)
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
        """Validate and apply a change plan, writing the exported copy."""
        self.validate_change_plan(plan)
        base_exif = self._load_base_exif(plan)
        result = metadata_writer.write_metadata(base_exif, plan)
        if plan.write_audit_sidecar and not plan.strip_all_metadata:
            diff = self.build_diff(plan)
            result.audit_sidecar_path = write_audit_sidecar(plan, result, diff)
        return result

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
