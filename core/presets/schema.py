"""Pydantic schema for device presets.

The schema validates the versioned ``iphone_presets.json`` file on startup and
guarantees the invariants the rest of the app relies on (unique ids, a known
``source_status``, etc.). ``source_status`` explicitly separates *verified*
data from *placeholder* data so we never present invented Apple lens values as
fact.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class SourceStatus(str, Enum):
    VERIFIED = "verified"
    PLACEHOLDER = "placeholder"
    GENERIC = "generic"
    CUSTOM = "custom"


class LensPreset(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    #: EXIF LensModel string; empty means "leave lens fields unset".
    lens_model: str = ""
    focal_length_mm: float | None = Field(default=None, gt=0, lt=1000)
    focal_length_35mm: float | None = Field(default=None, gt=0, lt=1000)
    f_number: float | None = Field(default=None, gt=0, lt=100)


class DevicePreset(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    manufacturer: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    #: Grouping label for the UI, e.g. "iPhone 13".
    generation: str | None = None
    exif_model: str = Field(..., min_length=1, max_length=128)
    software_default: str | None = None
    lenses: list[LensPreset] = Field(default_factory=list)
    notes: str = ""
    source_status: SourceStatus = SourceStatus.PLACEHOLDER

    @field_validator("id")
    @classmethod
    def _id_is_slug(cls, value: str) -> str:
        if not all(c.isalnum() or c in "-_" for c in value):
            raise ValueError(f"Preset id must be a slug (alnum/-/_): {value!r}")
        return value

    @model_validator(mode="after")
    def _unique_lens_ids(self) -> DevicePreset:
        seen: set[str] = set()
        for lens in self.lenses:
            if lens.id in seen:
                raise ValueError(f"Duplicate lens id {lens.id!r} in preset {self.id!r}")
            seen.add(lens.id)
        return self


class PresetLibrary(BaseModel):
    """The whole versioned preset file."""

    schema_version: int = Field(..., ge=1)
    devices: list[DevicePreset]

    @model_validator(mode="after")
    def _unique_device_ids(self) -> PresetLibrary:
        seen: set[str] = set()
        for device in self.devices:
            if device.id in seen:
                raise ValueError(f"Duplicate device preset id: {device.id!r}")
            seen.add(device.id)
        return self

    def by_id(self, preset_id: str) -> DevicePreset | None:
        return next((d for d in self.devices if d.id == preset_id), None)
