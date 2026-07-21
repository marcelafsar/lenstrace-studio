"""Delivery orchestration: provider registry + job lifecycle.

Owns job ids, state, cancellation, and status polling so the individual
providers stay small strategies. Resolves ``export_id`` → validated path via the
export registry; providers never see a renderer-supplied path.
"""

from __future__ import annotations

import secrets
from threading import Lock

from backend.logging_config import get_logger
from backend.services.apple_devices_service import AppleDevicesProvider
from backend.services.export_registry import get_export_registry
from backend.services.icloud_photos_service import ICloudPhotosProvider
from backend.services.pairdrop_service import PairDropProvider
from core.delivery.exceptions import DeliveryError, DeliveryProviderUnavailableError
from core.delivery.metadata_verification import build_export_info
from core.delivery.models import (
    AvailabilityLevel,
    DeliveryAvailability,
    DeliveryJob,
    DeliveryJobStatus,
    DeliveryOptions,
    DeliveryResult,
    DeliveryState,
    ExportFileInfo,
    ProviderId,
)
from core.delivery.provider import DeliveryProvider, ProviderPreparation

logger = get_logger(__name__)


def _build_providers() -> dict[ProviderId, DeliveryProvider]:
    return {
        ProviderId.ICLOUD_PHOTOS: ICloudPhotosProvider(),
        ProviderId.PAIRDROP: PairDropProvider(),
        ProviderId.APPLE_DEVICES: AppleDevicesProvider(),
    }


class DeliveryService:
    def __init__(self) -> None:
        self._providers = _build_providers()
        self._jobs: dict[str, DeliveryJob] = {}
        self._status: dict[str, DeliveryJobStatus] = {}
        self._cancelled: set[str] = set()
        self._lock = Lock()

    # ---- Availability ----------------------------------------------------

    def list_availability(self) -> list[DeliveryAvailability]:
        results: list[DeliveryAvailability] = []
        for provider in self._providers.values():
            try:
                results.append(provider.availability())
            except Exception as exc:  # noqa: BLE001 - one provider must not break all
                logger.warning("Availability check failed: %s", type(exc).__name__)
                results.append(
                    DeliveryAvailability(
                        provider_id=provider.provider_id,
                        level=AvailabilityLevel.UNAVAILABLE,
                        summary="Availability could not be determined.",
                    )
                )
        return results

    def _provider(self, provider_id: ProviderId) -> DeliveryProvider:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise DeliveryProviderUnavailableError(f"No such provider: {provider_id}")
        return provider

    # ---- Prepare ---------------------------------------------------------

    def prepare(
        self, provider_id: ProviderId, export_id: str, options: DeliveryOptions
    ) -> tuple[str, ProviderPreparation, ExportFileInfo]:
        registry = get_export_registry()
        source_path = registry.resolve(export_id)  # raises UnknownExportError
        source_info = registry.get_info(export_id) or build_export_info(source_path)
        registry.set_info(export_id, source_info)

        provider = self._provider(provider_id)
        preparation = provider.prepare(source_path, source_info, options)

        job_id = secrets.token_urlsafe(12)
        job = DeliveryJob(
            job_id=job_id,
            provider_id=provider_id,
            export_id=export_id,
            state=(
                DeliveryState.READY if preparation.ready_to_execute else DeliveryState.AWAITING_USER
            ),
            options=options,
            source_info=source_info,
        )
        status = DeliveryJobStatus(
            job_id=job_id,
            provider_id=provider_id,
            state=job.state,
            message="Ready to send." if preparation.ready_to_execute else "Action needed.",
            source_info=source_info,
            user_action=preparation.user_action,
            warnings=list(preparation.warnings),
        )
        with self._lock:
            self._jobs[job_id] = job
            self._status[job_id] = status
        return job_id, preparation, source_info

    # ---- Execute ---------------------------------------------------------

    def execute(self, job_id: str) -> DeliveryResult:
        with self._lock:
            job = self._jobs.get(job_id)
            cancelled = job_id in self._cancelled
        if job is None:
            raise DeliveryError(
                f"Unknown job: {job_id}", user_message="That delivery is no longer available."
            )
        if cancelled:
            self._finalise_cancelled(job_id, job.provider_id)
            return DeliveryResult(
                job_id=job_id,
                provider_id=job.provider_id,
                state=DeliveryState.CANCELLED,
                success=False,
                message="Delivery cancelled.",
            )

        registry = get_export_registry()
        source_path = registry.resolve(job.export_id)
        source_info = job.source_info or build_export_info(source_path)
        provider = self._provider(job.provider_id)

        self._set_state(job_id, DeliveryState.COPYING, "Working…")
        try:
            result = provider.execute(source_path, source_info, job.options)
        except DeliveryError as exc:
            self._set_state(job_id, DeliveryState.FAILED, exc.user_message)
            status = self._status[job_id]
            status.errors = [exc.user_message]
            status.state = DeliveryState.FAILED
            raise
        result.job_id = job_id

        # Only WAITING_FOR_SYNC/COMPLETED count as a verified copy; AWAITING_USER
        # (e.g. PairDrop) is never reported as completed.
        completed = result.state in (DeliveryState.COMPLETED, DeliveryState.WAITING_FOR_SYNC)
        with self._lock:
            job.state = result.state
            self._status[job_id] = DeliveryJobStatus(
                job_id=job_id,
                provider_id=job.provider_id,
                state=result.state,
                progress=1.0 if completed else 0.5,
                message=result.message,
                destination_name=result.destination_name,
                destination_verified=result.destination_verified,
                source_info=source_info,
                warnings=result.warnings,
                errors=result.errors,
                user_action=result.user_action,
                completed=result.state == DeliveryState.COMPLETED
                or result.state == DeliveryState.WAITING_FOR_SYNC,
                cancelled=False,
            )
        return result

    # ---- Status / cancel -------------------------------------------------

    def status(self, job_id: str) -> DeliveryJobStatus:
        with self._lock:
            status = self._status.get(job_id)
        if status is None:
            raise DeliveryError(
                f"Unknown job: {job_id}", user_message="That delivery is no longer available."
            )
        return status

    def cancel(self, job_id: str) -> DeliveryJobStatus:
        with self._lock:
            if job_id not in self._jobs:
                raise DeliveryError(
                    f"Unknown job: {job_id}",
                    user_message="That delivery is no longer available.",
                )
            self._cancelled.add(job_id)
        return self._finalise_cancelled(job_id, self._jobs[job_id].provider_id)

    # ---- Internals -------------------------------------------------------

    def _set_state(self, job_id: str, state: DeliveryState, message: str) -> None:
        with self._lock:
            status = self._status.get(job_id)
            if status is not None:
                status.state = state
                status.message = message
            job = self._jobs.get(job_id)
            if job is not None:
                job.state = state

    def _finalise_cancelled(self, job_id: str, provider_id: ProviderId) -> DeliveryJobStatus:
        status = DeliveryJobStatus(
            job_id=job_id,
            provider_id=provider_id,
            state=DeliveryState.CANCELLED,
            message="Delivery cancelled.",
            cancelled=True,
        )
        with self._lock:
            self._status[job_id] = status
            if job_id in self._jobs:
                self._jobs[job_id].state = DeliveryState.CANCELLED
        return status


_service: DeliveryService | None = None


def get_delivery_service() -> DeliveryService:
    global _service
    if _service is None:
        _service = DeliveryService()
    return _service
