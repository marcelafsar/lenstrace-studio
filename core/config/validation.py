"""Small, strict parsers for environment-derived configuration values."""

from __future__ import annotations

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}

#: Values that clearly indicate a placeholder rather than a real secret/value.
PLACEHOLDER_TOKENS = {
    "",
    "changeme",
    "your-token-here",
    "your_token_here",
    "xxx",
    "todo",
    "replace-me",
    "replaceme",
    "none",
}


def parse_bool(value: str | None, *, default: bool = False) -> bool:
    """Strictly parse a boolean env string. Unknown values fall back to default."""
    if value is None:
        return default
    text = value.strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return default if text == "" else False
    return default


def parse_optional_int(value: str | None) -> int | None:
    """Parse an optional integer; return None for blank/invalid."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def looks_like_placeholder(value: str | None) -> bool:
    """Return True if a value is blank or a well-known placeholder."""
    if value is None:
        return True
    return value.strip().lower() in PLACEHOLDER_TOKENS
