"""Slash commands for the Discord bot: /metadata inspect|remove|edit|help.

All metadata work is delegated to core.MetadataEngine. Attachments are
downloaded to isolated temp workspaces and cleaned up after the reply.
Configuration replies are ephemeral; per-user sessions are isolated.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from bots.discord_bot.views import ConfirmView, EditPanel
from bots.shared.bot_sessions import BotSession, SessionManager
from bots.shared.formatting import CAPTURE_DISCLAIMER, format_diff, format_summary
from bots.shared.temporary_files import TemporaryWorkspace
from core.datetime_utils import offset_for_timezone
from core.exceptions import LensTraceError
from core.metadata_engine import MetadataEngine
from core.metadata_models import DateStrategy

logger = logging.getLogger(__name__)

engine = MetadataEngine()
sessions = SessionManager()

MAX_ATTACHMENT_MB = 25


class MetadataCommands(app_commands.Group):
    """The ``/metadata`` command group."""

    def __init__(self) -> None:
        super().__init__(name="metadata", description="Inspect, edit, or remove image metadata.")

    @app_commands.command(description="Show an image's current metadata.")
    async def inspect(self, interaction: discord.Interaction, image: discord.Attachment) -> None:
        with TemporaryWorkspace() as ws:
            path = await _download(image, ws)
            try:
                summary = engine.inspect_image(path)
            except LensTraceError as exc:
                await interaction.response.send_message(exc.user_message, ephemeral=True)
                return
            await interaction.response.send_message(
                f"```\n{format_summary(summary)}\n```\n{CAPTURE_DISCLAIMER}", ephemeral=True
            )

    @app_commands.command(description="Return a copy with all metadata removed.")
    async def remove(self, interaction: discord.Interaction, image: discord.Attachment) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        with TemporaryWorkspace() as ws:
            path = await _download(image, ws)
            try:
                result = engine.remove_metadata(path, ws.output_dir)
            except LensTraceError as exc:
                await interaction.followup.send(exc.user_message, ephemeral=True)
                return
            await interaction.followup.send(
                content="Metadata removed. Original unchanged.",
                file=discord.File(result.destination_path),
                ephemeral=True,
            )

    @app_commands.command(description="Edit metadata with a guided panel.")
    async def edit(self, interaction: discord.Interaction, image: discord.Attachment) -> None:
        if image.size > MAX_ATTACHMENT_MB * 1024 * 1024:
            await interaction.response.send_message("Attachment is too large.", ephemeral=True)
            return
        session = sessions.get_or_create(interaction.user.id)
        ws = TemporaryWorkspace()
        session.config = {"workspace": ws}
        session.source_path = await _download(image, ws)
        session.original_name = image.filename

        panel = EditPanel(session, on_review=_show_review)
        await interaction.response.send_message(
            content="Configure the metadata edit, then press **Review**.",
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


async def _download(attachment: discord.Attachment, ws: TemporaryWorkspace):
    dest = ws.input_path(attachment.filename)
    await attachment.save(dest)
    return dest


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
