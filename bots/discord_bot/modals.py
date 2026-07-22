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


class CustomExposureModal(discord.ui.Modal, title="Custom exposure (simulated)"):
    """Manual exposure entry. These are simulated values, not measurements."""

    iso_input = discord.ui.TextInput(label="ISO", placeholder="200", required=True, max_length=8)
    shutter_input = discord.ui.TextInput(
        label="Shutter (e.g. 1/500)", placeholder="1/500", required=True, max_length=16
    )
    ev_input = discord.ui.TextInput(
        label="Exposure compensation EV", placeholder="0", required=False, max_length=8
    )

    def __init__(
        self, on_submit: Callable[[discord.Interaction, int, float, float], object]
    ) -> None:
        super().__init__()
        self._on_submit = on_submit

    async def on_submit(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        from core.exceptions import LensTraceError
        from core.exposure.validation import parse_shutter_speed

        try:
            iso = int(self.iso_input.value)
            shutter = parse_shutter_speed(self.shutter_input.value)
            ev = float(self.ev_input.value) if self.ev_input.value else 0.0
        except (ValueError, LensTraceError):
            await interaction.response.send_message(
                "Enter ISO as a number and shutter like 1/500.", ephemeral=True
            )
            return
        await self._on_submit(interaction, iso, shutter, ev)


class CustomResolutionModal(discord.ui.Modal, title="Custom output resolution"):
    width_input = discord.ui.TextInput(label="Width (px)", placeholder="3024", required=True)
    height_input = discord.ui.TextInput(label="Height (px)", placeholder="4032", required=True)

    def __init__(self, on_submit: Callable[[discord.Interaction, int, int], object]) -> None:
        super().__init__()
        self._on_submit = on_submit

    async def on_submit(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        try:
            width = int(self.width_input.value)
            height = int(self.height_input.value)
        except ValueError:
            await interaction.response.send_message(
                "Width and height must be whole numbers.", ephemeral=True
            )
            return
        if not (0 < width <= 30000 and 0 < height <= 30000):
            await interaction.response.send_message(
                "Dimensions must be between 1 and 30000 px.", ephemeral=True
            )
            return
        await self._on_submit(interaction, width, height)


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
