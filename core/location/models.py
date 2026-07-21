"""Normalized location search result model."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class LocationSearchResult(BaseModel):
    """A single geocoding result (already validated + carrying a safe map URL)."""

    result_id: str
    display_name: str
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    provider: str
    result_type: str | None = None
    #: [south, north, west, east] when the provider supplies it.
    bounding_box: list[float] | None = None
    #: Safe HTTPS map link built from the numeric coordinates only.
    map_url: str

    @field_validator("bounding_box")
    @classmethod
    def _valid_bbox(cls, value: list[float] | None) -> list[float] | None:
        if value is not None and len(value) != 4:
            raise ValueError("bounding_box must have four numbers")
        return value

    def short_label(self, max_len: int = 72) -> str:
        """A shortened, single-line label safe for buttons/select options."""
        label = " ".join(self.display_name.split())
        return label if len(label) <= max_len else label[: max_len - 1] + "…"
