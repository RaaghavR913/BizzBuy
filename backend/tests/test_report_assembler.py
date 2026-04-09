from __future__ import annotations

from app.agents.schemas import (
    AgentEnvelope,
    AgentExecutionStatus,
    AgentName,
    AgentResult,
    DeterministicScorecard,
    DeterministicTag,
    DocumentInfo,
    DocumentSection,
    DocumentType,
    FindingCategory,
    IngestionMetadata,
    IngestionOutput,
    MissingInput,
    NormalizedFinding,
    NormalizedMetric,
    PipelineMetadata,
    PipelineStageMetric,
    ScoreConflict,
    Severity,
    SynthesisReportOutput,
    Timeframe,
)
from app.services.report_assembler import assemble_summary_report


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
                        extracted_data={"revenue": 1200000, "sde": 300000},
                        raw_text="Revenue 1200000 and SDE 300000",
                        confidence=0.91,
                    )
                ],
            )
        ],
        metadata=IngestionMetadata(
            total_documents=1,
            successfully_parsed=1,
            failed_documents=[],
            warnings=[],
            analysis_id="analysis-123",
        ),
    )


def _finding(
    finding_id: str,
    source_agent: AgentName,
    severity: Severity,
    title: str,
    *,
    category: FindingCategory = FindingCategory.EARNINGS_QUALITY,
    missing_data: bool = False,
) -> NormalizedFinding:
    return NormalizedFinding(
        finding_id=finding_id,
        source_agent=source_agent,
        category=category,
        severity=severity,
        title=title,
        description=title,
        deterministic_tags=[DeterministicTag.DEAL_BREAKER_CANDIDATE] if severity == Severity.CRITICAL else [],
        confidence=0.89,
        missing_data=missing_data,
    )


