"""Tests for EXIF date formatting and UTC offset handling."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from core.datetime_utils import (
    format_exif_datetime,
    format_utc_offset,
    offset_for_timezone,
    parse_exif_datetime,
    parse_offset_string,
    parse_user_datetime,
)
from core.exceptions import InvalidDateTimeError


def test_format_exif_datetime():
    dt = datetime(2026, 7, 21, 16, 45, 30)
    assert format_exif_datetime(dt) == "2026:07:21 16:45:30"


def test_parse_exif_roundtrip():
    dt = datetime(2001, 12, 3, 9, 5, 1)
    assert parse_exif_datetime(format_exif_datetime(dt)) == dt


def test_parse_exif_invalid():
    with pytest.raises(InvalidDateTimeError):
        parse_exif_datetime("not-a-date")


@pytest.mark.parametrize(
    "delta,expected",
    [
        (timedelta(hours=2), "+02:00"),
        (timedelta(hours=-5), "-05:00"),
        (timedelta(hours=5, minutes=30), "+05:30"),
        (timedelta(0), "+00:00"),
        (timedelta(hours=-9, minutes=-30), "-09:30"),
    ],
)
def test_format_utc_offset(delta, expected):
    assert format_utc_offset(delta) == expected


def test_offset_out_of_range():
    with pytest.raises(InvalidDateTimeError):
        format_utc_offset(timedelta(hours=15))


def test_parse_offset_string_roundtrip():
    assert parse_offset_string("+05:30") == timedelta(hours=5, minutes=30)
    assert parse_offset_string("-08:00") == timedelta(hours=-8)


def test_offset_for_known_timezone():
    # UTC is always +00:00 regardless of DST.
    assert offset_for_timezone("UTC") == "+00:00"


def test_offset_for_unknown_timezone():
    with pytest.raises(InvalidDateTimeError):
        offset_for_timezone("Mars/Olympus_Mons")


def test_parse_user_datetime_formats():
    assert parse_user_datetime("2026-07-21 16:45:00") == datetime(2026, 7, 21, 16, 45, 0)
    assert parse_user_datetime("2026-07-21T16:45") == datetime(2026, 7, 21, 16, 45)


def test_parse_user_datetime_invalid():
    with pytest.raises(InvalidDateTimeError):
        parse_user_datetime("21/07/2026")
