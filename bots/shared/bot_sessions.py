"""Per-user bot session state with expiration.

Sessions hold the in-progress change configuration for a single user while they
walk through the conversation. They expire after a configurable timeout so
abandoned conversations do not leak state or temp files.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any


@dataclass
class BotSession:
    """Mutable per-user session. ``config`` mirrors the desktop workflow inputs."""

    user_id: int
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    source_path: Path | None = None
    original_name: str | None = None
    #: Free-form config: preset_id, lens_id, datetime, utc_offset, gps, etc.
    config: dict[str, Any] = field(default_factory=dict)
    #: Current conversation state name (bot-specific).
    state: str = "idle"

    def touch(self) -> None:
        self.updated_at = time.time()


class SessionManager:
    """Thread-safe registry of user sessions with lazy expiration."""

    def __init__(self, timeout_minutes: int = 15) -> None:
        self._timeout = timeout_minutes * 60
        self._sessions: dict[int, BotSession] = {}
        self._lock = Lock()

    def get_or_create(self, user_id: int) -> BotSession:
        with self._lock:
            self._expire_locked()
            session = self._sessions.get(user_id)
            if session is None:
                session = BotSession(user_id=user_id)
                self._sessions[user_id] = session
            session.touch()
            return session

    def get(self, user_id: int) -> BotSession | None:
        with self._lock:
            self._expire_locked()
            return self._sessions.get(user_id)

    def clear(self, user_id: int) -> BotSession | None:
        """Remove and return a user's session (caller cleans up temp files)."""
        with self._lock:
            return self._sessions.pop(user_id, None)

    def is_expired(self, session: BotSession, *, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        return (now - session.updated_at) > self._timeout

    def _expire_locked(self) -> None:
        now = time.time()
        expired = [uid for uid, s in self._sessions.items() if self.is_expired(s, now=now)]
        for uid in expired:
            self._sessions.pop(uid, None)

    def active_count(self) -> int:
        with self._lock:
            self._expire_locked()
            return len(self._sessions)
