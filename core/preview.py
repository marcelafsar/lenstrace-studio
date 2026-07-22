"""Build the human-readable camera summary shown on every review screen.

The summary is generated from the actual :class:`ChangePlan` (never hardcoded)
so desktop, Telegram, and Discord all show identical, truthful lines. Simulated
exposure values are labelled as such by the caller.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.exposure.models import ExposureMode
from core.metadata_engine import _parse_numeric_or_fraction
from core.metadata_models import ChangePlan


class CameraPreview(BaseModel):
    """Structured camera summary for a change plan."""

    device_line: str | None = None
    lens_line: str | None = None
    resolution_line: str | None = None
    exposure_line: str | None = None
    #: True when any exposure value on the card was generated from a profile.
    exposure_simulated: bool = False
    exposure_source_label: str | None = None
    resolution_changed: bool = False
    lines: list[str] = Field(default_factory=list)


def _lens_display_name(plan: ChangePlan) -> str | None:
    if not plan.preset_id or not plan.lens_id:
        return None
    from core.presets.loader import get_default_loader

    try:
        device = get_default_loader().get(plan.preset_id)
    except Exception:  # noqa: BLE001 - preview must never raise
        return None
    lens = next((ln for ln in device.lenses if ln.id == plan.lens_id), None)
    return lens.display_name if lens else None


def _fmt_number(value: float) -> str:
    return f"{value:g}"


def build_camera_preview(plan: ChangePlan) -> CameraPreview:
    """Assemble the review-screen camera summary from a plan."""
    preview = CameraPreview()
    lines: list[str] = []

    # Line 1 — device identity.
    if plan.make or plan.model:
        preview.device_line = " ".join(p for p in (plan.make, plan.model) if p)
        lines.append(preview.device_line)

    # Line 2 — lens: "Wide Camera — 26 mm f/1.5".
    lens_name = _lens_display_name(plan)
    if lens_name:
        parts = [lens_name]
        detail = []
        if plan.focal_length_35mm is not None:
            detail.append(f"{_fmt_number(plan.focal_length_35mm)} mm")
        if plan.f_number is not None:
            detail.append(f"f/{_fmt_number(plan.f_number)}")
        preview.lens_line = f"{parts[0]} — {' '.join(detail)}" if detail else parts[0]
        lines.append(preview.lens_line)

    # Line 3 — resolution + megapixels from the ACTUAL output dimensions.
    out_w = out_h = None
    if plan.resolution is not None:
        out_w, out_h = plan.resolution.output_width, plan.resolution.output_height
        preview.resolution_changed = plan.resolution.changes_dimensions
    elif plan.original_summary is not None:
        out_w, out_h = plan.original_summary.width, plan.original_summary.height
    if out_w and out_h:
        megapixels = round(out_w * out_h / 1_000_000)
        preview.resolution_line = f"{megapixels} MP • {out_w} × {out_h}"
        lines.append(preview.resolution_line)

    # Line 4 — exposure. Effective values: resolved (simulated/custom) or source.
    resolved = plan.resolved_exposure
    src = plan.original_summary
    iso = resolved.iso if resolved and resolved.iso is not None else (src.iso if src else None)
    exposure_time = None
    if resolved and resolved.exposure_time_seconds is not None:
        ratio = resolved.exposure_time_ratio()
        exposure_time = f"{ratio[0]}/{ratio[1]}" if ratio else None
    elif src and src.exposure_time:
        exposure_time = src.exposure_time
    bias = None
    if resolved and resolved.exposure_bias is not None:
        bias = _fmt_number(resolved.exposure_bias)
    elif src and src.exposure_bias is not None:
        bias = _parse_and_fmt(src.exposure_bias)

    exposure_bits: list[str] = []
    if iso is not None:
        exposure_bits.append(f"ISO {iso}")
    if plan.focal_length_35mm is not None:
        exposure_bits.append(f"{_fmt_number(plan.focal_length_35mm)} mm")
    if bias is not None:
        exposure_bits.append(f"{bias} EV")
    if plan.f_number is not None:
        exposure_bits.append(f"f/{_fmt_number(plan.f_number)}")
    if exposure_time is not None:
        exposure_bits.append(f"{exposure_time} s")
    if exposure_bits:
        preview.exposure_line = " • ".join(exposure_bits)
        lines.append(preview.exposure_line)

    if resolved is not None and resolved.is_simulated:
        preview.exposure_simulated = True
        preview.exposure_source_label = "Simulated exposure metadata"
    elif plan.exposure_mode == ExposureMode.CUSTOM:
        preview.exposure_source_label = "Custom exposure values"
    elif iso is not None or exposure_time is not None:
        preview.exposure_source_label = "Preserved from source"

    preview.lines = lines
    return preview


def _parse_and_fmt(value: str) -> str | None:
    parsed = _parse_numeric_or_fraction(value)
    return _fmt_number(parsed) if parsed is not None else value
