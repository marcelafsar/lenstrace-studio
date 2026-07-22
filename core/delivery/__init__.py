"""Unified, provider-based delivery of LensTrace exports toward an iPhone.

This package is interface-agnostic (no FastAPI, Electron, or bot types). It
provides a common :class:`DeliveryProvider` protocol plus shared helpers for
checksums, metadata verification, filename-collision resolution, and URL
validation, so the three concrete providers (iCloud Photos, PairDrop, Apple
Devices) share one architecture rather than three unrelated implementations.

Important honesty constraint enforced throughout: copying or opening an
external app is NEVER reported as "delivered to the iPhone". Apple and external
transfer services control final import behaviour and any source/provenance
labels. Metadata is editable and does not prove capture facts.
"""

from core.delivery.exceptions import (
    DeliveryError,
    DeliveryProviderUnavailableError,
    DestinationInvalidError,
    IntegrityVerificationError,
    UnknownExportError,
    UnsafeUrlError,
)
from core.delivery.models import (
    DeliveryAvailability,
    DeliveryJob,
    DeliveryJobStatus,
    DeliveryOptions,
    DeliveryResult,
    DeliveryState,
    ExportFileInfo,
    ProviderId,
)

__all__ = [
    "ProviderId",
    "DeliveryState",
    "DeliveryAvailability",
    "DeliveryOptions",
    "DeliveryJob",
    "DeliveryJobStatus",
    "DeliveryResult",
    "ExportFileInfo",
    "DeliveryError",
    "DeliveryProviderUnavailableError",
    "DestinationInvalidError",
    "IntegrityVerificationError",
    "UnknownExportError",
    "UnsafeUrlError",
]
