"""Telegram handlers. All metadata work is delegated to core.MetadataEngine.

Robust document-upload flow: EVERY document reaches ``on_document`` (the handler
is registered with ``filters.Document.ALL``), which accepts image MIME types and
also image documents whose MIME is missing/``application/octet-stream`` but whose
extension is supported (common from iOS "Send as File"). Content is then
validated by actually decoding it. The user is acknowledged immediately, and a
global error handler guarantees no silent failure.

Logging never records image bytes or coordinates at INFO level.
"""

from __future__ import annotations

import logging
from datetime import datetime

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bots.shared.bot_sessions import BotSession, SessionManager
from bots.shared.formatting import CAPTURE_DISCLAIMER, format_diff, format_summary
from bots.shared.image_validation import accept_document, validate_image_content
from bots.shared.status_events import emit_error, emit_status
from bots.shared.temporary_files import TemporaryWorkspace
from bots.telegram_bot import keyboards
from bots.telegram_bot.conversation import (
    MANUAL_COORDS_FORMAT,
    MANUAL_DATETIME_FORMAT,
    EditState,
)
from core.datetime_utils import offset_for_timezone, parse_user_datetime
from core.exceptions import LensTraceError
from core.metadata_engine import MetadataEngine
from core.metadata_models import DateStrategy, GPSData

logger = logging.getLogger(__name__)

engine = MetadataEngine()
sessions = SessionManager()

_KIND = "telegram"

WELCOME = (
    "👋 *LensTrace Studio bot*\n\n"
    "Send me an image *as a file/document* (not as a compressed photo) and I'll "
    "let you inspect, edit, or remove its metadata. I always return a new copy — "
    "your original is never changed.\n\n"
    f"{CAPTURE_DISCLAIMER}"
)

PRIVACY = (
    "*Privacy*\n"
    "• Files are processed on the server running this bot and deleted right after "
    "your result is sent.\n"
    "• I don't log image contents or coordinates.\n"
    "• Address search (if used) sends only the text you type, never your image.\n"
    "• Use /cancel any time to discard your session."
)

HELP = (
    "*Commands*\n"
    "/start – begin (also resets your current session)\n"
    "/help – this message\n"
    "/privacy – how your data is handled\n"
    "/cancel – discard the current session\n\n"
    "Send an image as a *document/file* to start."
)

GENERIC_ERROR = (
    "LensTrace could not process that file. The file may be unsupported or "
    "damaged. You can send another image or use /cancel."
)


# ---- Commands ------------------------------------------------------------


async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    # /start always safely resets any in-progress session and temp files.
    _discard(update.effective_user.id)
    session = sessions.get_or_create(update.effective_user.id)
    session.state = EditState.WAITING_FOR_UPLOAD.value
    await update.message.reply_markdown(WELCOME)


