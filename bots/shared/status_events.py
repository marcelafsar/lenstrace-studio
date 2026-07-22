"""Structured, redacted status/error events emitted by bot child processes.

A bot prints single lines like::

    BOT_STATUS telegram polling_ready
    BOT_STATUS discord commands_synced count=4
    BOT_ERROR telegram upload_handler CorruptImageError

to stdout (flushed). The supervisor's :class:`BotProcess` reader parses these to
report *real* readiness (authenticated vs. ready vs. commands synced), not just
"the process exists". Tokens and coordinates are never included.
"""

from __future__ import annotations

import contextlib
import sys
from dataclasses import dataclass

STATUS_PREFIX = "BOT_STATUS"
ERROR_PREFIX = "BOT_ERROR"

# Recognised readiness phases (bot-agnostic where shared).
PHASE_STARTING = "starting"
PHASE_AUTHENTICATED = "authenticated"
PHASE_POLLING_READY = "polling_ready"  # Telegram
PHASE_GATEWAY_READY = "gateway_ready"  # Discord
PHASE_COMMANDS_SYNCED = "commands_synced"  # Discord
PHASE_READY = "ready"
PHASE_STOPPED = "stopped"


def emit_status(kind: str, phase: str, **fields: object) -> None:
    """Print a ``BOT_STATUS`` line and flush immediately."""
    extra = " ".join(f"{k}={v}" for k, v in fields.items())
    line = f"{STATUS_PREFIX} {kind} {phase}"
    if extra:
        line += f" {extra}"
    print(line, flush=True)


def emit_error(kind: str, where: str, message: str) -> None:
    """Print a ``BOT_ERROR`` line and flush. ``message`` must be non-sensitive."""
    # Keep it single-line and short; the supervisor also runs redaction.
    safe = message.replace("\n", " ").strip()[:200]
    print(f"{ERROR_PREFIX} {kind} {where} {safe}", flush=True)


@dataclass
class StatusEvent:
    kind: str
    phase: str
    fields: dict[str, str]


@dataclass
class ErrorEvent:
    kind: str
    where: str
    message: str


def parse_event(line: str) -> StatusEvent | ErrorEvent | None:
    """Parse a captured stdout line into a status/error event, or None."""
    line = line.strip()
    if line.startswith(STATUS_PREFIX + " "):
        parts = line[len(STATUS_PREFIX) + 1 :].split()
        if len(parts) < 2:
            return None
        kind, phase, *rest = parts
        fields: dict[str, str] = {}
        for token in rest:
            if "=" in token:
                key, value = token.split("=", 1)
                fields[key] = value
        return StatusEvent(kind=kind, phase=phase, fields=fields)
    if line.startswith(ERROR_PREFIX + " "):
        parts = line[len(ERROR_PREFIX) + 1 :].split(maxsplit=2)
        if len(parts) < 2:
            return None
        kind = parts[0]
        where = parts[1]
        message = parts[2] if len(parts) > 2 else ""
        return ErrorEvent(kind=kind, where=where, message=message)
    return None


def force_unbuffered_stdout() -> None:
    """Best-effort: make stdout line-buffered so events stream promptly."""
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
