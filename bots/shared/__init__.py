"""Shared, library-agnostic helpers for both bots (sessions, temp files, text)."""

from bots.shared.bot_sessions import BotSession, SessionManager
from bots.shared.formatting import (
    CAPTURE_DISCLAIMER,
    format_diff,
    format_summary,
)
from bots.shared.image_validation import accept_document, validate_image_content
from bots.shared.temporary_files import TemporaryWorkspace, cleanup_stale_workspaces

__all__ = [
    "BotSession",
    "SessionManager",
    "TemporaryWorkspace",
    "cleanup_stale_workspaces",
    "accept_document",
    "validate_image_content",
    "format_summary",
    "format_diff",
    "CAPTURE_DISCLAIMER",
]
