"""Integration-style tests for the Telegram bot handlers.

These reproduce the original failure (image documents with a non-image MIME being
silently dropped) and confirm the fix, using synthetic Telegram objects and
mocked network I/O — no live token. Handlers are exercised through the real
Application/handler registration where it matters (filter matching), and
directly (with mocks) for behaviour.
"""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import piexif
import pytest
from PIL import Image

from bots.telegram_bot import handlers
from bots.telegram_bot.conversation import EditState


def _run(coro):
    return asyncio.run(coro)


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 24), (10, 120, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    exif = {
        "0th": {piexif.ImageIFD.Make: b"OldMake"},
        "Exif": {},
        "GPS": {},
        "1st": {},
        "Interop": {},
        "thumbnail": None,
    }
    Image.new("RGB", (32, 24), (5, 5, 5)).save(buf, format="JPEG", exif=piexif.dump(exif))
    return buf.getvalue()


@dataclass
class FakeDoc:
    file_id: str = "f1"
    file_name: str | None = "PHOTO.PNG"
    mime_type: str | None = "application/octet-stream"
    file_size: int = 1234


class FakeFile:
    """Mimics telegram.File; writes prepared bytes on download."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def download_to_drive(self, custom_path: str) -> None:
        from pathlib import Path

        Path(custom_path).write_bytes(self._payload)


def make_message(**kwargs) -> AsyncMock:
    msg = AsyncMock()
    msg.chat_id = 999
    msg.document = kwargs.get("document")
    msg.photo = kwargs.get("photo")
    msg.location = kwargs.get("location")
    msg.text = kwargs.get("text")
    return msg


def make_update(user_id: int = 42, **kwargs) -> SimpleNamespace:
    msg = kwargs.get("message") or make_message(**kwargs)
    return SimpleNamespace(
        effective_message=msg,
        message=msg,
        effective_user=SimpleNamespace(id=user_id),
        callback_query=kwargs.get("callback_query"),
    )


def make_ctx(payload: bytes | None = None) -> SimpleNamespace:
    bot = AsyncMock()
    if payload is not None:
        bot.get_file = AsyncMock(return_value=FakeFile(payload))
    bot.send_chat_action = AsyncMock()
    return SimpleNamespace(bot=bot, error=None)


@pytest.fixture(autouse=True)
def _clear_sessions():
    handlers.sessions._sessions.clear()
    yield
    handlers.sessions._sessions.clear()


# ---- The core regression: octet-stream document is handled -----------------


def test_document_handler_matches_octet_stream_via_application():
    """The registered handler must match a non-image-MIME image document."""
    import os

    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:fake")
    from telegram import Chat, Document, Message, Update, User

    from bots.telegram_bot.main import build_application

    app = build_application()
    handlers_group = app.handlers[0]

    def doc_update(mime):
        doc = Document(file_id="x", file_unique_id="u", file_name="A.PNG", mime_type=mime)
        msg = Message(
            message_id=1,
            date=datetime.now(),
            chat=Chat(id=1, type="private"),
            from_user=User(id=1, first_name="t", is_bot=False),
            document=doc,
        )
        return Update(update_id=1, message=msg)

    for mime in ("image/png", "application/octet-stream", None):
        upd = doc_update(mime)
        names = [h.callback.__name__ for h in handlers_group if h.check_update(upd)]
        assert "on_document" in names, f"octet-stream/{mime} not routed to on_document"


def test_document_png_accepted_and_shows_actions():
    upd = make_update(document=FakeDoc(mime_type="image/png", file_name="a.png"))
    ctx = make_ctx(_png_bytes())
    _run(handlers.on_document(upd, ctx))

    # Immediate acknowledgement happened.
    ack_texts = [c.args[0] for c in upd.effective_message.reply_text.call_args_list]
    assert any("received" in t.lower() for t in ack_texts)
    # A metadata/action message with buttons followed.
    assert upd.effective_message.reply_text.call_count >= 2
    session = handlers.sessions.get(42)
    assert session is not None and session.source_path is not None
    assert session.state == EditState.AWAIT_ACTION.value


def test_document_octet_stream_with_png_extension_accepted():
    upd = make_update(document=FakeDoc(mime_type="application/octet-stream", file_name="IMG.PNG"))
    ctx = make_ctx(_png_bytes())
    _run(handlers.on_document(upd, ctx))
    assert handlers.sessions.get(42).source_path is not None


def test_document_jpeg_accepted():
    upd = make_update(document=FakeDoc(mime_type="image/jpeg", file_name="a.jpg"))
    ctx = make_ctx(_jpeg_bytes())
    _run(handlers.on_document(upd, ctx))
    assert handlers.sessions.get(42).source_path is not None


def test_unsupported_document_rejected_without_download():
    upd = make_update(document=FakeDoc(mime_type="text/plain", file_name="notes.txt"))
    ctx = make_ctx(_png_bytes())
    _run(handlers.on_document(upd, ctx))
    ctx.bot.get_file.assert_not_called()
    # No usable session source was set.
    session = handlers.sessions.get(42)
    assert session is None or session.source_path is None


def test_oversized_document_rejected_before_download(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    upd = make_update(
        document=FakeDoc(mime_type="image/png", file_name="big.png", file_size=5 * 1024 * 1024)
    )
    ctx = make_ctx(_png_bytes())
    _run(handlers.on_document(upd, ctx))
    ctx.bot.get_file.assert_not_called()


def test_corrupt_image_gives_user_error():
    upd = make_update(document=FakeDoc(mime_type="image/png", file_name="broken.png"))
    ctx = make_ctx(b"this is not an image")
    _run(handlers.on_document(upd, ctx))
    texts = [c.args[0] for c in upd.effective_message.reply_text.call_args_list]
    assert any("not a supported image" in t.lower() or "damaged" in t.lower() for t in texts)
    session = handlers.sessions.get(42)
    assert session is None or session.source_path is None


# ---- Commands & photo route ------------------------------------------------


def test_cmd_start_resets_session():
    # Seed a stale session, then /start should replace it cleanly.
    handlers.sessions.get_or_create(42).source_path = "stale"
    upd = make_update()
    _run(handlers.cmd_start(upd, make_ctx()))
    upd.message.reply_markdown.assert_awaited()
    assert handlers.sessions.get(42).source_path is None
    assert handlers.sessions.get(42).state == EditState.WAITING_FOR_UPLOAD.value


def test_cmd_cancel_clears_tempfiles():
    upd = make_update(document=FakeDoc(mime_type="image/png", file_name="a.png"))
    _run(handlers.on_document(upd, make_ctx(_png_bytes())))
    ws = handlers.sessions.get(42).config["workspace"]
    assert ws.path.exists()
    _run(handlers.cmd_cancel(make_update(), make_ctx()))
    assert not ws.path.exists()
    assert handlers.sessions.get(42) is None


def test_photo_route_warns_with_keyboard():
    upd = make_update(photo=[SimpleNamespace(file_id="p1")])
    _run(handlers.on_photo(upd, make_ctx()))
    call = upd.effective_message.reply_text.call_args
    assert call.kwargs.get("reply_markup") is not None


def test_document_works_after_photo_warning():
    # 1) a photo warning, then 2) a proper document upload must still work.
    _run(handlers.on_photo(make_update(photo=[SimpleNamespace(file_id="p1")]), make_ctx()))
    upd = make_update(document=FakeDoc(mime_type="image/png", file_name="a.png"))
    _run(handlers.on_document(upd, make_ctx(_png_bytes())))
    assert handlers.sessions.get(42).source_path is not None


# ---- Callback actions ------------------------------------------------------


def _seed_session_with_image(user_id: int = 42) -> None:
    upd = make_update(user_id=user_id, document=FakeDoc(mime_type="image/png", file_name="a.png"))
    _run(handlers.on_document(upd, make_ctx(_png_bytes())))


def make_query(data: str, user_id: int = 42) -> AsyncMock:
    query = AsyncMock()
    query.data = data
    query.from_user = SimpleNamespace(id=user_id)
    query.message = AsyncMock()
    return query


def test_callback_inspect():
    _seed_session_with_image()
    query = make_query("action:inspect")
    upd = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=42))
    _run(handlers.on_callback(upd, make_ctx()))
    query.answer.assert_awaited()
    query.edit_message_text.assert_awaited()


def test_callback_remove_sends_document():
    _seed_session_with_image()
    query = make_query("action:remove")
    upd = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=42))
    _run(handlers.on_callback(upd, make_ctx()))
    query.message.reply_document.assert_awaited()
    assert handlers.sessions.get(42) is None  # cleaned up after remove


def test_full_edit_export_path_sends_document():
    _seed_session_with_image()
    steps = ["action:edit", "preset:iphone-15", "lens:keep", "dt:keep", "loc:skip", "confirm:yes"]
    last_query = None
    for data in steps:
        last_query = make_query(data)
        upd = SimpleNamespace(callback_query=last_query, effective_user=SimpleNamespace(id=42))
        _run(handlers.on_callback(upd, make_ctx()))
    # The confirm step returns the exported file as a document.
    last_query.message.reply_document.assert_awaited()
    assert handlers.sessions.get(42) is None


def test_stale_callback_is_handled_gracefully():
    # No session at all → friendly expiry message, no crash.
    query = make_query("action:inspect", user_id=777)
    upd = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=777))
    _run(handlers.on_callback(upd, make_ctx()))
    query.edit_message_text.assert_awaited()


# ---- Global error handler --------------------------------------------------


def test_error_handler_notifies_user():
    from telegram import Update as TgUpdate

    msg = AsyncMock()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        effective_message=msg,
        callback_query=None,
    )
    # Make isinstance(update, Update) pass by faking the class check target.
    ctx = SimpleNamespace(error=ValueError("boom"))

    # Patch Update to our SimpleNamespace type for the isinstance check.
    original = handlers.Update
    handlers.Update = SimpleNamespace  # type: ignore[assignment]
    try:
        _run(handlers.on_error(update, ctx))
    finally:
        handlers.Update = original
    msg.reply_text.assert_awaited()
    assert TgUpdate  # imported for clarity
