"""Slash commands for the Discord bot: /metadata inspect|remove|edit|help.

All metadata work is delegated to core.MetadataEngine. Every command that
downloads an attachment defers the interaction FIRST (downloads can exceed
Discord's 3-second initial-response window) and then replies via a follow-up.
Attachments are validated by actually decoding them, stored in isolated temp
workspaces, and cleaned up after the reply. Configuration replies are ephemeral;
sessions are per-user and reject other users' clicks.
"""

from __future__ import annotations

import logging
import os

import discord
from discord import app_commands

from bots.discord_bot.views import ConfirmView, EditPanel
from bots.shared.bot_sessions import BotSession, SessionManager
from bots.shared.formatting import CAPTURE_DISCLAIMER, format_diff, format_summary
from bots.shared.image_validation import accept_document, validate_image_content
from bots.shared.status_events import emit_status
from bots.shared.temporary_files import TemporaryWorkspace
from core.datetime_utils import offset_for_timezone
from core.exceptions import LensTraceError
from core.metadata_engine import MetadataEngine
from core.metadata_models import DateStrategy

logger = logging.getLogger(__name__)

engine = MetadataEngine()
sessions = SessionManager()

_KIND = "discord"


def _max_bytes() -> int:
    return int(os.environ.get("MAX_UPLOAD_MB", "25")) * 1024 * 1024


async def _download(attachment: discord.Attachment, ws: TemporaryWorkspace):
    dest = ws.input_path(attachment.filename)
    await attachment.save(dest)
    return dest


async def _prepare(
    interaction: discord.Interaction, image: discord.Attachment, ws: TemporaryWorkspace
):
    """Validate + download + content-check an attachment. Returns (path, summary).

    On any problem, sends an ephemeral follow-up and returns ``(None, None)``.
    Assumes the interaction has already been deferred.
    """
    if not accept_document(image.filename, image.content_type):
        await interaction.followup.send(
            "That file type isn't supported. Attach a JPEG, PNG, WebP, or TIFF image.",
            ephemeral=True,
        )
        return None, None
    if image.size > _max_bytes():
        await interaction.followup.send(
            f"Attachment is {image.size // (1024 * 1024)} MB, larger than the "
            f"{_max_bytes() // (1024 * 1024)} MB limit.",
            ephemeral=True,
        )
        return None, None
    path = await _download(image, ws)
    try:
        summary = validate_image_content(path)
    except LensTraceError as exc:
        await interaction.followup.send(exc.user_message, ephemeral=True)
        return None, None
    return path, summary


class MetadataCommands(app_commands.Group):
    """The ``/metadata`` command group."""

    def __init__(self) -> None:
        super().__init__(name="metadata", description="Inspect, edit, or remove image metadata.")

    @app_commands.command(description="Show an image's current metadata.")
    async def inspect(self, interaction: discord.Interaction, image: discord.Attachment) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        with TemporaryWorkspace() as ws:
            _path, summary = await _prepare(interaction, image, ws)
            if summary is None:
                return
            emit_status(_KIND, "processed", what="inspect")
            await interaction.followup.send(
                f"```\n{format_summary(summary)}\n```\n{CAPTURE_DISCLAIMER}", ephemeral=True
            )

    @app_commands.command(description="Return a copy with all metadata removed.")
    async def remove(self, interaction: discord.Interaction, image: discord.Attachment) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        with TemporaryWorkspace() as ws:
            path, summary = await _prepare(interaction, image, ws)
            if path is None:
                return
            try:
                result = engine.remove_metadata(path, ws.output_dir)
            except LensTraceError as exc:
                await interaction.followup.send(exc.user_message, ephemeral=True)
                return
            emit_status(_KIND, "processed", what="remove")
            await interaction.followup.send(
                content="Metadata removed. Original unchanged.",
                file=discord.File(result.destination_path),
                ephemeral=True,
            )

    @app_commands.command(description="Edit metadata with a guided panel.")
    async def edit(self, interaction: discord.Interaction, image: discord.Attachment) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        session = sessions.get_or_create(interaction.user.id)
        _cleanup(session)  # discard any previous pending edit for this user
        session = sessions.get_or_create(interaction.user.id)
        ws = TemporaryWorkspace()
        session.config = {"workspace": ws}
        path, summary = await _prepare(interaction, image, ws)
        if path is None:
            ws.cleanup()
            return
        session.source_path = path
        session.original_name = image.filename
        emit_status(_KIND, "processed", what="edit")

        panel = EditPanel(session, on_review=_show_review)
        await interaction.followup.send(
            content=(
                f"```\n{format_summary(summary)}\n```\n"
                "Configure the edit below, then press **Review**."
            ),
            view=panel,
            ephemeral=True,
        )

    @app_commands.command(description="How this bot works and its privacy stance.")
    async def help(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "**LensTrace Studio**\n"
            "• `/metadata inspect` – view metadata\n"
            "• `/metadata edit` – guided edit (device, date, location)\n"
            "• `/metadata remove` – strip all metadata\n\n"
            "Originals are never modified; files are deleted after the reply.\n"
            f"{CAPTURE_DISCLAIMER}",
            ephemeral=True,
        )


