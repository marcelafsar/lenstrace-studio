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
    # Telegram API URL form: .../bot<digits>:<token>/method — the token is
    # preceded by "bot" (a word char), so a \b-anchored pattern would MISS it.
    (
        re.compile(r"bot(\d{5,}):[A-Za-z0-9_\-]{20,}", re.I),
        r"bot\1:<redacted-telegram-token>",
    ),
    # Bare Telegram bot-token shape (no leading word boundary requirement).
    (re.compile(r"(?<![\w])\d{6,}:[A-Za-z0-9_\-]{30,}"), "<redacted-telegram-token>"),
    (
        re.compile(r"\b[MN][A-Za-z0-9_\-]{23}\.[A-Za-z0-9_\-]{6}\.[A-Za-z0-9_\-]{27,}\b"),
        "<redacted-discord-token>",
    ),
]


def redact(text: str) -> str:
    """Scrub known-sensitive substrings (tokens) from an arbitrary string.

    Reused by the bot supervisor to sanitise captured child-process output
    before it enters the in-memory log ring buffer.
    """
    if not text:
        return text
    redacted = text
    for pattern, replacement in _REDACT_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


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
    # Also attach the redaction filter to the handler-less flow and to noisy
    # HTTP client loggers that would otherwise log full request URLs. The
    # Telegram Bot API embeds the token in the request path, so httpx's INFO
    # "HTTP Request: POST .../bot<token>/..." line must never be emitted.
    for noisy in ("httpx", "httpcore", "telegram.vendor", "hpack"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
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
