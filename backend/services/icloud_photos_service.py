"""iCloud Photos for Windows delivery provider.

Copies the exact exported file into the iCloud Photos upload location so iCloud
can sync it. LensTrace does NOT log in, does not touch Apple credentials, and
does not claim the file reached the iPhone — Apple controls upload and sync.
"""

from __future__ import annotations

import os
from pathlib import Path

from backend.logging_config import get_logger
from backend.services import settings_service
from core.delivery.exceptions import DestinationInvalidError
from core.delivery.models import (
    AvailabilityLevel,
    DeliveryAvailability,
    DeliveryOptions,
    DeliveryResult,
    DeliveryState,
    ExportFileInfo,
    ProviderId,
    UserAction,
)
from core.delivery.provider import ProviderPreparation
from core.delivery.transfer import copy_verified

logger = get_logger(__name__)


def _candidate_folders() -> list[Path]:
    """Known iCloud Photos folder locations on Windows (read-only checks)."""
    userprofile = os.environ.get("USERPROFILE") or str(Path.home())
    home = Path(userprofile)
    return [
        home / "iCloudPhotos",
        home / "Pictures" / "iCloud Photos",
        home / "iCloud Photos",
        home / "Pictures" / "iCloudPhotos",
    ]


def _detect_folder(configured: str | None) -> Path | None:
    """Return the best iCloud Photos target folder, or None if not found."""
    if configured:
        p = Path(configured)
        if p.is_dir():
            return _prefer_uploads(p)
    for candidate in _candidate_folders():
        if candidate.is_dir():
            return _prefer_uploads(candidate)
    return None


def _prefer_uploads(folder: Path) -> Path:
    """iCloud for Windows exposes an 'Uploads' subfolder for outgoing photos."""
    uploads = folder / "Uploads"
    return uploads if uploads.is_dir() else folder


class ICloudPhotosProvider:
    provider_id = ProviderId.ICLOUD_PHOTOS

    def availability(self) -> DeliveryAvailability:
        config = settings_service.get_config().delivery
        if not config.icloud_photos_enabled:
            return DeliveryAvailability(
                provider_id=self.provider_id,
                level=AvailabilityLevel.UNAVAILABLE,
                summary="iCloud Photos integration is disabled.",
            )
        folder = _detect_folder(config.icloud_photos_path)
        if folder is not None:
            return DeliveryAvailability(
                provider_id=self.provider_id,
                level=AvailabilityLevel.READY,
                recommended=True,
                summary="iCloud Photos folder detected.",
                details={"destination": folder.name},
            )
        return DeliveryAvailability(
            provider_id=self.provider_id,
            level=AvailabilityLevel.NEEDS_SETUP,
            summary="iCloud Photos folder not detected. Choose a folder or use the browser.",
        )

    def _resolve_destination(self, options: DeliveryOptions) -> Path | None:
        config = settings_service.get_config().delivery
        if options.destination_dir:
            chosen = Path(options.destination_dir)
            if not chosen.is_dir():
                raise DestinationInvalidError(
                    f"Chosen iCloud destination is not a folder: {chosen}",
                    user_message="The chosen destination folder is not valid.",
                )
            return chosen
        return _detect_folder(config.icloud_photos_path)

    def prepare(
        self, source_path: Path, source_info: ExportFileInfo, options: DeliveryOptions
    ) -> ProviderPreparation:
        destination = self._resolve_destination(options)
        if destination is None:
            return ProviderPreparation(
                provider_id=self.provider_id,
                ready_to_execute=False,
                user_action=UserAction(
                    title="Choose the iCloud Photos folder",
                    instructions=[
                        "Install iCloud for Windows and enable iCloud Photos, or",
                        "Pick your iCloud Photos (or its Uploads) folder manually, or",
                        "Use the browser option to upload at iCloud.com.",
                    ],
                    open_url=None,
                ),
                notes=["iCloud controls upload and synchronisation."],
            )
        return ProviderPreparation(
            provider_id=self.provider_id,
            ready_to_execute=True,
            destination_name=source_info.filename,
            destination_label=destination.name,
            notes=[
                "The exact exported file will be copied here.",
                "Apple controls upload and synchronisation status.",
            ],
        )

    def execute(
        self, source_path: Path, source_info: ExportFileInfo, options: DeliveryOptions
    ) -> DeliveryResult:
        destination = self._resolve_destination(options)
        if destination is None:
            return DeliveryResult(
                job_id="",
                provider_id=self.provider_id,
                state=DeliveryState.AWAITING_USER,
                success=False,
                source_info=source_info,
                errors=["No iCloud Photos destination is configured."],
                message="Choose an iCloud Photos folder or use the browser option.",
            )
        outcome = copy_verified(source_path, destination, options)
        logger.info(
            "iCloud copy verified (checksum=%s, metadata=%s).",
            outcome.checksum_verified,
            outcome.metadata_verified,
        )
        return DeliveryResult(
            job_id="",
            provider_id=self.provider_id,
            state=DeliveryState.WAITING_FOR_SYNC,
            success=True,
            destination_name=outcome.destination_path.name,
            destination_verified=outcome.checksum_verified and outcome.metadata_verified,
            source_info=source_info,
            warnings=outcome.warnings,
            message=(
                "Copied to the iCloud Photos folder. "
                "Apple controls upload and synchronisation status."
            ),
        )
