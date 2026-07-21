"""Build and validate safe map links from numeric coordinates only.

A map URL is generated exclusively from validated latitude/longitude — never
from the raw user address query — and points only at an approved HTTPS host.
"""

from __future__ import annotations

from urllib.parse import urlparse

from core.validation import validate_coordinates

#: Only these HTTPS hosts may be handed to the user as map links.
_ALLOWED_MAP_HOSTS = {"www.openstreetmap.org", "openstreetmap.org"}


def osm_map_url(latitude: float, longitude: float, zoom: int = 15) -> str:
    """Return an OpenStreetMap URL centred on the (validated) coordinates."""
    validate_coordinates(latitude, longitude)
    zoom = max(1, min(19, zoom))
    return (
        f"https://www.openstreetmap.org/?mlat={latitude:.6f}&mlon={longitude:.6f}"
        f"#map={zoom}/{latitude:.6f}/{longitude:.6f}"
    )


def is_allowed_map_url(url: str) -> bool:
    """Return True only for an https URL on an approved map host."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in _ALLOWED_MAP_HOSTS
