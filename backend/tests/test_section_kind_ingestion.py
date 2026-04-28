from __future__ import annotations

from app.agents.deterministic import compute_customer_metrics, compute_financial_metrics, compute_ops_metrics
from app.agents.schemas import DocumentInfo, DocumentSection, DocumentType, IngestionMetadata, IngestionOutput, Timeframe
from app.services.financial_data_extractor import extract_financial_data
from app.services.ingestion_service import ingest_document_payloads


def _section(
    document_id: str,
    document_type: DocumentType,
    extracted_data: dict,
    *,
    section_kind: str | None = None,
    section_name: str | None = None,
    fiscal_year: int | None = 2024,
) -> DocumentSection:
    return DocumentSection(
        document_id=document_id,
        document_type=document_type,
        section_kind=section_kind,
        timeframe=Timeframe(fiscal_year=fiscal_year),
        extracted_data=extracted_data,
        raw_text="",
        confidence=0.9,
        section_name=section_name,
    )


def _ingestion_output(documents: list[DocumentInfo]) -> IngestionOutput:
    return IngestionOutput(
        documents=documents,
        metadata=IngestionMetadata(
            total_documents=len(documents),
            successfully_parsed=len(documents),
            failed_documents=[],
            warnings=[],
        ),
    )


def test_document_section_section_kind_round_trips_through_schema() -> None:
    section = _section(
        "doc-1",
        DocumentType.BALANCE_SHEET,
        {"total_assets": 313300},
        section_kind="balance_sheet",
        section_name="Balance Sheet",
    )

    payload = section.model_dump(mode="json")
    restored = DocumentSection.model_validate(payload)

    assert payload["section_kind"] == "balance_sheet"
    assert restored.section_kind == "balance_sheet"
    assert restored.document_type == DocumentType.BALANCE_SHEET


def test_document_payload_round_trip_preserves_section_identity() -> None:
    output = ingest_document_payloads(
        [
            {
                "id": "financials-1",
                "fileName": "Financials.xlsx",
                "documentType": "profit_and_loss",
                "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "sections": [
                    {
                        "sectionId": "financials-1:sheet-1",
                        "sectionName": "Balance Sheet",
                        "document_type": "balance_sheet",
                        "section_kind": "balance_sheet",
                        "extracted_data": {"total_assets": 313300},
                        "raw_text": "",
                        "confidence": 0.9,
                    }
                ],
            }
        ]
    )

    section = output.documents[0].sections[0]

    assert output.documents[0].document_type == DocumentType.PROFIT_AND_LOSS
    assert section.document_type == DocumentType.BALANCE_SHEET
    assert section.section_kind == "balance_sheet"


def test_financial_metrics_use_section_identity_inside_one_parent_workbook() -> None:
    sections = [
        _section(
            "financials-1",
            DocumentType.PROFIT_AND_LOSS,
            {"revenue": 983000, "cogs": 520990, "gross_profit": 462010, "net_income": 102904},
            section_kind="profit_and_loss",
            section_name="P&L Statement",
        ),
        _section(
            "financials-1",
            DocumentType.BALANCE_SHEET,
            {"current_assets": 173500, "current_liabilities": 69000, "total_assets": 313300, "total_liabilities": 174000, "equity": 139300},
            section_kind="balance_sheet",
            section_name="Balance Sheet",
        ),
        _section(
            "financials-1",
            DocumentType.PROFIT_AND_LOSS,
            {"sde": 346045, "interest_expense": 5880, "owner_salary": 172000, "depreciation_amortization": 18000},
            section_kind="sde_summary",
            section_name="SDE Summary",
        ),
    ]

    metrics = compute_financial_metrics(sections)

    assert metrics["data_years_available"] == 1
    assert metrics["most_recent_year"]["revenue"] == 983000
    assert metrics["balance_sheet"]["total_assets"] == 313300
    assert metrics["working_capital"] == 104500
    assert metrics["sde"]["sde"] == 298784
    assert "sde_summary" in metrics["document_types"]


def test_review_financial_extractor_falls_back_when_section_kind_is_other() -> None:
    ingestion = _ingestion_output(
        [
            DocumentInfo(
                document_id="financials-1",
                file_name="Financials.xlsx",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                document_type=DocumentType.PROFIT_AND_LOSS,
                sections=[
                    _section(
                        "financials-1",
                        DocumentType.PROFIT_AND_LOSS,
                        {
                            "rows": [
                                {"row_index": 1, "A": "", "B": "FY 2024"},
                                {"row_index": 2, "A": "Total Revenue", "B": "983000"},
                                {"row_index": 3, "A": "Total Cost of Revenue", "B": "520990"},
                                {"row_index": 4, "A": "Gross Profit", "B": "462010"},
                                {"row_index": 5, "A": "Total Operating Expenses", "B": "359106"},
                                {"row_index": 6, "A": "Net Income", "B": "102904"},
                            ]
                        },
                        section_kind="other",
                        section_name="P&L Statement",
                    )
                ],
            )
        ]
    )

    extracted = extract_financial_data(ingestion)

    assert extracted.income_statement is not None
    assert extracted.income_statement.revenue == 983000
    assert extracted.income_statement.net_income == 102904


def test_extractor_uses_explicit_docx_deal_table_asking_price() -> None:
    output = ingest_document_payloads(
        [
            {
                "id": "cim-1",
                "fileName": "CIM_Alpine.docx",
                "documentType": "contract",
                "sections": [
                    {
                        "sectionId": "cim-1:table-1",
                        "sectionName": "Transaction Details",
                        "extractedData": {
                            "rows": [
                                {"row_index": 1, "A": "Asking Price", "B": "$1,300,000"},
                                {"row_index": 2, "A": "Structure", "B": "Asset sale"},
                            ]
                        },
                        "rawText": "Asking Price | $1,300,000\nStructure | Asset sale",
                        "confidence": 0.9,
                    }
                ],
            }
        ]
    )

    extracted = extract_financial_data(output)

    assert extracted.loan_terms is not None
    assert extracted.loan_terms.asking_price == 1_300_000
    assert extracted.loan_terms.asking_price_estimated is False


def test_customer_and_equipment_sections_from_one_workbook_feed_different_metrics() -> None:
    ingestion = _ingestion_output(
        [
            DocumentInfo(
                document_id="customers-equipment-1",
                file_name="Customers_PPE.xlsx",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                document_type=DocumentType.CUSTOMER_LIST,
                sections=[
                    _section(
                        "customers-equipment-1",
                        DocumentType.CUSTOMER_LIST,
                        {"customers": [{"name": "Alpha Co", "annualRevenue": 700}, {"name": "Beta Co", "annualRevenue": 300}]},
                        section_kind="customer_list",
                        section_name="Customer List",
                    ),
                    _section(
                        "customers-equipment-1",
                        DocumentType.EQUIPMENT_LIST,
                        {"equipment": [{"name": "Truck", "estimatedValue": 50000}]},
                        section_kind="equipment_list",
                        section_name="PP&E Schedule",
                    ),
                ],
            )
        ]
    )

    customer_metrics = compute_customer_metrics(ingestion)
    ops_metrics = compute_ops_metrics(ingestion)

    assert customer_metrics["total_revenue"] == 1000
    assert customer_metrics["top_customer_percent"] == 70
    assert ops_metrics["total_equipment_value"] == 50000
    assert ops_metrics["has_operational_docs"] is True
