"""Optional JSON audit sidecar describing the changes applied to an export.

The sidecar is written next to the exported file as ``<name>.audit.json``. It
records what was requested and what was written so users have a transparent,
reviewable record. It intentionally states that metadata does not prove capture
facts.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from core.metadata_models import ChangeDiff, ChangePlan, ExportResult

AUDIT_DISCLAIMER = (
    "Metadata is user-editable and does NOT prove when, where, or how an image "
    "was actually captured. This record documents an intentional metadata edit."
)


def build_audit_record(plan: ChangePlan, result: ExportResult, diff: ChangeDiff) -> dict:
    """Assemble the audit dictionary (JSON-serialisable)."""
    return {
        "tool": "LensTrace Studio",
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": AUDIT_DISCLAIMER,
        "source_file": Path(plan.source_path).name,
        "destination_file": Path(result.destination_path).name,
        "converted_to_jpeg": result.converted_to_jpeg,
        "warnings": list(result.warnings),
        "applied": {
            "preset_id": plan.preset_id,
            "make": plan.make,
            "model": plan.model,
            "lens_model": plan.lens_model or None,
            "software": plan.software,
            "date_strategy": plan.date_strategy.value,
            "datetime_original": _iso(plan.datetime_original),
            "create_date": _iso(plan.create_date),
            "modify_date": _iso(plan.modify_date),
            "utc_offset": plan.utc_offset,
            "timezone_name": plan.timezone_name,
            "gps": _gps_dict(plan),
            "remove_gps": plan.remove_gps,
            "strip_all_metadata": plan.strip_all_metadata,
            "exposure": _exposure_dict(plan),
            "resolution": _resolution_dict(plan),
        },
        "diff": [row.model_dump() for row in diff.rows],
    }


def _exposure_dict(plan: ChangePlan) -> dict | None:
    """Record the exposure simulation, clearly labelling generated values."""
    resolved = plan.resolved_exposure
    if resolved is None or plan.exposure_mode.value == "preserve":
        return {"mode": plan.exposure_mode.value, "simulated": False}
    return {
        "mode": plan.exposure_mode.value,
        "profile_id": resolved.profile_id,
        "profile_display_name": resolved.profile_display_name,
        # Explicit, non-deceptive label for any generated exposure values.
        "label": "Simulated exposure metadata" if resolved.is_simulated else "User/preserved",
        "simulated": resolved.is_simulated,
        "fields": {name: source.value for name, source in resolved.sources.items()},
    }


def _resolution_dict(plan: ChangePlan) -> dict | None:
    """Record any output-resolution transform, including honest upscale notes."""
    res = plan.resolution
    if res is None or not res.changes_dimensions:
        return {"mode": res.mode.value if res else "keep", "changed": False}
    return {
        "mode": res.mode.value,
        "fit": res.fit.value,
        "source": f"{res.source_width}x{res.source_height}",
        "output": f"{res.output_width}x{res.output_height}",
        "changed": True,
        "is_upscale": res.is_upscale,
        "note": (
            "Pixel dimensions were changed. This does not restore real detail "
            "that was absent from the source."
        ),
    }


def write_audit_sidecar(plan: ChangePlan, result: ExportResult, diff: ChangeDiff) -> Path:
    """Write the audit sidecar next to the export and return its path."""
    record = build_audit_record(plan, result, diff)
    sidecar = Path(result.destination_path).with_suffix(
        Path(result.destination_path).suffix + ".audit.json"
    )
    sidecar.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return sidecar


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _gps_dict(plan: ChangePlan) -> dict | None:
    if plan.gps is None:
        return None
    return {
        "latitude": plan.gps.latitude,
        "longitude": plan.gps.longitude,
        "altitude_m": plan.gps.altitude_m,
        "address_label": plan.gps.address_label,
    }
