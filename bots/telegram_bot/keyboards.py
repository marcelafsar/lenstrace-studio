"""Inline keyboard builders for the Telegram bot.

Kept separate from handler logic so the conversation flow stays readable.
Callback data is kept compact (well under Telegram's 64-byte limit) and never
carries session data, coordinates, or addresses — only short ids/tokens.
"""

from __future__ import annotations

import calendar
import datetime as _dt

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.location.models import LocationSearchResult
from core.presets.loader import get_default_loader

# Practical bounds for the calendar picker.
_MIN_YEAR = 1990
_MAX_YEAR = _dt.date.today().year + 1
_WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def main_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✏️ Edit metadata", callback_data="action:edit"),
                InlineKeyboardButton("🔍 Inspect", callback_data="action:inspect"),
            ],
            [
                InlineKeyboardButton("🧹 Remove metadata", callback_data="action:remove"),
                InlineKeyboardButton("✖ Cancel", callback_data="action:cancel"),
            ],
        ]
    )


def generation_keyboard() -> InlineKeyboardMarkup:
    groups = get_default_loader().grouped_by_generation()
    rows = [[InlineKeyboardButton(gen, callback_data=f"gen:{gen}")] for gen in groups]
    rows.append(
        [InlineKeyboardButton("Generic Apple iPhone", callback_data="preset:generic-apple-iphone")]
    )
    return InlineKeyboardMarkup(rows)


def device_keyboard(generation: str) -> InlineKeyboardMarkup:
    groups = get_default_loader().grouped_by_generation()
    devices = groups.get(generation, [])
    rows = [[InlineKeyboardButton(d.display_name, callback_data=f"preset:{d.id}")] for d in devices]
    rows.append([InlineKeyboardButton("« Back", callback_data="nav:generations")])
    return InlineKeyboardMarkup(rows)


def lens_keyboard(preset_id: str) -> InlineKeyboardMarkup:
    device = get_default_loader().get(preset_id)
    rows = [
        [InlineKeyboardButton(lens.display_name, callback_data=f"lens:{lens.id}")]
        for lens in device.lenses
    ]
    rows.append([InlineKeyboardButton("Keep original lens", callback_data="lens:keep")])
    return InlineKeyboardMarkup(rows)


def datetime_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Keep original", callback_data="dt:keep")],
            [InlineKeyboardButton("Current date/time", callback_data="dt:now")],
            [InlineKeyboardButton("📅 Choose from calendar", callback_data="dt:calendar")],
            [InlineKeyboardButton("Enter manually", callback_data="dt:manual")],
        ]
    )


# ---- Calendar picker -------------------------------------------------------


def calendar_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    """Month-grid inline calendar. Callback data: cal:d|p|n|today|cancel."""
    year = max(_MIN_YEAR, min(_MAX_YEAR, year))
    rows: list[list[InlineKeyboardButton]] = []
    header = f"{calendar.month_name[month]} {year}"
    prev_y, prev_m = (year, month - 1) if month > 1 else (year - 1, 12)
    next_y, next_m = (year, month + 1) if month < 12 else (year + 1, 1)
    rows.append(
        [
            InlineKeyboardButton("‹", callback_data=f"cal:p:{prev_y}-{prev_m:02d}"),
            InlineKeyboardButton(header, callback_data="cal:noop"),
            InlineKeyboardButton("›", callback_data=f"cal:n:{next_y}-{next_m:02d}"),
        ]
    )
    rows.append([InlineKeyboardButton(d, callback_data="cal:noop") for d in _WEEKDAYS])
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="cal:noop"))
            else:
                row.append(
                    InlineKeyboardButton(
                        str(day), callback_data=f"cal:d:{year}-{month:02d}-{day:02d}"
                    )
                )
        rows.append(row)
    rows.append(
        [
            InlineKeyboardButton("Today", callback_data="cal:today"),
            InlineKeyboardButton("✖ Cancel", callback_data="action:cancel"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def hour_keyboard() -> InlineKeyboardMarkup:
    """24-hour quick selection (callback th:HH), plus keep/custom."""
    rows: list[list[InlineKeyboardButton]] = []
    for start in range(0, 24, 6):
        rows.append(
            [
                InlineKeyboardButton(f"{h:02d}", callback_data=f"th:{h:02d}")
                for h in range(start, start + 6)
            ]
        )
    rows.append(
        [
            InlineKeyboardButton("Keep time", callback_data="th:keep"),
            InlineKeyboardButton("Custom", callback_data="th:custom"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def minute_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(m, callback_data=f"tm:{m}") for m in ("00", "15", "30", "45")],
            [InlineKeyboardButton("Custom minutes", callback_data="tm:custom")],
        ]
    )


# ---- Location / address search ---------------------------------------------


def location_result_keyboard(results: list[LocationSearchResult]) -> InlineKeyboardMarkup:
    """One button per geocoding result; callback carries only the opaque id."""
    rows = [
        [InlineKeyboardButton(r.short_label(60), callback_data=f"locpick:{r.result_id}")]
        for r in results
    ]
    rows.append(
        [
            InlineKeyboardButton("🔍 Search again", callback_data="loc:search"),
            InlineKeyboardButton("✖ Cancel", callback_data="action:cancel"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def location_confirm_keyboard(result_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Use this location", callback_data=f"locuse:{result_id}")],
            [
                InlineKeyboardButton("🔍 Search again", callback_data="loc:search"),
                InlineKeyboardButton("Enter coordinates", callback_data="loc:coords"),
            ],
            [
                InlineKeyboardButton("Remove location", callback_data="loc:remove"),
                InlineKeyboardButton("✖ Cancel", callback_data="action:cancel"),
            ],
        ]
    )


def location_empty_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔍 Search again", callback_data="loc:search")],
            [InlineKeyboardButton("Enter coordinates", callback_data="loc:coords")],
            [InlineKeyboardButton("Skip", callback_data="loc:skip")],
        ]
    )


#: A small, curated set of common IANA zones for quick selection.
_COMMON_TIMEZONES = [
    ("UTC", "UTC"),
    ("London", "Europe/London"),
    ("Paris", "Europe/Paris"),
    ("Istanbul", "Europe/Istanbul"),
    ("New York", "America/New_York"),
    ("Los Angeles", "America/Los_Angeles"),
    ("Tokyo", "Asia/Tokyo"),
    ("Sydney", "Australia/Sydney"),
]


def timezone_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"tz:{zone}")]
        for label, zone in _COMMON_TIMEZONES
    ]
    rows.append([InlineKeyboardButton("No time zone (skip)", callback_data="tz:skip")])
    return InlineKeyboardMarkup(rows)


def location_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔍 Search by address", callback_data="loc:search")],
            [InlineKeyboardButton("📍 Enter coordinates", callback_data="loc:coords")],
            [InlineKeyboardButton("Send my Telegram location", callback_data="loc:tg")],
            [InlineKeyboardButton("Skip (keep original)", callback_data="loc:skip")],
            [InlineKeyboardButton("Remove existing GPS", callback_data="loc:remove")],
        ]
    )


def photo_warning_keyboard() -> InlineKeyboardMarkup:
    """Shown when a compressed photo arrives via Telegram's photo route."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Continue with this photo", callback_data="photo:continue")],
            [InlineKeyboardButton("I'll send it as a file", callback_data="photo:asfile")],
            [InlineKeyboardButton("✖ Cancel", callback_data="action:cancel")],
        ]
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirm & export", callback_data="confirm:yes"),
                InlineKeyboardButton("✖ Cancel", callback_data="action:cancel"),
            ]
        ]
    )
