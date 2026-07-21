"""Date/time helpers for EXIF formatting and time-zone offsets.

EXIF stores timestamps as ``"YYYY:MM:DD HH:MM:SS"`` (note colon date
separators) and, since EXIF 2.31, separate ``OffsetTime*`` tags in
``"+HH:MM"`` form.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

try:  # Python 3.9+
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    _ZONEINFO_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ZONEINFO_AVAILABLE = False

from core.exceptions import InvalidDateTimeError

EXIF_DATETIME_FORMAT = "%Y:%m:%d %H:%M:%S"


def format_exif_datetime(dt: datetime) -> str:
    """Format a :class:`datetime` as an EXIF datetime string."""
    return dt.strftime(EXIF_DATETIME_FORMAT)


def parse_exif_datetime(value: str) -> datetime:
    """Parse an EXIF datetime string. Raises :class:`InvalidDateTimeError`."""
    try:
        return datetime.strptime(value.strip(), EXIF_DATETIME_FORMAT)
    except (ValueError, AttributeError) as exc:
        raise InvalidDateTimeError(
            f"Cannot parse EXIF datetime: {value!r}",
            user_message="The stored date/time is not in a recognised format.",
        ) from exc


def parse_user_datetime(value: str) -> datetime:
    """Parse a user-entered datetime.

    Accepts ISO-8601 (``2026-07-21T16:45:00``) and the documented bot format
    ``YYYY-MM-DD HH:MM:SS`` (seconds optional).
    """
    value = value.strip()
    candidates = (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    )
    for fmt in candidates:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise InvalidDateTimeError(
        f"Unrecognised datetime: {value!r}",
        user_message="Please use the format YYYY-MM-DD HH:MM:SS (e.g. 2026-07-21 16:45:00).",
    )


def format_utc_offset(offset: timedelta) -> str:
    """Format a :class:`timedelta` offset as ``"+HH:MM"`` / ``"-HH:MM"``."""
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    if hours > 14:
        raise InvalidDateTimeError(
            f"UTC offset out of range: {offset}",
            user_message="The UTC offset is outside the valid range (-12:00 to +14:00).",
        )
    return f"{sign}{hours:02d}:{minutes:02d}"


def offset_for_timezone(tz_name: str, at: datetime | None = None) -> str:
    """Return the ``"+HH:MM"`` UTC offset for an IANA zone at a given instant.

    Uses the offset in effect on ``at`` (default: now) so DST is respected.
    """
    if not _ZONEINFO_AVAILABLE:  # pragma: no cover
        raise InvalidDateTimeError(
            "zoneinfo unavailable",
            user_message="Time-zone support is unavailable in this environment.",
        )
    try:
        zone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise InvalidDateTimeError(
            f"Unknown time zone: {tz_name!r}",
            user_message=f"'{tz_name}' is not a known time zone.",
        ) from exc
    moment = (at or datetime.now()).replace(tzinfo=zone)
    utc_offset = moment.utcoffset() or timedelta(0)
    return format_utc_offset(utc_offset)


def parse_offset_string(offset: str) -> timedelta:
    """Parse ``"+HH:MM"`` / ``"-HH:MM"`` into a :class:`timedelta`."""
    offset = offset.strip()
    try:
        sign = 1
        if offset[0] in "+-":
            sign = -1 if offset[0] == "-" else 1
            offset = offset[1:]
        hours_str, minutes_str = offset.split(":")
        delta = timedelta(hours=int(hours_str), minutes=int(minutes_str))
    except (ValueError, IndexError) as exc:
        raise InvalidDateTimeError(
            f"Bad offset string: {offset!r}",
            user_message="UTC offset must look like +02:00 or -05:00.",
        ) from exc
    return sign * delta


def utc_offset_now(tz: timezone) -> str:
    """Convenience: format the offset of a fixed :class:`timezone`."""
    return format_utc_offset(tz.utcoffset(None) or timedelta(0))
