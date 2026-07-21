"""PairDrop delivery provider (external integration).

PairDrop (https://github.com/schlagmichdoch/PairDrop) is an independent,
GPL-3.0 browser/PWA WebRTC file-transfer project. LensTrace integrates with it
as an EXTERNAL service — it does not vendor, bundle, or modify PairDrop source.
See docs/pairdrop-integration.md for the licensing rationale and attribution.

The browser fallback is the default and needs no installation. LensTrace only
validates the PairDrop URL and shows instructions; the user performs the
transfer and iOS performs the final save. Opening a browser is never treated as
completed delivery.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from backend.logging_config import get_logger
from backend.services import settings_service
from core.delivery.exceptions import UnsafeUrlError
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
from core.delivery.validation import hostname_of, validate_external_url

logger = get_logger(__name__)

_DEFAULT_URL = "https://pairdrop.net/"

_PRIVACY_NOTE = (
    "PairDrop normally uses browser-based peer-to-peer transfer; a relay may be "
    "involved depending on your network. LensTrace does not control PairDrop's "
    "servers, and iOS performs the final save into Photos."
)
_PROVENANCE_NOTE = (
    "PairDrop transfers the exported file. LensTrace cannot control Apple Photos "
    "source or provenance labels."
)


def resolve_url(options: DeliveryOptions) -> str:
    """Return the validated PairDrop URL from options or configuration."""
    raw = options.extra.get("pairdrop_url") if options.extra else None
    if not raw:
        raw = settings_service.get_config().delivery.pairdrop_url or _DEFAULT_URL
    return validate_external_url(raw)


def is_default_instance(url: str) -> bool:
    return hostname_of(url) == hostname_of(_DEFAULT_URL)


def detect_cli() -> str | None:
    """Return a PairDrop CLI path if configured or on PATH, else None."""
    config = settings_service.get_config().delivery
    if config.pairdrop_cli_path:
        p = Path(config.pairdrop_cli_path)
        if p.is_file():
            return str(p)
    found = shutil.which("pairdrop")
    return found


def build_cli_command(cli_path: str, file_path: Path) -> list[str]:
    """Build a safe argv list for the PairDrop CLI (never a shell string)."""
    # Arguments are an explicit list so spaces/Unicode are handled by the OS,
    # not a shell. The exact CLI flags depend on the installed version; this is
    # intentionally a minimal, quoted-by-construction invocation.
    return [str(cli_path), str(file_path)]


class PairDropProvider:
    provider_id = ProviderId.PAIRDROP

    def availability(self) -> DeliveryAvailability:
        config = settings_service.get_config().delivery
        if not config.pairdrop_enabled:
            return DeliveryAvailability(
                provider_id=self.provider_id,
                level=AvailabilityLevel.UNAVAILABLE,
                summary="PairDrop integration is disabled.",
            )
        try:
            url = validate_external_url(config.pairdrop_url or _DEFAULT_URL)
            host = hostname_of(url)
        except UnsafeUrlError:
            host = hostname_of(_DEFAULT_URL)
        cli = detect_cli()
        details = {"host": host}
        if cli:
            details["cli"] = "detected"
        return DeliveryAvailability(
            provider_id=self.provider_id,
            level=AvailabilityLevel.READY,
            summary="Works through your browser — no install needed.",
            details=details,
        )

    def prepare(
        self, source_path: Path, source_info: ExportFileInfo, options: DeliveryOptions
    ) -> ProviderPreparation:
        url = resolve_url(options)
        instructions = [
            "Open the same PairDrop instance on your iPhone (scan the QR code).",
            "On this PC, choose the LensTrace-exported file in PairDrop.",
            "Select your iPhone as the destination device.",
            "Accept the transfer on the iPhone, then use iOS share/save controls.",
        ]
        notes = [_PRIVACY_NOTE, _PROVENANCE_NOTE]
        if not is_default_instance(url):
            notes.append(f"Using a custom PairDrop instance: {hostname_of(url)}")
        return ProviderPreparation(
            provider_id=self.provider_id,
            ready_to_execute=True,
            destination_label=hostname_of(url),
            user_action=UserAction(
                title="Send with PairDrop",
                instructions=instructions,
                open_url=url,  # QR payload is exactly this URL and nothing else.
            ),
            notes=notes,
        )

    def execute(
        self, source_path: Path, source_info: ExportFileInfo, options: DeliveryOptions
    ) -> DeliveryResult:
        # PairDrop is user-driven: LensTrace provides the validated URL/QR and
        # instructions. Opening the browser is NOT completion.
        url = resolve_url(options)
        return DeliveryResult(
            job_id="",
            provider_id=self.provider_id,
            state=DeliveryState.AWAITING_USER,
            success=True,
            source_info=source_info,
            user_action=UserAction(
                title="Complete the transfer in PairDrop",
                instructions=[
                    "Open PairDrop on both devices and select the exported file.",
                    "iOS performs the final save into Photos.",
                ],
                open_url=url,
            ),
            message="Opened PairDrop. Finish the transfer on your devices; iOS saves the file.",
        )
