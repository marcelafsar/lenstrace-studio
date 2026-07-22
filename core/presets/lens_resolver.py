"""Resolve a device + lens selection into concrete EXIF lens values.

Centralises the one rule that fixes the "model shows but lens is blank" bug:
a selected lens ALWAYS yields a non-empty ``LensModel``. When a preset provides
a verified ``lens_model`` we use it; otherwise we generate a transparent generic
fallback (e.g. "Apple iPhone 13 Pro Max Main Camera") and mark it GENERIC so the
UI never presents it as verified original Apple metadata. Optical values
(focal length, aperture, 35 mm equivalent, lens specification) are only ever
written when the preset actually supplies them — they are never invented.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.presets.schema import DevicePreset, LensPreset, LensSourceStatus

#: Centralised, documented template for the generic LensModel fallback.
GENERIC_LENS_TEMPLATE = "{manufacturer} {model} {lens}"


@dataclass(frozen=True)
class ResolvedLens:
    """Concrete lens values ready to write to EXIF (LensModel never blank)."""

    lens_id: str
    display_name: str
    lens_model: str
    focal_length_mm: float | None
    focal_length_35mm: float | None
    f_number: float | None
    lens_specification: list[float] | None
    source: LensSourceStatus

    @property
    def is_generic(self) -> bool:
        return self.source == LensSourceStatus.GENERIC


def generic_lens_model(device: DevicePreset, lens: LensPreset) -> str:
    """Build the transparent generic LensModel string for a device + lens."""
    return GENERIC_LENS_TEMPLATE.format(
        manufacturer=device.manufacturer,
        model=device.exif_model,
        lens=lens.display_name,
    ).strip()


def resolve_lens(device: DevicePreset, lens: LensPreset) -> ResolvedLens:
    """Resolve a lens preset to concrete values, guaranteeing a LensModel."""
    provided = (lens.lens_model or "").strip()
    if provided:
        source = lens.source_status or LensSourceStatus.VERIFIED
        model = provided
    else:
        source = LensSourceStatus.GENERIC
        model = generic_lens_model(device, lens)
    return ResolvedLens(
        lens_id=lens.id,
        display_name=lens.display_name,
        lens_model=model,
        focal_length_mm=lens.focal_length_mm,
        focal_length_35mm=lens.focal_length_35mm,
        f_number=lens.f_number,
        lens_specification=lens.lens_specification,
        source=source,
    )


def resolve_lens_by_id(device: DevicePreset, lens_id: str) -> ResolvedLens | None:
    """Resolve by lens id, or None if the lens does not exist on the device."""
    lens = next((ln for ln in device.lenses if ln.id == lens_id), None)
    return resolve_lens(device, lens) if lens is not None else None
