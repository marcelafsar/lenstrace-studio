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
    return InlineKeyboardMarkup(rows)


def datetime_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Keep original", callback_data="dt:keep")],
            [InlineKeyboardButton("Current date/time", callback_data="dt:now")],
            [InlineKeyboardButton("Enter manually", callback_data="dt:manual")],
        ]
    )


def location_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Skip", callback_data="loc:skip")],
            [InlineKeyboardButton("Enter coordinates", callback_data="loc:coords")],
            [InlineKeyboardButton("Remove existing GPS", callback_data="loc:remove")],
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
