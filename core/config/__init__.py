"""Shared configuration models and validation for LensTrace.

Non-secret settings (feature flags, URLs, folder paths) are typed here and
loaded by the backend settings service. Secret values (bot tokens) are never
stored in these models — they are handled separately by the secrets service and
never returned through the renderer API.
"""

from core.config.models import BotKind, ConfigSource, DeliveryConfig, LensTraceConfig
from core.config.validation import parse_bool, parse_optional_int

__all__ = [
    "LensTraceConfig",
    "DeliveryConfig",
    "BotKind",
    "ConfigSource",
    "parse_bool",
    "parse_optional_int",
]
