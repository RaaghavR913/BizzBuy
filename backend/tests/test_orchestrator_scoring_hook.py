from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.agents.orchestrator import run_pipeline
from app.agents.schemas import (
    AgentResult,
    DeterministicScorecard,
    DocumentInfo,
    DocumentSection,
    DocumentType,
    IngestionMetadata,
    IngestionOutput,
    Timeframe,
)


def _ingestion_output() -> IngestionOutput:
    return IngestionOutput(
        documents=[
            DocumentInfo(
                document_id="doc-1",
                file_name="pnl.pdf",
                mime_type="application/pdf",
                document_type=DocumentType.PROFIT_AND_LOSS,
                sections=[
                    DocumentSection(
                        document_id="doc-1",
                        document_type=DocumentType.PROFIT_AND_LOSS,
                        timeframe=Timeframe(fiscal_year=2024),
                        extracted_data={"revenue": 1200000},
                        raw_text="Revenue 1200000",
                        confidence=0.9,
                    )
                ],
            )
        ],
        metadata=IngestionMetadata(
            total_documents=1,
            successfully_parsed=1,
            failed_documents=[],
            warnings=[],
        ),
    )


def _success(score: int, summary: str) -> AgentResult[dict]:
    return AgentResult(
        status="success",
        data={
            "overall_score": score,
            "confidence": 0.8,
            "summary": summary,
            "risks": [],
            "compliance_flags": [],
            "collectibility_flags": [],
            "contract_risks": [],
            "threats": [],
            "sba7a": {"dscr": 1.4, "dscr_meets_minimum": True},
            "affordability_analysis": {"asking_price": 900000, "adjusted_sde": 300000, "sde_multiple": 3.0},
            "buyer_requirements": {"total_cash_needed": 225000},
        },
    )


