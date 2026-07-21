"""Streaming SHA-256 helpers used to verify byte-for-byte delivery.

Delivery never decodes/re-encodes an image; it copies raw bytes and confirms
the destination hash matches the source hash.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 1024 * 1024  # 1 MiB


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of a file, read in streaming chunks."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def files_match(a: Path, b: Path) -> bool:
    """Return True if two files have identical size and SHA-256."""
    a, b = Path(a), Path(b)
    if a.stat().st_size != b.stat().st_size:
        return False
    return sha256_file(a) == sha256_file(b)
