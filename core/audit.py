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
        },
        "diff": [row.model_dump() for row in diff.rows],
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
