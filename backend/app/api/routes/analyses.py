from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.models.schemas import AnalysisJobRequest, AnalysisJobResponse
from app.services.analysis_jobs import get_analysis_job, start_analysis_job

router = APIRouter()


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
