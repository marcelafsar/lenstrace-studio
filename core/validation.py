"""Input validation and filesystem-safety helpers.

These functions never trust caller-supplied filenames or paths. They are used
by the engine, the backend, and both bots.
"""

from __future__ import annotations

import re
from pathlib import Path

from core.exceptions import ExportCollisionError, InvalidCoordinateError

# Characters not allowed in a single path component on Windows (plus control chars).
_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Windows reserved device names (case-insensitive), without extension.
_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_MAX_COMPONENT_LEN = 200


def sanitize_filename(name: str, *, default: str = "image") -> str:
    """Return a safe single-component filename derived from ``name``.

    Strips directory separators, illegal characters, leading dots, and trailing
    whitespace/dots (which Windows silently drops). Never returns an empty or
    reserved name.
    """
    # Only ever consider the final component, never a path.
    name = Path(name).name
    name = _ILLEGAL_FILENAME_CHARS.sub("_", name)
    name = name.strip().strip(". ")
    if not name:
        name = default
    stem = Path(name).stem
    if stem.upper() in _RESERVED_NAMES:
        name = f"_{name}"
    if len(name) > _MAX_COMPONENT_LEN:
        suffix = Path(name).suffix[:16]
        name = name[: _MAX_COMPONENT_LEN - len(suffix)] + suffix
    return name


def ensure_within_directory(path: Path, directory: Path) -> Path:
    """Resolve ``path`` and confirm it stays inside ``directory``.

    Guards against path-traversal (``..``) and absolute-path escapes. Returns
    the resolved path. Raises :class:`ValueError` if it escapes.
    """
    directory = directory.resolve()
    resolved = (directory / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        resolved.relative_to(directory)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Path escapes the allowed directory: {resolved}") from exc
    return resolved


def build_output_path(
    source: Path,
    output_dir: Path,
    *,
    suffix: str = "_metadata",
    preserve_name: bool = False,
    on_collision: str = "increment",
) -> Path:
    """Compute a safe, non-colliding destination path inside ``output_dir``.

    ``on_collision`` is one of:
      - ``"increment"``: append ``_1``, ``_2`` … until a free name is found.
      - ``"overwrite"``: return the target even if it exists.
      - ``"error"``: raise :class:`ExportCollisionError` if the target exists.
    """
    output_dir = Path(output_dir)
    safe = sanitize_filename(source.name)
    stem = Path(safe).stem
    ext = Path(safe).suffix or ".jpg"
    base = stem if preserve_name else f"{stem}{suffix}"
    candidate = output_dir / f"{base}{ext}"

    if not candidate.exists() or on_collision == "overwrite":
        return candidate
    if on_collision == "error":
        raise ExportCollisionError(
            f"Destination already exists: {candidate}",
            user_message=f"A file named '{candidate.name}' already exists in the output folder.",
        )
    # increment
    counter = 1
    while True:
        candidate = output_dir / f"{base}_{counter}{ext}"
        if not candidate.exists():
            return candidate
        counter += 1


def validate_coordinates(latitude: float, longitude: float) -> None:
    """Raise :class:`InvalidCoordinateError` if lat/lon are out of range or NaN."""
    if latitude != latitude or longitude != longitude:  # NaN check
        raise InvalidCoordinateError("Coordinates are NaN.")
    if not -90.0 <= latitude <= 90.0:
        raise InvalidCoordinateError(
            f"Latitude {latitude} out of range",
            user_message="Latitude must be between -90 and 90.",
        )
    if not -180.0 <= longitude <= 180.0:
        raise InvalidCoordinateError(
            f"Longitude {longitude} out of range",
            user_message="Longitude must be between -180 and 180.",
        )
