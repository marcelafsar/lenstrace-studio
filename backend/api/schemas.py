"""Request/response DTOs for the local API.

These are distinct from the core engine models so the wire format can evolve
independently. The service layer translates between the two.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.metadata_models import ChangeDiff, ExportResult, MetadataSummary

# ---- Files ---------------------------------------------------------------


class UploadedFileResponse(BaseModel):
    file_id: str
    original_name: str
    image_format: str
    width: int | None = None
    height: int | None = None
    thumbnail_data_uri: str | None = None


class InspectResponse(BaseModel):
    file_id: str
    summary: MetadataSummary


# ---- Presets -------------------------------------------------------------


class LensDTO(BaseModel):
    id: str
    display_name: str
    lens_model: str = ""
    focal_length_35mm: float | None = None
    f_number: float | None = None


class DeviceDTO(BaseModel):
    id: str
    display_name: str
    generation: str | None = None
    exif_model: str
    source_status: str
    lenses: list[LensDTO] = Field(default_factory=list)
    notes: str = ""


class PresetsResponse(BaseModel):
    schema_version: int
    devices: list[DeviceDTO]


# ---- Exposure profiles ---------------------------------------------------


class ExposureProfileDTO(BaseModel):
    id: str
    display_name: str
    iso: int
    exposure_time: str
    exposure_bias: float
    flash_fired: bool


class ProfilesResponse(BaseModel):
    schema_version: int
    profiles: list[ExposureProfileDTO]
    #: The mode/profile applied by default when auto-fill is on (transparency).
    default_profile_id: str


# ---- Change requests -----------------------------------------------------


class GPSInput(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    altitude_m: float | None = None
    address_label: str | None = Field(default=None, max_length=512)


class ChangeRequest(BaseModel):
    """Everything the UI collected across the guided workflow."""

    file_id: str
    output_dir: str | None = None

    preset_id: str | None = None
    lens_id: str | None = None
    make: str | None = None
    model: str | None = None
    lens_model: str | None = None
    software: str | None = None

    # Date/time
    set_datetime: bool = False
    datetime_original: str | None = Field(
        default=None, description="ISO-8601 or 'YYYY-MM-DD HH:MM:SS'."
    )
    timezone_name: str | None = None
    utc_offset: str | None = Field(default=None, description="e.g. +02:00")

    # Location
    gps: GPSInput | None = None
    remove_gps: bool = False

    # Exposure simulation. Modes: preserve | fill_missing | override | custom.
    # Profile/custom values are SIMULATED, never authentic measurements.
    exposure_mode: str | None = Field(
        default=None, description="preserve | fill_missing | override | custom"
    )
    exposure_profile_id: str | None = None
    auto_fill_exposure: bool = True
    # Custom exposure values (used when exposure_mode == 'custom').
    exposure_iso: int | None = Field(default=None, gt=0)
    exposure_shutter: str | None = Field(default=None, description='e.g. "1/121"')
    exposure_ev: float | None = Field(default=None, ge=-10.0, le=10.0)
    exposure_flash_fired: bool | None = None

    # Legacy shortcut (maps to custom mode); retained for older callers.
    set_exposure: bool = False
    photographic_sensitivity: int | None = Field(default=None, gt=0, description="ISO")
    exposure_time: float | None = Field(default=None, gt=0, description="Seconds")
    exposure_bias: float | None = Field(default=None, ge=-10.0, le=10.0, description="EV stops")

    # Output resolution. Modes: keep | iphone_12mp | custom. Fit: crop_to_fill | fit_with_padding.
    resolution_mode: str = "keep"
    resolution_fit: str = "crop_to_fill"
    custom_width: int | None = Field(default=None, gt=0, le=30000)
    custom_height: int | None = Field(default=None, gt=0, le=30000)

    # Options
    strip_all_metadata: bool = False
    write_audit_sidecar: bool = True
    filename_suffix: str = "_metadata"
    preserve_name: bool = False
    on_collision: str = "increment"


class CameraPreviewDTO(BaseModel):
    device_line: str | None = None
    lens_line: str | None = None
    resolution_line: str | None = None
    exposure_line: str | None = None
    exposure_simulated: bool = False
    exposure_source_label: str | None = None
    resolution_changed: bool = False
    lines: list[str] = Field(default_factory=list)


class PreviewResponse(BaseModel):
    diff: ChangeDiff
    destination_name: str
    disclaimer: str
    camera_preview: CameraPreviewDTO | None = None


class ExportResponse(BaseModel):
    result: ExportResult
    disclaimer: str
    #: Opaque id for handing this export to a delivery provider (never a path).
    export_id: str | None = None


class BatchExportRequest(BaseModel):
    requests: list[ChangeRequest]


class BatchItemResult(BaseModel):
    file_id: str
    success: bool
    destination_name: str | None = None
    export_id: str | None = None
    error: str | None = None


class BatchExportResponse(BaseModel):
    results: list[BatchItemResult]


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
