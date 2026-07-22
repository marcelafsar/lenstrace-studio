"""Device preset listing endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.schemas import (
    DeviceDTO,
    ExposureProfileDTO,
    LensDTO,
    PresetsResponse,
    ProfilesResponse,
)
from core.exposure.loader import DEFAULT_PROFILE_ID, get_default_profile_loader
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
                LensDTO(
                    id=ln.id,
                    display_name=ln.display_name,
                    lens_model=ln.lens_model,
                    focal_length_35mm=ln.focal_length_35mm,
                    f_number=ln.f_number,
                )
                for ln in d.lenses
            ],
        )
        for d in library.devices
    ]
    return PresetsResponse(schema_version=library.schema_version, devices=devices)


@router.get("/exposure-profiles", response_model=ProfilesResponse)
def list_exposure_profiles() -> ProfilesResponse:
    loader = get_default_profile_loader()
    library = loader.load()
    profiles = [
        ExposureProfileDTO(
            id=p.id,
            display_name=p.display_name,
            iso=p.iso,
            exposure_time=p.exposure_time,
            exposure_bias=p.exposure_bias,
            flash_fired=p.flash_fired,
        )
        for p in library.profiles
    ]
    return ProfilesResponse(
        schema_version=library.schema_version,
        profiles=profiles,
        default_profile_id=DEFAULT_PROFILE_ID,
    )
