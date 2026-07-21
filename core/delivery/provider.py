"""The delivery-provider strategy interface.

Design note: job lifecycle/storage (job ids, cancellation, status polling) is
owned by the backend ``DeliveryService`` so providers stay small, stateless
strategies that are easy to unit-test. A provider is handed an already-resolved,
already-validated source path (never a raw renderer-supplied path) plus the
captured integrity record.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from core.delivery.models import (
    DeliveryAvailability,
    DeliveryOptions,
    DeliveryResult,
    ExportFileInfo,
    ProviderId,
    UserAction,
)


class ProviderPreparation(BaseModel):
    """What a provider reports after ``prepare`` — a preview + any user action.

    ``prepare`` performs no side effects that transfer the file; it validates
    options, computes the intended destination (if any), and returns the
    instructions the user needs. ``execute`` performs the actual copy/open.
    """

    provider_id: ProviderId
    ready_to_execute: bool
    #: Basename of the intended destination file, if a copy will occur.
    destination_name: str | None = None
    #: A human-readable destination label (folder name, not full path).
    destination_label: str | None = None
    user_action: UserAction | None = None
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


@runtime_checkable
class DeliveryProvider(Protocol):
    """A strategy for moving an exported file toward an iPhone."""

    provider_id: ProviderId

    def availability(self) -> DeliveryAvailability:
        """Report whether this method is ready, needs setup, or unavailable."""
        ...

    def prepare(
        self,
        source_path: Path,
        source_info: ExportFileInfo,
        options: DeliveryOptions,
    ) -> ProviderPreparation:
        """Validate options and describe what execution will do. No transfer."""
        ...

    def execute(
        self,
        source_path: Path,
        source_info: ExportFileInfo,
        options: DeliveryOptions,
    ) -> DeliveryResult:
        """Perform the provider's actual action (verified copy and/or open)."""
        ...
