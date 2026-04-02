from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import AnalyzeRequest, AnalyzeResponse
from app.services.analysis_service import run_analysis

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_route(payload: AnalyzeRequest) -> AnalyzeResponse:
    report = run_analysis(payload.financials, payload.questionnaire, payload.deal_info)
    return AnalyzeResponse(success=True, report=report)
