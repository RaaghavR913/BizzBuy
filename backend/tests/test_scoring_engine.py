from __future__ import annotations

import pytest

from app.agents.schemas import (
    AgentEnvelope,
    AgentExecutionStatus,
    AgentName,
    AgentResult,
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
    Severity,
    Timeframe,
)
from app.services.scoring_engine import compute_pipeline_scorecard

RECOMMENDATION_ORDER = ["strong_buy", "buy", "conditional_buy", "caution", "do_not_buy"]


def _metric(value, *, unit: str | None = None, confidence: float = 0.9) -> NormalizedMetric:
    return NormalizedMetric(value=value, unit=unit, confidence=confidence)


def _finding(
    finding_id: str,
    source_agent: AgentName,
    severity: Severity,
    title: str,
    *,
    category: FindingCategory = FindingCategory.EARNINGS_QUALITY,
    missing_data: bool = False,
    tags: list[DeterministicTag] | None = None,
) -> NormalizedFinding:
    return NormalizedFinding(
        finding_id=finding_id,
        source_agent=source_agent,
        category=category,
        severity=severity,
        title=title,
        description=title,
        deterministic_tags=tags or [],
        confidence=0.9,
        missing_data=missing_data,
    )


def _envelope(
    agent_name: AgentName,
    score: int,
    confidence: float,
    *,
    summary: str = "Summary",
    metrics: dict[str, NormalizedMetric] | None = None,
    findings: list[NormalizedFinding] | None = None,
    missing_inputs: list[MissingInput] | None = None,
) -> AgentEnvelope:
    return AgentEnvelope(
        agent_name=agent_name,
        status=AgentExecutionStatus.SUCCESS,
        summary=summary,
        confidence=confidence,
        overall_score=score,
        normalized_metrics=metrics or {},
        findings=findings or [],
        missing_inputs=missing_inputs or [],
    )


def _result(envelope: AgentEnvelope) -> AgentResult[AgentEnvelope]:
    return AgentResult(status="success", data=envelope)


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
                        confidence=0.92,
                    )
                ],
            )
        ],
        metadata=IngestionMetadata(
            total_documents=1,
            successfully_parsed=1,
            failed_documents=[],
            warnings=[],
            overall_confidence=0.88,
        ),
    )


def _recommendation_rank(value: str | None) -> int:
    assert value is not None
    return RECOMMENDATION_ORDER.index(value)


def test_compute_pipeline_scorecard_builds_deterministic_scorecard_from_normalized_outputs() -> None:
    agent_results = {
        "financial_analysis": _result(
            _envelope(
                AgentName.FINANCIAL_ANALYSIS,
                8,
                0.92,
                summary="Healthy margins and working capital.",
                metrics={
                    "revenue_latest": _metric(1200000, unit="usd"),
                    "sde_validated_candidate": _metric(310000, unit="usd"),
                    "working_capital": _metric(180000, unit="usd"),
                },
            )
        ),
        "tax_compliance": _result(
            _envelope(
                AgentName.TAX_COMPLIANCE,
                7,
                0.75,
                summary="Minor reconciliation items only.",
                metrics={
                    "max_revenue_discrepancy_pct": _metric(0.03, unit="ratio"),
                    "missing_tax_years_count": _metric(0),
                },
            )
        ),
        "ar_collections": AgentResult(status="failed"),
        "customer_concentration": _result(
            _envelope(
                AgentName.CUSTOMER_CONCENTRATION,
                6,
                0.8,
                metrics={
                    "top_customer_revenue_pct": _metric(18, unit="pct"),
                    "single_customer_dependency": _metric(False),
                },
                findings=[
                    _finding(
                        "cust-watch",
                        AgentName.CUSTOMER_CONCENTRATION,
                        Severity.MEDIUM,
                        "Top customer concentration should still be monitored.",
                        category=FindingCategory.CUSTOMER_CONCENTRATION,
                    )
                ],
            )
        ),
        "operations_transferability": AgentResult(status="failed"),
        "lease_contract": AgentResult(status="failed"),
        "market_macro": AgentResult(status="failed"),
        "lending_affordability": _result(
            _envelope(
                AgentName.LENDING_AFFORDABILITY,
                8,
                0.84,
                summary="Financeable under a normal SBA structure.",
                metrics={
                    "adjusted_sde": _metric(300000, unit="usd"),
                    "dscr": _metric(1.42, unit="ratio"),
                    "dscr_meets_minimum": _metric(True),
                    "sde_multiple": _metric(3.0, unit="x"),
                    "total_cash_needed": _metric(225000, unit="usd"),
                    "eligible_for_sba": _metric(True),
                },
            )
        ),
    }

    scorecard = compute_pipeline_scorecard(_ingestion_output(), agent_results)

    assert scorecard.overall_risk_score is not None
    assert scorecard.overall_risk_score < 50
    assert scorecard.overall_recommendation == "buy"
    assert scorecard.completeness_score == 0.6
    assert scorecard.confidence_score == 0.8047
    assert scorecard.validated_metrics["adjusted_sde"].value == 300000
    assert scorecard.validated_metrics["dscr"].value == 1.42
    assert scorecard.technical_scorecards[0].name == "Financial Analysis"
    assert scorecard.technical_scorecards[0].score == 8
    assert scorecard.buyer_facing_dimensions[0].label == "Financial Quality"
    assert len(scorecard.conflicts) == 1
    assert scorecard.conflicts[0].key == "adjusted_sde"


