from __future__ import annotations

from unittest.mock import patch

from app.agents.runners import _classify_file_route, run_document_ingestion


def test_classify_file_route_supports_pdf() -> None:
    assert _classify_file_route("financials.pdf", "application/pdf") == "ocr"


def test_classify_file_route_supports_docx() -> None:
    assert (
        _classify_file_route(
            "seller-summary.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        == "structured"
    )


def test_run_document_ingestion_reuses_sections_no_ocr() -> None:
    """A doc payload with non-empty sections must NOT trigger ocr_document."""
    doc_with_sections = {
        "document_id": "test-doc",
        "file_name": "financials.pdf",
        "mime_type": "application/pdf",
        "document_type": "profit_and_loss",
        "sections": [
            {
                "section_id": "s1",
                "document_id": "test-doc",
                "document_type": "profit_and_loss",
                "section_kind": "profit_and_loss",
                "section_name": "Income Statement",
                "raw_text": "| Line Item | 2024 |\n| Total Revenue | 2410000 |",
                "extracted_data": {
                    "rows": [
                        {"row_index": 1, "A": "Line Item", "B": "2024"},
                        {"row_index": 2, "A": "Total Revenue", "B": "2410000"},
                    ]
                },
                "confidence": 0.95,
                "notes": [],
                "timeframe": None,
            }
        ],
    }

    with patch("app.agents.runners.ocr_document") as mock_ocr:
        result = run_document_ingestion([doc_with_sections])
        mock_ocr.assert_not_called()

    assert result.status == "success"
    assert result.data is not None
    assert len(result.data.documents) == 1


def test_run_document_ingestion_calls_ocr_when_no_sections() -> None:
    """A PDF payload with raw content and no sections must call ocr_document."""
    import base64
    from app.agents.mistral_ocr_client import IngestionResult, DocumentClassification, PageContent

    dummy_result = IngestionResult(
        filename="test.pdf",
        file_hash="abc",
        page_count=1,
        classification=DocumentClassification(
            document_type="other", confidence=0.5, reasoning="test"
        ),
        pages=[PageContent(page_number=1, markdown="Hello")],
        full_markdown="Hello",
        processing_time_ms=100,
        cost_usd=0.002,
    )

    doc_without_sections = {
        "document_id": "test-doc-2",
        "file_name": "financials.pdf",
        "mime_type": "application/pdf",
        "document_type": "profit_and_loss",
        "sections": [],
        "content": base64.b64encode(b"%PDF-1.4 fake").decode(),
    }

    with patch("app.agents.runners.ocr_document", return_value=dummy_result):
        result = run_document_ingestion([doc_without_sections])

    assert result.status == "success"
