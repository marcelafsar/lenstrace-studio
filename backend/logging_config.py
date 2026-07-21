"""Structured logging with secret/PII redaction.

Never logs bot tokens, session tokens, image bytes, or (at normal levels) exact
private paths and personal coordinates. A logging filter scrubs known-sensitive
patterns from every record as a defence-in-depth measure.
"""

from __future__ import annotations

import logging
import re
from typing import Any

# Patterns that must never appear in logs, regardless of level.
_REDACT_PATTERNS = [
    (re.compile(r"(session[_-]?token[\"'=:\s]+)[\w\-\.]+", re.I), r"\1<redacted>"),
    (re.compile(r"(bot[_-]?token[\"'=:\s]+)[\w\-\.:]+", re.I), r"\1<redacted>"),
    # Telegram/Discord token shapes.
    (re.compile(r"\b\d{6,}:[A-Za-z0-9_\-]{30,}\b"), "<redacted-telegram-token>"),
    (
        re.compile(r"\b[MN][A-Za-z0-9_\-]{23}\.[A-Za-z0-9_\-]{6}\.[A-Za-z0-9_\-]{27,}\b"),
        "<redacted-discord-token>",
    ),
]


class RedactionFilter(logging.Filter):
    """Scrub sensitive substrings from formatted log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - never let logging crash the app
            return True
        redacted = message
        for pattern, replacement in _REDACT_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


class _KeyValueFormatter(logging.Formatter):
    """Compact structured formatter: ``time level logger | message``."""

    def format(self, record: logging.LogRecord) -> str:
        base = (
            f"{self.formatTime(record, '%Y-%m-%dT%H:%M:%S')} "
            f"{record.levelname:<7} {record.name} | {record.getMessage()}"
        )
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once, with redaction enabled."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    # Avoid duplicate handlers on repeated calls (e.g. reload).
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(_KeyValueFormatter())
    handler.addFilter(RedactionFilter())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def safe_path(path: Any) -> str:
    """Return just the filename for logging, hiding the full private path."""
    from pathlib import Path

    try:
        return Path(str(path)).name
    except Exception:  # noqa: BLE001
        return "<path>"
