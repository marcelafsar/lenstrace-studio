"""Inline keyboard builders for the Telegram bot.

Kept separate from handler logic so the conversation flow stays readable.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.presets.loader import get_default_loader


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
            [InlineKeyboardButton("Enter manually", callback_data="dt:manual")],
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
            [InlineKeyboardButton("Skip (keep original)", callback_data="loc:skip")],
            [InlineKeyboardButton("Enter coordinates", callback_data="loc:coords")],
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
