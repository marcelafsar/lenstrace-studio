"""Filename-collision resolution using the Windows/Explorer style.

``photo.jpg`` → ``photo (1).jpg`` → ``photo (2).jpg`` …
"""

from __future__ import annotations

from pathlib import Path

from core.delivery.exceptions import DeliveryError


def resolve_collision(dest_dir: Path, filename: str, strategy: str = "increment") -> Path:
    """Return a non-colliding destination path inside ``dest_dir``.

    ``strategy``:
      - ``"increment"``: append `` (n)`` before the extension until free.
      - ``"error"``: raise :class:`DeliveryError` if the target exists.
    """
    dest_dir = Path(dest_dir)
    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate
    if strategy == "error":
        raise DeliveryError(
            f"Destination already exists: {candidate.name}",
            user_message=f"A file named '{candidate.name}' already exists at the destination.",
        )

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        candidate = dest_dir / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
