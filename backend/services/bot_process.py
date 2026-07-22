"""A single supervised bot child process.

Design goals (see PHASE 8 requirements):
  * Never uses ``shell=True``; the command is an explicit argument list.
  * The token is passed only via the child's environment, never in argv.
  * Captures bounded, redacted stdout/stderr into an in-memory ring buffer.
  * Stops gracefully (terminate) before forcing (kill) after a timeout.
  * Detects unexpected exits (crashes) and reports them without leaking secrets.
"""

from __future__ import annotations

import subprocess
import threading
from collections import deque
from collections.abc import Callable
from datetime import datetime, timezone

from backend.logging_config import get_logger, redact
from bots.shared.status_events import ErrorEvent, StatusEvent, parse_event
from core.bots.status import BotRuntimeState

logger = get_logger(__name__)

_STOP_TIMEOUT_S = 8.0
_LOG_CAPACITY = 200


class BotProcess:
    """Supervises one bot subprocess. Not started until :meth:`start` is called."""

    def __init__(
        self,
        name: str,
        command: list[str],
        env: dict[str, str],
        cwd: str | None = None,
        on_exit: Callable[[BotProcess], None] | None = None,
        log_capacity: int = _LOG_CAPACITY,
    ) -> None:
        self.name = name
        self._command = command
        self._env = env
        self._cwd = cwd
        self._on_exit = on_exit

        self._proc: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._lock = threading.Lock()
        self._stop_requested = False

        self.state = BotRuntimeState.STOPPED
        self.restart_count = 0
        self.last_started_at: datetime | None = None
        self.last_error: str | None = None
        self._logs: deque[str] = deque(maxlen=log_capacity)

        # Real-readiness signals parsed from the child's structured status events.
        self.phase: str | None = None
        self.authenticated: bool = False
        self.ready: bool = False
        self.commands_synced: bool = False
        self.commands_count: int | None = None
        self.last_processed: str | None = None
        self.last_handler_error: str | None = None

    # ---- Lifecycle -------------------------------------------------------

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        """Spawn the child process. Raises if already running (no duplicates)."""
        with self._lock:
            if self.is_running():
                raise RuntimeError(f"{self.name} bot is already running.")
            self._stop_requested = False
            self.state = BotRuntimeState.STARTING
            self._reset_readiness()
            self._append_log(f"Starting {self.name} bot process.")
            # Force unbuffered child stdout so status events stream promptly to
            # the Bot Control Center instead of sitting in a pipe buffer.
            child_env = dict(self._env)
            child_env["PYTHONUNBUFFERED"] = "1"
            try:
                self._proc = subprocess.Popen(  # noqa: S603 - explicit argv, no shell
                    self._command,
                    env=child_env,
                    cwd=self._cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                    shell=False,
                )
            except OSError as exc:
                self.state = BotRuntimeState.CRASHED
                self.last_error = f"Could not start process: {type(exc).__name__}"
                self._append_log(self.last_error)
                raise
            self.last_started_at = datetime.now(timezone.utc)
            self.state = BotRuntimeState.RUNNING
            self._reader = threading.Thread(target=self._pump_output, daemon=True)
            self._reader.start()

    def stop(self, timeout: float = _STOP_TIMEOUT_S) -> None:
        """Gracefully stop the process, forcing termination after ``timeout``."""
        with self._lock:
            self._stop_requested = True
            if not self.is_running():
                self.state = BotRuntimeState.STOPPED
                return
            self.state = BotRuntimeState.STOPPING
            proc = self._proc
        assert proc is not None
        self._append_log(f"Stopping {self.name} bot process.")
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._append_log("Graceful stop timed out; killing process.")
            proc.kill()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._append_log("Process did not exit after kill.")
        self.state = BotRuntimeState.STOPPED

    # ---- Internals -------------------------------------------------------

    def _pump_output(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            for line in proc.stdout:
                stripped = line.rstrip("\n")
                self._append_log(redact(stripped))
                self._consume_event(stripped)
        except Exception:  # noqa: BLE001 - reader must never crash the app
            pass
        exit_code = proc.wait()
        self._handle_exit(exit_code)

    def _consume_event(self, line: str) -> None:
        """Update readiness signals from a structured status/error event line."""
        event = parse_event(line)
        if isinstance(event, StatusEvent):
            self.phase = event.phase
            if event.phase == "authenticated":
                self.authenticated = True
            elif event.phase in ("polling_ready", "gateway_ready", "ready"):
                self.authenticated = True
                self.ready = True
            elif event.phase == "commands_synced":
                self.commands_synced = True
                count = event.fields.get("count")
                self.commands_count = int(count) if count and count.isdigit() else None
            elif event.phase == "processed":
                self.last_processed = event.fields.get("what", "update")
        elif isinstance(event, ErrorEvent):
            self.last_handler_error = f"{event.where}: {event.message}".strip()

    def _reset_readiness(self) -> None:
        self.phase = None
        self.authenticated = False
        self.ready = False
        self.commands_synced = False
        self.commands_count = None
        self.last_processed = None
        self.last_handler_error = None

    def _handle_exit(self, exit_code: int) -> None:
        if self._stop_requested:
            self.state = BotRuntimeState.STOPPED
            self._append_log(f"{self.name} bot stopped (exit {exit_code}).")
        else:
            self.state = BotRuntimeState.CRASHED
            self.last_error = f"Process exited unexpectedly (code {exit_code})."
            self._append_log(self.last_error)
        if self._on_exit is not None:
            try:
                self._on_exit(self)
            except Exception:  # noqa: BLE001
                logger.warning("on_exit handler failed for %s bot.", self.name)

    def _append_log(self, message: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self._logs.append(f"{stamp} {redact(message)}")

    # ---- Introspection ---------------------------------------------------

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self.is_running() and self._proc else None

    def uptime_seconds(self) -> float | None:
        if self.is_running() and self.last_started_at is not None:
            return (datetime.now(timezone.utc) - self.last_started_at).total_seconds()
        return None

    def recent_logs(self, limit: int = 50) -> list[str]:
        return list(self._logs)[-limit:]

    def mark_stop_requested(self) -> None:
        self._stop_requested = True
