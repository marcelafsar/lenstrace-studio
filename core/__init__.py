"""LensTrace Studio shared metadata engine.

This package contains all metadata-processing logic used by every interface
(desktop backend, Telegram bot, Discord bot). No interface should duplicate
metadata reading or writing logic; import from here instead.
"""

from core.exceptions import (
    CorruptImageError,
    ExportCollisionError,
    ExternalToolUnavailableError,
    InvalidCoordinateError,
    InvalidDateTimeError,
    InvalidPresetError,
    LensTraceError,
    MetadataReadError,
    MetadataWriteError,
    UnsupportedImageFormatError,
)
from core.metadata_engine import MetadataEngine

__all__ = [
    "MetadataEngine",
    "LensTraceError",
    "UnsupportedImageFormatError",
    "CorruptImageError",
    "MetadataReadError",
    "MetadataWriteError",
    "InvalidPresetError",
    "InvalidCoordinateError",
    "InvalidDateTimeError",
    "ExportCollisionError",
    "ExternalToolUnavailableError",
]

__version__ = "0.1.0"