def test_assemble_summary_report_returns_frontend_ready_summary_payload() -> None:
    missing_tax_returns = MissingInput(
        key="tax_returns",
        description="Business tax returns were not provided.",
        document_type=DocumentType.TAX_RETURN_1120S,
        required=True,
        reason="Need returns to reconcile revenue.",
    )
    financial_envelope = AgentEnvelope(
        agent_name=AgentName.FINANCIAL_ANALYSIS,
        status=AgentExecutionStatus.SUCCESS,
        summary="Financials are workable but need reconciliation.",
        confidence=0.9,
        overall_score=6,
        normalized_metrics={"adjusted_sde": NormalizedMetric(value=300000, unit="usd")},
        findings=[_finding("fin-1", AgentName.FINANCIAL_ANALYSIS, Severity.HIGH, "Aggressive add-backs require validation.")],
    )
    tax_envelope = AgentEnvelope(
        agent_name=AgentName.TAX_COMPLIANCE,
        status=AgentExecutionStatus.SUCCESS,
        summary="Tax coverage is incomplete.",
        confidence=0.7,
        overall_score=3,
        findings=[_finding("tax-1", AgentName.TAX_COMPLIANCE, Severity.CRITICAL, "Recent tax returns are missing.", category=FindingCategory.TAX_COMPLIANCE)],
        missing_inputs=[missing_tax_returns],
    )
    scorecard = DeterministicScorecard(
        overall_risk_score=72,
        overall_recommendation="caution",
        technical_scorecards=[],
        deal_breakers=list(tax_envelope.findings),
        conflicts=[
            ScoreConflict(
                key="adjusted_sde",
                description="Conflicting SDE inputs detected; retained conservative value.",
                conservative_value=300000,
            )
        ],
        completeness_score=0.52,
        confidence_score=0.68,
        validated_metrics={"adjusted_sde": NormalizedMetric(value=300000, unit="usd")},
    )
    synthesis_result = AgentResult(
        status="success",
        data=SynthesisReportOutput.model_validate(
            {
                "executive_summary": "The deal has enough signal to continue, but the missing tax package is a material gating issue.",
                "red_flags": [
                    {
                        "id": "rf-1",
                        "severity": "high",
                        "source": "tax",
                        "title": "Tax package is incomplete",
                        "description": "Recent business returns were not included.",
                    }
                ],
                "green_flags": [],
                "section_summaries": {
                    "financial": {"score": 6, "summary": "Financials are workable.", "top_risks": []},
                    "tax": {"score": 3, "summary": "Tax returns are missing.", "top_risks": []},
                    "ar": {"score": 5, "summary": "AR not reviewed.", "top_risks": []},
                    "customer": {"score": 5, "summary": "Customer concentration not fully reviewed.", "top_risks": []},
                    "operations": {"score": 5, "summary": "Operations look neutral.", "top_risks": []},
                    "lease": {"score": 5, "summary": "Lease not reviewed.", "top_risks": []},
                    "market": {"score": 5, "summary": "Market is neutral.", "top_risks": []},
                    "lending": {"score": 5, "summary": "Lending is acceptable.", "top_risks": []},
                },
                "next_steps": [
                    {"priority": 1, "action": "Request the last two business tax returns.", "reason": "Need reconciliation support."},
                    {"priority": 2, "action": "Reconcile seller add-backs to source support.", "reason": "Validate cash flow quality."},
                ],
                "deal_terms_suggestion": "Use diligence conditions before advancing.",
            }
        ),
    )

    report = assemble_summary_report(
        ingestion_output=_ingestion_output(),
        agent_results={
            "financial_analysis": AgentResult(status="success", data=financial_envelope),
            "tax_compliance": AgentResult(status="success", data=tax_envelope),
        },
        scorecard=scorecard,
        synthesis_result=synthesis_result,
        metadata=PipelineMetadata(
            started_at="2026-04-08T12:00:00Z",
            completed_at="2026-04-08T12:01:00Z",
            total_tokens=3210,
            estimated_cost=0.123456,
            total_latency_ms=4567,
            stage_metrics={
                "financial_analysis": PipelineStageMetric(
                    status="success",
                    attempts=1,
                    latency_ms=1200,
                    total_tokens=2100,
                    estimated_cost=0.08,
                )
            },
        ),
    )

    payload = report.model_dump(by_alias=True)

    assert payload["modeAvailable"] == {"summary": True, "deep": False}
    assert payload["summary"]["headline"] == "Material diligence issues require caution"
    assert payload["summary"]["overview"].startswith("The deal has enough signal to continue")
    assert payload["summary"]["keyFindings"][0]["findingId"] == "tax-1"
    assert "Request the last two business tax returns." in payload["summary"]["recommendedActions"]
    assert payload["scorecard"]["overallRecommendation"] == "caution"
    assert payload["metadata"]["analysisId"] == "analysis-123"
    assert payload["metadata"]["pipelineStatus"] == "completed"
    assert payload["metadata"]["sourceDocumentCount"] == 1
    assert payload["metadata"]["totalTokens"] == 3210
    assert payload["metadata"]["estimatedCost"] == 0.123456
    assert payload["metadata"]["totalLatencyMs"] == 4567
    assert payload["metadata"]["auditMetadata"]["stageMetrics"]["financial_analysis"]["status"] == "success"


def test_assemble_summary_report_marks_partial_when_synthesis_fails() -> None:
    report = assemble_summary_report(
        ingestion_output=_ingestion_output(),
        agent_results={},
        scorecard=DeterministicScorecard(overall_risk_score=48, overall_recommendation="buy"),
        synthesis_result=AgentResult(status="error"),
        metadata=PipelineMetadata(
            started_at="2026-04-08T12:00:00Z",
            completed_at="2026-04-08T12:01:00Z",
            partial_failures=["tax_compliance"],
        ),
    )

    payload = report.model_dump(by_alias=True)

    assert payload["summary"]["headline"] == "Promising deal with manageable risk"
    assert payload["metadata"]["pipelineStatus"] == "partial"
    assert payload["summary"]["overview"].startswith("Pipeline completed with recommendation 'buy'")
    assert payload["metadata"]["auditMetadata"]["partialFailures"] == ["tax_compliance"]


