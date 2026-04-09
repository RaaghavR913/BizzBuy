from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.agents.orchestrator import run_pipeline
from app.agents.schemas import PipelineInput, PipelineState

router = APIRouter()


@router.post("/pipeline", response_model=PipelineState)
async def pipeline_endpoint(payload: PipelineInput) -> Dict[str, Any]:
    """Run the complete agent pipeline on uploaded documents"""
    if not payload.documents:
        raise HTTPException(status_code=400, detail="No documents provided")

    return await run_pipeline(payload.model_dump(mode="json"))
