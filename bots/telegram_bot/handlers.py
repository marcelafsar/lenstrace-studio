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

import contextlib
import logging
from datetime import date, datetime, time

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from backend.services.geocoding_service import GeocodingError, get_geocoding_service
from bots.shared.bot_sessions import BotSession, SessionManager
from bots.shared.formatting import CAPTURE_DISCLAIMER, format_diff, format_summary
from bots.shared.image_validation import accept_document, validate_image_content
from bots.shared.plan_config import exposure_resolution_kwargs as _exposure_resolution_kwargs
from bots.shared.status_events import emit_error, emit_status
from bots.shared.temporary_files import TemporaryWorkspace
from bots.telegram_bot import keyboards
from bots.telegram_bot.conversation import (
    MANUAL_COORDS_FORMAT,
    MANUAL_DATETIME_FORMAT,
    MANUAL_EXPOSURE_FORMAT,
    EditState,
)
from core.datetime_utils import offset_for_timezone, parse_user_datetime
from core.exceptions import LensTraceError
from core.location.validation import parse_coordinates
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
        await _ask_exposure(query, session)
    elif data == "exp:back":
        await _ask_exposure(query, session)
    elif data == "exp:preserve":
        session.config["exposure_mode"] = "preserve"
        session.config.pop("exposure_profile_id", None)
        await _ask_resolution(query, session)
    elif data == "exp:custom":
        session.state = EditState.ENTERING_CUSTOM_EXPOSURE.value
        await query.edit_message_text(
            f"Send custom exposure as `{MANUAL_EXPOSURE_FORMAT}`.\n\n"
            "_These are simulated values, not measured from the image._",
            parse_mode="Markdown",
        )
    elif data.startswith("expuse:"):
        session.config["exposure_mode"] = "override"
        session.config["exposure_profile_id"] = data.split(":", 1)[1]
        await _ask_resolution(query, session)
    elif data.startswith("exp:"):
        await _show_exposure_profile(query, session, data.split(":", 1)[1])
    elif data == "res:keep":
        session.config["resolution_mode"] = "keep"
        session.state = EditState.CHOOSING_DATE_MODE.value
        await query.edit_message_text("Date & time:", reply_markup=keyboards.datetime_keyboard())
    elif data == "res:12mp":
        session.config["resolution_mode"] = "iphone_12mp"
        session.state = EditState.CHOOSING_RESOLUTION_FIT.value
        await query.edit_message_text(
            "12 MP output — how should a non-3:4 source be fitted?",
            reply_markup=keyboards.resolution_fit_keyboard(),
        )
    elif data == "res:custom":
        session.state = EditState.ENTERING_CUSTOM_RESOLUTION.value
        await query.edit_message_text(
            "Send the custom size as `WIDTHxHEIGHT` (e.g. 3024x4032).", parse_mode="Markdown"
        )
    elif data == "resfit:crop":
        session.config["resolution_fit"] = "crop_to_fill"
        session.state = EditState.CHOOSING_DATE_MODE.value
        await query.edit_message_text("Date & time:", reply_markup=keyboards.datetime_keyboard())
    elif data == "resfit:fit":
        session.config["resolution_fit"] = "fit_with_padding"
        session.state = EditState.CHOOSING_DATE_MODE.value
        await query.edit_message_text("Date & time:", reply_markup=keyboards.datetime_keyboard())
    elif data == "resfit:back":
        await _ask_resolution(query, session)
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
    elif data == "dt:calendar":
        await _show_calendar(query, session)
    elif data.startswith("cal:"):
        await _on_calendar(query, session, data)
    elif data.startswith("th:"):
        await _on_hour(query, session, data.split(":", 1)[1])
    elif data.startswith("tm:"):
        await _on_minute(query, session, data.split(":", 1)[1])
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
    elif data == "loc:tg":
        await query.edit_message_text(
            "Share your location using Telegram's 📎 attach → Location, and I'll "
            "preview it for confirmation."
        )
    elif data == "loc:search":
        session.state = EditState.ENTERING_ADDRESS.value
        await query.edit_message_text(
            "Enter an address, landmark, city, or place name to search for."
        )
    elif data == "loc:coords":
        session.state = EditState.ENTERING_COORDINATES.value
        await query.edit_message_text(
            f"Send coordinates as `{MANUAL_COORDS_FORMAT}`, or share a Telegram location.",
            parse_mode="Markdown",
        )
    elif data.startswith("locpick:"):
        await _on_location_pick(query, ctx, session, data.split(":", 1)[1])
    elif data.startswith("locuse:"):
        await _on_location_use(query, session, data.split(":", 1)[1])
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
    elif session.state == EditState.ENTERING_CUSTOM_TIME.value:
        parsed = _parse_time(text)
        if parsed is None:
            await update.message.reply_text("Enter time as HH:MM or HH:MM:SS (24-hour).")
            return
        _apply_time(session, *parsed)
        await _ask_timezone_msg(update, session)
    elif session.state == EditState.ENTERING_COORDINATES.value:
        try:
            lat, lon = parse_coordinates(text)
            session.config["gps"] = GPSData(latitude=lat, longitude=lon)
            session.config["loc_mode"] = "set"
        except LensTraceError as exc:
            await update.message.reply_text(exc.user_message)
            return
        await _show_coord_preview_msg(update, session, lat, lon)
    elif session.state == EditState.ENTERING_CUSTOM_EXPOSURE.value:
        if not _apply_custom_exposure(session, text):
            await update.message.reply_text(
                f"Couldn't read that. Use `{MANUAL_EXPOSURE_FORMAT}`.", parse_mode="Markdown"
            )
            return
        await _ask_resolution_msg(update, session)
    elif session.state == EditState.ENTERING_CUSTOM_RESOLUTION.value:
        if not _apply_custom_resolution(session, text):
            await update.message.reply_text(
                "Use `WIDTHxHEIGHT`, e.g. 3024x4032.", parse_mode="Markdown"
            )
            return
        session.state = EditState.CHOOSING_DATE_MODE.value
        await update.message.reply_text("Date & time:", reply_markup=keyboards.datetime_keyboard())
    elif session.state == EditState.ENTERING_ADDRESS.value:
        await _run_address_search(update, session, text)
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
        **_exposure_resolution_kwargs(cfg),
    )
    return engine.apply_metadata(plan)