def test_compute_pipeline_scorecard_uses_conservative_metric_resolution_and_flags_conflicts() -> None:
    agent_results = {
        "financial_analysis": _result(
            _envelope(
                AgentName.FINANCIAL_ANALYSIS,
                6,
                0.82,
                metrics={"sde_validated_candidate": _metric(340000, unit="usd")},
            )
        ),
        "tax_compliance": _result(_envelope(AgentName.TAX_COMPLIANCE, 6, 0.72)),
        "ar_collections": AgentResult(status="failed"),
        "customer_concentration": AgentResult(status="failed"),
        "operations_transferability": AgentResult(status="failed"),
        "lease_contract": AgentResult(status="failed"),
        "market_macro": AgentResult(status="failed"),
        "lending_affordability": _result(
            _envelope(
                AgentName.LENDING_AFFORDABILITY,
                5,
                0.78,
                metrics={
                    "adjusted_sde": _metric(300000, unit="usd"),
                    "dscr": _metric(1.18, unit="ratio"),
                    "dscr_meets_minimum": _metric(False),
                },
                findings=[
                    _finding(
                        "lending-risk",
                        AgentName.LENDING_AFFORDABILITY,
                        Severity.HIGH,
                        "Debt service coverage is below policy minimum.",
                        category=FindingCategory.LENDING,
                    )
                ],
            )
        ),
    }

    scorecard = compute_pipeline_scorecard(_ingestion_output(), agent_results)

    assert scorecard.validated_metrics["adjusted_sde"].value == 300000
    assert len(scorecard.conflicts) == 1
    assert scorecard.conflicts[0].key == "adjusted_sde"
    assert scorecard.conflicts[0].conservative_value == 300000
    assert scorecard.overall_recommendation == "caution"
    assert scorecard.overall_risk_score is not None
    assert scorecard.overall_risk_score >= 60


def test_compute_pipeline_scorecard_penalizes_missing_required_inputs_and_surfaces_deal_breakers() -> None:
    missing_tax_returns = MissingInput(
        key="tax_returns",
        description="Business tax returns were not provided.",
        document_type=DocumentType.TAX_RETURN_1120S,
        required=True,
        reason="Tax reconciliation is not reliable without returns.",
    )
    critical_finding = _finding(
        "critical-tax-gap",
        AgentName.TAX_COMPLIANCE,
        Severity.CRITICAL,
        "Tax coverage gap is a close blocker.",
        category=FindingCategory.TAX_COMPLIANCE,
        tags=[DeterministicTag.DEAL_BREAKER_CANDIDATE],
    )
    agent_results = {
        "financial_analysis": _result(_envelope(AgentName.FINANCIAL_ANALYSIS, 7, 0.88)),
        "tax_compliance": _result(
            _envelope(
                AgentName.TAX_COMPLIANCE,
                3,
                0.55,
                findings=[critical_finding, _finding("missing-tax", AgentName.TAX_COMPLIANCE, Severity.HIGH, "Missing tax returns.", missing_data=True)],
                missing_inputs=[missing_tax_returns],
            )
        ),
        "ar_collections": AgentResult(status="failed"),
        "customer_concentration": AgentResult(status="failed"),
        "operations_transferability": AgentResult(status="failed"),
        "lease_contract": AgentResult(status="failed"),
        "market_macro": AgentResult(status="failed"),
        "lending_affordability": _result(
            _envelope(
                AgentName.LENDING_AFFORDABILITY,
                4,
                0.62,
                metrics={"dscr": _metric(0.96, unit="ratio"), "dscr_meets_minimum": _metric(False)},
            )
        ),
    }

    scorecard = compute_pipeline_scorecard(_ingestion_output(), agent_results)

    assert scorecard.completeness_score == 0.41
    assert scorecard.confidence_score == 0.7451
    assert len(scorecard.deal_breakers) == 1
    assert scorecard.deal_breakers[0].finding_id == "critical-tax-gap"
    assert scorecard.overall_recommendation == "do_not_buy"
    assert scorecard.overall_risk_score == 81


