"""Shared address-search (geocoding) service.

Both bots and the desktop backend use this — geocoding is never performed inside
a Telegram or Discord handler. Uses OpenStreetMap Nominatim per its usage policy:
a descriptive User-Agent, client-side rate limiting (max ~1 req/s), a short-term
cache, and a bounded result count. Images and tokens are never sent; exact
queries and coordinates are not logged at normal level.

Results are stored in a short-lived registry keyed by an opaque ``result_id`` so
callers put only that id into callback data / component values, never the full
address or coordinates.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from threading import Lock

from backend.logging_config import get_logger
from backend.services import settings_service
from core.exceptions import LensTraceError
from core.location.map_links import osm_map_url
from core.location.models import LocationSearchResult

logger = get_logger(__name__)

_SEARCH_ENDPOINT = "https://nominatim.openstreetmap.org/search"
_REVERSE_ENDPOINT = "https://nominatim.openstreetmap.org/reverse"
_MIN_INTERVAL_S = 1.1  # Nominatim: at most ~1 request/second.

#: A callable (url, params, headers, timeout) -> list/dict parsed JSON.
HttpGet = Callable[[str, dict, dict, float], object]


class GeocodingError(LensTraceError):
    default_user_message = "Address search is temporarily unavailable. Try again shortly."


class GeocodingDisabledError(GeocodingError):
    default_user_message = "Address search is turned off. Enter coordinates manually instead."


class _Registry:
    """Short-lived opaque result store (result_id -> result)."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[float, LocationSearchResult]] = {}
        self._lock = Lock()

    def put(self, result: LocationSearchResult) -> None:
        with self._lock:
            self._items[result.result_id] = (time.time(), result)

    def get(self, result_id: str, ttl_seconds: float) -> LocationSearchResult | None:
        with self._lock:
            entry = self._items.get(result_id)
            if entry is None:
                return None
            ts, result = entry
            if time.time() - ts > ttl_seconds:
                self._items.pop(result_id, None)
                return None
            return result

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


class GeocodingService:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, list[LocationSearchResult]]] = {}
        self._registry = _Registry()
        self._lock = Lock()
        self._last_call = 0.0

    # ---- Public API ------------------------------------------------------

    def is_enabled(self) -> bool:
        return settings_service.get_config().geocoding.enabled

    def search(self, query: str, *, http_get: HttpGet | None = None) -> list[LocationSearchResult]:
        cfg = settings_service.get_config().geocoding
        if not cfg.enabled:
            raise GeocodingDisabledError("Geocoding disabled")
        key = " ".join((query or "").strip().lower().split())
        if not key:
            return []

        cached = self._cache_get(key, cfg.cache_minutes)
        if cached is not None:
            for r in cached:
                self._registry.put(r)
            return cached

        self._rate_limit()
        raw = self._call(
            _SEARCH_ENDPOINT,
            {"q": query, "format": "jsonv2", "limit": str(cfg.max_results), "addressdetails": "0"},
            cfg,
            http_get,
        )
        results = self._normalize(raw, cfg.provider)
        self._cache_put(key, results)
        for r in results:
            self._registry.put(r)
        logger.info("Geocoding search returned %d result(s).", len(results))  # query NOT logged
        return results

    def reverse(
        self, latitude: float, longitude: float, *, http_get: HttpGet | None = None
    ) -> str | None:
        cfg = settings_service.get_config().geocoding
        if not cfg.enabled:
            return None
        self._rate_limit()
        raw = self._call(
            _REVERSE_ENDPOINT,
            {"lat": f"{latitude:.6f}", "lon": f"{longitude:.6f}", "format": "jsonv2"},
            cfg,
            http_get,
        )
        if isinstance(raw, dict):
            name = raw.get("display_name")
            return str(name) if name else None
        return None

    def get_result(self, result_id: str) -> LocationSearchResult | None:
        ttl = settings_service.get_config().geocoding.cache_minutes * 60 or 600
        return self._registry.get(result_id, ttl)

    # ---- Internals -------------------------------------------------------

    def _rate_limit(self) -> None:
        with self._lock:
            wait = _MIN_INTERVAL_S - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

    def _cache_get(self, key: str, minutes: int) -> list[LocationSearchResult] | None:
        with self._lock:
            entry = self._cache.get(key)
        if entry is None:
            return None
        ts, results = entry
        if time.time() - ts > minutes * 60:
            return None
        return results

    def _cache_put(self, key: str, results: list[LocationSearchResult]) -> None:
        with self._lock:
            self._cache[key] = (time.time(), results)

    def _call(self, url: str, params: dict, cfg, http_get: HttpGet | None) -> object:
        fn = http_get or self._default_http_get
        headers = {"User-Agent": cfg.user_agent, "Accept-Language": "en"}
        try:
            return fn(url, params, headers, cfg.timeout_seconds)
        except GeocodingError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak details/query
            logger.warning("Geocoding request failed: %s", type(exc).__name__)
            raise GeocodingError(f"Geocoding request failed: {type(exc).__name__}") from exc

    @staticmethod
    def _default_http_get(url: str, params: dict, headers: dict, timeout: float) -> object:
        import httpx

        resp = httpx.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            raise GeocodingError(f"Provider returned {resp.status_code}")
        return resp.json()

    def _normalize(self, raw: object, provider: str) -> list[LocationSearchResult]:
        if not isinstance(raw, list):
            return []
        results: list[LocationSearchResult] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                lat = float(item["lat"])
                lon = float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            bbox = _parse_bbox(item.get("boundingbox"))
            results.append(
                LocationSearchResult(
                    result_id=secrets.token_urlsafe(8),
                    display_name=str(item.get("display_name", "Unknown location")),
                    latitude=lat,
                    longitude=lon,
                    provider=provider,
                    result_type=item.get("type") or item.get("category"),
                    bounding_box=bbox,
                    map_url=osm_map_url(lat, lon),
                )
            )
        return results


def _parse_bbox(value: object) -> list[float] | None:
    # Nominatim boundingbox = [south, north, west, east] as strings.
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        return [float(v) for v in value]
    except (TypeError, ValueError):
        return None


_service: GeocodingService | None = None


def get_geocoding_service() -> GeocodingService:
    global _service
    if _service is None:
        _service = GeocodingService()
    return _service