async def cmd_help(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_markdown(HELP)


async def cmd_privacy(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_markdown(PRIVACY)


async def cmd_cancel(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    _discard(update.effective_user.id)
    await update.message.reply_text("Session cleared. Send a new image to start again.")


# ---- Upload --------------------------------------------------------------


async def on_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ANY uploaded document; accept only real, supported images."""
    message = update.effective_message
    doc = message.document if message else None
    if doc is None:
        return

    # Gate on the declared type first (image MIME, or generic MIME + supported
    # extension). Never accept a clearly non-image MIME.
    if not accept_document(doc.file_name, doc.mime_type):
        await message.reply_text(
            "That file type isn't supported. Send a JPEG, PNG, WebP, or TIFF image "
            "as a file/document."
        )
        return

    # Validate size BEFORE downloading anything.
    if doc.file_size and doc.file_size > _max_bytes():
        await message.reply_text(
            f"That file is {doc.file_size // (1024 * 1024)} MB, larger than the "
            f"{_max_bytes() // (1024 * 1024)} MB limit."
        )
        return

    # Acknowledge immediately, before the slower download/inspection.
    await message.reply_text("📥 File received. Inspecting metadata…")
    await ctx.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)

    session = sessions.get_or_create(update.effective_user.id)
    _discard_workspace(session)
    workspace = TemporaryWorkspace()
    session.config = {"workspace": workspace}

    dest = workspace.input_path(doc.file_name or "upload.img")
    tg_file = await ctx.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(custom_path=str(dest))

    # Verify the downloaded size where Telegram reported one.
    if doc.file_size and dest.stat().st_size != doc.file_size:
        logger.warning("Downloaded size mismatch for user upload (expected vs actual differ).")

    # Authoritative content validation (actually decode the image).
    try:
        summary = validate_image_content(dest)
    except LensTraceError as exc:
        _discard(session.user_id)
        await message.reply_text(exc.user_message)
        return

    session.source_path = dest
    session.original_name = doc.file_name
    session.state = EditState.AWAIT_ACTION.value
    logger.info("Received document (name hidden), %d bytes", doc.file_size or dest.stat().st_size)
    emit_status(_KIND, "processed", what="upload")

    await _send_summary_and_actions(message, session, summary)


async def on_photo(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Compressed photo route: warn, but offer to continue with reduced quality."""
    message = update.effective_message
    if message is None or not message.photo:
        return
    session = sessions.get_or_create(update.effective_user.id)
    # Remember the highest-resolution photo in case the user continues anyway.
    session.config["pending_photo_file_id"] = message.photo[-1].file_id
    session.state = EditState.WAITING_FOR_UPLOAD.value
    await message.reply_text(
        "That looks like a *compressed photo*. Telegram may have already stripped "
        "or reduced its metadata. For best results, send the image as a *file/"
        "document* instead.",
        parse_mode="Markdown",
        reply_markup=keyboards.photo_warning_keyboard(),
    )


async def on_location(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """A shared Telegram location sets GPS during the location step."""
    message = update.effective_message
    session = sessions.get(update.effective_user.id)
    if session is None or message is None or message.location is None:
        return
    if session.state != EditState.CHOOSING_LOCATION.value:
        return
    loc = message.location
    session.config["gps"] = GPSData(latitude=loc.latitude, longitude=loc.longitude)
    session.config["loc_mode"] = "set"
    await _show_review_msg(update, session)


# ---- Callback actions ----------------------------------------------------


async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    # Always answer promptly so the button spinner clears.
    await query.answer()
    data = query.data or ""

    # Photo-route buttons may fire before a real session exists.
    if data == "photo:asfile":
        await query.edit_message_text(
            "Great — send the image as a file/document and I'll process it."
        )
        return

    session = sessions.get(update.effective_user.id)
    if session is None:
        await query.edit_message_text("That button has expired. Send your image again to start.")
        return

    if data == "photo:continue":
        await _continue_with_photo(query, ctx, session)
        return

    if session.source_path is None:
        await query.edit_message_text("Your session expired. Send the image again.")
        return

    await _route_callback(query, ctx, session, data)


async def _route_callback(query, ctx, session: BotSession, data: str) -> None:
    if data == "action:cancel":
        _discard(session.user_id)
        await query.edit_message_text("Cancelled. Send another image whenever you like.")
    elif data == "action:inspect":
        await _do_inspect(query, session)
    elif data == "action:remove":
        await _do_remove(query, session)
    elif data == "action:edit":
        session.state = EditState.CHOOSING_DEVICE.value
        await query.edit_message_text(
            "Choose a device generation:", reply_markup=keyboards.generation_keyboard()
        )
    elif data.startswith("gen:"):
        await query.edit_message_text(
            "Choose a model:", reply_markup=keyboards.device_keyboard(data.split(":", 1)[1])
        )
    elif data == "nav:generations":
        await query.edit_message_text(
            "Choose a device generation:", reply_markup=keyboards.generation_keyboard()
        )
    elif data.startswith("preset:"):
        session.config["preset_id"] = data.split(":", 1)[1]
        session.state = EditState.CHOOSING_LENS.value
        await query.edit_message_text(
            "Choose a lens:", reply_markup=keyboards.lens_keyboard(session.config["preset_id"])
        )
    elif data.startswith("lens:"):
        lens_id = data.split(":", 1)[1]
        session.config["lens_id"] = None if lens_id == "keep" else lens_id
        session.state = EditState.CHOOSING_DATE_MODE.value
        await query.edit_message_text("Date & time:", reply_markup=keyboards.datetime_keyboard())
    elif data == "dt:keep":
        session.config["date_mode"] = "keep"
        await _ask_location(query, session)
    elif data == "dt:now":
        session.config["date_mode"] = "set"
        session.config["datetime"] = datetime.now().replace(microsecond=0)
        await _ask_timezone(query, session)
    elif data == "dt:manual":
        session.state = EditState.ENTERING_DATETIME.value
        await query.edit_message_text(
            f"Send the date/time as `{MANUAL_DATETIME_FORMAT}`.", parse_mode="Markdown"
        )
    elif data.startswith("tz:"):
        zone = data.split(":", 1)[1]
        if zone != "skip":
            session.config["timezone"] = zone
        await _ask_location(query, session)
    elif data == "loc:skip":
        session.config["loc_mode"] = "keep"
        await _show_review(query, session)
    elif data == "loc:remove":
        session.config["loc_mode"] = "remove"
        await _show_review(query, session)
    elif data == "loc:coords":
        session.state = EditState.ENTERING_COORDINATES.value
        await query.edit_message_text(
            f"Send coordinates as `{MANUAL_COORDS_FORMAT}`, or share a Telegram location.",
            parse_mode="Markdown",
        )
    elif data == "confirm:yes":
        await _do_export(query, session)
    else:
        await query.answer("That option isn't available anymore.", show_alert=False)


async def _continue_with_photo(query, ctx, session: BotSession) -> None:
    """Download the highest-res compressed photo and proceed (reduced quality)."""
    file_id = session.config.get("pending_photo_file_id")
    if not file_id:
        await query.edit_message_text("No photo to continue with. Send an image again.")
        return
    _discard_workspace(session)
    workspace = TemporaryWorkspace()
    session.config = {"workspace": workspace}
    dest = workspace.input_path("telegram_photo.jpg")
    tg_file = await ctx.bot.get_file(file_id)
    await tg_file.download_to_drive(custom_path=str(dest))
    try:
        summary = validate_image_content(dest)
    except LensTraceError as exc:
        _discard(session.user_id)
        await query.edit_message_text(exc.user_message)
        return
    session.source_path = dest
    session.original_name = "telegram_photo.jpg"
    session.state = EditState.AWAIT_ACTION.value
    await query.edit_message_text(
        "⚠️ Using the compressed photo — original metadata may already be missing."
    )
    emit_status(_KIND, "processed", what="photo")
    await _send_summary_and_actions(query.message, session, summary)


async def on_text(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle manual date/time and coordinate entry based on session state."""
    session = sessions.get(update.effective_user.id)
    if session is None:
        return
    text = (update.message.text or "").strip()

    if session.state == EditState.ENTERING_DATETIME.value:
        try:
            session.config["datetime"] = parse_user_datetime(text)
            session.config["date_mode"] = "set"
        except LensTraceError as exc:
            await update.message.reply_text(exc.user_message)
            return
        await _ask_timezone_msg(update, session)
    elif session.state == EditState.ENTERING_COORDINATES.value:
        try:
            lat_str, lon_str = text.split(",")
            session.config["gps"] = GPSData(latitude=float(lat_str), longitude=float(lon_str))
            session.config["loc_mode"] = "set"
        except (ValueError, LensTraceError):
            await update.message.reply_text(
                f"Could not parse coordinates. Use `{MANUAL_COORDS_FORMAT}`.", parse_mode="Markdown"
            )
            return
        await _show_review_msg(update, session)
    elif session.state == EditState.WAITING_FOR_UPLOAD.value:
        await update.message.reply_text("Send an image as a file/document to begin, or /help.")
    else:
        await update.message.reply_text("Please use the buttons above, or /cancel to start over.")


# ---- Global error handler ------------------------------------------------


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Capture every unhandled handler exception; never leave the user hanging."""
    err = context.error
    logger.error("Unhandled Telegram error: %s", type(err).__name__, exc_info=err)
    emit_error(_KIND, "handler", type(err).__name__ if err else "unknown")

    # Clean up the user's temp workspace if we can identify them.
    if isinstance(update, Update) and update.effective_user:
        _discard_workspace_only(update.effective_user.id)
        try:
            if update.effective_message:
                await update.effective_message.reply_text(GENERIC_ERROR)
            elif update.callback_query:
                await update.callback_query.message.reply_text(GENERIC_ERROR)
        except Exception:  # noqa: BLE001 - best-effort notification
            pass


# ---- Operations ----------------------------------------------------------


async def _send_summary_and_actions(message, session: BotSession, summary) -> None:
    await message.reply_text(
        f"*Metadata*\n```\n{format_summary(summary)}\n```\n\nWhat would you like to do?",
        parse_mode="Markdown",
        reply_markup=keyboards.main_actions_keyboard(),
    )


async def _do_inspect(query, session: BotSession) -> None:
    summary = engine.inspect_image(session.source_path)
    emit_status(_KIND, "processed", what="inspect")
    await query.edit_message_text(
        f"*Original metadata*\n```\n{format_summary(summary)}\n```\n\n{CAPTURE_DISCLAIMER}",
        parse_mode="Markdown",
        reply_markup=keyboards.main_actions_keyboard(),
    )


async def _do_remove(query, session: BotSession) -> None:
    workspace: TemporaryWorkspace = session.config["workspace"]
    result = engine.remove_metadata(session.source_path, workspace.output_dir)
    emit_status(_KIND, "processed", what="remove")
    with result.destination_path.open("rb") as fh:
        await query.message.reply_document(
            document=fh,
            filename=result.destination_path.name,
            caption="Metadata removed. Original unchanged.",
        )
    _discard(session.user_id)


async def _do_export(query, session: BotSession) -> None:
    session.state = EditState.PROCESSING.value
    try:
        result = _build_and_export(session)
    except LensTraceError as exc:
        await query.edit_message_text(f"Export failed: {exc.user_message}")
        return
    emit_status(_KIND, "processed", what="export")
    with result.destination_path.open("rb") as fh:
        await query.message.reply_document(
            document=fh,
            filename=result.destination_path.name,
            caption=f"Done. {CAPTURE_DISCLAIMER}",
        )
    if result.audit_sidecar_path:
        with result.audit_sidecar_path.open("rb") as fh:
            await query.message.reply_document(
                document=fh,
                filename=result.audit_sidecar_path.name,
                caption="Audit sidecar (JSON).",
            )
    _discard(session.user_id)


def _build_and_export(session: BotSession):
    workspace: TemporaryWorkspace = session.config["workspace"]
    cfg = session.config
    date_strategy = DateStrategy.KEEP_ORIGINAL
    dt_value = None
    utc_offset = None
    if cfg.get("date_mode") == "set" and cfg.get("datetime"):
        date_strategy = DateStrategy.SET_EXPLICIT
        dt_value = cfg["datetime"]
        tz = cfg.get("timezone")
        if tz:
            utc_offset = offset_for_timezone(tz, dt_value)

    plan = engine.build_change_plan(
        session.source_path,
        workspace.output_dir,
        preset_id=cfg.get("preset_id"),
        lens_id=cfg.get("lens_id"),
        date_strategy=date_strategy,
        datetime_original=dt_value,
        create_date=dt_value,
        modify_date=dt_value,
        utc_offset=utc_offset,
        gps=cfg.get("gps") if cfg.get("loc_mode") == "set" else None,
        remove_gps=cfg.get("loc_mode") == "remove",
    )
    return engine.apply_metadata(plan)


# ---- Review helpers (callback vs. text entry points) ---------------------


async def _ask_timezone(query, session: BotSession) -> None:
    session.state = EditState.CHOOSING_TIMEZONE.value
    await query.edit_message_text("Time zone:", reply_markup=keyboards.timezone_keyboard())


async def _ask_timezone_msg(update: Update, session: BotSession) -> None:
    session.state = EditState.CHOOSING_TIMEZONE.value
    await update.message.reply_text("Time zone:", reply_markup=keyboards.timezone_keyboard())


async def _ask_location(query, session: BotSession) -> None:
    session.state = EditState.CHOOSING_LOCATION.value
    await query.edit_message_text("Location:", reply_markup=keyboards.location_keyboard())


def _review_text(session: BotSession) -> str:
    plan = _preview_plan(session)
    diff = engine.build_diff(plan)
    return f"*Review*\n```\n{format_diff(diff)}\n```\n\n{CAPTURE_DISCLAIMER}"


def _preview_plan(session: BotSession):
    workspace: TemporaryWorkspace = session.config["workspace"]
    cfg = session.config
    date_strategy = (
        DateStrategy.SET_EXPLICIT if cfg.get("date_mode") == "set" else DateStrategy.KEEP_ORIGINAL
    )
    return engine.build_change_plan(
        session.source_path,
        workspace.output_dir,
        preset_id=cfg.get("preset_id"),
        lens_id=cfg.get("lens_id"),
        date_strategy=date_strategy,
        datetime_original=cfg.get("datetime"),
        gps=cfg.get("gps") if cfg.get("loc_mode") == "set" else None,
        remove_gps=cfg.get("loc_mode") == "remove",
    )


async def _show_review(query, session: BotSession) -> None:
    session.state = EditState.REVIEWING.value
    await query.edit_message_text(
        _review_text(session), parse_mode="Markdown", reply_markup=keyboards.confirm_keyboard()
    )


async def _show_review_msg(update: Update, session: BotSession) -> None:
    session.state = EditState.REVIEWING.value
    await update.effective_message.reply_text(
        _review_text(session), parse_mode="Markdown", reply_markup=keyboards.confirm_keyboard()
    )


# ---- Session cleanup -----------------------------------------------------


def _discard_workspace(session: BotSession) -> None:
    workspace = session.config.get("workspace")
    if isinstance(workspace, TemporaryWorkspace):
        workspace.cleanup()


def _discard_workspace_only(user_id: int) -> None:
    session = sessions.get(user_id)
    if session is not None:
        _discard_workspace(session)


def _discard(user_id: int) -> None:
    session = sessions.clear(user_id)
    if session is not None:
        _discard_workspace(session)


def _max_bytes() -> int:
    import os

    return int(os.environ.get("MAX_UPLOAD_MB", "25")) * 1024 * 1024
