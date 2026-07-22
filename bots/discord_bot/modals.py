"""Discord modals for strict manual date/time and coordinate entry."""

from __future__ import annotations

from collections.abc import Callable

import discord

from core.datetime_utils import parse_user_datetime
from core.exceptions import LensTraceError


class DateTimeModal(discord.ui.Modal, title="Set date & time"):
    """A strict manual datetime entry modal (Discord has no calendar widget)."""

    datetime_input = discord.ui.TextInput(
        label="Date & time (YYYY-MM-DD HH:MM:SS)",
        placeholder="2026-07-21 16:45:00",
        required=True,
        max_length=25,
    )
    timezone_input = discord.ui.TextInput(
        label="IANA time zone (optional)",
        placeholder="Europe/Istanbul",
        required=False,
        max_length=64,
    )

    def __init__(self, on_submit: Callable[[discord.Interaction, str, str], object]) -> None:
        super().__init__()
        self._on_submit = on_submit

    async def on_submit(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        try:
            parse_user_datetime(self.datetime_input.value)
        except LensTraceError as exc:
            await interaction.response.send_message(exc.user_message, ephemeral=True)
            return
        await self._on_submit(
            interaction, self.datetime_input.value, self.timezone_input.value or ""
        )


class AddressModal(discord.ui.Modal, title="Search for a location"):
    """Free-text address/place search input."""

    query = discord.ui.TextInput(
        label="Address, landmark, city, or place",
        placeholder="e.g. Sultanahmet, Istanbul",
        required=True,
        max_length=200,
    )

    def __init__(self, on_submit: Callable[[discord.Interaction, str], object]) -> None:
        super().__init__()
        self._on_submit = on_submit

    async def on_submit(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        await self._on_submit(interaction, self.query.value)


class CoordinatesModal(discord.ui.Modal, title="Set GPS coordinates"):
    latitude = discord.ui.TextInput(label="Latitude", placeholder="41.0082", required=True)
    longitude = discord.ui.TextInput(label="Longitude", placeholder="28.9784", required=True)
    altitude = discord.ui.TextInput(label="Altitude (m, optional)", required=False)

    def __init__(
        self, on_submit: Callable[[discord.Interaction, float, float, float | None], object]
    ) -> None:
        super().__init__()
        self._on_submit = on_submit

    async def on_submit(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        try:
            lat = float(self.latitude.value)
            lon = float(self.longitude.value)
            alt = float(self.altitude.value) if self.altitude.value else None
        except ValueError:
            await interaction.response.send_message("Coordinates must be numbers.", ephemeral=True)
            return
        await self._on_submit(interaction, lat, lon, alt)
