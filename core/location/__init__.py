"""Shared location primitives: result models, validation, and safe map links.

Interface-agnostic. The backend geocoding service and both bots use these; no
interface builds map URLs or parses coordinates on its own.
"""

from core.location.map_links import is_allowed_map_url, osm_map_url
from core.location.models import LocationSearchResult
from core.location.validation import parse_coordinates

__all__ = [
    "LocationSearchResult",
    "osm_map_url",
    "is_allowed_map_url",
    "parse_coordinates",
]
