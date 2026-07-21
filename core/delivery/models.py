"""Typed models and enums shared by all delivery providers."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class ProviderId(str, Enum):
    """Stable identifiers for the supported delivery methods."""

    ICLOUD_PHOTOS = "icloud_photos"
    PAIRDROP = "pairdrop"
    APPLE_DEVICES = "apple_devices"


class AvailabilityLevel(str, Enum):
    """How ready a provider is to be used right now."""

    READY = "ready"
    NEEDS_SETUP = "needs_setup"
    UNAVAILABLE = "unavailable"


class DeliveryState(str, Enum):
    """Lifecycle state of a single delivery job.

    Note: neither ``opening_external_app`` nor a copy-to-folder is treated as a
    final success. ``completed`` means only what the provider can actually
    guarantee (e.g. a checksum-verified local copy), never that Apple imported
    the asset.
    """

    UNAVAILABLE = "unavailable"
    READY = "ready"
    PREPARING = "preparing"
    AWAITING_USER = "awaiting_user"
    COPYING = "copying"
    OPENING_EXTERNAL_APP = "opening_external_app"
    VERIFYING = "verifying"
    WAITING_FOR_SYNC = "waiting_for_sync"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ExportFileInfo(BaseModel):
    """Integrity record captured for an exported file before delivery."""

    filename: str
    image_format: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    size_bytes: int = 0
    sha256: str = ""
    exif_make: str | None = None
    exif_model: str | None = None
    lens_model: str | None = None
    datetime_original: str | None = None
    offset_time_original: str | None = None
    gps_summary: str = "none"


class DeliveryAvailability(BaseModel):
    """A provider's current availability, shown on its card."""

    provider_id: ProviderId
    level: AvailabilityLevel
    recommended: bool = False
    #: Short, user-facing summary (e.g. "iCloud Photos folder detected").
    summary: str = ""
    #: Provider-specific, non-secret details (e.g. detected destination name).
    details: dict[str, str] = Field(default_factory=dict)


class DeliveryOptions(BaseModel):
    """User-controlled options collected before a delivery job runs."""

    #: Optional user-chosen destination directory (validated server-side).
    destination_dir: str | None = None
    verify_checksum: bool = True
    verify_metadata: bool = True
    #: One of: "increment" (photo (1).jpg), "error".
    collision_strategy: str = "increment"
    #: Provider-specific extras, e.g. {"pairdrop_url": "https://pairdrop.net/"}.
    extra: dict[str, str] = Field(default_factory=dict)


class DeliveryJob(BaseModel):
    """Server-side record of an in-progress delivery (holds absolute paths)."""

    job_id: str
    provider_id: ProviderId
    export_id: str
    state: DeliveryState = DeliveryState.PREPARING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    options: DeliveryOptions = Field(default_factory=DeliveryOptions)
    source_info: ExportFileInfo | None = None
    #: Absolute destination path — NEVER serialised to the renderer directly.
    destination_path: str | None = None

    model_config = {"use_enum_values": False}


class UserAction(BaseModel):
    """An action the user must take outside LensTrace to make progress."""

    title: str
    instructions: list[str] = Field(default_factory=list)
    #: A validated URL to open, if any (never contains file bytes or secrets).
    open_url: str | None = None
    #: A logical external app to open, if any (e.g. "apple_devices").
    open_app: str | None = None
    #: A folder to reveal, referenced by a safe logical key, not a raw path.
    open_folder: bool = False


class DeliveryJobStatus(BaseModel):
    """Outward-facing job status (safe to send to the renderer).

    Deliberately excludes absolute source/destination paths; only basenames and
    non-secret verification results are exposed.
    """

    job_id: str
    provider_id: ProviderId
    state: DeliveryState
    progress: float = 0.0
    message: str = ""
    destination_name: str | None = None
    destination_verified: bool | None = None
    source_info: ExportFileInfo | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    user_action: UserAction | None = None
    completed: bool = False
    cancelled: bool = False


class DeliveryResult(BaseModel):
    """The outcome of executing a delivery job."""

    job_id: str
    provider_id: ProviderId
    state: DeliveryState
    success: bool
    destination_name: str | None = None
    destination_verified: bool | None = None
    source_info: ExportFileInfo | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    user_action: UserAction | None = None
    message: str = ""
