"""Telegram handlers. All metadata work is delegated to core.MetadataEngine.

Implemented and runnable (with the library + token): /start, /help, /privacy,
/cancel, document/photo upload, inspect, and remove-metadata. The multi-step
edit flow (device → date → location → review → export) is wired through the
shared session model; see EditState in conversation.py.

Logging never records image bytes or coordinates at INFO level.
"""

from __future__ import annotations

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from bots.shared.bot_sessions import BotSession, SessionManager
from bots.shared.formatting import CAPTURE_DISCLAIMER, format_diff, format_summary
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
    "/start – begin\n"
    "/help – this message\n"
    "/privacy – how your data is handled\n"
    "/cancel – discard the current session\n\n"
    "Send an image as a *document* to start."
)


# ---- Commands ------------------------------------------------------------


async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
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
    """Handle an uploaded image document."""
    message = update.message
    doc = message.document
    if doc is None:
        return
    if doc.file_size and doc.file_size > _max_bytes():
        await message.reply_text("That file is larger than the configured limit.")
        return

    session = sessions.get_or_create(update.effective_user.id)
    _discard_workspace(session)
    workspace = TemporaryWorkspace()
    session.config["workspace"] = workspace

    dest = workspace.input_path(doc.file_name or "upload")
    tg_file = await ctx.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(custom_path=str(dest))

    session.source_path = dest
    session.original_name = doc.file_name
    session.state = EditState.AWAIT_ACTION.value
    logger.info("Received document from user (name hidden), %d bytes", doc.file_size or 0)

    await message.reply_text(
        "What would you like to do?", reply_markup=keyboards.main_actions_keyboard()
    )


async def on_photo(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Photos are recompressed by Telegram; warn and ask for a document."""
    await update.message.reply_text(
        "That looks like a compressed photo, which loses metadata quality. "
        "Please resend the image as a *file/document* to preserve it.",
        parse_mode="Markdown",
    )


# ---- Callback actions ----------------------------------------------------


async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    session = sessions.get(update.effective_user.id)
    if session is None or session.source_path is None:
        await query.edit_message_text("Your session expired. Send the image again.")
        return

    if data == "action:cancel":
        _discard(update.effective_user.id)
        await query.edit_message_text("Cancelled.")
    elif data == "action:inspect":
        await _do_inspect(query, session)
    elif data == "action:remove":
        await _do_remove(query, session)
    elif data == "action:edit":
        session.state = EditState.CHOOSE_GENERATION.value
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
        await query.edit_message_text(
            "Choose a lens:", reply_markup=keyboards.lens_keyboard(session.config["preset_id"])
        )
    elif data.startswith("lens:"):
        session.config["lens_id"] = data.split(":", 1)[1]
        session.state = EditState.CHOOSE_DATETIME.value
        await query.edit_message_text("Date & time:", reply_markup=keyboards.datetime_keyboard())
    elif data == "dt:keep":
        session.config["date_mode"] = "keep"
        await _ask_location(query, session)
    elif data == "dt:now":
        session.config["date_mode"] = "set"
        session.config["datetime"] = datetime.now().replace(microsecond=0)
        await _ask_location(query, session)
    elif data == "dt:manual":
        session.state = EditState.AWAIT_MANUAL_DATETIME.value
        await query.edit_message_text(
            f"Send the date/time as `{MANUAL_DATETIME_FORMAT}`.", parse_mode="Markdown"
        )
    elif data == "loc:skip":
        session.config["loc_mode"] = "keep"
        await _show_review(query, session)
    elif data == "loc:remove":
        session.config["loc_mode"] = "remove"
        await _show_review(query, session)
    elif data == "loc:coords":
        session.state = EditState.AWAIT_COORDS.value
        await query.edit_message_text(
            f"Send coordinates as `{MANUAL_COORDS_FORMAT}`.", parse_mode="Markdown"
        )
    elif data == "confirm:yes":
        await _do_export(query, session)


async def on_text(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle manual date/time and coordinate entry based on session state."""
    session = sessions.get(update.effective_user.id)
    if session is None:
        return
    text = (update.message.text or "").strip()

    if session.state == EditState.AWAIT_MANUAL_DATETIME.value:
        try:
            session.config["datetime"] = parse_user_datetime(text)
            session.config["date_mode"] = "set"
        except LensTraceError as exc:
            await update.message.reply_text(exc.user_message)
            return
        await _ask_location_msg(update, session)
    elif session.state == EditState.AWAIT_COORDS.value:
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


# ---- Operations ----------------------------------------------------------


async def _do_inspect(query, session: BotSession) -> None:
    summary = engine.inspect_image(session.source_path)
    await query.edit_message_text(
        f"*Original metadata*\n```\n{format_summary(summary)}\n```\n\n{CAPTURE_DISCLAIMER}",
        parse_mode="Markdown",
    )


async def _do_remove(query, session: BotSession) -> None:
    workspace: TemporaryWorkspace = session.config["workspace"]
    result = engine.remove_metadata(session.source_path, workspace.output_dir)
    await query.message.reply_document(
        document=result.destination_path.open("rb"),  # noqa: SIM115 - sent then cleaned
        filename=result.destination_path.name,
        caption="Metadata removed. Original unchanged.",
    )
    _discard(session.user_id)


async def _do_export(query, session: BotSession) -> None:
    try:
        result = _build_and_export(session)
    except LensTraceError as exc:
        await query.edit_message_text(f"Export failed: {exc.user_message}")
        return
    await query.message.reply_document(
        document=result.destination_path.open("rb"),  # noqa: SIM115 - sent then cleaned
        filename=result.destination_path.name,
        caption=f"Done. {CAPTURE_DISCLAIMER}",
    )
    if result.audit_sidecar_path:
        await query.message.reply_document(
            document=result.audit_sidecar_path.open("rb"),  # noqa: SIM115
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


async def _ask_location(query, session: BotSession) -> None:
    session.state = EditState.CHOOSE_LOCATION.value
    await query.edit_message_text("Location:", reply_markup=keyboards.location_keyboard())


async def _ask_location_msg(update: Update, session: BotSession) -> None:
    session.state = EditState.CHOOSE_LOCATION.value
    await update.message.reply_text("Location:", reply_markup=keyboards.location_keyboard())


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
    session.state = EditState.REVIEW.value
    await query.edit_message_text(
        _review_text(session), parse_mode="Markdown", reply_markup=keyboards.confirm_keyboard()
    )


async def _show_review_msg(update: Update, session: BotSession) -> None:
    session.state = EditState.REVIEW.value
    await update.message.reply_text(
        _review_text(session), parse_mode="Markdown", reply_markup=keyboards.confirm_keyboard()
    )


# ---- Session cleanup -----------------------------------------------------


def _discard_workspace(session: BotSession) -> None:
    workspace = session.config.get("workspace")
    if isinstance(workspace, TemporaryWorkspace):
        workspace.cleanup()


def _discard(user_id: int) -> None:
    session = sessions.clear(user_id)
    if session is not None:
        _discard_workspace(session)


def _max_bytes() -> int:
    import os

    return int(os.environ.get("MAX_UPLOAD_MB", "25")) * 1024 * 1024
