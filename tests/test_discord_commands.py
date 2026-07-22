"""Tests for the Discord slash-command workflow using mocked interactions.

No live Discord connection: interactions, attachments, and responses are mocked.
Verifies command registration, defer-before-download, follow-up usage,
attachment validation, owner-only controls, and error surfacing.
"""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from bots.discord_bot import commands as dc
from bots.discord_bot.main import LensTraceClient


def _run(coro):
    return asyncio.run(coro)


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (24, 24), (10, 120, 200)).save(buf, format="PNG")
    return buf.getvalue()


@dataclass
class FakeAttachment:
    filename: str = "a.png"
    content_type: str | None = "image/png"
    size: int = 2048
    payload: bytes = b""

    async def save(self, dest) -> None:
        Path(dest).write_bytes(self.payload or _png_bytes())


def make_interaction(user_id: int = 7) -> SimpleNamespace:
    response = AsyncMock()
    response.is_done = lambda: response.defer.await_count > 0
    followup = AsyncMock()
    return SimpleNamespace(
        response=response,
        followup=followup,
        user=SimpleNamespace(id=user_id),
    )


@pytest.fixture(autouse=True)
def _clear_sessions():
    dc.sessions._sessions.clear()
    yield
    dc.sessions._sessions.clear()


def _group() -> dc.MetadataCommands:
    return dc.MetadataCommands()


# ---- Command registration --------------------------------------------------


def test_required_commands_registered():
    client = LensTraceClient(guild_id=None)
    client.tree.add_command(_group())
    top = client.tree.get_commands()
    assert [c.name for c in top] == ["metadata"]
    subs = {s.name for s in top[0].commands}
    assert subs == {"inspect", "edit", "remove", "help"}


def test_dev_guild_id_stored():
    client = LensTraceClient(guild_id="123456789")
    assert client._guild_id == "123456789"


# ---- inspect ---------------------------------------------------------------


def test_inspect_defers_then_followups():
    group = _group()
    interaction = make_interaction()
    att = FakeAttachment(payload=_png_bytes())
    _run(group.inspect.callback(group, interaction, att))
    interaction.response.defer.assert_awaited()  # deferred first
    interaction.response.send_message.assert_not_called()  # not responded twice
    interaction.followup.send.assert_awaited()  # result via follow-up


def test_unsupported_attachment_rejected():
    group = _group()
    interaction = make_interaction()
    att = FakeAttachment(filename="notes.txt", content_type="text/plain")
    _run(group.inspect.callback(group, interaction, att))
    interaction.followup.send.assert_awaited()
    # The message should be the unsupported-type notice.
    msg = interaction.followup.send.call_args.args[0]
    assert "supported" in msg.lower()


