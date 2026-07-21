"""Typed models for metadata inspection, change plans, and results.

These Pydantic models are the contract shared across the desktop backend and
both bots. They are intentionally interface-agnostic (no FastAPI or bot types).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class ImageFormat(str, Enum):
    """Image formats the engine recognises."""

    JPEG = "JPEG"
    HEIF = "HEIF"
    TIFF = "TIFF"
    PNG = "PNG"
    WEBP = "WEBP"
    UNKNOWN = "UNKNOWN"


class DateStrategy(str, Enum):
    """How the date/time fields should be handled in a change plan."""

    KEEP_ORIGINAL = "keep_original"
    SET_EXPLICIT = "set_explicit"


class GPSData(BaseModel):
    """Decimal GPS coordinates plus optional altitude and label."""

    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    altitude_m: float | None = Field(
        default=None, description="Altitude in metres; positive above sea level."
    )
    address_label: str | None = Field(
        default=None,
        max_length=512,
        description="Human-readable label; NOT written to EXIF, kept for audit/UI.",
    )


class MetadataSummary(BaseModel):
    """A read-only snapshot of the metadata currently present in an image."""

    image_format: ImageFormat
    width: int | None = None
    height: int | None = None
    make: str | None = None
    model: str | None = None
    lens_model: str | None = None
    software: str | None = None
    datetime_original: str | None = None
    create_date: str | None = None
    modify_date: str | None = None
    offset_time_original: str | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    gps_altitude_m: float | None = None
    has_gps: bool = False
    #: Flat map of every raw tag we could decode, for the "inspect original" view.
    raw_tags: dict[str, str] = Field(default_factory=dict)


class ChangePlan(BaseModel):
    """A fully-specified, validated description of the changes to apply.

    A change plan is produced by :meth:`MetadataEngine.build_change_plan`,
    validated by :meth:`validate_change_plan`, and consumed by
    :meth:`apply_metadata`. It is the single source of truth for the review
    screen and the audit sidecar.
    """

    source_path: Path
    destination_path: Path
    original_summary: MetadataSummary | None = None

    # Device / camera identity
    preset_id: str | None = None
    make: str | None = None
    model: str | None = None
    lens_model: str | None = None
    software: str | None = None

    # Date / time
    date_strategy: DateStrategy = DateStrategy.KEEP_ORIGINAL
    datetime_original: datetime | None = None
    create_date: datetime | None = None
    modify_date: datetime | None = None
    #: e.g. "+02:00" — written to OffsetTime* tags.
    utc_offset: str | None = None
    timezone_name: str | None = Field(
        default=None, description="IANA zone name for audit/UI; not an EXIF tag."
    )

    # Location
    gps: GPSData | None = None
    remove_gps: bool = False

    # Tag management
    tags_to_remove: list[str] = Field(default_factory=list)
    strip_all_metadata: bool = False

    # Audit
    write_audit_sidecar: bool = True

    model_config = {"arbitrary_types_allowed": True}


class FieldChange(BaseModel):
    """One row of the before/after review table."""

    field: str
    original: str | None = None
    new: str | None = None
    #: One of: "added", "changed", "removed", "preserved".
    status: str


class ChangeDiff(BaseModel):
    """The full before/after diff shown on the review screen."""

    rows: list[FieldChange] = Field(default_factory=list)


class ExportResult(BaseModel):
    """The outcome of a single apply/export operation."""

    source_path: Path
    destination_path: Path
    audit_sidecar_path: Path | None = None
    bytes_written: int = 0
    converted_to_jpeg: bool = False
    warnings: list[str] = Field(default_factory=list)
    success: bool = True

    model_config = {"arbitrary_types_allowed": True}