def test_assemble_summary_report_can_include_deep_review_without_changing_summary_shape() -> None:
    missing_tax_returns = MissingInput(
        key="tax_returns",
        description="Business tax returns were not provided.",
        document_type=DocumentType.TAX_RETURN_1120S,
        required=True,
        reason="Need returns to reconcile revenue.",
    )
    evidence = [
        {
            "document_id": "doc-1",
            "file_name": "pnl.pdf",
            "section_id": "doc-1:section-1",
            "page": 1,
            "snippet": "Revenue 1200000 and SDE 300000",
            "extracted_fields": {"revenue": 1200000},
            "confidence": 0.91,
        }
    ]
    financial_envelope = AgentEnvelope(
        agent_name=AgentName.FINANCIAL_ANALYSIS,
        status=AgentExecutionStatus.SUCCESS,
        summary="Financials are workable but need reconciliation.",
        confidence=0.9,
        overall_score=6,
        normalized_metrics={"adjusted_sde": NormalizedMetric(value=300000, unit="usd", evidence=evidence)},
        findings=[_finding("fin-1", AgentName.FINANCIAL_ANALYSIS, Severity.HIGH, "Aggressive add-backs require validation.")],
        evidence=evidence,
    )
    tax_envelope = AgentEnvelope(
        agent_name=AgentName.TAX_COMPLIANCE,
        status=AgentExecutionStatus.SUCCESS,
        summary="Tax coverage is incomplete.",
        confidence=0.7,
        overall_score=3,
        findings=[
            _finding(
                "tax-1",
                AgentName.TAX_COMPLIANCE,
                Severity.CRITICAL,
                "Recent tax returns are missing.",
                category=FindingCategory.TAX_COMPLIANCE,
                missing_data=True,
            )
        ],
        missing_inputs=[missing_tax_returns],
    )
    scorecard = DeterministicScorecard(
        overall_risk_score=72,
        overall_recommendation="caution",
        technical_scorecards=[],
        deal_breakers=list(tax_envelope.findings),
        conflicts=[
            ScoreConflict(
                key="adjusted_sde",
                description="Conflicting SDE inputs detected; retained conservative value.",
                conservative_value=300000,
            )
        ],
        completeness_score=0.52,
        confidence_score=0.68,
        validated_metrics={"adjusted_sde": NormalizedMetric(value=300000, unit="usd")},
    )

    report = assemble_summary_report(
        ingestion_output=_ingestion_output(),
        agent_results={
            "financial_analysis": AgentResult(status="success", data=financial_envelope),
            "tax_compliance": AgentResult(status="success", data=tax_envelope),
        },
        scorecard=scorecard,
        synthesis_result=AgentResult(
            status="success",
            data=SynthesisReportOutput.model_validate(
                {
                    "executive_summary": "The deal can move forward only if missing diligence items are resolved.",
                    "red_flags": [],
                    "green_flags": [],
                    "section_summaries": {
                        "financial": {"score": 6, "summary": "Financials are workable.", "top_risks": []},
                        "tax": {"score": 3, "summary": "Tax returns are missing.", "top_risks": []},
                        "ar": {"score": 5, "summary": "AR not reviewed.", "top_risks": []},
                        "customer": {"score": 5, "summary": "Customer concentration not fully reviewed.", "top_risks": []},
                        "operations": {"score": 5, "summary": "Operations look neutral.", "top_risks": []},
                        "lease": {"score": 5, "summary": "Lease not reviewed.", "top_risks": []},
                        "market": {"score": 5, "summary": "Market is neutral.", "top_risks": []},
                        "lending": {"score": 5, "summary": "Lending is acceptable.", "top_risks": []},
                    },
                    "next_steps": [],
                    "deal_terms_suggestion": "Use diligence conditions before advancing.",
                }
            ),
        ),
        include_deep_review=True,
    )

    payload = report.model_dump(by_alias=True)

    assert payload["modeAvailable"] == {"summary": True, "deep": True}
    assert payload["summary"]["headline"] == "Material diligence issues require caution"
    assert payload["deepReview"] is not None
    assert payload["deepReview"]["agentReviews"][0]["agentName"] == "financial_analysis"
    assert payload["deepReview"]["agentReviews"][0]["keyMetrics"]["adjusted_sde"]["value"] == 300000
    assert payload["deepReview"]["agentReviews"][1]["missingInputs"][0]["key"] == "tax_returns"
    assert payload["deepReview"]["evidenceIndex"][0]["documentId"] == "doc-1"
    assert "Conflict logged for adjusted_sde" in payload["deepReview"]["auditTrail"][2]
    assert payload["deepReview"]["missingData"][0]["affectedAgents"] == ["tax_compliance"]
    assert payload["deepReview"]["missingData"][0]["impactSummary"].startswith("Required input lowered report completeness.")
