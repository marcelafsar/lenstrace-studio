"""Validation of user-entered custom exposure values."""

from __future__ import annotations

from fractions import Fraction

from core.exceptions import LensTraceError


class InvalidExposureError(LensTraceError):
    """Raised when a user-supplied exposure value is out of range or malformed."""


def parse_shutter_speed(value: str) -> float:
    """Parse a shutter speed like ``"1/121"``, ``"0.5"``, or ``"2"`` to seconds."""
    text = value.strip().rstrip("s").strip()
    try:
        if "/" in text:
            num_str, _, den_str = text.partition("/")
            num, den = float(num_str), float(den_str)
            if den == 0:
                raise ValueError("zero denominator")
            seconds = num / den
        else:
            seconds = float(text)
    except ValueError as exc:
        raise InvalidExposureError(
            f"Could not parse shutter speed {value!r}",
            user_message="Enter a shutter speed like 1/121, 0.5, or 2.",
        ) from exc
    if not 0 < seconds <= 3600:
        raise InvalidExposureError(
            f"Shutter speed out of range: {seconds}",
            user_message="Shutter speed must be between 1/8000 s and 3600 s.",
        )
    return seconds


def validate_iso(value: int) -> int:
    if not 1 <= value <= 1_000_000:
        raise InvalidExposureError(
            f"ISO out of range: {value}",
            user_message="ISO must be between 1 and 1,000,000.",
        )
    return value


def validate_exposure_bias(value: float) -> float:
    if not -10.0 <= value <= 10.0:
        raise InvalidExposureError(
            f"Exposure bias out of range: {value}",
            user_message="Exposure compensation must be between -10 and +10 EV.",
        )
    return value


def shutter_to_ratio(seconds: float) -> tuple[int, int]:
    frac = Fraction(seconds).limit_denominator(1_000_000)
    return frac.numerator, frac.denominator or 1