@pytest.mark.asyncio
async def test_run_pipeline_computes_scorecard_before_synthesis(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    async def direct_executor(func, *args):
        return func(*args)

    def ingestion_stub(_documents):
        return AgentResult(status="success", data=_ingestion_output())

    def specialist_stub(_ingestion_output, *_args):
        return _success(7, "Specialist completed.")

    def scorecard_stub(ingestion_output, specialist_results):
        assert ingestion_output.metadata.total_documents == 1
        assert specialist_results["financial_analysis"].status == "success"
        assert specialist_results["lending_affordability"].status == "success"
        events.append("scorecard")
        return DeterministicScorecard(overall_risk_score=55, overall_recommendation="conditional_buy")

    def synthesis_stub(scorecard, specialist_results):
        assert scorecard.overall_risk_score == 55
        assert scorecard.overall_recommendation == "conditional_buy"
        assert specialist_results["financial_analysis"].status == "success"
        events.append("synthesis")
        return AgentResult(
            status="success",
            data={
                "executive_summary": "Summary",
                "red_flags": [],
                "green_flags": [],
                "section_summaries": {
                    "financial": {"score": 7, "summary": "Financials are stable.", "top_risks": []},
                    "tax": {"score": 7, "summary": "Tax review is stable.", "top_risks": []},
                    "ar": {"score": 7, "summary": "AR quality is acceptable.", "top_risks": []},
                    "customer": {"score": 7, "summary": "Customer base is manageable.", "top_risks": []},
                    "operations": {"score": 7, "summary": "Operations are transferable.", "top_risks": []},
                    "lease": {"score": 7, "summary": "Lease looks workable.", "top_risks": []},
                    "market": {"score": 7, "summary": "Market backdrop is neutral.", "top_risks": []},
                    "lending": {"score": 7, "summary": "Lending profile is workable.", "top_risks": []},
                },
                "next_steps": [],
                "deal_terms_suggestion": "Proceed with normal diligence.",
            },
        )

    monkeypatch.setattr("app.agents.orchestrator._run_in_executor", direct_executor)
    monkeypatch.setattr("app.agents.orchestrator.run_document_ingestion", ingestion_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_financial_analysis", specialist_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_tax_compliance", specialist_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_ar_collections", specialist_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_customer_concentration", specialist_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_ops_transferability", specialist_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_lease_contract", specialist_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_market_macro", specialist_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_lending_affordability", specialist_stub)
    monkeypatch.setattr("app.agents.orchestrator.compute_pipeline_scorecard", scorecard_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_synthesis_report", synthesis_stub)
    monkeypatch.setattr(
        "app.agents.orchestrator.get_settings",
        lambda: SimpleNamespace(
            pipeline_enabled=True,
            analysis_jobs_enabled=True,
            pipeline_allow_partial_failures=True,
            pipeline_enable_synthesis=True,
            pipeline_retry_attempts=1,
            pipeline_stage_timeout_seconds=1.0,
        ),
    )

    payload = await run_pipeline({"documents": [{"id": "doc-1"}], "asking_price": 900000})

    assert events == ["scorecard", "synthesis"]
    assert payload["summary"]["headline"] == "Proceed, but only with targeted diligence conditions"
    assert payload["summary"]["overview"] == "Summary"
    assert payload["scorecard"]["overallRiskScore"] == 55
    assert payload["scorecard"]["overallRecommendation"] == "conditional_buy"
    assert payload["metadata"]["pipelineStatus"] == "completed"
    assert payload["metadata"]["sourceDocumentCount"] == 1
    assert payload["metadata"]["totalTokens"] == 0
    assert payload["metadata"]["auditMetadata"]["partialFailures"] == []
    assert payload["metadata"]["auditMetadata"]["stageMetrics"]["financial_analysis"]["status"] == "success"


@pytest.mark.asyncio
async def test_run_pipeline_marks_partial_and_records_stage_metrics_when_specialist_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def direct_executor(func, *args):
        return func(*args)

    def ingestion_stub(_documents):
        return AgentResult(status="success", data=_ingestion_output())

    def specialist_success(_ingestion_output, *_args):
        return _success(7, "Specialist completed.")

    def tax_failure(_ingestion_output, *_args):
        return AgentResult(status="error")

    def scorecard_stub(_ingestion_output, specialist_results):
        assert specialist_results["tax_compliance"].status == "error"
        return DeterministicScorecard(overall_risk_score=58, overall_recommendation="caution")

    def synthesis_stub(_scorecard, _specialist_results):
        return AgentResult(
            status="success",
            data={
                "executive_summary": "Summary",
                "red_flags": [],
                "green_flags": [],
                "section_summaries": {
                    "financial": {"score": 7, "summary": "Financials are stable.", "top_risks": []},
                    "tax": {"score": 3, "summary": "Tax review is incomplete.", "top_risks": []},
                    "ar": {"score": 7, "summary": "AR quality is acceptable.", "top_risks": []},
                    "customer": {"score": 7, "summary": "Customer base is manageable.", "top_risks": []},
                    "operations": {"score": 7, "summary": "Operations are transferable.", "top_risks": []},
                    "lease": {"score": 7, "summary": "Lease looks workable.", "top_risks": []},
                    "market": {"score": 7, "summary": "Market backdrop is neutral.", "top_risks": []},
                    "lending": {"score": 7, "summary": "Lending profile is workable.", "top_risks": []},
                },
                "next_steps": [],
                "deal_terms_suggestion": "Proceed with normal diligence.",
            },
        )

    monkeypatch.setattr("app.agents.orchestrator._run_in_executor", direct_executor)
    monkeypatch.setattr("app.agents.orchestrator.run_document_ingestion", ingestion_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_financial_analysis", specialist_success)
    monkeypatch.setattr("app.agents.orchestrator.run_tax_compliance", tax_failure)
    monkeypatch.setattr("app.agents.orchestrator.run_ar_collections", specialist_success)
    monkeypatch.setattr("app.agents.orchestrator.run_customer_concentration", specialist_success)
    monkeypatch.setattr("app.agents.orchestrator.run_ops_transferability", specialist_success)
    monkeypatch.setattr("app.agents.orchestrator.run_lease_contract", specialist_success)
    monkeypatch.setattr("app.agents.orchestrator.run_market_macro", specialist_success)
    monkeypatch.setattr("app.agents.orchestrator.run_lending_affordability", specialist_success)
    monkeypatch.setattr("app.agents.orchestrator.compute_pipeline_scorecard", scorecard_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_synthesis_report", synthesis_stub)
    monkeypatch.setattr(
        "app.agents.orchestrator.get_settings",
        lambda: SimpleNamespace(
            pipeline_enabled=True,
            analysis_jobs_enabled=True,
            pipeline_allow_partial_failures=True,
            pipeline_enable_synthesis=True,
            pipeline_retry_attempts=1,
            pipeline_stage_timeout_seconds=1.0,
        ),
    )

    payload = await run_pipeline({"documents": [{"id": "doc-1"}], "asking_price": 900000})

    assert payload["metadata"]["pipelineStatus"] == "partial"
    assert "tax_compliance" in payload["metadata"]["auditMetadata"]["partialFailures"]
    assert payload["metadata"]["auditMetadata"]["stageMetrics"]["tax_compliance"]["attempts"] == 2
    assert payload["metadata"]["auditMetadata"]["stageMetrics"]["tax_compliance"]["status"] == "error"
    assert payload["metadata"]["auditMetadata"]["stageMetrics"]["synthesis_report"]["status"] == "success"