async def _show_review(interaction: discord.Interaction, session: BotSession) -> None:
    plan = _preview_plan(session)
    diff = engine.build_diff(plan)
    embed = discord.Embed(title="Review changes", description=f"```\n{format_diff(diff)}\n```")
    embed.set_footer(text="Metadata does not prove capture facts.")
    await interaction.response.edit_message(
        content=None, embed=embed, view=ConfirmView(session, on_confirm=_do_export)
    )


async def _do_export(interaction: discord.Interaction, session: BotSession) -> None:
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        result = _build_and_export(session)
    except LensTraceError as exc:
        await interaction.followup.send(f"Export failed: {exc.user_message}", ephemeral=True)
        _cleanup(session)
        return
    emit_status(_KIND, "processed", what="export")
    files = [discord.File(result.destination_path)]
    if result.audit_sidecar_path:
        files.append(discord.File(result.audit_sidecar_path))
    await interaction.followup.send(
        content=f"Done. {CAPTURE_DISCLAIMER}", files=files, ephemeral=True
    )
    _cleanup(session)


def _preview_plan(session: BotSession):
    cfg = session.config
    ws: TemporaryWorkspace = cfg["workspace"]
    strategy = (
        DateStrategy.SET_EXPLICIT if cfg.get("date_mode") == "set" else DateStrategy.KEEP_ORIGINAL
    )
    return engine.build_change_plan(
        session.source_path,
        ws.output_dir,
        preset_id=cfg.get("preset_id"),
        lens_id=cfg.get("lens_id"),
        date_strategy=strategy,
        datetime_original=cfg.get("datetime"),
        gps=cfg.get("gps") if cfg.get("loc_mode") == "set" else None,
        remove_gps=cfg.get("loc_mode") == "remove",
    )


def _build_and_export(session: BotSession):
    cfg = session.config
    ws: TemporaryWorkspace = cfg["workspace"]
    strategy = (
        DateStrategy.SET_EXPLICIT if cfg.get("date_mode") == "set" else DateStrategy.KEEP_ORIGINAL
    )
    dt_value = cfg.get("datetime")
    utc_offset = cfg.get("utc_offset")
    if (
        strategy == DateStrategy.SET_EXPLICIT
        and dt_value
        and not utc_offset
        and cfg.get("timezone")
    ):
        utc_offset = offset_for_timezone(cfg["timezone"], dt_value)
    plan = engine.build_change_plan(
        session.source_path,
        ws.output_dir,
        preset_id=cfg.get("preset_id"),
        lens_id=cfg.get("lens_id"),
        date_strategy=strategy,
        datetime_original=dt_value,
        create_date=dt_value,
        modify_date=dt_value,
        utc_offset=utc_offset,
        gps=cfg.get("gps") if cfg.get("loc_mode") == "set" else None,
        remove_gps=cfg.get("loc_mode") == "remove",
    )
    return engine.apply_metadata(plan)


def _cleanup(session: BotSession) -> None:
    ws = session.config.get("workspace")
    if isinstance(ws, TemporaryWorkspace):
        ws.cleanup()
    sessions.clear(session.user_id)
