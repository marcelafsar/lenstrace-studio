"""File upload, inspection, and cleanup endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, status

from backend.api.schemas import InspectResponse, UploadedFileResponse
from backend.logging_config import get_logger
from backend.services import file_service
from backend.services.session_service import get_session_store
from core.exceptions import LensTraceError
from core.metadata_reader import read_summary

logger = get_logger(__name__)
router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", response_model=UploadedFileResponse)
async def upload_file(file: UploadFile) -> UploadedFileResponse:
    data = await file.read()
    try:
        entry = file_service.save_upload(data, file.filename or "upload")
        summary = read_summary(entry.path)
        thumb = file_service.make_thumbnail_data_uri(entry.path)
    except LensTraceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.user_message) from exc
    return UploadedFileResponse(
        file_id=entry.file_id,
        original_name=entry.original_name,
        image_format=summary.image_format.value,
        width=summary.width,
        height=summary.height,
        thumbnail_data_uri=thumb,
    )


@router.get("/{file_id}/inspect", response_model=InspectResponse)
def inspect_file(file_id: str) -> InspectResponse:
    entry = get_session_store().get(file_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found in this session.")
    try:
        summary = read_summary(entry.path)
    except LensTraceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.user_message) from exc
    return InspectResponse(file_id=file_id, summary=summary)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: str) -> None:
    get_session_store().remove(file_id)