def test_compute_pipeline_scorecard_resolves_boolean_conflicts_conservatively() -> None:
    agent_results = {
        "financial_analysis": _result(_envelope(AgentName.FINANCIAL_ANALYSIS, 8, 0.9)),
        "tax_compliance": _result(_envelope(AgentName.TAX_COMPLIANCE, 7, 0.82)),
        "ar_collections": AgentResult(status="failed"),
        "customer_concentration": _result(
            _envelope(
                AgentName.CUSTOMER_CONCENTRATION,
                7,
                0.81,
                metrics={"single_customer_dependency": _metric(False)},
            )
        ),
        "operations_transferability": AgentResult(status="failed"),
        "lease_contract": AgentResult(status="failed"),
        "market_macro": AgentResult(status="failed"),
        "lending_affordability": _result(
            _envelope(
                AgentName.LENDING_AFFORDABILITY,
                8,
                0.83,
                metrics={
                    "single_customer_dependency": _metric(True),
                    "eligible_for_sba": _metric(True),
                    "dscr": _metric(1.39, unit="ratio"),
                    "dscr_meets_minimum": _metric(True),
                },
            )
        ),
    }

    scorecard = compute_pipeline_scorecard(_ingestion_output(), agent_results)

    assert scorecard.validated_metrics["single_customer_dependency"].value is True
    assert len(scorecard.conflicts) == 1
    assert scorecard.conflicts[0].key == "single_customer_dependency"
    assert scorecard.conflicts[0].conservative_value is True
    assert scorecard.confidence_score == 0.808


def test_compute_pipeline_scorecard_applies_conflict_and_override_pressure_to_recommendation() -> None:
    baseline_results = {
        "financial_analysis": _result(
            _envelope(
                AgentName.FINANCIAL_ANALYSIS,
                8,
                0.92,
                metrics={"revenue_latest": _metric(1400000, unit="usd"), "working_capital": _metric(200000, unit="usd")},
            )
        ),
        "tax_compliance": _result(
            _envelope(
                AgentName.TAX_COMPLIANCE,
                8,
                0.88,
                metrics={"max_revenue_discrepancy_pct": _metric(0.02, unit="ratio")},
            )
        ),
        "ar_collections": AgentResult(status="failed"),
        "customer_concentration": _result(
            _envelope(
                AgentName.CUSTOMER_CONCENTRATION,
                7,
                0.82,
                metrics={"top_customer_revenue_pct": _metric(19, unit="pct")},
            )
        ),
        "operations_transferability": AgentResult(status="failed"),
        "lease_contract": AgentResult(status="failed"),
        "market_macro": AgentResult(status="failed"),
        "lending_affordability": _result(
            _envelope(
                AgentName.LENDING_AFFORDABILITY,
                8,
                0.86,
                metrics={
                    "adjusted_sde": _metric(360000, unit="usd"),
                    "dscr": _metric(1.46, unit="ratio"),
                    "dscr_meets_minimum": _metric(True),
                    "sde_multiple": _metric(3.1, unit="x"),
                    "eligible_for_sba": _metric(True),
                },
            )
        ),
    }
    stressed_results = {
        **baseline_results,
        "financial_analysis": _result(
            _envelope(
                AgentName.FINANCIAL_ANALYSIS,
                8,
                0.92,
                metrics={
                    "revenue_latest": _metric(1400000, unit="usd"),
                    "working_capital": _metric(200000, unit="usd"),
                    "adjusted_sde": _metric(420000, unit="usd"),
                    "dscr_meets_minimum": _metric(True),
                },
            )
        ),
        "tax_compliance": _result(
            _envelope(
                AgentName.TAX_COMPLIANCE,
                8,
                0.88,
                metrics={
                    "max_revenue_discrepancy_pct": _metric(0.12, unit="ratio"),
                    "eligible_for_sba": _metric(False),
                },
            )
        ),
        "lending_affordability": _result(
            _envelope(
                AgentName.LENDING_AFFORDABILITY,
                8,
                0.86,
                metrics={
                    "adjusted_sde": _metric(360000, unit="usd"),
                    "dscr": _metric(1.18, unit="ratio"),
                    "dscr_meets_minimum": _metric(False),
                    "sde_multiple": _metric(3.9, unit="x"),
                    "eligible_for_sba": _metric(True),
                },
            )
        ),
    }

    baseline = compute_pipeline_scorecard(_ingestion_output(), baseline_results)
    stressed = compute_pipeline_scorecard(_ingestion_output(), stressed_results)

    assert baseline.overall_recommendation == "buy"
    assert stressed.overall_recommendation == "do_not_buy"
    assert len(stressed.conflicts) == 3
    assert {conflict.key for conflict in stressed.conflicts} == {"adjusted_sde", "dscr_meets_minimum", "eligible_for_sba"}
    assert stressed.overall_risk_score > baseline.overall_risk_score
    assert _recommendation_rank(stressed.overall_recommendation) > _recommendation_rank(baseline.overall_recommendation)


