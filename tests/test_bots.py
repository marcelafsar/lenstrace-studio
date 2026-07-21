"""Tests for the shared, library-agnostic bot infrastructure.

These do not import discord.py or python-telegram-bot; they exercise the session
model, temp-file safety, and message formatting that both bots rely on.
"""

from __future__ import annotations

import time

from bots.shared.bot_sessions import SessionManager
from bots.shared.formatting import format_diff, format_summary
from bots.shared.temporary_files import TemporaryWorkspace
from core.metadata_models import ChangeDiff, FieldChange, ImageFormat, MetadataSummary


def test_session_get_or_create_is_stable():
    mgr = SessionManager(timeout_minutes=15)
    a = mgr.get_or_create(42)
    b = mgr.get_or_create(42)
    assert a is b
    assert mgr.active_count() == 1


def test_session_expiration():
    mgr = SessionManager(timeout_minutes=15)
    session = mgr.get_or_create(7)
    # Force the session to look old.
    session.updated_at = time.time() - 16 * 60
    assert mgr.is_expired(session)
    assert mgr.get(7) is None  # lazily expired on access


def test_session_clear_returns_session():
    mgr = SessionManager()
    mgr.get_or_create(1)
    cleared = mgr.clear(1)
    assert cleared is not None
    assert mgr.get(1) is None


def test_temporary_workspace_cleans_up():
    with TemporaryWorkspace() as ws:
        path = ws.path
        assert path.exists()
        assert ws.input_dir.exists() and ws.output_dir.exists()
    assert not path.exists()


def test_temporary_workspace_sanitizes_input_name():
    with TemporaryWorkspace() as ws:
        target = ws.input_path("../../evil.jpg")
        assert ".." not in target.name
        assert target.parent == ws.input_dir


def test_format_summary_has_no_raw_bytes():
    summary = MetadataSummary(
        image_format=ImageFormat.JPEG,
        width=100,
        height=80,
        make="Apple",
        model="iPhone 13 Pro",
        has_gps=False,
    )
    text = format_summary(summary)
    assert "iPhone 13 Pro" in text
    assert "GPS: none" in text


def test_format_diff_skips_preserved():
    diff = ChangeDiff(
        rows=[
            FieldChange(field="Model", original="Old", new="iPhone 15", status="changed"),
            FieldChange(field="Make", original="Apple", new="Apple", status="preserved"),
        ]
    )
    text = format_diff(diff)
    assert "Model" in text
    assert "Make" not in text