def test_oversized_attachment_rejected_before_download(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    group = _group()
    interaction = make_interaction()
    att = FakeAttachment(size=5 * 1024 * 1024)
    att.save = AsyncMock()  # must NOT be called
    _run(group.inspect.callback(group, interaction, att))
    att.save.assert_not_called()


def test_corrupt_attachment_errors():
    group = _group()
    interaction = make_interaction()
    att = FakeAttachment(payload=b"not an image", content_type="image/png")
    _run(group.inspect.callback(group, interaction, att))
    interaction.followup.send.assert_awaited()


# ---- remove ----------------------------------------------------------------


def test_remove_returns_file():
    group = _group()
    interaction = make_interaction()
    att = FakeAttachment(payload=_png_bytes())
    _run(group.remove.callback(group, interaction, att))
    interaction.response.defer.assert_awaited()
    # A follow-up with a file attachment is sent.
    assert interaction.followup.send.await_count >= 1
    kwargs = interaction.followup.send.call_args.kwargs
    assert "file" in kwargs


# ---- edit ------------------------------------------------------------------


def test_edit_defers_and_sends_panel():
    group = _group()
    interaction = make_interaction()
    att = FakeAttachment(payload=_png_bytes())
    _run(group.edit.callback(group, interaction, att))
    interaction.response.defer.assert_awaited()
    kwargs = interaction.followup.send.call_args.kwargs
    assert kwargs.get("view") is not None
    assert dc.sessions.get(7).source_path is not None


def test_edit_panel_rejects_other_user():
    from bots.discord_bot.views import EditPanel
    from bots.shared.bot_sessions import BotSession

    session = BotSession(user_id=7)
    panel = EditPanel(session, on_review=AsyncMock())
    other = make_interaction(user_id=99)
    allowed = _run(panel.interaction_check(other))
    assert allowed is False
    other.response.send_message.assert_awaited()


def test_edit_panel_allows_owner():
    from bots.discord_bot.views import EditPanel
    from bots.shared.bot_sessions import BotSession

    session = BotSession(user_id=7)
    panel = EditPanel(session, on_review=AsyncMock())
    owner = make_interaction(user_id=7)
    assert _run(panel.interaction_check(owner)) is True


def test_edit_panel_timeout_cleans_up(tmp_path):
    from bots.discord_bot.views import EditPanel
    from bots.shared.bot_sessions import BotSession
    from bots.shared.temporary_files import TemporaryWorkspace

    ws = TemporaryWorkspace()
    session = BotSession(user_id=7)
    session.config = {"workspace": ws}
    panel = EditPanel(session, on_review=AsyncMock())
    assert ws.path.exists()
    _run(panel.on_timeout())
    assert not ws.path.exists()


# ---- error surfacing -------------------------------------------------------


def test_app_command_error_notifies_user():
    import discord

    client = LensTraceClient(guild_id=None)
    interaction = make_interaction()
    interaction.response.is_done = lambda: False
    err = discord.app_commands.AppCommandError("boom")
    _run(client._on_app_command_error(interaction, err))
    interaction.response.send_message.assert_awaited()


# ---- Discord pickers & address search --------------------------------------


def test_edit_panel_has_picker_and_address_buttons():
    from bots.discord_bot.views import EditPanel
    from bots.shared.bot_sessions import BotSession

    panel = EditPanel(BotSession(user_id=7), on_review=AsyncMock())
    labels = {getattr(c, "label", None) for c in panel.children}
    assert "📅 Date picker" in labels
    assert "🔍 Address" in labels
    assert "Coordinates" in labels
    assert "Review" in labels


def test_date_picker_splits_days_for_31_day_month():
    from bots.discord_bot import pickers
    from bots.shared.bot_sessions import BotSession

    view = pickers.DatePickerView(BotSession(user_id=7), on_date=AsyncMock())
    view.year, view.month = 2024, 1  # 31 days
    view._build()
    day_selects = [c for c in view.children if type(c).__name__ == "_DaySelect"]
    assert len(day_selects) == 2  # 1-16 and 17-31
    # Leap February has 29 days (still splits into two).
    view.year, view.month = 2024, 2
    view._build()
    day_selects = [c for c in view.children if type(c).__name__ == "_DaySelect"]
    assert len(day_selects) == 2


def test_time_view_confirm_sets_datetime():
    import datetime as dt

    from bots.discord_bot import pickers
    from bots.shared.bot_sessions import BotSession

    session = BotSession(user_id=7)
    finished = {}

    async def on_finish(interaction):
        finished["done"] = True

    view = pickers.TimeView(session, dt.date(2026, 8, 15), on_finish)
    view.hour, view.minute, view.timezone = 14, 30, "Europe/Istanbul"
    interaction = make_interaction()
    _run(view.confirm.callback(interaction))
    assert session.config["datetime"] == dt.datetime(2026, 8, 15, 14, 30, 0)
    assert session.config["timezone"] == "Europe/Istanbul"
    assert session.config.get("utc_offset")  # offset computed
    assert finished.get("done")


def _fake_geo(results):
    class _G:
        def search(self, q, **k):
            return results

        def get_result(self, rid):
            return {r.result_id: r for r in results}.get(rid)

    return _G()


def _geo_results():
    from core.location.map_links import osm_map_url
    from core.location.models import LocationSearchResult

    return [
        LocationSearchResult(
            result_id="rid1",
            display_name="Sultanahmet, Istanbul",
            latitude=41.0054,
            longitude=28.9768,
            provider="nominatim",
            map_url=osm_map_url(41.0054, 28.9768),
        )
    ]


def test_discord_address_search_flow(monkeypatch):
    from bots.discord_bot.views import EditPanel
    from bots.shared.bot_sessions import BotSession

    results = _geo_results()
    monkeypatch.setattr(
        "backend.services.geocoding_service.get_geocoding_service", lambda: _fake_geo(results)
    )
    session = BotSession(user_id=7)
    panel = EditPanel(session, on_review=AsyncMock())

    # Run search -> results view sent.
    interaction = make_interaction()
    _run(panel._run_address_search(interaction, "sultanahmet"))
    assert interaction.response.send_message.await_args.kwargs.get("view") is not None

    # Pick -> confirm view.
    pick_i = make_interaction()
    _run(panel._on_location_pick(pick_i, "rid1"))
    pick_i.response.edit_message.assert_awaited()

    # Use -> GPS applied.
    use_i = make_interaction()
    _run(panel._on_location_use(use_i, results[0]))
    assert session.config["loc_mode"] == "set"
    assert abs(session.config["gps"].latitude - 41.0054) < 1e-6
    assert session.config["gps"].address_label == "Sultanahmet, Istanbul"


def test_discord_address_empty_results(monkeypatch):
    from bots.discord_bot.views import EditPanel
    from bots.shared.bot_sessions import BotSession

    monkeypatch.setattr(
        "backend.services.geocoding_service.get_geocoding_service", lambda: _fake_geo([])
    )
    panel = EditPanel(BotSession(user_id=7), on_review=AsyncMock())
    interaction = make_interaction()
    _run(panel._run_address_search(interaction, "nowhere"))
    # A helpful ephemeral message is sent; no view.
    assert interaction.response.send_message.await_args.kwargs.get("view") is None


def test_location_results_view_rejects_other_user():
    from bots.discord_bot import pickers
    from bots.shared.bot_sessions import BotSession

    view = pickers.LocationResultsView(
        BotSession(user_id=7), _geo_results(), AsyncMock(), AsyncMock()
    )
    other = make_interaction(user_id=99)
    assert _run(view.interaction_check(other)) is False
