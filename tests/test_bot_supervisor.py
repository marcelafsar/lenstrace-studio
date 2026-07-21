"""Tests for the bot process supervisor and BotProcess.

Uses trivial Python child commands (never a real bot) so no network or token is
required. Verifies lifecycle, duplicate prevention, crash detection, bounded and
redacted logs, and graceful shutdown.
"""

from __future__ import annotations

import os
import sys
import time

import pytest

from backend.services import bot_config_service, settings_service
from backend.services.bot_process import BotProcess
from backend.services.bot_supervisor import BotSupervisor
from core.bots.status import BotRuntimeState
from core.config.models import BotKind


def _wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _sleeper(seconds: float = 30.0) -> list[str]:
    return [sys.executable, "-c", f"import time; time.sleep({seconds})"]


def test_start_and_stop():
    proc = BotProcess("telegram", _sleeper(), dict(os.environ))
    proc.start()
    assert proc.is_running()
    assert proc.pid is not None
    assert proc.uptime_seconds() is not None
    proc.stop()
    assert not proc.is_running()
    assert proc.state == BotRuntimeState.STOPPED


def test_duplicate_start_rejected():
    proc = BotProcess("telegram", _sleeper(), dict(os.environ))
    proc.start()
    try:
        with pytest.raises(RuntimeError):
            proc.start()
    finally:
        proc.stop()


def test_crash_detected():
    proc = BotProcess("discord", [sys.executable, "-c", "raise SystemExit(3)"], dict(os.environ))
    proc.start()
    assert _wait_for(lambda: proc.state == BotRuntimeState.CRASHED)
    assert proc.last_error is not None


def test_logs_bounded_and_redacted():
    token = "987654321:ABCDEFghijklmnop_qrstuvwxyz012345678"
    code = f"print('leaking {token}')"
    proc = BotProcess("telegram", [sys.executable, "-c", code], dict(os.environ), log_capacity=10)
    proc.start()
    assert _wait_for(lambda: any("redacted" in ln for ln in proc.recent_logs()))
    joined = "\n".join(proc.recent_logs())
    assert token not in joined
    assert len(proc.recent_logs(100)) <= 10


def test_supervisor_status_not_configured(isolated_state):
    sup = BotSupervisor()
    status = sup.status(BotKind.TELEGRAM)
    assert status.state == BotRuntimeState.NOT_CONFIGURED
    assert status.configured is False


def test_supervisor_start_stop_with_dummy(isolated_state, monkeypatch):
    sup = BotSupervisor()
    # Pretend a token is configured and launch a harmless sleeper instead of a bot.
    monkeypatch.setattr(bot_config_service, "resolve_token", lambda kind: ("fake-token", None))
    monkeypatch.setattr(sup, "_build_command", lambda kind: _sleeper())
    status = sup.start(BotKind.TELEGRAM)
    assert status.state in (BotRuntimeState.RUNNING, BotRuntimeState.STARTING)
    stopped = sup.stop(BotKind.TELEGRAM)
    assert stopped.state == BotRuntimeState.STOPPED


def test_supervisor_shutdown_all(isolated_state, monkeypatch):
    sup = BotSupervisor()
    monkeypatch.setattr(bot_config_service, "resolve_token", lambda kind: ("fake-token", None))
    monkeypatch.setattr(sup, "_build_command", lambda kind: _sleeper())
    sup.start(BotKind.TELEGRAM)
    sup.start(BotKind.DISCORD)
    sup.shutdown_all()
    assert sup.status(BotKind.TELEGRAM).state != BotRuntimeState.RUNNING
    assert sup.status(BotKind.DISCORD).state != BotRuntimeState.RUNNING


def test_supervisor_does_not_auto_start_without_config(isolated_state, monkeypatch):
    sup = BotSupervisor()
    # Default settings: auto_start False → nothing starts.
    settings_service.reload_config()
    sup.start_auto_start_bots()
    assert sup.status(BotKind.TELEGRAM).state == BotRuntimeState.NOT_CONFIGURED
