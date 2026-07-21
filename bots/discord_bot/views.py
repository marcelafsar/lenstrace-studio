"""Discord views: the ephemeral edit panel with buttons and select menus.

Component counts are kept well within Discord's limits (max 5 action rows, 25
select options). Device selection is paginated by generation to stay under the
option cap.
"""

from __future__ import annotations

import discord

from bots.discord_bot.modals import CoordinatesModal, DateTimeModal
from bots.shared.bot_sessions import BotSession
from core.datetime_utils import offset_for_timezone, parse_user_datetime
from core.metadata_models import GPSData
from core.presets.loader import get_default_loader


class GenerationSelect(discord.ui.Select):
    def __init__(self, panel: EditPanel) -> None:
        groups = get_default_loader().grouped_by_generation()
        options = [discord.SelectOption(label=gen, value=gen) for gen in list(groups)[:25]]
        super().__init__(placeholder="Choose a device generation…", options=options)
        self._panel = panel

    async def callback(self, interaction: discord.Interaction) -> None:
        self._panel.set_generation(self.values[0])
        await interaction.response.edit_message(view=self._panel)


class DeviceSelect(discord.ui.Select):
    def __init__(self, panel: EditPanel, generation: str) -> None:
        devices = get_default_loader().grouped_by_generation().get(generation, [])[:25]
        options = [discord.SelectOption(label=d.display_name, value=d.id) for d in devices]
        super().__init__(
            placeholder="Choose a model…",
            options=options or [discord.SelectOption(label="(none)", value="none")],
        )
        self._panel = panel

    async def callback(self, interaction: discord.Interaction) -> None:
        self._panel.session.config["preset_id"] = self.values[0]
        device = get_default_loader().get(self.values[0])
        self._panel.session.config["lens_id"] = device.lenses[0].id if device.lenses else None
        await interaction.response.edit_message(
            content=self._panel.summary_line(), view=self._panel
        )


class EditPanel(discord.ui.View):
    """The main ephemeral configuration panel for ``/metadata edit``."""

    def __init__(self, session: BotSession, on_review, timeout: float = 600) -> None:
        super().__init__(timeout=timeout)
        self.session = session
        self._on_review = on_review
        self.add_item(GenerationSelect(self))

    def set_generation(self, generation: str) -> None:
        # Replace any existing device select with one for this generation.
        for item in list(self.children):
            if isinstance(item, DeviceSelect):
                self.remove_item(item)
        self.add_item(DeviceSelect(self, generation))

    def summary_line(self) -> str:
        cfg = self.session.config
        preset = cfg.get("preset_id", "—")
        dt = cfg.get("datetime")
        loc = cfg.get("loc_mode", "keep")
        return f"**Device:** {preset}  **Date:** {dt or 'keep'}  **Location:** {loc}"

    @discord.ui.button(label="Date/time", style=discord.ButtonStyle.secondary, row=2)
    async def date_button(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        async def submit(inner: discord.Interaction, value: str, tz: str) -> None:
            self.session.config["datetime"] = parse_user_datetime(value)
            self.session.config["date_mode"] = "set"
            if tz:
                self.session.config["timezone"] = tz
                self.session.config["utc_offset"] = offset_for_timezone(
                    tz, self.session.config["datetime"]
                )
            await inner.response.edit_message(content=self.summary_line(), view=self)

        await interaction.response.send_modal(DateTimeModal(submit))

    @discord.ui.button(label="Location", style=discord.ButtonStyle.secondary, row=2)
    async def location_button(
        self, interaction: discord.Interaction, _b: discord.ui.Button
    ) -> None:
        async def submit(
            inner: discord.Interaction, lat: float, lon: float, alt: float | None
        ) -> None:
            self.session.config["gps"] = GPSData(latitude=lat, longitude=lon, altitude_m=alt)
            self.session.config["loc_mode"] = "set"
            await inner.response.edit_message(content=self.summary_line(), view=self)

        await interaction.response.send_modal(CoordinatesModal(submit))

    @discord.ui.button(label="Remove GPS", style=discord.ButtonStyle.secondary, row=2)
    async def remove_gps_button(
        self, interaction: discord.Interaction, _b: discord.ui.Button
    ) -> None:
        self.session.config["loc_mode"] = "remove"
        await interaction.response.edit_message(content=self.summary_line(), view=self)

    @discord.ui.button(label="Review", style=discord.ButtonStyle.primary, row=3)
    async def review_button(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        await self._on_review(interaction, self.session)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=3)
    async def cancel_button(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Cancelled.", view=None)
        self.stop()


class ConfirmView(discord.ui.View):
    """Final confirm/cancel step shown with the review embed."""

    def __init__(self, session: BotSession, on_confirm, timeout: float = 300) -> None:
        super().__init__(timeout=timeout)
        self.session = session
        self._on_confirm = on_confirm

    @discord.ui.button(label="Confirm & export", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        await self._on_confirm(interaction, self.session)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Cancelled.", view=None)
        self.stop()