# ---- Exposure & resolution steps -----------------------------------------


async def _ask_exposure(query, session: BotSession) -> None:
    session.state = EditState.CHOOSING_EXPOSURE.value
    await query.edit_message_text(
        "Camera exposure (simulated metadata, not measured from the image):",
        reply_markup=keyboards.exposure_keyboard(),
    )


async def _show_exposure_profile(query, session: BotSession, profile_id: str) -> None:
    from core.exposure.loader import get_default_profile_loader

    try:
        profile = get_default_profile_loader().get(profile_id)
    except LensTraceError:
        await _ask_exposure(query, session)
        return
    flash = "Fired" if profile.flash_fired else "Off"
    lens = _selected_lens_display(session)
    await query.edit_message_text(
        f"*{profile.display_name}* — simulated exposure metadata\n```\n"
        f"ISO {profile.iso}\n"
        f"Shutter {profile.exposure_time} s\n"
        f"EV {profile.exposure_bias:g}\n"
        f"Flash {flash}\n"
        f"{lens}\n```",
        parse_mode="Markdown",
        reply_markup=keyboards.exposure_confirm_keyboard(profile_id),
    )


def _selected_lens_display(session: BotSession) -> str:
    """Aperture + 35 mm focal length from the selected lens preset (for display)."""
    preset_id = session.config.get("preset_id")
    lens_id = session.config.get("lens_id")
    if not preset_id or not lens_id:
        return "Aperture/focal from lens preset"
    from core.presets.loader import get_default_loader

    try:
        device = get_default_loader().get(preset_id)
    except LensTraceError:
        return "Aperture/focal from lens preset"
    lens = next((ln for ln in device.lenses if ln.id == lens_id), None)
    if lens is None:
        return "Aperture/focal from lens preset"
    bits = []
    if lens.f_number is not None:
        bits.append(f"Aperture f/{lens.f_number:g}")
    if lens.focal_length_35mm is not None:
        bits.append(f"35 mm focal length {lens.focal_length_35mm:g} mm")
    return "  ".join(bits) if bits else "Aperture/focal from lens preset"


