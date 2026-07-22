"""Tests for the shared geocoding service, location models, and map links."""

from __future__ import annotations

import pytest

from backend.services.geocoding_service import (
    GeocodingDisabledError,
    GeocodingError,
    GeocodingService,
)
from core.exceptions import InvalidCoordinateError
from core.location.map_links import is_allowed_map_url, osm_map_url
from core.location.validation import parse_coordinates

_FAKE = [
    {
        "display_name": "Sultanahmet, Fatih, Istanbul, Türkiye",
        "lat": "41.0054",
        "lon": "28.9768",
        "type": "suburb",
        "boundingbox": ["41.0", "41.01", "28.97", "28.98"],
    },
    {
        "display_name": "Sultanahmet Mosque",
        "lat": "41.0055",
        "lon": "28.9769",
        "type": "attraction",
    },
]


def _ok_http(result):
    def http_get(url, params, headers, timeout):
        assert "User-Agent" in headers  # policy: descriptive UA
        return result

    return http_get


@pytest.fixture
def svc(isolated_state):
    return GeocodingService()


# ---- search ----------------------------------------------------------------


def test_search_success(svc):
    results = svc.search("sultanahmet", http_get=_ok_http(_FAKE))
    assert len(results) == 2
    assert results[0].result_id
    assert results[0].result_type == "suburb"
    assert is_allowed_map_url(results[0].map_url)


def test_search_multiple_and_registry_roundtrip(svc):
    results = svc.search("x", http_get=_ok_http(_FAKE))
    got = svc.get_result(results[0].result_id)
    assert got is not None and got.latitude == results[0].latitude


def test_search_empty_results(svc):
    assert svc.search("nowhere", http_get=_ok_http([])) == []


def test_search_empty_query_returns_empty(svc):
    assert svc.search("   ", http_get=_ok_http(_FAKE)) == []


def test_provider_error(svc):
    def boom(url, params, headers, timeout):
        raise RuntimeError("timeout")

    with pytest.raises(GeocodingError):
        svc.search("q", http_get=boom)


def test_cache_avoids_second_call(svc):
    svc.search("cached", http_get=_ok_http(_FAKE))

    def must_not_call(*a):
        raise AssertionError("second call should be served from cache")

    again = svc.search("cached", http_get=must_not_call)
    assert len(again) == 2


def test_disabled_raises(isolated_state, monkeypatch):
    monkeypatch.setenv("GEOCODING_ENABLED", "false")
    from backend.services import settings_service

    settings_service.reload_config()
    with pytest.raises(GeocodingDisabledError):
        GeocodingService().search("q", http_get=_ok_http(_FAKE))


def test_unicode_and_long_query(svc):
    results = svc.search("Kadıköy İstanbul café" * 20, http_get=_ok_http(_FAKE))
    assert len(results) == 2


def test_map_url_excludes_query_text(svc):
    results = svc.search("secretplace", http_get=_ok_http(_FAKE))
    assert "secretplace" not in results[0].map_url


def test_invalid_coords_in_provider_data_skipped(svc):
    bad = [{"display_name": "bad", "lat": "999", "lon": "0"}, _FAKE[0]]
    results = svc.search("q", http_get=_ok_http(bad))
    assert len(results) == 1  # the out-of-range one is dropped


# ---- map links -------------------------------------------------------------


def test_osm_map_url_valid():
    url = osm_map_url(41.0, 28.9)
    assert url.startswith("https://www.openstreetmap.org/")
    assert is_allowed_map_url(url)


def test_osm_map_url_rejects_bad_coords():
    with pytest.raises(InvalidCoordinateError):
        osm_map_url(200, 0)


@pytest.mark.parametrize(
    "url,ok",
    [
        ("https://www.openstreetmap.org/?mlat=1&mlon=2", True),
        ("http://www.openstreetmap.org/", False),  # not https
        ("https://evil.example.com/?mlat=1", False),  # wrong host
        ("javascript:alert(1)", False),
    ],
)
def test_is_allowed_map_url(url, ok):
    assert is_allowed_map_url(url) is ok


# ---- coordinate parsing ----------------------------------------------------


@pytest.mark.parametrize(
    "text,lat,lon",
    [
        ("41.0082, 28.9784", 41.0082, 28.9784),
        ("41.0082 28.9784", 41.0082, 28.9784),
        ("-33.8688,151.2093", -33.8688, 151.2093),
    ],
)
def test_parse_coordinates_ok(text, lat, lon):
    assert parse_coordinates(text) == (lat, lon)


@pytest.mark.parametrize("text", ["41.0082", "abc, def", "91, 0", "0, 181", ""])
def test_parse_coordinates_invalid(text):
    with pytest.raises(InvalidCoordinateError):
        parse_coordinates(text)
