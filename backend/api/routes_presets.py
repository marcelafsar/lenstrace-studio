"""Device preset listing endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.schemas import DeviceDTO, LensDTO, PresetsResponse
from core.presets.loader import get_default_loader

router = APIRouter(prefix="/presets", tags=["presets"])


@router.get("", response_model=PresetsResponse)
def list_presets() -> PresetsResponse:
    loader = get_default_loader()
    library = loader.load()
    devices = [
        DeviceDTO(
            id=d.id,
            display_name=d.display_name,
            generation=d.generation,
            exif_model=d.exif_model,
            source_status=d.source_status.value,
            notes=d.notes,
            lenses=[
                LensDTO(id=ln.id, display_name=ln.display_name, lens_model=ln.lens_model)
                for ln in d.lenses
            ],
        )
        for d in library.devices
    ]
    return PresetsResponse(schema_version=library.schema_version, devices=devices)
