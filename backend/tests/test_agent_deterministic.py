from __future__ import annotations

from types import SimpleNamespace

from app.agents.deterministic import (
    compute_ar_metrics,
    compute_customer_metrics,
    compute_financial_metrics,
    compute_sba_lending,
    compute_synthesis_metrics,
    compute_tax_metrics,
)
from app.agents.schemas import (
    AgentResult,
    DocumentInfo,
    DocumentSection,
    DocumentType,
    IngestionMetadata,
    IngestionOutput,
    Severity,
    Timeframe,
)


def make_section(
    document_id: str,
    document_type: DocumentType,
    fiscal_year: int | None,
    extracted_data: dict,
    raw_text: str = "",
) -> DocumentSection:
    return DocumentSection(
        document_id=document_id,
        document_type=document_type,
        timeframe=Timeframe(fiscal_year=fiscal_year),
        extracted_data=extracted_data,
        raw_text=raw_text,
        confidence=0.9,
    )


def make_ingestion_output(documents: list[DocumentInfo]) -> IngestionOutput:
    return IngestionOutput(
        documents=documents,
        metadata=IngestionMetadata(
            total_documents=len(documents),
            successfully_parsed=len(documents),
            failed_documents=[],
            warnings=[],
        ),
    )


def test_compute_financial_metrics_uses_deterministic_backend_math() -> None:
    sections = [
        make_section("pl-2023", DocumentType.PROFIT_AND_LOSS, 2023, {"revenue": 1000, "cogs": 500, "net_income": 80}),
        make_section(
            "pl-2024",
            DocumentType.PROFIT_AND_LOSS,
            2024,
            {
                "revenue": 1200,
                "cogs": 600,
                "net_income": 100,
                "depreciation": 10,
                "interest_expense": 5,
                "income_tax": 15,
                "owner_salary": 40,
                "owner_benefits": 10,
                "one_time_expenses": 5,
                "operating_expenses": 450,
            },
        ),
        make_section(
            "bs-2024",
            DocumentType.BALANCE_SHEET,
            2024,
            {"current_assets": 300, "current_liabilities": 120, "total_assets": 900, "total_liabilities": 400, "equity": 500},
        ),
        make_section(
            "cf-2024",
            DocumentType.CASH_FLOW_STATEMENT,
            2024,
            {"operating_cash_flow": 130, "capital_expenditures": -20},
        ),
    ]

    metrics = compute_financial_metrics(sections)

    assert metrics["data_years_available"] == 2
    assert metrics["revenue_growth_rates"][0]["rate"] == 0.2
    assert metrics["gross_margin"] == 0.5
    assert metrics["net_margin"] == 100 / 1200
    assert metrics["ebitda_margin"] == 130 / 1200
    assert metrics["working_capital"] == 180
    assert metrics["cash_flow"]["free_cash_flow"] == 110
    assert metrics["cash_flow_vs_net_income_divergence"] == 0.3
    assert metrics["sde"]["sde"] == 170


def test_compute_tax_metrics_detects_revenue_discrepancy() -> None:
    sections = [
        make_section("pl-2024", DocumentType.PROFIT_AND_LOSS, 2024, {"revenue": 1200}),
        make_section("pl-2023", DocumentType.PROFIT_AND_LOSS, 2023, {"revenue": 1000}),
        make_section("tax-2024", DocumentType.TAX_RETURN_1120S, 2024, {"gross_receipts": 1000}),
        make_section("tax-2023", DocumentType.TAX_RETURN_1120S, 2023, {"gross_receipts": 1000}),
    ]

    metrics = compute_tax_metrics(sections)

    assert metrics["has_tax_returns"] is True
    assert metrics["year_coverage"]["overlapping_years"] == [2023, 2024]
    discrepancy_2024 = next(item for item in metrics["revenue_discrepancies"] if item["year"] == 2024)
    assert discrepancy_2024["absolute_discrepancy"] == 200
    assert round(discrepancy_2024["percentage_discrepancy"], 4) == round(200 / 1200, 4)
    assert discrepancy_2024["flagged"] is True


def test_compute_ar_metrics_calculates_dso_and_write_off_risk() -> None:
    sections = [
        make_section(
            "ar-1",
            DocumentType.AR_AGING_REPORT,
            2024,
            {
                "current": 50,
                "30_days": 25,
                "60_days": 15,
                "90_days": 5,
                "over_90": 5,
                "customers": [
                    {"id": "c1", "name": "Alpha", "total": 60},
                    {"id": "c2", "name": "Beta", "total": 30},
                    {"id": "c3", "name": "Gamma", "total": 10},
                ],
            },
        ),
        make_section("pl-2024", DocumentType.PROFIT_AND_LOSS, 2024, {"revenue": 1200}),
    ]

    metrics = compute_ar_metrics(sections)

    assert metrics["total_ar"] == 100
    assert round(metrics["dso"], 2) == round((100 / 1200) * 365, 2)
    assert metrics["top_customer_percent"] == 0.6
    assert metrics["top5_customers_percent"] == 1.0
    assert metrics["estimated_write_off_amount"] == 7.0
    assert metrics["estimated_write_off_percent"] == 0.07


def test_compute_customer_metrics_calculates_hhi() -> None:
    ingestion = make_ingestion_output(
        [
            DocumentInfo(
                document_id="cust-1",
                file_name="customers.csv",
                mime_type="text/csv",
                document_type=DocumentType.CUSTOMER_LIST,
                sections=[
                    make_section(
                        "cust-1",
                        DocumentType.CUSTOMER_LIST,
                        2024,
                        {"customers": [{"name": "A", "annualRevenue": 500}, {"name": "B", "annualRevenue": 300}, {"name": "C", "annualRevenue": 200}]},
                    )
                ],
            )
        ]
    )

    metrics = compute_customer_metrics(ingestion)

    assert metrics["total_revenue"] == 1000
    assert metrics["top_customer_percent"] == 50
    assert metrics["top5_percent"] == 100
    assert metrics["herfindahl_index"] == 3800
    assert metrics["single_customer_dependency"] is True


def test_compute_sba_lending_returns_bankability_metrics() -> None:
    metrics = compute_sba_lending(300000, 900000)

    assert metrics["loan_amount"] == 720000
    assert metrics["dscr_meets_minimum"] is True
    assert metrics["suggested_price_range"] == {"low": 750000, "high": 1050000}
    assert metrics["total_cash_needed"]["down_payment"] == 180000
    assert len(metrics["down_payment_scenarios"]) == 3


def test_compute_synthesis_metrics_uses_weighted_scores_and_flags() -> None:
    high_risk = SimpleNamespace(id="risk-1", severity=Severity.HIGH, title="High Risk", description="Important risk", financial_impact=50000)
    financial_result = AgentResult(status="success", data=SimpleNamespace(overall_score=8, summary="Financially solid", risks=[high_risk]))
    tax_result = AgentResult(status="success", data=SimpleNamespace(overall_score=6, summary="Tax has issues", compliance_flags=[]))

    metrics = compute_synthesis_metrics(
        {
            "financial_analysis": financial_result,
            "tax_compliance": tax_result,
        }
    )

    assert metrics["composite_score"] == 36
    assert metrics["completeness"] == 0.25
    assert metrics["red_flags"][0]["title"] == "High Risk"
    assert metrics["green_flags"][0]["title"] == "Financial Analysis - Strong"
    assert "financial_analysis" in metrics["successful_agents"]
    assert "customer_concentration" in metrics["failed_agents"]
