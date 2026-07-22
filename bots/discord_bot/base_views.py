"""Shared Discord view base: owner-only controls with timeout cleanup."""

from __future__ import annotations

import discord

from bots.shared.bot_sessions import BotSession
from bots.shared.temporary_files import TemporaryWorkspace


def expire_session(session: BotSession) -> None:
    """Clean up a session's temp workspace when its view expires."""
    ws = session.config.get("workspace")
    if isinstance(ws, TemporaryWorkspace):
        ws.cleanup()


class OwnedView(discord.ui.View):
    """A view whose controls only the invoking user may operate."""

    def __init__(self, session: BotSession, timeout: float = 600) -> None:
        super().__init__(timeout=timeout)
        self.session = session

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message(
                "This isn't your editing session.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        expire_session(self.session)