def test_compute_pipeline_scorecard_dedupes_missing_inputs_across_ingestion_and_agents() -> None:
    missing_tax_returns = MissingInput(
        key="tax_returns",
        description="Business tax returns were not provided.",
        document_type=DocumentType.TAX_RETURN_1120S,
        required=True,
        reason="Tax reconciliation is not reliable without returns.",
    )
    agent_results = {
        "financial_analysis": _result(_envelope(AgentName.FINANCIAL_ANALYSIS, 7, 0.88)),
        "tax_compliance": _result(
            _envelope(
                AgentName.TAX_COMPLIANCE,
                5,
                0.68,
                missing_inputs=[missing_tax_returns],
            )
        ),
        "ar_collections": AgentResult(status="failed"),
        "customer_concentration": AgentResult(status="failed"),
        "operations_transferability": AgentResult(status="failed"),
        "lease_contract": AgentResult(status="failed"),
        "market_macro": AgentResult(status="failed"),
        "lending_affordability": _result(
            _envelope(
                AgentName.LENDING_AFFORDABILITY,
                6,
                0.74,
                metrics={"dscr": _metric(1.21, unit="ratio"), "dscr_meets_minimum": _metric(False)},
            )
        ),
    }
    ingestion_with_duplicate = _ingestion_output()
    ingestion_with_duplicate.metadata.missing_inputs = [missing_tax_returns]
    ingestion_without_duplicate = _ingestion_output()

    with_duplicate = compute_pipeline_scorecard(ingestion_with_duplicate, agent_results)
    without_duplicate = compute_pipeline_scorecard(ingestion_without_duplicate, agent_results)

    assert with_duplicate.completeness_score == without_duplicate.completeness_score
    assert with_duplicate.confidence_score == without_duplicate.confidence_score
    assert with_duplicate.overall_risk_score == without_duplicate.overall_risk_score


