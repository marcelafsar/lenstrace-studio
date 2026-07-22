"""Validation helpers for delivery: external URLs and destination paths.

URL validation is security-critical — user-supplied strings are never opened
blindly. Only http(s) with a real host is allowed; http is permitted solely for
localhost development instances.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, urlunparse

from core.delivery.exceptions import DestinationInvalidError, UnsafeUrlError

_ALLOWED_SCHEMES = {"http", "https"}
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def validate_external_url(raw: str) -> str:
    """Validate and normalise an external URL for opening in the browser.

    Rules:
      * Scheme must be http or https (rejects javascript:, data:, file:, etc.).
      * http is allowed only for localhost/127.0.0.1 (dev instances).
      * No embedded credentials (``user:pass@host``).
      * A non-empty hostname is required.

    Returns the normalised URL. Raises :class:`UnsafeUrlError` otherwise.
    """
    if not raw or not isinstance(raw, str):
        raise UnsafeUrlError("Empty URL", user_message="No web address was provided.")

    candidate = raw.strip()
    parsed = urlparse(candidate)

    scheme = parsed.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise UnsafeUrlError(
            f"Disallowed URL scheme: {scheme!r}",
            user_message="Only http(s) web addresses are allowed.",
        )

    if parsed.username or parsed.password:
        raise UnsafeUrlError(
            "URL contains embedded credentials",
            user_message="Web addresses with embedded usernames or passwords are not allowed.",
        )

    host = (parsed.hostname or "").lower()
    if not host:
        raise UnsafeUrlError("URL has no host", user_message="That web address has no host name.")

    if scheme == "http" and host not in _LOCAL_HOSTS:
        raise UnsafeUrlError(
            f"Insecure http for non-local host {host!r}",
            user_message="Only secure https web addresses are allowed (except localhost).",
        )

    # Re-serialise from parsed parts to strip any surprises; preserve path/query.
    normalised = urlunparse(
        (
            scheme,
            parsed.netloc,
            parsed.path or "/",
            parsed.params,
            parsed.query,
            "",  # drop fragments
        )
    )
    return normalised


def hostname_of(url: str) -> str:
    """Return the lowercase hostname of a URL, or '' if none."""
    return (urlparse(url).hostname or "").lower()


def validate_destination_dir(path: Path, *, allow_unc: bool = False) -> Path:
    """Resolve and validate a user-chosen destination directory.

    Rejects path traversal that escapes to a non-existent parent, UNC paths
    (unless explicitly allowed), and non-directories. Returns the resolved
    absolute path.
    """
    raw = Path(path)
    if _is_unc(raw) and not allow_unc:
        raise DestinationInvalidError(
            f"UNC path not allowed: {raw}",
            user_message="Network (UNC) paths are not supported for this destination.",
        )
    try:
        resolved = raw.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise DestinationInvalidError(
            f"Destination does not resolve: {raw}",
            user_message="The destination folder could not be found.",
        ) from exc
    if not resolved.is_dir():
        raise DestinationInvalidError(
            f"Destination is not a directory: {resolved}",
            user_message="The destination is not a folder.",
        )
    return resolved


def _is_unc(path: Path) -> bool:
    text = str(path)
    return text.startswith("\\\\") or text.startswith("//")
