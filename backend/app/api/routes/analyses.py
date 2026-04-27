from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.core.path_safety import UnsafePathError, validate_analysis_id
from app.core.security import RequestIdentity, acquire_sse_slot, protect_expensive_route, release_sse_slot
from app.models.schemas import AnalysisJobRequest, AnalysisJobResponse
from app.services.analysis_jobs import AnalysisJobLimitError, get_analysis_job, start_analysis_job
from app.services.sse_registry import subscribe, unsubscribe

router = APIRouter()

_KEEPALIVE_S = 30.0
_protect_analysis_route = protect_expensive_route("analysis")
_protect_sse_route = protect_expensive_route("sse")


@router.post(
    "/analyses",
    response_model=AnalysisJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_protect_analysis_route)],
)
def create_analysis_job(payload: AnalysisJobRequest) -> AnalysisJobResponse:
    settings = get_settings()
    if not settings.analysis_jobs_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analysis jobs are disabled by rollout configuration.",
        )
    if not payload.documents and not (payload.financials and payload.questionnaire and payload.deal_info):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Analysis jobs require either pipeline documents or structured financial inputs.",
        )
    try:
        return start_analysis_job(payload)
    except UnsafePathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AnalysisJobLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc


@router.get(
    "/analyses/{analysis_id}",
    response_model=AnalysisJobResponse,
    dependencies=[Depends(_protect_analysis_route)],
)
def get_analysis_job_status(analysis_id: str) -> AnalysisJobResponse:
    try:
        safe_analysis_id = validate_analysis_id(analysis_id)
    except UnsafePathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    job = get_analysis_job(safe_analysis_id or analysis_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis job not found.")
    return job


@router.get("/analyses/{analysis_id}/events")
async def stream_analysis_events(
    analysis_id: str,
    request: Request,
    access: RequestIdentity = Depends(_protect_sse_route),
) -> StreamingResponse:
    """Server-Sent Events stream of `AnalysisJobResponse` JSON (same shape as GET /analyses/{id})."""
    settings = get_settings()
    if not settings.analysis_jobs_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analysis jobs are disabled by rollout configuration.",
        )

    try:
        safe_analysis_id = validate_analysis_id(analysis_id)
    except UnsafePathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if get_analysis_job(safe_analysis_id or analysis_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis job not found.")

    acquire_sse_slot(access)
    queue = subscribe(safe_analysis_id or analysis_id)

    async def event_gen() -> AsyncIterator[bytes]:
        try:
            fresh = get_analysis_job(safe_analysis_id or analysis_id)
            if fresh is None:
                return
            initial = fresh.model_dump(mode="json", by_alias=True)
            yield f"data: {json.dumps(initial, default=str)}\n\n".encode("utf-8")
            if fresh.status in ("completed", "failed"):
                return

            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_S)
                except asyncio.TimeoutError:
                    yield b": keepalive\n\n"
                    continue
                if await request.is_disconnected():
                    break
                try:
                    update = json.loads(msg)
                except json.JSONDecodeError:
                    continue
                st = update.get("status")
                yield f"data: {msg}\n\n".encode("utf-8")
                if st in ("completed", "failed"):
                    break
        finally:
            unsubscribe(safe_analysis_id or analysis_id, queue)
            release_sse_slot(access)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
