from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.models.schemas import AnalysisJobRequest, AnalysisJobResponse
from app.services.analysis_jobs import get_analysis_job, start_analysis_job
from app.services.sse_registry import subscribe, unsubscribe

router = APIRouter()

_KEEPALIVE_S = 30.0


@router.post("/analyses", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
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
    return start_analysis_job(payload)


@router.get("/analyses/{analysis_id}", response_model=AnalysisJobResponse)
def get_analysis_job_status(analysis_id: str) -> AnalysisJobResponse:
    job = get_analysis_job(analysis_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis job not found.")
    return job


@router.get("/analyses/{analysis_id}/events")
async def stream_analysis_events(analysis_id: str, request: Request) -> StreamingResponse:
    """Server-Sent Events stream of `AnalysisJobResponse` JSON (same shape as GET /analyses/{id})."""
    settings = get_settings()
    if not settings.analysis_jobs_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analysis jobs are disabled by rollout configuration.",
        )

    if get_analysis_job(analysis_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis job not found.")

    queue = subscribe(analysis_id)

    async def event_gen() -> AsyncIterator[bytes]:
        try:
            fresh = get_analysis_job(analysis_id)
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
            unsubscribe(analysis_id, queue)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