async def _ask_resolution(query, session: BotSession) -> None:
    session.state = EditState.CHOOSING_RESOLUTION.value
    await query.edit_message_text(
        "Output resolution:", reply_markup=keyboards.resolution_keyboard()
    )


async def _ask_resolution_msg(update: Update, session: BotSession) -> None:
    session.state = EditState.CHOOSING_RESOLUTION.value
    await update.effective_message.reply_text(
        "Output resolution:", reply_markup=keyboards.resolution_keyboard()
    )


def _apply_custom_exposure(session: BotSession, text: str) -> bool:
    """Parse 'ISO, shutter, EV' into a custom exposure config. Returns success."""
    from core.exposure.validation import parse_shutter_speed

    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 2:
        return False
    try:
        iso = int(parts[0])
        shutter = parse_shutter_speed(parts[1])
        ev = float(parts[2]) if len(parts) >= 3 and parts[2] else 0.0
    except (ValueError, LensTraceError):
        return False
    session.config["exposure_mode"] = "custom"
    session.config["exposure_custom"] = {
        "iso": iso,
        "exposure_time_seconds": shutter,
        "exposure_bias": ev,
    }
    return True


def _apply_custom_resolution(session: BotSession, text: str) -> bool:
    lowered = text.lower().replace(" ", "")
    if "x" not in lowered:
        return False
    w_str, _, h_str = lowered.partition("x")
    try:
        w, h = int(w_str), int(h_str)
    except ValueError:
        return False
    if not (0 < w <= 30000 and 0 < h <= 30000):
        return False
    session.config["resolution_mode"] = "custom"
    session.config["custom_width"] = w
    session.config["custom_height"] = h
    return True


# ---- Calendar / time pickers ---------------------------------------------


async def _show_calendar(query, session: BotSession) -> None:
    session.state = EditState.CHOOSING_CALENDAR.value
    today = date.today()
    await query.edit_message_text(
        "Pick a date:", reply_markup=keyboards.calendar_keyboard(today.year, today.month)
    )


async def _on_calendar(query, session: BotSession, data: str) -> None:
    parts = data.split(":")
    action = parts[1]
    if action == "noop":
        return
    if action in ("p", "n"):  # navigate month
        year, month = (int(x) for x in parts[2].split("-"))
        await query.edit_message_text(
            "Pick a date:", reply_markup=keyboards.calendar_keyboard(year, month)
        )
    elif action == "today":
        session.config["pick_date"] = date.today()
        await _ask_hour(query, session)
    elif action == "d":  # a specific day
        year, month, day = (int(x) for x in parts[2].split("-"))
        session.config["pick_date"] = date(year, month, day)
        await _ask_hour(query, session)


async def _ask_hour(query, session: BotSession) -> None:
    session.state = EditState.CHOOSING_HOUR.value
    picked: date = session.config["pick_date"]
    await query.edit_message_text(
        f"Date: {picked.isoformat()}\nChoose the hour (24-hour):",
        reply_markup=keyboards.hour_keyboard(),
    )


async def _on_hour(query, session: BotSession, value: str) -> None:
    if value == "keep":
        # Keep original time -> use midnight on the chosen date, then timezone.
        _apply_time(session, 0, 0, 0)
        await _ask_timezone(query, session)
        return
    if value == "custom":
        session.state = EditState.ENTERING_CUSTOM_TIME.value
        await query.edit_message_text("Send the time as HH:MM or HH:MM:SS (24-hour).")
        return
    session.config["pick_hour"] = int(value)
    session.state = EditState.CHOOSING_MINUTE.value
    await query.edit_message_text("Choose the minute:", reply_markup=keyboards.minute_keyboard())


