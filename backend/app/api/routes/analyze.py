from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import protect_expensive_route
from app.models.schemas import AnalyzeRequest, AnalyzeResponse
from app.services.analysis_service import run_analysis

router = APIRouter()
_protect_analysis_route = protect_expensive_route("analysis")


@router.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(_protect_analysis_route)])
def analyze_route(payload: AnalyzeRequest) -> AnalyzeResponse:
    report = run_analysis(payload.financials, payload.questionnaire, payload.deal_info)
    return AnalyzeResponse(success=True, report=report)
