"""Shared, library-agnostic helpers for both bots (sessions, temp files, text)."""

from bots.shared.bot_sessions import BotSession, SessionManager
from bots.shared.formatting import (
    CAPTURE_DISCLAIMER,
    format_diff,
    format_summary,
)
from bots.shared.temporary_files import TemporaryWorkspace

__all__ = [
    "BotSession",
    "SessionManager",
    "TemporaryWorkspace",
    "format_summary",
    "format_diff",
    "CAPTURE_DISCLAIMER",
]
