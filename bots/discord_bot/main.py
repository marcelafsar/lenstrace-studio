"""Discord bot entry point.

Run with:  python -m bots.discord_bot.main
Requires the DISCORD_BOT_TOKEN environment variable.

NOTE: This bot has not been run against the live Discord API in this repo's CI.
Interaction logic reuses the shared, tested engine; verify end-to-end before
relying on it in production.
"""

from __future__ import annotations

import logging
import os
import sys

import discord
from discord import app_commands

from backend.logging_config import configure_logging
from bots.discord_bot.commands import MetadataCommands


class LensTraceClient(discord.Client):
    def __init__(self) -> None:
        # Slash commands need no privileged intents.
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        self.tree.add_command(MetadataCommands())
        await self.tree.sync()


def main() -> None:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN is not set. Copy .env.example to .env.", file=sys.stderr)
        raise SystemExit(1)
    logging.getLogger(__name__).info("Starting Discord bot.")
    LensTraceClient().run(token)


if __name__ == "__main__":
    main()
