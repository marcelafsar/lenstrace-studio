"""Preview and export endpoints for metadata changes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.api.schemas import (
    BatchExportRequest,
    BatchExportResponse,
    BatchItemResult,
    ChangeRequest,
    ExportResponse,
    PreviewResponse,
)
from backend.logging_config import get_logger
from backend.services import preview_service
from core.exceptions import LensTraceError

logger = get_logger(__name__)
router = APIRouter(prefix="/metadata", tags=["metadata"])


@router.post("/preview", response_model=PreviewResponse)
def preview_changes(request: ChangeRequest) -> PreviewResponse:
    try:
        diff, dest_name = preview_service.preview(request)
    except LensTraceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.user_message) from exc
    return PreviewResponse(
        diff=diff, destination_name=dest_name, disclaimer=preview_service.disclaimer()
    )


@router.post("/export", response_model=ExportResponse)
def export_changes(request: ChangeRequest) -> ExportResponse:
    try:
        result = preview_service.export(request)
    except LensTraceError as exc:
        logger.warning("Export failed: %s", exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.user_message) from exc
    logger.info("Exported 1 file successfully")
    return ExportResponse(result=result, disclaimer=preview_service.disclaimer())


@router.post("/export-batch", response_model=BatchExportResponse)
def export_batch(request: BatchExportRequest) -> BatchExportResponse:
    outcomes = preview_service.export_batch(request.requests)
    results: list[BatchItemResult] = []
    for file_id, outcome in outcomes:
        if isinstance(outcome, LensTraceError):
            results.append(
                BatchItemResult(file_id=file_id, success=False, error=outcome.user_message)
            )
        else:
            results.append(
                BatchItemResult(
                    file_id=file_id,
                    success=True,
                    destination_name=outcome.destination_path.name,
                )
            )
    return BatchExportResponse(results=results)
