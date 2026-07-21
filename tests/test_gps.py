"""Tests for GPS decimal <-> EXIF rational conversion and references."""

from __future__ import annotations

import pytest

from core.exceptions import InvalidCoordinateError
from core.gps import (
    altitude_to_rational,
    decimal_to_dms_rational,
    dms_rational_to_decimal,
    latitude_ref,
    longitude_ref,
)
from core.validation import validate_coordinates


def test_roundtrip_positive():
    lat = 41.0082
    dms = decimal_to_dms_rational(lat)
    back = dms_rational_to_decimal(dms, "N")
    assert back == pytest.approx(lat, abs=1e-4)


def test_roundtrip_negative_west():
    lon = -73.9857
    dms = decimal_to_dms_rational(lon)
    back = dms_rational_to_decimal(dms, longitude_ref(lon))
    assert back == pytest.approx(lon, abs=1e-4)


def test_dms_is_rational_tuples():
    dms = decimal_to_dms_rational(28.9784)
    assert len(dms) == 3
    for num, denom in dms:
        assert isinstance(num, int) and isinstance(denom, int)
        assert denom > 0


def test_latitude_reference():
    assert latitude_ref(10.0) == "N"
    assert latitude_ref(-0.5) == "S"
    assert latitude_ref(0.0) == "N"


def test_longitude_reference():
    assert longitude_ref(10.0) == "E"
    assert longitude_ref(-0.5) == "W"


def test_altitude_above_and_below():
    (num, denom), ref = altitude_to_rational(100.0)
    assert ref == 0 and num / denom == pytest.approx(100.0)
    (num, denom), ref = altitude_to_rational(-12.5)
    assert ref == 1 and num / denom == pytest.approx(12.5)


def test_seconds_carry_does_not_overflow():
    # A value that rounds seconds up to 60 must carry into minutes.
    dms = decimal_to_dms_rational(1.0 - 1e-9)
    seconds = dms[2][0] / dms[2][1]
    assert seconds < 60


@pytest.mark.parametrize(
    "lat,lon",
    [(91.0, 0.0), (-91.0, 0.0), (0.0, 181.0), (0.0, -181.0)],
)
def test_invalid_coordinates_raise(lat, lon):
    with pytest.raises(InvalidCoordinateError):
        validate_coordinates(lat, lon)


def test_valid_coordinates_pass():
    validate_coordinates(90.0, 180.0)
    validate_coordinates(-90.0, -180.0)
