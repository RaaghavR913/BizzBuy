from __future__ import annotations

from app.agents.runners import _classify_file_route


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
