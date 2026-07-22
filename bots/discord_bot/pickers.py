"""Discord component pickers: address-search results and a date/time picker.

All views are owner-only (via :class:`OwnedView`) and ephemeral. Option counts
stay within Discord limits (<=25 per select); the day picker is split across two
selects because a month can have up to 31 days.
"""

from __future__ import annotations

import calendar
import datetime as _dt
import logging
from collections.abc import Awaitable, Callable

import discord

from bots.discord_bot.base_views import OwnedView
from bots.shared.bot_sessions import BotSession
from core.datetime_utils import offset_for_timezone
from core.location.models import LocationSearchResult
from core.metadata_models import GPSData

logger = logging.getLogger(__name__)

_MIN_YEAR_BACK = 12
_COMMON_TZ = [
    ("Keep / none", "keep"),
    ("UTC", "UTC"),
    ("London", "Europe/London"),
    ("Paris", "Europe/Paris"),
    ("Istanbul", "Europe/Istanbul"),
    ("New York", "America/New_York"),
    ("Los Angeles", "America/Los_Angeles"),
    ("Tokyo", "Asia/Tokyo"),
]


# ---- Address search results ----------------------------------------------


class _ResultSelect(discord.ui.Select):
    def __init__(self, results: list[LocationSearchResult]) -> None:
        options = [
            discord.SelectOption(label=r.short_label(90)[:100], value=r.result_id)
            for r in results[:25]
        ]
        super().__init__(placeholder="Choose the correct location…", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: LocationResultsView = self.view  # type: ignore[assignment]
        await view.on_pick(interaction, self.values[0])


class LocationResultsView(OwnedView):
    """Ephemeral select of geocoding results (option values are opaque ids)."""

    def __init__(
        self,
        session: BotSession,
        results: list[LocationSearchResult],
        on_pick: Callable[[discord.Interaction, str], Awaitable[None]],
        on_search_again: Callable[[discord.Interaction], Awaitable[None]],
    ) -> None:
        super().__init__(session, timeout=300)
        self._on_pick = on_pick
        self._on_search_again = on_search_again
        self.add_item(_ResultSelect(results))

    async def on_pick(self, interaction: discord.Interaction, result_id: str) -> None:
        await self._on_pick(interaction, result_id)

    @discord.ui.button(label="Search again", style=discord.ButtonStyle.secondary, row=1)
    async def search_again(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        await self._on_search_again(interaction)


class LocationConfirmView(OwnedView):
    """Confirm a chosen location (details + map link were shown alongside)."""

    def __init__(
        self,
        session: BotSession,
        result: LocationSearchResult,
        on_use: Callable[[discord.Interaction, LocationSearchResult], Awaitable[None]],
        on_search_again: Callable[[discord.Interaction], Awaitable[None]],
    ) -> None:
        super().__init__(session, timeout=300)
        self._result = result
        self._on_use = on_use
        self._on_search_again = on_search_again

    @discord.ui.button(label="Use this location", style=discord.ButtonStyle.success)
    async def use(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        await self._on_use(interaction, self._result)

    @discord.ui.button(label="Search again", style=discord.ButtonStyle.secondary)
    async def again(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        await self._on_search_again(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Location unchanged.", view=None)
        self.stop()


def apply_location(session: BotSession, result: LocationSearchResult) -> None:
    session.config["gps"] = GPSData(
        latitude=result.latitude,
        longitude=result.longitude,
        address_label=result.display_name,
    )
    session.config["loc_mode"] = "set"


# ---- Date / time picker ---------------------------------------------------


class _YearSelect(discord.ui.Select):
    def __init__(self, selected: int) -> None:
        this_year = _dt.date.today().year
        years = list(range(this_year - _MIN_YEAR_BACK, this_year + 2))
        options = [
            discord.SelectOption(label=str(y), value=str(y), default=(y == selected)) for y in years
        ]
        super().__init__(placeholder="Year", options=options, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: DatePickerView = self.view  # type: ignore[assignment]
        view.year = int(self.values[0])
        await view.refresh(interaction)


class _MonthSelect(discord.ui.Select):
    def __init__(self, selected: int) -> None:
        options = [
            discord.SelectOption(
                label=calendar.month_name[m], value=str(m), default=(m == selected)
            )
            for m in range(1, 13)
        ]
        super().__init__(placeholder="Month", options=options, row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: DatePickerView = self.view  # type: ignore[assignment]
        view.month = int(self.values[0])
        view.day = min(view.day, calendar.monthrange(view.year, view.month)[1])
        await view.refresh(interaction)


class _DaySelect(discord.ui.Select):
    def __init__(self, low: int, high: int, selected: int, row: int) -> None:
        options = [
            discord.SelectOption(label=str(d), value=str(d), default=(d == selected))
            for d in range(low, high + 1)
        ]
        super().__init__(placeholder=f"Day {low}–{high}", options=options, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: DatePickerView = self.view  # type: ignore[assignment]
        view.day = int(self.values[0])
        await view.refresh(interaction)


class DatePickerView(OwnedView):
    """Year/month/day picker (day split across two selects for the 25-cap)."""

    def __init__(
        self,
        session: BotSession,
        on_date: Callable[[discord.Interaction, _dt.date], Awaitable[None]],
    ) -> None:
        super().__init__(session, timeout=300)
        today = _dt.date.today()
        self.year = today.year
        self.month = today.month
        self.day = today.day
        self._on_date = on_date
        self._build()

    def _build(self) -> None:
        self.clear_items()
        self.add_item(_YearSelect(self.year))
        self.add_item(_MonthSelect(self.month))
        last = calendar.monthrange(self.year, self.month)[1]
        self.add_item(_DaySelect(1, min(16, last), self.day, row=2))
        if last > 16:
            self.add_item(_DaySelect(17, last, self.day, row=3))
        self.add_item(self._next_button())

    def _next_button(self) -> discord.ui.Button:
        button = discord.ui.Button(
            label="Next: choose time", style=discord.ButtonStyle.primary, row=4
        )

        async def cb(interaction: discord.Interaction) -> None:
            await self._on_date(interaction, _dt.date(self.year, self.month, self.day))

        button.callback = cb  # type: ignore[assignment]
        return button

    async def refresh(self, interaction: discord.Interaction) -> None:
        self._build()
        await interaction.response.edit_message(
            content=f"Selected date: {self.year}-{self.month:02d}-{self.day:02d}", view=self
        )


class _HourSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [discord.SelectOption(label=f"{h:02d}", value=str(h)) for h in range(24)]
        super().__init__(placeholder="Hour", options=options, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: TimeView = self.view  # type: ignore[assignment]
        view.hour = int(self.values[0])
        await interaction.response.defer()


class _MinuteSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [discord.SelectOption(label=m, value=m) for m in ("00", "15", "30", "45")]
        super().__init__(placeholder="Minute", options=options, row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: TimeView = self.view  # type: ignore[assignment]
        view.minute = int(self.values[0])
        await interaction.response.defer()


class _TzSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [discord.SelectOption(label=lbl, value=val) for lbl, val in _COMMON_TZ]
        super().__init__(placeholder="Time zone", options=options, row=2)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: TimeView = self.view  # type: ignore[assignment]
        view.timezone = self.values[0]
        await interaction.response.defer()


class TimeView(OwnedView):
    """Hour/minute/timezone picker; confirms and writes the datetime to session."""

    def __init__(
        self,
        session: BotSession,
        picked_date: _dt.date,
        on_finish: Callable[[discord.Interaction], Awaitable[None]],
    ) -> None:
        super().__init__(session, timeout=300)
        self._date = picked_date
        self._on_finish = on_finish
        self.hour = 0
        self.minute = 0
        self.timezone = "keep"
        self.add_item(_HourSelect())
        self.add_item(_MinuteSelect())
        self.add_item(_TzSelect())

    @discord.ui.button(label="Confirm date/time", style=discord.ButtonStyle.success, row=3)
    async def confirm(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        value = _dt.datetime.combine(self._date, _dt.time(self.hour, self.minute, 0))
        self.session.config["datetime"] = value
        self.session.config["date_mode"] = "set"
        if self.timezone != "keep":
            self.session.config["timezone"] = self.timezone
            self.session.config["utc_offset"] = offset_for_timezone(self.timezone, value)
        await self._on_finish(interaction)
