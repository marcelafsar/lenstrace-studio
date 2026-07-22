"""Conversation state constants for the Telegram edit flow.

The Telegram bot uses callback-driven state stored on the shared BotSession
rather than python-telegram-bot's ConversationHandler states, so the same
session model can be reused by the Discord bot. State ownership is therefore
explicit and single-sourced: ``BotSession.state`` (a value from
:class:`EditState`) is the one place the current step lives.
"""

from __future__ import annotations

from enum import Enum


class EditState(str, Enum):
    # No pending upload; waiting for the user to send an image document.
    WAITING_FOR_UPLOAD = "waiting_for_upload"
    # A document was received and inspected; showing the action buttons.
    AWAIT_ACTION = "await_action"
    CHOOSING_DEVICE = "choosing_device"
    CHOOSING_LENS = "choosing_lens"
    CHOOSING_EXPOSURE = "choosing_exposure"
    ENTERING_CUSTOM_EXPOSURE = "entering_custom_exposure"
    CHOOSING_RESOLUTION = "choosing_resolution"
    CHOOSING_RESOLUTION_FIT = "choosing_resolution_fit"
    ENTERING_CUSTOM_RESOLUTION = "entering_custom_resolution"
    CHOOSING_DATE_MODE = "choosing_date_mode"
    ENTERING_DATETIME = "entering_datetime"
    CHOOSING_CALENDAR = "choosing_calendar"
    CHOOSING_HOUR = "choosing_hour"
    CHOOSING_MINUTE = "choosing_minute"
    ENTERING_CUSTOM_TIME = "entering_custom_time"
    CHOOSING_TIMEZONE = "choosing_timezone"
    CHOOSING_LOCATION = "choosing_location"
    ENTERING_ADDRESS = "entering_address"
    ENTERING_COORDINATES = "entering_coordinates"
    REVIEWING = "reviewing"
    PROCESSING = "processing"


#: Documented manual datetime format shown to users.
MANUAL_DATETIME_FORMAT = "YYYY-MM-DD HH:MM:SS"
#: Documented manual coordinate format shown to users.
MANUAL_COORDS_FORMAT = "latitude, longitude   (e.g. 41.0082, 28.9784)"
#: Documented manual custom-exposure format shown to users.
MANUAL_EXPOSURE_FORMAT = "ISO, shutter, EV   (e.g. 200, 1/500, 0)"
