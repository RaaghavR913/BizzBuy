from __future__ import annotations

from app.agents.mistral_ocr_client import _ocr_process_options


def test_docx_ocr_process_options_disable_images() -> None:
    options = _ocr_process_options("seller-summary.docx")

    assert options["include_image_base64"] is False
    assert options["image_limit"] == 0


def test_pdf_ocr_process_options_keep_default_image_behavior() -> None:
    options = _ocr_process_options("financials.pdf")

    assert options["include_image_base64"] is False
    assert "image_limit" not in options