@pytest.mark.parametrize(
    ("fixture_name", "agent_results", "missing_inputs", "expected_recommendation", "expected_risk_score", "expected_conflicts"),
    [
        (
            "sample_company1",
            {
                "financial_analysis": _result(
                    _envelope(
                        AgentName.FINANCIAL_ANALYSIS,
                        4,
                        0.74,
                        summary="Earnings are pressured by weak working capital and low-quality add-backs.",
                        metrics={
                            "revenue_latest": _metric(980000, unit="usd"),
                            "working_capital": _metric(-40000, unit="usd"),
                            "sde_validated_candidate": _metric(205000, unit="usd"),
                        },
                        findings=[
                            _finding("fin-addbacks", AgentName.FINANCIAL_ANALYSIS, Severity.HIGH, "Seller add-backs require heavy validation."),
                        ],
                    )
                ),
                "tax_compliance": _result(
                    _envelope(
                        AgentName.TAX_COMPLIANCE,
                        3,
                        0.66,
                        metrics={
                            "max_revenue_discrepancy_pct": _metric(0.17, unit="ratio"),
                            "missing_tax_years_count": _metric(1),
                        },
                        findings=[
                            _finding(
                                "tax-gap",
                                AgentName.TAX_COMPLIANCE,
                                Severity.CRITICAL,
                                "Recent tax coverage is incomplete.",
                                category=FindingCategory.TAX_COMPLIANCE,
                                tags=[DeterministicTag.DEAL_BREAKER_CANDIDATE],
                            ),
                        ],
                    )
                ),
                "ar_collections": AgentResult(status="failed"),
                "customer_concentration": _result(
                    _envelope(
                        AgentName.CUSTOMER_CONCENTRATION,
                        4,
                        0.71,
                        metrics={
                            "top_customer_revenue_pct": _metric(41, unit="pct"),
                            "single_customer_dependency": _metric(True),
                        },
                    )
                ),
                "operations_transferability": AgentResult(status="failed"),
                "lease_contract": AgentResult(status="failed"),
                "market_macro": AgentResult(status="failed"),
                "lending_affordability": _result(
                    _envelope(
                        AgentName.LENDING_AFFORDABILITY,
                        3,
                        0.69,
                        summary="Debt service fails policy minimum on validated earnings.",
                        metrics={
                            "adjusted_sde": _metric(180000, unit="usd"),
                            "dscr": _metric(0.91, unit="ratio"),
                            "dscr_meets_minimum": _metric(False),
                            "sde_multiple": _metric(4.6, unit="x"),
                            "eligible_for_sba": _metric(False),
                        },
                        findings=[
                            _finding(
                                "lending-break",
                                AgentName.LENDING_AFFORDABILITY,
                                Severity.HIGH,
                                "Debt service coverage is below 1.0x.",
                                category=FindingCategory.LENDING,
                            ),
                        ],
                    )
                ),
            },
            [
                MissingInput(
                    key="ar_aging",
                    description="AR aging was not provided.",
                    document_type=DocumentType.AR_AGING_REPORT,
                    required=False,
                    reason="Collections quality cannot be verified.",
                )
            ],
            "do_not_buy",
            100,
            1,
        ),
        (
            "sample_company3_lone_star_plumbing",
            {
                "financial_analysis": _result(
                    _envelope(
                        AgentName.FINANCIAL_ANALYSIS,
                        8,
                        0.9,
                        summary="Margins and working capital are healthy.",
                        metrics={
                            "revenue_latest": _metric(1550000, unit="usd"),
                            "working_capital": _metric(210000, unit="usd"),
                            "sde_validated_candidate": _metric(360000, unit="usd"),
                        },
                    )
                ),
                "tax_compliance": _result(
                    _envelope(
                        AgentName.TAX_COMPLIANCE,
                        8,
                        0.86,
                        metrics={"max_revenue_discrepancy_pct": _metric(0.01, unit="ratio"), "missing_tax_years_count": _metric(0)},
                    )
                ),
                "ar_collections": AgentResult(status="failed"),
                "customer_concentration": _result(
                    _envelope(
                        AgentName.CUSTOMER_CONCENTRATION,
                        7,
                        0.82,
                        metrics={"top_customer_revenue_pct": _metric(16, unit="pct"), "single_customer_dependency": _metric(False)},
                    )
                ),
                "operations_transferability": _result(_envelope(AgentName.OPERATIONS_TRANSFERABILITY, 7, 0.8)),
                "lease_contract": _result(_envelope(AgentName.LEASE_CONTRACT, 7, 0.79)),
                "market_macro": AgentResult(status="failed"),
                "lending_affordability": _result(
                    _envelope(
                        AgentName.LENDING_AFFORDABILITY,
                        8,
                        0.84,
                        summary="Bankability looks solid on validated cash flow.",
                        metrics={
                            "adjusted_sde": _metric(355000, unit="usd"),
                            "dscr": _metric(1.47, unit="ratio"),
                            "dscr_meets_minimum": _metric(True),
                            "sde_multiple": _metric(3.2, unit="x"),
                            "eligible_for_sba": _metric(True),
                        },
                    )
                ),
            },
            [],
            "buy",
            39,
            1,
        ),
    ],
)
def test_compute_pipeline_scorecard_matches_selected_fixture_expectations(
    fixture_name: str,
    agent_results: dict[str, AgentResult[AgentEnvelope]],
    missing_inputs: list[MissingInput],
    expected_recommendation: str,
    expected_risk_score: int,
    expected_conflicts: int,
) -> None:
    ingestion_output = _ingestion_output()
    ingestion_output.metadata.missing_inputs = missing_inputs

    scorecard = compute_pipeline_scorecard(ingestion_output, agent_results)

    assert scorecard.overall_recommendation == expected_recommendation, fixture_name
    assert scorecard.overall_risk_score == expected_risk_score, fixture_name
    assert len(scorecard.conflicts) == expected_conflicts, fixture_name
