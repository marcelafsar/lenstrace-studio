"""Coordinate parsing/validation for location input."""

from __future__ import annotations

from core.exceptions import InvalidCoordinateError
from core.validation import validate_coordinates


def parse_coordinates(text: str) -> tuple[float, float]:
    """Parse ``lat, lon`` or ``lat lon`` into a validated (lat, lon) tuple.

    Accepts a comma or whitespace separator. Raises
    :class:`InvalidCoordinateError` on malformed or out-of-range input.
    """
    raw = (text or "").strip()
    if "," in raw:  # noqa: SIM108 - clearer as an explicit branch
        parts = [p.strip() for p in raw.split(",") if p.strip()]
    else:
        parts = raw.split()
    if len(parts) != 2:
        raise InvalidCoordinateError(
            f"Expected two numbers, got {raw!r}",
            user_message="Enter coordinates as 'latitude, longitude' (e.g. 41.0082, 28.9784).",
        )
    try:
        lat = float(parts[0])
        lon = float(parts[1])
    except ValueError as exc:
        raise InvalidCoordinateError(
            f"Non-numeric coordinates: {raw!r}",
            user_message="Coordinates must be numbers, e.g. 41.0082, 28.9784.",
        ) from exc
    validate_coordinates(lat, lon)
    return lat, lon
