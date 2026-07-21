"""Discord bot entry point.

Run with:  python -m bots.discord_bot.main
Requires the DISCORD_BOT_TOKEN environment variable. An optional
DISCORD_GUILD_ID enables instant per-guild command sync for testing.

Emits structured BOT_STATUS/BOT_ERROR lines so the Bot Control Center can report
real readiness: authenticated → gateway ready → commands synced.
"""

from __future__ import annotations

import logging
import os
import sys

import discord
from discord import app_commands

from backend.logging_config import configure_logging
from bots.discord_bot.commands import MetadataCommands
from bots.shared.status_events import emit_error, emit_status, force_unbuffered_stdout
from bots.shared.temporary_files import cleanup_stale_workspaces

logger = logging.getLogger(__name__)
_KIND = "discord"


class LensTraceClient(discord.Client):
    def __init__(self, guild_id: str | None) -> None:
        # Slash-command-only workflows need no privileged (message content) intent.
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
        self.tree.on_error = self._on_app_command_error  # type: ignore[assignment]
        self._guild_id = guild_id
        self._ready_announced = False

    async def setup_hook(self) -> None:
        # Runs once per process start (not on every gateway reconnect), so we do
        # not re-sync commands repeatedly.
        self.tree.add_command(MetadataCommands())
        try:
            if self._guild_id and self._guild_id.isdigit():
                guild = discord.Object(id=int(self._guild_id))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
            else:
                synced = await self.tree.sync()
            emit_status(_KIND, "commands_synced", count=len(synced))
            logger.info("Synced %d Discord command(s).", len(synced))
        except discord.DiscordException as exc:
            emit_error(_KIND, "command_sync", type(exc).__name__)
            logger.error("Command sync failed: %s", type(exc).__name__)

    async def on_ready(self) -> None:
        if not self._ready_announced:
            name = self.user.name if self.user else "unknown"
            emit_status(_KIND, "authenticated", username=name)
            emit_status(_KIND, "gateway_ready", username=name)
            logger.info("Discord bot ready as %s", name)
            self._ready_announced = True

    async def _on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        emit_error(_KIND, "command", type(error).__name__)
        logger.error("App command error: %s", type(error).__name__)
        message = "Something went wrong running that command. Please try again."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.DiscordException:
            pass


def main() -> None:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    force_unbuffered_stdout()
    cleanup_stale_workspaces()
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN is not set. Copy .env.example to .env.", file=sys.stderr)
        raise SystemExit(1)
    logger.info("Starting Discord bot.")
    client = LensTraceClient(guild_id=os.environ.get("DISCORD_GUILD_ID"))
    client.run(token, log_handler=None)


if __name__ == "__main__":
    main()
