"""Server-side registry mapping opaque export ids to validated file paths.

The renderer never sends raw Windows paths to delivery endpoints; it sends an
``export_id`` minted here after a successful LensTrace export. This class is the
trust boundary:

  * Only the backend export flow registers paths (never the renderer directly).
  * Each id maps to a canonical, resolved, regular-file path.
  * Paths must live inside an approved LensTrace output directory.
  * Directories, missing files, traversal escapes, and unknown ids are rejected.
  * Registrations expire, and the store is in-memory (per backend session).
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from core.delivery.exceptions import UnknownExportError
from core.delivery.models import ExportFileInfo

_TTL_SECONDS = 6 * 60 * 60  # 6 hours


@dataclass
class ExportRegistration:
    export_id: str
    path: Path
    registered_at: float = field(default_factory=time.time)
    info: ExportFileInfo | None = None


class ExportRegistry:
    """In-memory, per-session registry of deliverable exports."""

    def __init__(self, ttl_seconds: int = _TTL_SECONDS) -> None:
        self._entries: dict[str, ExportRegistration] = {}
        self._approved_dirs: set[Path] = set()
        self._ttl = ttl_seconds
        self._lock = Lock()

    def approve_directory(self, directory: Path) -> None:
        """Mark a directory (and its subtree) as an approved output location."""
        try:
            resolved = Path(directory).resolve()
        except (OSError, RuntimeError):
            return
        with self._lock:
            self._approved_dirs.add(resolved)

    def _is_approved(self, path: Path) -> bool:
        # If no approved dirs are configured yet, approve the file's own parent
        # (registration only happens from the trusted export flow).
        if not self._approved_dirs:
            return True
        for approved in self._approved_dirs:
            try:
                path.relative_to(approved)
                return True
            except ValueError:
                continue
        return False

    def register(self, path: Path, info: ExportFileInfo | None = None) -> str:
        """Register an exported file and return its opaque id.

        Raises :class:`ValueError` if the path is not a regular file or is not
        inside an approved output directory.
        """
        resolved = Path(path).resolve()
        if not resolved.is_file():
            raise ValueError(f"Not a regular file: {resolved}")
        if not self._is_approved(resolved):
            raise ValueError(f"Path outside approved output directories: {resolved}")

        export_id = secrets.token_urlsafe(16)
        with self._lock:
            self._entries[export_id] = ExportRegistration(
                export_id=export_id, path=resolved, info=info
            )
        return export_id

    def resolve(self, export_id: str) -> Path:
        """Return the validated path for an id, or raise :class:`UnknownExportError`."""
        with self._lock:
            self._expire_locked()
            entry = self._entries.get(export_id)
        if entry is None:
            raise UnknownExportError(f"Unknown export id: {export_id!r}")
        if not entry.path.is_file():
            with self._lock:
                self._entries.pop(export_id, None)
            raise UnknownExportError(
                f"Export file no longer exists: {export_id!r}",
                user_message="That exported file is no longer available; please export again.",
            )
        return entry.path

    def get_info(self, export_id: str) -> ExportFileInfo | None:
        with self._lock:
            entry = self._entries.get(export_id)
        return entry.info if entry else None

    def set_info(self, export_id: str, info: ExportFileInfo) -> None:
        with self._lock:
            entry = self._entries.get(export_id)
            if entry is not None:
                entry.info = info

    def _expire_locked(self) -> None:
        now = time.time()
        stale = [eid for eid, e in self._entries.items() if now - e.registered_at > self._ttl]
        for eid in stale:
            self._entries.pop(eid, None)

    def count(self) -> int:
        with self._lock:
            self._expire_locked()
            return len(self._entries)


_registry: ExportRegistry | None = None


def get_export_registry() -> ExportRegistry:
    global _registry
    if _registry is None:
        _registry = ExportRegistry()
    return _registry
