"""GPS conversion helpers between decimal degrees and EXIF rational form.

EXIF stores GPS coordinates as three unsigned rationals (degrees, minutes,
seconds) plus a hemisphere reference character. Altitude is a single rational
plus a 0/1 reference byte. All rationals are ``(numerator, denominator)``.
"""

from __future__ import annotations

from core.validation import validate_coordinates

Rational = tuple[int, int]
DMSRational = tuple[Rational, Rational, Rational]

#: Denominator used for the seconds component (4 decimal places of a second
#: ≈ 3 mm of latitude — far finer than consumer GPS accuracy).
_SEC_DENOM = 10_000
_ALT_DENOM = 1_000


def decimal_to_dms_rational(value: float) -> DMSRational:
    """Convert an absolute decimal degree value to EXIF (deg, min, sec) rationals.

    The sign is dropped here; use :func:`latitude_ref` / :func:`longitude_ref`
    to derive the hemisphere.
    """
    value = abs(value)
    degrees = int(value)
    minutes_float = (value - degrees) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    seconds_num = int(round(seconds * _SEC_DENOM))

    # Handle rounding that pushes seconds to 60 (carry into minutes/degrees).
    if seconds_num >= 60 * _SEC_DENOM:
        seconds_num -= 60 * _SEC_DENOM
        minutes += 1
    if minutes >= 60:
        minutes -= 60
        degrees += 1

    return ((degrees, 1), (minutes, 1), (seconds_num, _SEC_DENOM))


def dms_rational_to_decimal(dms: DMSRational, ref: str) -> float:
    """Inverse of :func:`decimal_to_dms_rational`, applying the hemisphere ref."""
    deg = dms[0][0] / dms[0][1]
    minutes = dms[1][0] / dms[1][1]
    sec = dms[2][0] / dms[2][1]
    decimal = deg + minutes / 60 + sec / 3600
    if ref.upper() in ("S", "W"):
        decimal = -decimal
    return decimal


def latitude_ref(latitude: float) -> str:
    """Return ``"N"`` for non-negative latitude, else ``"S"``."""
    return "N" if latitude >= 0 else "S"


def longitude_ref(longitude: float) -> str:
    """Return ``"E"`` for non-negative longitude, else ``"W"``."""
    return "E" if longitude >= 0 else "W"


def altitude_to_rational(altitude_m: float) -> tuple[Rational, int]:
    """Return ``((num, denom), ref)`` where ``ref`` is 0 (above) or 1 (below) sea level."""
    ref = 0 if altitude_m >= 0 else 1
    num = int(round(abs(altitude_m) * _ALT_DENOM))
    return (num, _ALT_DENOM), ref


def build_gps_ifd(
    latitude: float,
    longitude: float,
    altitude_m: float | None = None,
) -> dict[int, object]:
    """Build a piexif-compatible GPS IFD dict from decimal coordinates.

    Uses piexif's ``GPSIFD`` tag numbers directly so the engine does not need
    piexif imported for its pure-conversion tests.
    """
    validate_coordinates(latitude, longitude)

    # piexif.GPSIFD tag numbers (stable EXIF constants).
    GPS_VERSION_ID = 0
    GPS_LAT_REF, GPS_LAT = 1, 2
    GPS_LON_REF, GPS_LON = 3, 4
    GPS_ALT_REF, GPS_ALT = 5, 6

    ifd: dict[int, object] = {
        GPS_VERSION_ID: (2, 3, 0, 0),
        GPS_LAT_REF: latitude_ref(latitude),
        GPS_LAT: list(decimal_to_dms_rational(latitude)),
        GPS_LON_REF: longitude_ref(longitude),
        GPS_LON: list(decimal_to_dms_rational(longitude)),
    }
    if altitude_m is not None:
        alt_rational, alt_ref = altitude_to_rational(altitude_m)
        ifd[GPS_ALT_REF] = alt_ref
        ifd[GPS_ALT] = alt_rational
    return ifd
