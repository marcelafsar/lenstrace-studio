"""Domain exceptions for the delivery subsystem.

Each carries a ``user_message`` suitable for a non-technical user, mirroring the
convention in :mod:`core.exceptions`.
"""

from __future__ import annotations

from core.exceptions import LensTraceError


class DeliveryError(LensTraceError):
    """Base class for delivery errors."""

    default_user_message = "The delivery could not be completed."


class DeliveryProviderUnavailableError(DeliveryError):
    default_user_message = "This delivery method is not available right now."


class DestinationInvalidError(DeliveryError):
    default_user_message = "The chosen destination folder is not valid."


class IntegrityVerificationError(DeliveryError):
    default_user_message = "The copied file did not match the original exactly and was removed."


class UnknownExportError(DeliveryError):
    default_user_message = "That export is no longer available; please export again."


class UnsafeUrlError(DeliveryError):
    default_user_message = "That link is not a safe web address and was blocked."
