"""Delivery endpoints: provider availability, prepare, execute, status, cancel.

Delivery routes accept an opaque ``export_id`` (never a raw file path). Blocking
copy/verify work runs in a thread so the event loop is not blocked.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from backend.services import apple_devices_service
from backend.services.delivery_service import get_delivery_service
from core.delivery.exceptions import DeliveryError, UnknownExportError, UnsafeUrlError
from core.delivery.models import (
    DeliveryAvailability,
    DeliveryJobStatus,
    DeliveryOptions,
    ExportFileInfo,
    ProviderId,
)
from core.delivery.provider import ProviderPreparation
from core.delivery.validation import hostname_of, validate_external_url

router = APIRouter(prefix="/delivery", tags=["delivery"])


class ProvidersResponse(BaseModel):
    providers: list[DeliveryAvailability]
    #: Non-secret display info for the UI (folder names, default URL).
    sync_folder_name: str
    pairdrop_default_url: str


class PrepareRequest(BaseModel):
    export_id: str
    options: DeliveryOptions = DeliveryOptions()


class PrepareResponse(BaseModel):
    job_id: str
    preparation: ProviderPreparation
    source_info: ExportFileInfo


class ValidateUrlRequest(BaseModel):
    url: str


class ValidateUrlResponse(BaseModel):
    valid: bool
    normalized: str | None = None
    hostname: str | None = None
    is_default: bool = False
    error: str | None = None


def _provider_id(name: str) -> ProviderId:
    try:
        return ProviderId(name)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown delivery method.") from exc


@router.get("/providers", response_model=ProvidersResponse)
def list_providers() -> ProvidersResponse:
    from backend.services import settings_service

    service = get_delivery_service()
    return ProvidersResponse(
        providers=service.list_availability(),
        sync_folder_name=apple_devices_service.default_sync_folder().name,
        pairdrop_default_url=settings_service.get_config().delivery.pairdrop_url,
    )


@router.post("/validate-url", response_model=ValidateUrlResponse)
def validate_url(body: ValidateUrlRequest) -> ValidateUrlResponse:
    try:
        normalized = validate_external_url(body.url)
    except UnsafeUrlError as exc:
        return ValidateUrlResponse(valid=False, error=exc.user_message)
    return ValidateUrlResponse(
        valid=True,
        normalized=normalized,
        hostname=hostname_of(normalized),
        is_default=hostname_of(normalized) == hostname_of("https://pairdrop.net/"),
    )


@router.post("/{provider}/prepare", response_model=PrepareResponse)
def prepare(provider: str, body: PrepareRequest) -> PrepareResponse:
    provider_id = _provider_id(provider)
    service = get_delivery_service()
    try:
        job_id, preparation, source_info = service.prepare(
            provider_id, body.export_id, body.options
        )
    except UnknownExportError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=exc.user_message) from exc
    except DeliveryError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.user_message) from exc
    return PrepareResponse(job_id=job_id, preparation=preparation, source_info=source_info)


@router.post("/jobs/{job_id}/execute", response_model=DeliveryJobStatus)
async def execute(job_id: str) -> DeliveryJobStatus:
    service = get_delivery_service()
    try:
        # Copy + checksum verification can block; run it off the event loop.
        await run_in_threadpool(service.execute, job_id)
    except DeliveryError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.user_message) from exc
    return service.status(job_id)


@router.get("/jobs/{job_id}", response_model=DeliveryJobStatus)
def job_status(job_id: str) -> DeliveryJobStatus:
    try:
        return get_delivery_service().status(job_id)
    except DeliveryError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=exc.user_message) from exc


@router.post("/jobs/{job_id}/cancel", response_model=DeliveryJobStatus)
def cancel_job(job_id: str) -> DeliveryJobStatus:
    try:
        return get_delivery_service().cancel(job_id)
    except DeliveryError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=exc.user_message) from exc
