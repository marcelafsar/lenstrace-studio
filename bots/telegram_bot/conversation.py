"""Conversation state constants for the Telegram edit flow.

The Telegram bot uses callback-driven state stored on the shared BotSession
rather than python-telegram-bot's ConversationHandler states, so the same
session model can be reused by the Discord bot.
"""

from __future__ import annotations

from enum import Enum


class EditState(str, Enum):
    IDLE = "idle"
    AWAIT_ACTION = "await_action"
    CHOOSE_GENERATION = "choose_generation"
    CHOOSE_DEVICE = "choose_device"
    CHOOSE_LENS = "choose_lens"
    CHOOSE_DATETIME = "choose_datetime"
    AWAIT_MANUAL_DATETIME = "await_manual_datetime"
    CHOOSE_LOCATION = "choose_location"
    AWAIT_COORDS = "await_coords"
    REVIEW = "review"


#: Documented manual datetime format shown to users.
MANUAL_DATETIME_FORMAT = "YYYY-MM-DD HH:MM:SS"
#: Documented manual coordinate format shown to users.
MANUAL_COORDS_FORMAT = "latitude, longitude   (e.g. 41.0082, 28.9784)"
