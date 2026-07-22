"""Tests for shared bot infrastructure: image validation, status events,
temp-workspace cleanup, and supervisor readiness reporting."""

from __future__ import annotations

import os
import sys
import time

import pytest
from PIL import Image

from bots.shared import image_validation as iv
from bots.shared import status_events as se
from bots.shared.temporary_files import (
    TemporaryWorkspace,
    cleanup_stale_workspaces,
)
from core.exceptions import CorruptImageError


def _png(path):
    Image.new("RGB", (16, 16), (1, 2, 3)).save(path, format="PNG")


# ---- accept_document -------------------------------------------------------


@pytest.mark.parametrize(
    "name,mime,expected",
    [
        ("a.png", "image/png", True),
        ("a.jpg", "image/jpeg", True),
        ("IMG.PNG", "application/octet-stream", True),  # iOS "send as file"
        ("IMG.PNG", None, True),
        ("a.tiff", "application/octet-stream", True),
        ("notes.txt", "text/plain", False),
        ("archive.zip", "application/octet-stream", False),  # unsupported extension
        ("noext", "application/octet-stream", False),
    ],
)
def test_accept_document(name, mime, expected):
    assert iv.accept_document(name, mime) is expected


def test_validate_image_content_ok(tmp_path):
    p = tmp_path / "a.png"
    _png(p)
    summary = iv.validate_image_content(p)
    assert summary.image_format.value == "PNG"


def test_validate_image_content_rejects_non_image(tmp_path):
    p = tmp_path / "a.png"
    p.write_bytes(b"definitely not an image")
    with pytest.raises(CorruptImageError):
        iv.validate_image_content(p)


# ---- status events ---------------------------------------------------------


def test_emit_and_parse_status(capsys):
    se.emit_status("telegram", "polling_ready", username="Bot")
    line = capsys.readouterr().out.strip()
    event = se.parse_event(line)
    assert isinstance(event, se.StatusEvent)
    assert event.kind == "telegram" and event.phase == "polling_ready"
    assert event.fields["username"] == "Bot"


def test_emit_and_parse_error(capsys):
    se.emit_error("discord", "command", "ValueError")
    line = capsys.readouterr().out.strip()
    event = se.parse_event(line)
    assert isinstance(event, se.ErrorEvent)
    assert event.kind == "discord" and event.where == "command"


def test_parse_ignores_normal_lines():
    assert se.parse_event("just a normal log line") is None


# ---- token redaction (regression: token embedded in a Telegram API URL) ----


def test_redaction_scrubs_url_embedded_telegram_token():
    from backend.logging_config import redact

    # Synthetic token with a real token's shape, embedded in the API URL form
    # httpx logs. The leading "bot" defeats a \b-anchored pattern, so this is a
    # regression guard for that exact case.
    line = "HTTP Request: POST https://api.telegram.org/bot1234567890:AAFakeSecret_abcdefghijklmnop12/getMe"
    out = redact(line)
    assert "AAFakeSecret" not in out
    assert "redacted-telegram-token" in out


def test_redaction_scrubs_bare_telegram_token():
    from backend.logging_config import redact

    out = redact("using 9876543210:ZZZZfakesecret_abcdefghijklmnop here")
    assert "ZZZZfakesecret" not in out


def test_redaction_keeps_status_events_readable():
    from backend.logging_config import redact

    line = "BOT_STATUS telegram polling_ready username=lenstracebot"
    assert redact(line) == line


# ---- temp workspace cleanup ------------------------------------------------


def test_cleanup_stale_workspaces(tmp_path, monkeypatch):
    import tempfile

    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    # A fresh workspace (should be kept) and a faked-old one (should be removed).
    fresh = TemporaryWorkspace()
    old = TemporaryWorkspace()
    old_time = time.time() - 24 * 60 * 60
    os.utime(old.path, (old_time, old_time))
    removed = cleanup_stale_workspaces(retention_seconds=3600)
    assert removed >= 1
    assert fresh.path.exists()
    assert not old.path.exists()
    fresh.cleanup()


def test_workspace_sanitizes_traversal():
    with TemporaryWorkspace() as ws:
        target = ws.input_path("../../evil.png")
        assert ".." not in target.name
        assert target.parent == ws.input_dir


# ---- supervisor readiness --------------------------------------------------


def test_supervisor_reports_ready_only_after_event(isolated_state, monkeypatch):
    from backend.services import bot_config_service
    from backend.services.bot_supervisor import BotSupervisor
    from core.bots.status import BotRuntimeState
    from core.config.models import BotKind

    sup = BotSupervisor()
    monkeypatch.setattr(bot_config_service, "resolve_token", lambda kind: ("fake", None))
    # Child emits polling_ready shortly, then stays alive briefly.
    code = (
        "import time; from bots.shared.status_events import emit_status; "
        "time.sleep(0.3); emit_status('telegram','polling_ready'); time.sleep(2)"
    )
    monkeypatch.setattr(sup, "_build_command", lambda kind: [sys.executable, "-c", code])

    sup.start(BotKind.TELEGRAM)
    # Immediately after start, the process exists but is not ready → STARTING.
    early = sup.status(BotKind.TELEGRAM)
    assert early.state == BotRuntimeState.STARTING
    assert early.ready is False

    # After the readiness event, it flips to RUNNING/ready.
    deadline = time.time() + 5
    while time.time() < deadline and not sup.status(BotKind.TELEGRAM).ready:
        time.sleep(0.05)
    ready = sup.status(BotKind.TELEGRAM)
    assert ready.ready is True
    assert ready.state == BotRuntimeState.RUNNING
    sup.stop(BotKind.TELEGRAM)


def test_supervisor_discord_commands_synced_event(isolated_state, monkeypatch):
    from backend.services import bot_config_service
    from backend.services.bot_supervisor import BotSupervisor
    from core.config.models import BotKind

    sup = BotSupervisor()
    monkeypatch.setattr(bot_config_service, "resolve_token", lambda kind: ("fake", None))
    code = (
        "import time; from bots.shared.status_events import emit_status; "
        "emit_status('discord','gateway_ready'); "
        "emit_status('discord','commands_synced', count=4); time.sleep(2)"
    )
    monkeypatch.setattr(sup, "_build_command", lambda kind: [sys.executable, "-c", code])
    sup.start(BotKind.DISCORD)
    deadline = time.time() + 5
    while time.time() < deadline and not sup.status(BotKind.DISCORD).commands_synced:
        time.sleep(0.05)
    status = sup.status(BotKind.DISCORD)
    assert status.commands_synced is True
    assert status.commands_count == 4
    sup.stop(BotKind.DISCORD)
