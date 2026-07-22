"""Configuration status endpoint (environment checker over HTTP).

Returns the same structured checks as the CLI, without any secret values. The
desktop Diagnostics panel calls this rather than re-implementing checks in TS.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from backend.services.env_check_service import CheckReport, run_checks

router = APIRouter(prefix="/config", tags=["config"])


class StatusResponse(BaseModel):
    report: CheckReport


@router.get("/status", response_model=StatusResponse)
async def config_status(service: str = "all", connectivity: bool = False) -> StatusResponse:
    # Checks touch the filesystem and (optionally) the network; run off-loop.
    report = await run_in_threadpool(
        run_checks, service=service, strict=False, connectivity=connectivity
    )
    return StatusResponse(report=report)


@router.post("/recheck", response_model=StatusResponse)
async def recheck(service: str = "all", connectivity: bool = False) -> StatusResponse:
    report = await run_in_threadpool(
        run_checks, service=service, strict=False, connectivity=connectivity
    )
    return StatusResponse(report=report)
