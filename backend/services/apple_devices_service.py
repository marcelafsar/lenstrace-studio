"""Apple Devices assisted-sync provider.

This is an ASSISTED Windows workflow, not direct Camera Roll injection. It
copies the exact exported file into a local "LensTrace Sync" folder, verifies
it, and guides the user to sync it with the Apple Devices app. Apple Devices
controls synchronisation; items synced this way behave as computer-synced
photos. LensTrace never automates the app, sends keystrokes, edits Apple
databases, or claims the result is a native Camera capture.
"""

from __future__ import annotations

import os
from pathlib import Path

from backend.logging_config import get_logger
from backend.services import settings_service
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

_SYNC_INSTRUCTIONS = [
    "Connect the iPhone by USB, or use an existing Wi-Fi sync relationship.",
    "Unlock the iPhone and trust this computer if prompted.",
    "Open the Apple Devices app and select your device.",
    "Open Photos, then choose the 'LensTrace Sync' folder.",
    "Apply/sync. Apple Devices controls synchronisation.",
]


def default_sync_folder() -> Path:
    """Return the configured or default LensTrace Sync folder path."""
    configured = settings_service.get_config().delivery.lenstrace_sync_path
    if configured:
        return Path(configured)
    userprofile = os.environ.get("USERPROFILE") or str(Path.home())
    return Path(userprofile) / "Pictures" / "LensTrace Sync"


def ensure_sync_folder(options: DeliveryOptions) -> Path:
    """Return the sync folder, creating it if necessary."""
    folder = Path(options.destination_dir) if options.destination_dir else default_sync_folder()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def detect_apple_devices() -> bool:
    """Best-effort, read-only check for the Apple Devices / iTunes app.

    Detection on Windows is unreliable (Apple Devices is a Store app), so this
    only returns True on a clear signal and otherwise defers to the user.
    """
    program_files = [
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
    ]
    candidates = ["Apple\\Apple Devices\\AppleDevices.exe", "iTunes\\iTunes.exe"]
    for base in program_files:
        if not base:
            continue
        for rel in candidates:
            if (Path(base) / rel).is_file():
                return True
    return False


class AppleDevicesProvider:
    provider_id = ProviderId.APPLE_DEVICES

    def availability(self) -> DeliveryAvailability:
        config = settings_service.get_config().delivery
        if not config.apple_devices_enabled:
            return DeliveryAvailability(
                provider_id=self.provider_id,
                level=AvailabilityLevel.UNAVAILABLE,
                summary="Apple Devices integration is disabled.",
            )
        detected = detect_apple_devices()
        return DeliveryAvailability(
            provider_id=self.provider_id,
            level=AvailabilityLevel.READY,
            summary="USB/Wi-Fi assisted sync via the Apple Devices app.",
            details={
                "apple_devices": "detected" if detected else "unknown",
                "sync_folder": default_sync_folder().name,
            },
        )

    def prepare(
        self, source_path: Path, source_info: ExportFileInfo, options: DeliveryOptions
    ) -> ProviderPreparation:
        folder = default_sync_folder()
        return ProviderPreparation(
            provider_id=self.provider_id,
            ready_to_execute=True,
            destination_name=source_info.filename,
            destination_label=folder.name,
            user_action=UserAction(
                title="Sync with Apple Devices",
                instructions=_SYNC_INSTRUCTIONS,
                open_app="apple_devices",
                open_folder=True,
            ),
            notes=[
                "The file is copied to your local LensTrace Sync folder and verified.",
                "Apple Devices controls the actual synchronisation.",
                "Items synced this way may behave as computer-synced photos.",
                "Apple Devices photo-sync options may be hidden when iCloud Photos is on.",
            ],
        )

    def execute(
        self, source_path: Path, source_info: ExportFileInfo, options: DeliveryOptions
    ) -> DeliveryResult:
        folder = ensure_sync_folder(options)
        outcome = copy_verified(source_path, folder, options)
        logger.info(
            "Apple Devices sync copy verified (checksum=%s, metadata=%s).",
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
            user_action=UserAction(
                title="Finish in Apple Devices",
                instructions=_SYNC_INSTRUCTIONS,
                open_app="apple_devices",
                open_folder=True,
            ),
            message=(
                "Copied to your LensTrace Sync folder and verified. "
                "Open Apple Devices to complete the sync — Apple controls the import."
            ),
        )
