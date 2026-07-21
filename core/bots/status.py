"""Runtime status model for supervised bot processes (library-agnostic)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class BotRuntimeState(str, Enum):
    NOT_CONFIGURED = "not_configured"
    CONFIGURATION_INCOMPLETE = "configuration_incomplete"
    READY = "ready"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    AUTHENTICATION_FAILED = "authentication_failed"
    CONNECTION_FAILED = "connection_failed"
    CRASHED = "crashed"
    DISABLED = "disabled"


#: States in which starting is not permitted.
TERMINAL_BUSY = {BotRuntimeState.STARTING, BotRuntimeState.RUNNING, BotRuntimeState.STOPPING}


class BotRuntimeStatus(BaseModel):
    """A snapshot of a supervised bot's runtime status (no secrets)."""

    state: BotRuntimeState
    configured: bool = False
    last_started_at: datetime | None = None
    uptime_seconds: float | None = None
    last_connection_at: datetime | None = None
    #: Nontechnical, redacted last error suitable for the UI.
    last_error: str | None = None
    restart_count: int = 0
    pid: int | None = None
    #: Bounded recent log lines (already redacted).
    recent_logs: list[str] = Field(default_factory=list)

    # ---- Real-readiness signals reported by the bot process ----
    #: Last structured phase reported (e.g. "polling_ready", "gateway_ready").
    phase: str | None = None
    #: The bot authenticated with the platform API.
    authenticated: bool = False
    #: The bot is actually ready to receive updates (polling/gateway ready).
    ready: bool = False
    #: Discord: slash commands have been synchronised.
    commands_synced: bool = False
    commands_count: int | None = None
    #: Short label of the last update/command processed (no user content).
    last_processed: str | None = None
    #: Last handler-level error surfaced by the bot (redacted, non-sensitive).
    last_handler_error: str | None = None
