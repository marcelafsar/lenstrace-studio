"""Domain-specific exceptions for the metadata engine.

Every exception carries a ``user_message`` suitable for showing to a
non-technical user. The exception's ``str()`` may contain technical detail for
logs. Interfaces should present ``user_message`` and log the full exception.
"""

from __future__ import annotations


class LensTraceError(Exception):
    """Base class for all LensTrace domain errors."""

    #: Default nontechnical message; subclasses/instances may override.
    default_user_message = "Something went wrong while processing the image."

    def __init__(self, message: str, *, user_message: str | None = None) -> None:
        super().__init__(message)
        self.user_message = user_message or self.default_user_message


class UnsupportedImageFormatError(LensTraceError):
    default_user_message = "This image format is not supported for the requested operation."


class CorruptImageError(LensTraceError):
    default_user_message = "The image could not be read; it may be corrupt or incomplete."


class MetadataReadError(LensTraceError):
    default_user_message = "The image's metadata could not be read."


class MetadataWriteError(LensTraceError):
    default_user_message = "The new metadata could not be written to the exported copy."


class InvalidPresetError(LensTraceError):
    default_user_message = "A device preset is invalid or could not be loaded."


class InvalidCoordinateError(LensTraceError):
    default_user_message = "The GPS coordinates are out of range or invalid."


class InvalidDateTimeError(LensTraceError):
    default_user_message = "The date or time provided is invalid."


class ExportCollisionError(LensTraceError):
    default_user_message = "A file with the target name already exists at the destination."


class ExternalToolUnavailableError(LensTraceError):
    default_user_message = "A required external tool (e.g. ExifTool) is not available."
