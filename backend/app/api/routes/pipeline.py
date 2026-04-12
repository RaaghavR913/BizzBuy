from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.agents.orchestrator import run_pipeline
from app.agents.schemas import PipelineInput
from app.core.config import get_settings
from app.models.schemas import ReportOutputV2

router = APIRouter()


@router.post("/pipeline", response_model=ReportOutputV2)
async def pipeline_endpoint(payload: PipelineInput) -> Dict[str, Any]:
    """Run the complete agent pipeline on uploaded documents"""
    settings = get_settings()
    if not settings.pipeline_enabled:
        raise HTTPException(status_code=503, detail="Pipeline is disabled by rollout configuration.")
    if not payload.documents:
        raise HTTPException(status_code=400, detail="No documents provided")

    return await run_pipeline(payload.model_dump(mode="json"))
