import pytest
from pydantic import ValidationError

from app.agents.schemas import AgentEnvelope as BackendAgentEnvelope
from app.agents.schemas import AgentExecutionStatus, AgentName, DocumentType, FindingCategory, Severity, SynthesisReportOutput
from app.models.schemas import ReportOutputV2


def test_agent_envelope_accepts_camel_case_contract_fields() -> None:
    envelope = BackendAgentEnvelope.model_validate(
        {
            "agentName": "financial_analysis",
            "status": "success",
            "summary": "Normalized financial view",
            "confidence": 0.92,
            "overallScore": 8,
            "normalizedMetrics": {
                "revenue_latest": {
                    "value": 1200000,
                    "unit": "usd",
                    "displayValue": "$1.2M",
                    "confidence": 0.95,
                    "evidence": [
                        {
                            "documentId": "doc-1",
                            "fileName": "pnl.pdf",
                            "page": 2,
                            "snippet": "Revenue: $1,200,000",
                            "extractedFields": {"revenue": 1200000},
                            "confidence": 0.95,
                        }
                    ],
                }
            },
            "findings": [
                {
                    "findingId": "financial-001",
                    "sourceAgent": "financial_analysis",
                    "category": "earnings_quality",
                    "severity": "high",
                    "title": "Aggressive add-backs",
                    "description": "Add-backs exceed policy comfort.",
                    "deterministicTags": ["sde_adjustment"],
                    "metricImpact": {"validated_sde_delta": -25000},
                    "evidence": [],
                    "confidence": 0.84,
                    "missingData": False,
                }
            ],
            "missingInputs": [
                {
                    "key": "tax_returns",
                    "description": "Tax returns were not provided",
                    "documentType": "tax_return_1120s",
                    "required": True,
                }
            ],
            "evidence": [],
            "rawDomainOutput": {"summary": "kept for compatibility"},
        }
    )

    assert envelope.agent_name == AgentName.FINANCIAL_ANALYSIS
    assert envelope.status == AgentExecutionStatus.SUCCESS
    assert envelope.findings[0].category == FindingCategory.EARNINGS_QUALITY
    assert envelope.findings[0].severity == Severity.HIGH
    assert envelope.missing_inputs[0].document_type == DocumentType.TAX_RETURN_1120S


def test_report_output_v2_serializes_to_camel_case() -> None:
    report = ReportOutputV2(
        summary={
            "headline": "Proceed carefully",
            "overview": "Core issues are documented.",
            "keyFindings": [
                {
                    "findingId": "tax-001",
                    "sourceAgent": "tax_compliance",
                    "category": "tax_compliance",
                    "severity": "medium",
                    "title": "Revenue discrepancy",
                    "description": "Books and returns diverge.",
                    "deterministicTags": ["valuation_pressure"],
                    "metricImpact": {"max_revenue_discrepancy_pct": 0.18},
                    "evidence": [],
                    "confidence": 0.81,
                    "missingData": False,
                }
            ],
            "recommendedActions": ["Request a CPA reconciliation."],
        },
        scorecard={
            "overallRiskScore": 63,
            "overallRecommendation": "proceed_with_caution",
            "validatedMetrics": {
                "dscr": {
                    "value": 1.32,
                    "unit": "ratio",
                    "evidence": [],
                }
            },
        },
        metadata={
            "generatedAt": "2026-04-08T12:00:00Z",
            "analysisId": "analysis-123",
            "pipelineStatus": "contract_defined",
            "sourceDocumentCount": 4,
        },
    )

    payload = report.model_dump(by_alias=True)

    assert payload["modeAvailable"] == {"summary": True, "deep": False}
    assert payload["summary"]["keyFindings"][0]["findingId"] == "tax-001"
    assert payload["scorecard"]["validatedMetrics"]["dscr"]["value"] == 1.32
    assert payload["metadata"]["contractVersion"] == "2.0"


def test_report_output_v2_accepts_structured_deep_review_sections() -> None:
    report = ReportOutputV2.model_validate(
        {
            "modeAvailable": {"summary": True, "deep": True},
            "summary": {"headline": "Proceed carefully"},
            "scorecard": {"overallRiskScore": 63, "overallRecommendation": "proceed_with_caution"},
            "deepReview": {
                "agentReviews": [
                    {
                        "agentName": "tax_compliance",
                        "headline": "Tax returns do not reconcile cleanly.",
                        "summary": "The tax package is incomplete.",
                        "technicalScore": 3,
                        "confidence": 0.72,
                        "keyMetrics": {},
                        "findings": [],
                        "evidence": [],
                        "missingInputs": [
                            {
                                "key": "tax_returns",
                                "description": "Tax returns were not provided",
                                "documentType": "tax_return_1120s",
                                "required": True,
                            }
                        ],
                        "scoringImpact": {
                            "buyerFacingDimensions": ["financial_quality"],
                            "riskContribution": 70,
                        },
                    }
                ],
                "evidenceIndex": [],
                "auditTrail": ["Shared evidence base assembled."],
                "missingData": [
                    {
                        "key": "tax_returns",
                        "description": "Tax returns were not provided",
                        "documentType": "tax_return_1120s",
                        "required": True,
                        "affectedAgents": ["tax_compliance"],
                        "relatedFindings": ["tax-001"],
                        "impactSummary": "Required input lowered report completeness.",
                    }
                ],
            },
            "metadata": {"generatedAt": "2026-04-08T12:00:00Z"},
        }
    )

    payload = report.model_dump(by_alias=True)

    assert payload["deepReview"]["agentReviews"][0]["scoringImpact"]["buyerFacingDimensions"] == ["financial_quality"]
    assert payload["deepReview"]["missingData"][0]["affectedAgents"] == ["tax_compliance"]


def test_synthesis_report_output_rejects_deprecated_score_and_recommendation_fields() -> None:
    with pytest.raises(ValidationError):
        SynthesisReportOutput.model_validate(
            {
                "executive_summary": "Narrative only.",
                "overall_risk_score": 55,
                "recommendation": "conditional_buy",
                "red_flags": [],
                "green_flags": [],
                "section_summaries": {
                    "financial": {"score": 7, "summary": "Stable.", "top_risks": []},
                    "tax": {"score": 7, "summary": "Stable.", "top_risks": []},
                    "ar": {"score": 7, "summary": "Stable.", "top_risks": []},
                    "customer": {"score": 7, "summary": "Stable.", "top_risks": []},
                    "operations": {"score": 7, "summary": "Stable.", "top_risks": []},
                    "lease": {"score": 7, "summary": "Stable.", "top_risks": []},
                    "market": {"score": 7, "summary": "Stable.", "top_risks": []},
                    "lending": {"score": 7, "summary": "Stable.", "top_risks": []},
                },
                "next_steps": [],
                "deal_terms_suggestion": "Hold price discipline.",
            }
        )
