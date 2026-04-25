from __future__ import annotations

import asyncio
import pytest
from types import SimpleNamespace

from app.agents import orchestrator
from app.agents.orchestrator import run_pipeline
from app.agents.schemas import (
    AgentEnvelope,
    AgentResult,
    DeterministicScorecard,
    DocumentInfo,
    DocumentSection,
    DocumentType,
    IngestionMetadata,
    IngestionOutput,
    Timeframe,
)
from app.services.analysis_repository import FileSystemAnalysisArtifactRepository


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

    def ingestion_stub(_documents, *_args):
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
            pipeline_prompt_debug_artifacts_enabled=False,
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

    def ingestion_stub(_documents, *_args):
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
            pipeline_prompt_debug_artifacts_enabled=False,
        ),
    )

    payload = await run_pipeline({"documents": [{"id": "doc-1"}], "asking_price": 900000})

    assert payload["metadata"]["pipelineStatus"] == "partial"
    assert "tax_compliance" in payload["metadata"]["auditMetadata"]["partialFailures"]
    assert payload["metadata"]["auditMetadata"]["stageMetrics"]["tax_compliance"]["attempts"] == 2
    assert payload["metadata"]["auditMetadata"]["stageMetrics"]["tax_compliance"]["status"] == "error"
    assert payload["metadata"]["auditMetadata"]["stageMetrics"]["synthesis_report"]["status"] == "success"


