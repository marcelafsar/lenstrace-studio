"""Typed models for the output-resolution transform."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

#: iPhone-style 12 MP dimensions (portrait); landscape swaps the two.
IPHONE_12MP_LONG = 4032
IPHONE_12MP_SHORT = 3024


class ResolutionMode(str, Enum):
    KEEP = "keep"
    IPHONE_12MP = "iphone_12mp"
    CUSTOM = "custom"


class FitMode(str, Enum):
    """How to reconcile a non-matching source aspect ratio with the target."""

    CROP_TO_FILL = "crop_to_fill"
    FIT_WITH_PADDING = "fit_with_padding"


class ResolutionPlan(BaseModel):
    """A resolved description of the output-resolution transform."""

    mode: ResolutionMode = ResolutionMode.KEEP
    fit: FitMode = FitMode.CROP_TO_FILL
    #: Final output dimensions (equal to source when mode is KEEP).
    output_width: int = Field(..., gt=0)
    output_height: int = Field(..., gt=0)
    source_width: int = Field(..., gt=0)
    source_height: int = Field(..., gt=0)

    @property
    def changes_dimensions(self) -> bool:
        return (self.output_width, self.output_height) != (
            self.source_width,
            self.source_height,
        )

    @property
    def is_upscale(self) -> bool:
        return self.output_width * self.output_height > self.source_width * self.source_height
