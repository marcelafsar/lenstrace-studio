"""Typed models for exposure modes, simulation profiles, and resolved values.

These are interface-agnostic (no FastAPI/bot/EXIF-library types) so the same
objects flow through the desktop backend and both bots.
"""

from __future__ import annotations

from enum import Enum
from fractions import Fraction

from pydantic import BaseModel, Field, field_validator


class ExposureMode(str, Enum):
    """How the exposure fields of an export should be decided."""

    #: Keep whatever the source already had; never generate missing values.
    PRESERVE = "preserve"
    #: Preserve existing source values; generate only the missing ones.
    FILL_MISSING = "fill_missing"
    #: Replace exposure-related fields with the selected simulation profile.
    OVERRIDE = "override"
    #: Use individual user-entered values.
    CUSTOM = "custom"


class FieldSource(str, Enum):
    """Provenance of a single written field, for the audit/verification report."""

    PRESERVED = "preserved"  # copied unchanged from the source image
    SIMULATED = "simulated"  # generated from a simulation profile
    CUSTOM = "custom"  # entered by the user
    DERIVED = "derived"  # computed (e.g. APEX) from another field
    LENS = "lens"  # supplied by a verified lens preset
    UNSUPPORTED = "unsupported"


# EXIF enumerated constants (kept here so profiles.json holds plain ints).
FLASH_DID_NOT_FIRE = 0x0000
FLASH_FIRED = 0x0001
LIGHT_SOURCE_FLASH = 4


class ExposureProfile(BaseModel):
    """A named, data-driven set of *simulated* exposure values.

    The lens preset — not the profile — supplies FNumber / 35 mm focal length /
    LensModel, so a profile applies to any selected lens. ``exposure_time`` is a
    string ratio (e.g. ``"1/121"``) for readability and exact rational encoding.
    """

    id: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=64)
    iso: int = Field(..., gt=0, le=1_000_000)
    exposure_time: str = Field(..., description='Shutter time as a ratio, e.g. "1/121".')
    exposure_bias: float = Field(default=0.0, ge=-10.0, le=10.0)
    #: Raw EXIF Flash bit field (0 = did not fire, 1 = fired).
    flash: int = Field(default=FLASH_DID_NOT_FIRE, ge=0, le=0xFFFF)
    exposure_program: int = Field(default=2, ge=0, le=8)
    metering_mode: int = Field(default=5, ge=0, le=255)
    white_balance: int = Field(default=0, ge=0, le=1)
    exposure_mode_exif: int = Field(default=0, ge=0, le=2)
    scene_capture_type: int = Field(default=0, ge=0, le=3)
    #: Optional EXIF LightSource (e.g. 4 = Flash); omitted when null.
    light_source: int | None = Field(default=None, ge=0, le=255)

    @field_validator("exposure_time")
    @classmethod
    def _valid_ratio(cls, value: str) -> str:
        num, den = _parse_ratio(value)
        if num <= 0 or den <= 0:
            raise ValueError(f"exposure_time must be a positive ratio, got {value!r}")
        return value

    @property
    def exposure_time_seconds(self) -> float:
        num, den = _parse_ratio(self.exposure_time)
        return num / den

    @property
    def exposure_time_ratio(self) -> tuple[int, int]:
        return _parse_ratio(self.exposure_time)

    @property
    def flash_fired(self) -> bool:
        return bool(self.flash & 0x0001)


class ProfileLibrary(BaseModel):
    """The whole versioned profile file."""

    schema_version: int = Field(..., ge=1)
    profiles: list[ExposureProfile]

    def by_id(self, profile_id: str) -> ExposureProfile | None:
        return next((p for p in self.profiles if p.id == profile_id), None)


class ResolvedExposure(BaseModel):
    """Concrete exposure values to write, plus the provenance of each field.

    Produced by :func:`core.exposure.resolver.resolve_exposure` and stored on the
    :class:`~core.metadata_models.ChangePlan` so the writer, verifier, audit
    report, and UI preview all read one authoritative object.
    """

    #: Pure exposure values to actually write (None = leave/absent). Lens-owned
    #: fields (FNumber, 35 mm focal length, LensModel) live on the ChangePlan
    #: itself, not here — this object never re-writes them.
    iso: int | None = None
    exposure_time_seconds: float | None = None
    exposure_bias: float | None = None
    flash: int | None = None
    exposure_program: int | None = None
    metering_mode: int | None = None
    white_balance: int | None = None
    exposure_mode_exif: int | None = None
    scene_capture_type: int | None = None
    light_source: int | None = None

    #: field name -> provenance, for the audit + verification report.
    sources: dict[str, FieldSource] = Field(default_factory=dict)
    #: The simulation profile applied, if any.
    profile_id: str | None = None
    profile_display_name: str | None = None
    #: True when ANY written field came from a simulation profile.
    is_simulated: bool = False
    #: The workflow mode that produced this resolution.
    mode: ExposureMode = ExposureMode.PRESERVE

    def exposure_time_ratio(self) -> tuple[int, int] | None:
        if self.exposure_time_seconds is None:
            return None
        frac = Fraction(self.exposure_time_seconds).limit_denominator(1_000_000)
        return (frac.numerator, frac.denominator or 1)


def _parse_ratio(value: str) -> tuple[int, int]:
    """Parse ``"1/121"`` or ``"0.5"`` into an integer ``(num, den)`` pair."""
    value = value.strip()
    if "/" in value:
        num_str, _, den_str = value.partition("/")
        return int(num_str), int(den_str)
    frac = Fraction(value).limit_denominator(1_000_000)
    return frac.numerator, frac.denominator or 1
