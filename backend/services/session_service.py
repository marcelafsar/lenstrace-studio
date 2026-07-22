"""In-memory session store mapping opaque ids to uploaded working files.

Keeps a registry of files the desktop app has uploaded/selected during the
current backend run so subsequent requests can reference them by id instead of
sending a raw path (which we would otherwise have to trust and re-validate).
"""

from __future__ import annotations

import contextlib
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock


@dataclass
class FileEntry:
    file_id: str
    path: Path
    original_name: str
    created_at: float = field(default_factory=time.time)


class SessionStore:
    """Thread-safe registry of working files for the current run."""

    def __init__(self) -> None:
        self._entries: dict[str, FileEntry] = {}
        self._lock = Lock()

    def register(self, path: Path, original_name: str) -> FileEntry:
        entry = FileEntry(
            file_id=secrets.token_urlsafe(12),
            path=Path(path),
            original_name=original_name,
        )
        with self._lock:
            self._entries[entry.file_id] = entry
        return entry

    def get(self, file_id: str) -> FileEntry | None:
        with self._lock:
            return self._entries.get(file_id)

    def remove(self, file_id: str) -> None:
        with self._lock:
            entry = self._entries.pop(file_id, None)
        if entry and entry.path.exists():
            with contextlib.suppress(OSError):
                entry.path.unlink()

    def all(self) -> list[FileEntry]:
        with self._lock:
            return list(self._entries.values())


_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
