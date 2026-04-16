"""Thin sync client wrapping the Mistral OCR API (mistral-ocr-2512).

Known limitation: one document receives one classification. If a PDF
bundles multiple document types (e.g. P&L + balance sheet in a single
file), only one label is returned. A future multi-section classifier
can split such PDFs, but that is out of scope for this implementation.
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import time
from typing import Any, Literal

from pydantic import BaseModel, Field

MISTRAL_OCR_MODEL = "mistral-ocr-2512"
PER_PAGE_RATE_USD = 0.002
_MIN_OCR_WORD_COUNT = 5
_MIN_OCR_UNIQUE_WORD_RATIO = 0.15


class MistralOCRError(Exception):
    """Wraps Mistral SDK exceptions with enough context for the orchestrator's
    error-metadata layer."""

    def __init__(self, message: str, *, cause: Exception | None = None):
        self.cause = cause
        super().__init__(message)


class DocumentClassification(BaseModel):
    document_type: Literal[
        "pnl_income_statement",
        "balance_sheet",
        "cash_flow_statement",
        "tax_return",
        "lease_contract",
        "ar_aging_report",
        "bank_statement",
        "business_acquisition_document",
        "other",
    ]
    confidence: float = Field(..., ge=0, le=1)
    reasoning: str
    detected_period: str = ""


class PageContent(BaseModel):
    page_number: int  # 1-indexed
    markdown: str
    image_refs: list[str] = Field(default_factory=list)


class IngestionResult(BaseModel):
    filename: str
    file_hash: str  # sha256 of uploaded bytes
    page_count: int
    classification: DocumentClassification
    pages: list[PageContent]
    full_markdown: str  # all pages joined with "\n\n---\n\n"
    ocr_model: str = MISTRAL_OCR_MODEL
    processing_time_ms: int
    cost_usd: float


_client = None


def _ocr_process_options(filename: str) -> dict[str, Any]:
    """Return per-file OCR options for Mistral process calls."""
    options: dict[str, Any] = {"include_image_base64": False}
    # DOCX requests can fail unless images are disabled explicitly.
    if filename.lower().endswith(".docx"):
        options["image_limit"] = 0
    return options


def get_mistral_client():
    """Lazy-initialized Mistral client reading MISTRAL_API_KEY from env."""
    global _client
    if _client is None:
        from mistralai.client import Mistral

        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise MistralOCRError("MISTRAL_API_KEY environment variable not set")
        _client = Mistral(api_key=api_key)
    return _client


def ocr_document(file_bytes: bytes, filename: str) -> IngestionResult:
    """OCR a single document via Mistral OCR.

    All files are sent as inline base64. The upload route caps files at
    50 MB, so inline encoding covers 100 % of valid inputs.

    Uses ``document_annotation_format`` to extract a
    ``DocumentClassification`` alongside the OCR text.
    """
    from mistralai.extra import response_format_from_pydantic_model

    from app.core.config import get_settings

    if get_settings().use_mistral_batch:
        raise NotImplementedError("Batch mode not yet implemented")

    file_hash = hashlib.sha256(file_bytes).hexdigest()
    client = get_mistral_client()
    start_ns = time.perf_counter_ns()

    encoded = base64.b64encode(file_bytes).decode("ascii")
    guessed_mime, _ = mimetypes.guess_type(filename)
    mime = guessed_mime or "application/pdf"

    document = {
        "type": "document_url",
        "document_url": f"data:{mime};base64,{encoded}",
    }
    process_options = _ocr_process_options(filename)

    try:
        response = client.ocr.process(
            model=MISTRAL_OCR_MODEL,
            document=document,
            document_annotation_format=response_format_from_pydantic_model(
                DocumentClassification,
            ),
            **process_options,
        )
    except Exception as exc:
        raise MistralOCRError(
            f"Mistral OCR failed for {filename}: {exc}", cause=exc,
        ) from exc

    elapsed_ms = (time.perf_counter_ns() - start_ns) // 1_000_000

    pages = [
        PageContent(
            page_number=page.index + 1,
            markdown=page.markdown,
            image_refs=[img.id for img in (page.images or [])],
        )
        for page in response.pages
    ]
    full_markdown = "\n\n---\n\n".join(p.markdown for p in pages)

    raw_annotation = response.document_annotation
    if raw_annotation is None:
        classification = DocumentClassification(
            document_type="other",
            confidence=0.0,
            reasoning="Mistral OCR returned no document annotation.",
        )
    elif isinstance(raw_annotation, str):
        classification = DocumentClassification.model_validate(
            json.loads(raw_annotation),
        )
    else:
        classification = DocumentClassification.model_validate(raw_annotation)

    stripped_text = full_markdown.strip()
    words = stripped_text.split() if stripped_text else []
    word_count = len(words)
    unique_ratio = len(set(w.lower() for w in words)) / word_count if word_count else 0.0

    if word_count < _MIN_OCR_WORD_COUNT:
        classification = DocumentClassification(
            document_type="other",
            confidence=0.0,
            reasoning=(
                f"OCR extracted only {word_count} word(s) — below the "
                f"{_MIN_OCR_WORD_COUNT}-word minimum for reliable classification. "
                f"The file may be blank, corrupt, or contain only images without text."
            ),
        )
    elif unique_ratio < _MIN_OCR_UNIQUE_WORD_RATIO:
        classification = DocumentClassification(
            document_type="other",
            confidence=0.0,
            reasoning=(
                f"OCR output appears to be hallucinated: {word_count} words but only "
                f"{unique_ratio:.0%} are unique (threshold: {_MIN_OCR_UNIQUE_WORD_RATIO:.0%}). "
                f"The file may be blank, corrupt, or unreadable."
            ),
        )

    return IngestionResult(
        filename=filename,
        file_hash=file_hash,
        page_count=len(pages),
        classification=classification,
        pages=pages,
        full_markdown=full_markdown,
        processing_time_ms=elapsed_ms,
        cost_usd=len(pages) * PER_PAGE_RATE_USD,
    )