@pytest.mark.asyncio
async def test_stage_specific_timeout_applied_to_financial_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def timeout_executor(func, *args):
        if getattr(func, "__name__", "") == "run_financial_analysis":
            await asyncio.sleep(0.02)
        return func(*args)

    def ingestion_stub(_documents, *_args):
        return AgentResult(status="success", data=_ingestion_output())

    def specialist_success(_ingestion_output, *_args):
        return _success(7, "Specialist completed.")

    def scorecard_stub(_ingestion_output, _specialist_results):
        return DeterministicScorecard(overall_risk_score=58, overall_recommendation="buy")

    def synthesis_stub(_scorecard, _specialist_results):
        return AgentResult(
            status="success",
            data={
                "executive_summary": "Summary",
                "red_flags": [],
                "green_flags": [],
                "section_summaries": {
                    "financial": {"score": 6, "summary": "Financials fallback.", "top_risks": []},
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

    monkeypatch.setattr("app.agents.orchestrator._run_in_executor", timeout_executor)
    monkeypatch.setattr(orchestrator.AGENT_REGISTRY["financial-analysis"], "timeout_seconds", 0.01)
    monkeypatch.setattr("app.agents.orchestrator.run_document_ingestion", ingestion_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_tax_compliance", specialist_success)
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
            pipeline_retry_attempts=0,
            pipeline_stage_timeout_seconds=1.0,
            pipeline_prompt_debug_artifacts_enabled=False,
        ),
    )

    payload = await run_pipeline({"documents": [{"id": "doc-1"}], "asking_price": 900000})

    financial_metric = payload["metadata"]["auditMetadata"]["stageMetrics"]["financial_analysis"]
    assert financial_metric["timeout_seconds"] == 0.01
    assert financial_metric["status"] == "error"
    assert financial_metric["timed_out"] is True
    assert financial_metric["fallback_used"] is False
    assert financial_metric["token_usage_known"] is False
    assert financial_metric["token_usage_unknown_due_to_timeout"] is True
    assert financial_metric["provider_response_received"] is False


@pytest.mark.asyncio
async def test_prompt_debug_artifact_writes_full_prompt_bodies_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    async def direct_executor(func, *args):
        return func(*args)

    def ingestion_stub(_documents, *_args):
        return AgentResult(status="success", data=_ingestion_output())

    def specialist_stub(_ingestion_output, *_args, diagnostic_context=None):
        if diagnostic_context is not None:
            diagnostic_context.update(
                {
                    "prompt_chars": 111,
                    "schema_chars": 22,
                    "prompt_sections": {"metrics": 10},
                    "context_truncation": {"truncated_field_count": 1},
                    "response_chars": 33,
                    "model": "z-ai/glm-5.1",
                    "provider_response_received": True,
                    "usage_received": True,
                    "tool_call_found": True,
                    "validation_passed": True,
                    "token_usage_known": True,
                }
            )
            if diagnostic_context.get("capture_prompt_bodies"):
                diagnostic_context["system_prompt"] = "FINANCIAL SYSTEM"
                diagnostic_context["user_message"] = "FINANCIAL USER"
        return _success(7, "Specialist completed.")

    def lending_stub(_ingestion_output, *_args, diagnostic_context=None):
        if diagnostic_context is not None:
            diagnostic_context.update({"model": "z-ai/glm-5.1"})
        return _success(7, "Lending completed.")

    def scorecard_stub(_ingestion_output, _specialist_results):
        return DeterministicScorecard(overall_risk_score=55, overall_recommendation="conditional_buy")

    def synthesis_stub(_scorecard, _specialist_results, diagnostic_context=None):
        if diagnostic_context is not None:
            diagnostic_context.update(
                {
                    "prompt_chars": 444,
                    "schema_chars": 55,
                    "prompt_sections": {"specialist_context": 400},
                    "response_chars": 66,
                    "model": "z-ai/glm-5.1",
                    "provider_response_received": True,
                    "usage_received": True,
                    "tool_call_found": True,
                    "validation_passed": True,
                    "token_usage_known": True,
                }
            )
            if diagnostic_context.get("capture_prompt_bodies"):
                diagnostic_context["system_prompt"] = "SYNTHESIS SYSTEM"
                diagnostic_context["user_message"] = "SYNTHESIS USER"
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

    repository = FileSystemAnalysisArtifactRepository(tmp_path)
    monkeypatch.setattr("app.agents.orchestrator._run_in_executor", direct_executor)
    monkeypatch.setattr("app.agents.orchestrator.run_document_ingestion", ingestion_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_financial_analysis", specialist_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_tax_compliance", specialist_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_ar_collections", specialist_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_customer_concentration", specialist_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_ops_transferability", specialist_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_lease_contract", specialist_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_market_macro", specialist_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_lending_affordability", lending_stub)
    monkeypatch.setattr("app.agents.orchestrator.compute_pipeline_scorecard", scorecard_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_synthesis_report", synthesis_stub)
    monkeypatch.setattr("app.agents.orchestrator.get_analysis_artifact_repository", lambda: repository)
    monkeypatch.setattr("app.services.analysis_repository.get_analysis_artifact_repository", lambda: repository)
    monkeypatch.setattr("app.services.analysis_jobs.broadcast_job_snapshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "app.agents.orchestrator.get_settings",
        lambda: SimpleNamespace(
            pipeline_enabled=True,
            analysis_jobs_enabled=True,
            pipeline_allow_partial_failures=True,
            pipeline_enable_synthesis=True,
            pipeline_retry_attempts=0,
            pipeline_stage_timeout_seconds=1.0,
            pipeline_prompt_debug_artifacts_enabled=True,
            pipeline_prompt_debug_include_bodies=True,
            pipeline_prompt_debug_stages=["financial_analysis", "synthesis_report"],
        ),
    )

    await run_pipeline(
        {
            "analysis_id": "analysis-debug-1",
            "documents": [{"id": "doc-1"}],
            "asking_price": 900000,
        }
    )

    artifact = repository.load_prompt_debug_artifact("analysis-debug-1")

    assert artifact is not None
    assert set(artifact["stages"]) == {"financial_analysis", "synthesis_report"}
    assert artifact["stages"]["financial_analysis"]["systemPrompt"] == "FINANCIAL SYSTEM"
    assert artifact["stages"]["financial_analysis"]["userMessage"] == "FINANCIAL USER"
    assert artifact["stages"]["financial_analysis"]["schemaChars"] == 22
    assert artifact["stages"]["financial_analysis"]["attemptCount"] is None
    assert artifact["stages"]["financial_analysis"]["providerResponseReceived"] is True
    assert artifact["stages"]["synthesis_report"]["systemPrompt"] == "SYNTHESIS SYSTEM"
    assert artifact["stages"]["synthesis_report"]["userMessage"] == "SYNTHESIS USER"


def test_selected_prompt_debug_stages_defaults_include_tax() -> None:
    settings = SimpleNamespace(pipeline_prompt_debug_stages=[])

    assert orchestrator._selected_prompt_debug_stages(settings) == {
        "ingestion",
        "financial_analysis",
        "tax_compliance",
        "ar_collections",
        "customer_concentration",
        "operations_transferability",
        "lease_contract",
        "market_macro",
        "lending_affordability",
        "synthesis_report",
    }


@pytest.mark.asyncio
async def test_synthesis_timeout_surfaces_agent_error_without_deterministic_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def timeout_executor(func, *args):
        if getattr(func, "__name__", "") == "run_synthesis_report":
            await asyncio.sleep(0.02)
        return func(*args)

    def ingestion_stub(_documents, *_args):
        return AgentResult(status="success", data=_ingestion_output())

    def specialist_success(_ingestion_output, *_args):
        return AgentResult(
            status="success",
            data=AgentEnvelope(
                agent_name="financial_analysis",
                status="success",
                summary="Financial analysis complete.",
                confidence=0.8,
                overall_score=7,
            ),
        )

    monkeypatch.setattr("app.agents.orchestrator._run_in_executor", timeout_executor)
    monkeypatch.setattr(orchestrator.AGENT_REGISTRY["synthesis-report"], "timeout_seconds", 0.01)
    monkeypatch.setattr("app.agents.orchestrator.run_document_ingestion", ingestion_stub)
    monkeypatch.setattr("app.agents.orchestrator.run_financial_analysis", specialist_success)
    monkeypatch.setattr("app.agents.orchestrator.run_tax_compliance", specialist_success)
    monkeypatch.setattr("app.agents.orchestrator.run_ar_collections", specialist_success)
    monkeypatch.setattr("app.agents.orchestrator.run_customer_concentration", specialist_success)
    monkeypatch.setattr("app.agents.orchestrator.run_ops_transferability", specialist_success)
    monkeypatch.setattr("app.agents.orchestrator.run_lease_contract", specialist_success)
    monkeypatch.setattr("app.agents.orchestrator.run_market_macro", specialist_success)
    monkeypatch.setattr("app.agents.orchestrator.run_lending_affordability", specialist_success)
    monkeypatch.setattr(
        "app.agents.orchestrator.compute_pipeline_scorecard",
        lambda *_args, **_kwargs: DeterministicScorecard(
            overall_risk_score=61,
            overall_recommendation="conditional_buy",
        ),
    )
    monkeypatch.setattr(
        "app.agents.orchestrator.get_settings",
        lambda: SimpleNamespace(
            pipeline_enabled=True,
            analysis_jobs_enabled=True,
            pipeline_allow_partial_failures=True,
            pipeline_enable_synthesis=True,
            pipeline_retry_attempts=0,
            pipeline_stage_timeout_seconds=1.0,
            pipeline_prompt_debug_artifacts_enabled=False,
        ),
    )

    payload = await run_pipeline({"documents": [{"id": "doc-1"}], "asking_price": 900000})

    synthesis_metric = payload["metadata"]["auditMetadata"]["stageMetrics"]["synthesis_report"]
    assert synthesis_metric["status"] == "error"
    assert synthesis_metric["timed_out"] is True
    assert synthesis_metric["fallback_used"] is False
    assert payload["metadata"]["pipelineStatus"] == "partial"
    assert payload["summary"]["overview"] is not None
