"""Central supervisor for the Telegram and Discord bot child processes.

Only the authenticated local desktop API may drive this (the routes sit behind
the session-token dependency). Bots never start automatically unless the user
enabled auto-start. Child processes are stopped when LensTrace exits.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from backend.logging_config import get_logger
from backend.services import bot_config_service, settings_service
from backend.services.bot_process import BotProcess
from core.bots.status import BotRuntimeState, BotRuntimeStatus
from core.config.models import BotKind

logger = get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAX_BACKOFF_S = 30.0


def _python_executable() -> str:
    """Resolve the interpreter used to launch bots.

    Isolated so a future packaged build can substitute a bundled runtime
    without touching the supervisor logic.
    """
    return sys.executable


def _module_for(kind: BotKind) -> str:
    return "bots.telegram_bot.main" if kind == BotKind.TELEGRAM else "bots.discord_bot.main"


class BotSupervisor:
    """Manages lifecycle for both bots."""

    def __init__(self) -> None:
        self._procs: dict[BotKind, BotProcess] = {}
        self._auto_restart_counts: dict[BotKind, int] = {}
        self._timers: dict[BotKind, threading.Timer] = {}
        self._lock = threading.Lock()

    # ---- Command / env construction -------------------------------------

    def _build_command(self, kind: BotKind) -> list[str]:
        return [_python_executable(), "-m", _module_for(kind)]

    def _build_env(self, kind: BotKind, token: str) -> dict[str, str]:
        import os

        env = dict(os.environ)
        # Token is injected via the environment only, never via argv.
        env[bot_config_service.token_key(kind)] = token
        config = settings_service.get_config()
        env["LOG_LEVEL"] = config.log_level
        if kind == BotKind.DISCORD and config.discord.guild_id:
            env["DISCORD_GUILD_ID"] = config.discord.guild_id
        return env

    # ---- Public controls -------------------------------------------------

    def start(self, kind: BotKind) -> BotRuntimeStatus:
        with self._lock:
            token, _ = bot_config_service.resolve_token(kind)
            if not token:
                return self.status(kind)  # NOT_CONFIGURED
            existing = self._procs.get(kind)
            if existing is not None and existing.is_running():
                return self._status_locked(kind)
            self._auto_restart_counts[kind] = 0
            proc = BotProcess(
                name=kind.value,
                command=self._build_command(kind),
                env=self._build_env(kind, token),
                cwd=str(_REPO_ROOT),
                on_exit=self._on_process_exit,
            )
            self._procs[kind] = proc
            try:
                proc.start()
            except (RuntimeError, OSError) as exc:
                logger.warning("Failed to start %s bot: %s", kind.value, type(exc).__name__)
            return self._status_locked(kind)

    def stop(self, kind: BotKind) -> BotRuntimeStatus:
        with self._lock:
            self._cancel_timer(kind)
            proc = self._procs.get(kind)
            if proc is not None:
                proc.mark_stop_requested()
        # Stop outside the lock (it blocks on process wait).
        if proc is not None:
            proc.stop()
        with self._lock:
            return self._status_locked(kind)

    def restart(self, kind: BotKind) -> BotRuntimeStatus:
        self.stop(kind)
        return self.start(kind)

    def status(self, kind: BotKind) -> BotRuntimeStatus:
        with self._lock:
            return self._status_locked(kind)

    def logs(self, kind: BotKind, limit: int = 50) -> list[str]:
        with self._lock:
            proc = self._procs.get(kind)
            return proc.recent_logs(limit) if proc else []

    def shutdown_all(self) -> None:
        """Stop every child process — called when LensTrace exits."""
        with self._lock:
            for kind in list(self._timers):
                self._cancel_timer(kind)
            procs = list(self._procs.values())
            for proc in procs:
                proc.mark_stop_requested()
        for proc in procs:
            proc.stop()

    def start_auto_start_bots(self) -> None:
        """Start only bots the user marked auto-start AND that are configured."""
        config = settings_service.get_config()
        for kind, settings in (
            (BotKind.TELEGRAM, config.telegram),
            (BotKind.DISCORD, config.discord),
        ):
            if settings.auto_start:
                token, _ = bot_config_service.resolve_token(kind)
                if token:
                    logger.info("Auto-starting %s bot.", kind.value)
                    self.start(kind)

    # ---- Internals -------------------------------------------------------

    def _status_locked(self, kind: BotKind) -> BotRuntimeStatus:
        proc = self._procs.get(kind)
        token_configured = bot_config_service.resolve_token(kind)[0] is not None

        state: BotRuntimeState
        if proc is not None and proc.state in (
            BotRuntimeState.STARTING,
            BotRuntimeState.RUNNING,
            BotRuntimeState.STOPPING,
            BotRuntimeState.CRASHED,
        ):
            state = proc.state
        elif not token_configured:
            state = BotRuntimeState.NOT_CONFIGURED
        elif proc is not None and proc.state == BotRuntimeState.STOPPED:
            state = BotRuntimeState.STOPPED
        else:
            state = BotRuntimeState.READY

        return BotRuntimeStatus(
            state=state,
            configured=token_configured,
            last_started_at=proc.last_started_at if proc else None,
            uptime_seconds=proc.uptime_seconds() if proc else None,
            last_error=proc.last_error if proc else None,
            restart_count=self._auto_restart_counts.get(kind, 0),
            pid=proc.pid if proc else None,
            recent_logs=proc.recent_logs(20) if proc else [],
        )

    def _on_process_exit(self, proc: BotProcess) -> None:
        """Handle a child exit; auto-restart with backoff if configured."""
        kind = BotKind(proc.name)
        config = settings_service.get_config()
        if proc.state != BotRuntimeState.CRASHED:
            return  # clean stop, nothing to do
        if not config.lifecycle.restart_after_crash:
            return
        with self._lock:
            count = self._auto_restart_counts.get(kind, 0)
            if count >= config.lifecycle.max_restarts:
                logger.warning("%s bot reached max restarts (%d).", kind.value, count)
                return
            self._auto_restart_counts[kind] = count + 1
            delay = min(2.0**count, _MAX_BACKOFF_S)
            logger.info("Scheduling %s bot restart #%d in %.0fs.", kind.value, count + 1, delay)
            timer = threading.Timer(delay, self._auto_restart, args=(kind,))
            timer.daemon = True
            self._timers[kind] = timer
            timer.start()

    def _auto_restart(self, kind: BotKind) -> None:
        with self._lock:
            token, _ = bot_config_service.resolve_token(kind)
            if not token:
                return
            proc = BotProcess(
                name=kind.value,
                command=self._build_command(kind),
                env=self._build_env(kind, token),
                cwd=str(_REPO_ROOT),
                on_exit=self._on_process_exit,
            )
            # Preserve the restart counter across the new process instance.
            self._procs[kind] = proc
            try:
                proc.start()
            except (RuntimeError, OSError):
                logger.warning("Auto-restart of %s bot failed.", kind.value)

    def _cancel_timer(self, kind: BotKind) -> None:
        timer = self._timers.pop(kind, None)
        if timer is not None:
            timer.cancel()


_supervisor: BotSupervisor | None = None


def get_supervisor() -> BotSupervisor:
    global _supervisor
    if _supervisor is None:
        _supervisor = BotSupervisor()
    return _supervisor
