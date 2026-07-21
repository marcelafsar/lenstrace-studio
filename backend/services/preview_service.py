"""Translate API change requests into engine change plans and execute them."""

from __future__ import annotations

from pathlib import Path

from backend.api.schemas import ChangeRequest
from backend.config import get_settings
from backend.services.session_service import get_session_store
from core.audit import AUDIT_DISCLAIMER
from core.datetime_utils import offset_for_timezone, parse_user_datetime
from core.exceptions import LensTraceError, MetadataReadError
from core.metadata_engine import MetadataEngine
from core.metadata_models import ChangeDiff, ChangePlan, DateStrategy, ExportResult, GPSData

_engine = MetadataEngine()

CAPTURE_DISCLAIMER = (
    "Reminder: metadata is editable and does not prove when, where, or how an "
    "image was actually captured."
)


def _resolve_source(request: ChangeRequest) -> Path:
    entry = get_session_store().get(request.file_id)
    if entry is None:
        raise MetadataReadError(
            f"Unknown file_id {request.file_id!r}",
            user_message="That image is no longer available; please re-select it.",
        )
    return entry.path


def _resolve_output_dir(request: ChangeRequest) -> Path:
    if request.output_dir:
        return Path(request.output_dir)
    return get_settings().default_output_dir


def build_plan(request: ChangeRequest) -> ChangePlan:
    """Construct a validated :class:`ChangePlan` from a request DTO."""
    source = _resolve_source(request)
    output_dir = _resolve_output_dir(request)

    date_strategy = DateStrategy.KEEP_ORIGINAL
    dt_original = None
    utc_offset = request.utc_offset

    if request.set_datetime and request.datetime_original:
        date_strategy = DateStrategy.SET_EXPLICIT
        dt_original = parse_user_datetime(request.datetime_original)
        if utc_offset is None and request.timezone_name:
            utc_offset = offset_for_timezone(request.timezone_name, dt_original)

    gps = None
    if request.gps is not None and not request.remove_gps:
        gps = GPSData(
            latitude=request.gps.latitude,
            longitude=request.gps.longitude,
            altitude_m=request.gps.altitude_m,
            address_label=request.gps.address_label,
        )

    plan = _engine.build_change_plan(
        source,
        output_dir,
        preset_id=request.preset_id,
        lens_id=request.lens_id,
        make=request.make,
        model=request.model,
        lens_model=request.lens_model,
        software=request.software,
        date_strategy=date_strategy,
        datetime_original=dt_original,
        create_date=dt_original,
        modify_date=dt_original,
        utc_offset=utc_offset,
        timezone_name=request.timezone_name,
        gps=gps,
        remove_gps=request.remove_gps,
        strip_all_metadata=request.strip_all_metadata,
        write_audit_sidecar=request.write_audit_sidecar,
        filename_suffix=request.filename_suffix,
        preserve_name=request.preserve_name,
        on_collision=request.on_collision,
    )
    _engine.validate_change_plan(plan)
    return plan


def preview(request: ChangeRequest) -> tuple[ChangeDiff, str]:
    """Return the before/after diff and the destination filename."""
    plan = build_plan(request)
    diff = _engine.build_diff(plan)
    return diff, Path(plan.destination_path).name


def export(request: ChangeRequest) -> ExportResult:
    """Apply the change plan and write the exported copy."""
    plan = build_plan(request)
    return _engine.apply_metadata(plan)


def export_batch(requests: list[ChangeRequest]) -> list[tuple[str, ExportResult | LensTraceError]]:
    """Process many requests, isolating per-file failures."""
    results: list[tuple[str, ExportResult | LensTraceError]] = []
    for req in requests:
        try:
            results.append((req.file_id, export(req)))
        except LensTraceError as exc:
            results.append((req.file_id, exc))
    return results


def disclaimer() -> str:
    return f"{CAPTURE_DISCLAIMER} {AUDIT_DISCLAIMER}"