async def _on_minute(query, session: BotSession, value: str) -> None:
    if value == "custom":
        session.state = EditState.ENTERING_CUSTOM_TIME.value
        await query.edit_message_text("Send the time as HH:MM or HH:MM:SS (24-hour).")
        return
    hour = int(session.config.get("pick_hour", 0))
    _apply_time(session, hour, int(value), 0)
    await _ask_timezone(query, session)


def _parse_time(text: str) -> tuple[int, int, int] | None:
    """Parse HH:MM or HH:MM:SS strictly; return (h, m, s) or None."""
    parts = text.strip().split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        return None
    h, m = int(parts[0]), int(parts[1])
    s = int(parts[2]) if len(parts) == 3 else 0
    if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
        return None
    return h, m, s


def _apply_time(session: BotSession, hour: int, minute: int, second: int) -> None:
    """Combine the picked calendar date with a time into the session datetime."""
    picked: date = session.config.get("pick_date") or date.today()
    session.config["datetime"] = datetime.combine(picked, time(hour, minute, second))
    session.config["date_mode"] = "set"


# ---- Address search flow -------------------------------------------------


async def _run_address_search(update: Update, session: BotSession, query_text: str) -> None:
    await update.message.reply_text("🔎 Searching for that location…")
    try:
        results = get_geocoding_service().search(query_text)
    except GeocodingError as exc:
        await update.message.reply_text(
            f"{exc.user_message} You can enter coordinates instead.",
            reply_markup=keyboards.location_empty_keyboard(),
        )
        return
    if not results:
        await update.message.reply_text(
            "No matching location found.", reply_markup=keyboards.location_empty_keyboard()
        )
        return
    session.config["last_results"] = [r.result_id for r in results]
    await update.message.reply_text(
        "Select the correct location:",
        reply_markup=keyboards.location_result_keyboard(results),
    )


async def _on_location_pick(query, ctx, session: BotSession, result_id: str) -> None:
    result = get_geocoding_service().get_result(result_id)
    if result is None:
        await query.edit_message_text(
            "That result expired. Search again.", reply_markup=keyboards.location_empty_keyboard()
        )
        return
    # Show details + a map link, and send a Telegram location preview.
    await query.edit_message_text(
        f"*{result.display_name}*\n"
        f"`{result.latitude:.5f}, {result.longitude:.5f}`\n"
        f"[Open map]({result.map_url})",
        parse_mode="Markdown",
        reply_markup=keyboards.location_confirm_keyboard(result_id),
        disable_web_page_preview=False,
    )
    with contextlib.suppress(Exception):  # preview is best-effort
        await ctx.bot.send_location(
            chat_id=query.message.chat_id,
            latitude=result.latitude,
            longitude=result.longitude,
        )


async def _on_location_use(query, session: BotSession, result_id: str) -> None:
    result = get_geocoding_service().get_result(result_id)
    if result is None:
        await query.edit_message_text(
            "That result expired. Search again.", reply_markup=keyboards.location_empty_keyboard()
        )
        return
    session.config["gps"] = GPSData(
        latitude=result.latitude,
        longitude=result.longitude,
        address_label=result.display_name,
    )
    session.config["loc_mode"] = "set"
    await _show_review(query, session)


async def _show_coord_preview_msg(
    update: Update, session: BotSession, lat: float, lon: float
) -> None:
    """After manual coords: show a map link and go to review."""
    from core.location.map_links import osm_map_url

    await update.effective_message.reply_text(
        f"Location set: `{lat:.5f}, {lon:.5f}`\n[Open map]({osm_map_url(lat, lon)})",
        parse_mode="Markdown",
    )
    await _show_review_msg(update, session)


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
    from core.preview import build_camera_preview

    plan = _preview_plan(session)
    diff = engine.build_diff(plan)
    preview = build_camera_preview(plan)
    summary_block = ""
    if preview.lines:
        summary_block = "\n".join(preview.lines)
        if preview.exposure_source_label:
            summary_block += f"\n({preview.exposure_source_label})"
        summary_block = f"```\n{summary_block}\n```\n"
    return f"*Review*\n{summary_block}```\n{format_diff(diff)}\n```\n\n{CAPTURE_DISCLAIMER}"


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
        **_exposure_resolution_kwargs(cfg),
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
