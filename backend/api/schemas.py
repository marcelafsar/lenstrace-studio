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

    # Options
    strip_all_metadata: bool = False
    write_audit_sidecar: bool = True
    filename_suffix: str = "_metadata"
    preserve_name: bool = False
    on_collision: str = "increment"


class PreviewResponse(BaseModel):
    diff: ChangeDiff
    destination_name: str
    disclaimer: str


class ExportResponse(BaseModel):
    result: ExportResult
    disclaimer: str


class BatchExportRequest(BaseModel):
    requests: list[ChangeRequest]


class BatchItemResult(BaseModel):
    file_id: str
    success: bool
    destination_name: str | None = None
    error: str | None = None


class BatchExportResponse(BaseModel):
    results: list[BatchItemResult]


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
