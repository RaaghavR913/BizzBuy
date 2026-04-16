from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import UploadFile

from app.agents.mistral_ocr_client import (
    DocumentClassification,
    IngestionResult,
    MistralOCRError,
    PageContent,
)
from app.api.routes import ingest_documents as ingest_route


def _build_docx_bytes(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>" for paragraph in paragraphs)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body>"
        "</w:document>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )

    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", rels_xml)
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def test_structured_upload_attempts_ocr_then_falls_back(monkeypatch, tmp_path: Path) -> None:
    ocr_calls: list[str] = []

    def _raise_ocr_error(_file_bytes: bytes, filename: str) -> IngestionResult:
        ocr_calls.append(filename)
        raise MistralOCRError("unsupported mime")

    monkeypatch.setattr(ingest_route, "ocr_document", _raise_ocr_error)

    upload = UploadFile(
        filename="seller-pnl.csv",
        file=BytesIO(b"Revenue,Net Income,EBITDA\n100,50,30\n"),
        headers={"content-type": "text/csv"},
    )

    async def _run() -> ingest_route.ClassifiedFile:
        return await ingest_route._classify_one(upload, tmp_path, asyncio.get_running_loop())

    classified = asyncio.run(_run())

    assert ocr_calls == ["seller-pnl.csv"]
    assert classified.detected_type == "profit_and_loss"
    assert classified.confidence == 0.7
    assert "Falling back to structured parser" in classified.rationale
    assert classified.error is None


def test_structured_upload_merges_sheet_metadata_when_ocr_succeeds(monkeypatch, tmp_path: Path) -> None:
    def _fake_ocr(_file_bytes: bytes, filename: str) -> IngestionResult:
        return IngestionResult(
            filename=filename,
            file_hash="abc123",
            page_count=1,
            classification=DocumentClassification(
                document_type="ar_aging_report",
                confidence=0.82,
                reasoning="Detected by OCR layout and labels.",
                detected_period="2025-Q4",
            ),
            pages=[PageContent(page_number=1, markdown="stub markdown", image_refs=[])],
            full_markdown="stub markdown",
            processing_time_ms=12,
            cost_usd=0.002,
        )

    monkeypatch.setattr(ingest_route, "ocr_document", _fake_ocr)

    upload = UploadFile(
        filename="aging.csv",
        file=BytesIO(b"Customer,Current,30 days,60 days,90 days\nACME,100,50,20,10\n"),
        headers={"content-type": "text/csv"},
    )

    async def _run() -> ingest_route.ClassifiedFile:
        return await ingest_route._classify_one(upload, tmp_path, asyncio.get_running_loop())

    classified = asyncio.run(_run())

    assert classified.detected_type == "ar_aging_report"
    assert classified.confidence == 0.82
    assert classified.extracted_metadata["periodStart"] == "2025-Q4"
    assert classified.extracted_metadata["rowCount"] == 1
    assert "columns" in classified.extracted_metadata


def test_docx_upload_attempts_ocr_then_falls_back(monkeypatch, tmp_path: Path) -> None:
    ocr_calls: list[str] = []

    def _raise_ocr_error(_file_bytes: bytes, filename: str) -> IngestionResult:
        ocr_calls.append(filename)
        raise MistralOCRError("unsupported mime")

    monkeypatch.setattr(ingest_route, "ocr_document", _raise_ocr_error)

    upload = UploadFile(
        filename="seller-summary.docx",
        file=BytesIO(_build_docx_bytes(["Revenue 1200000", "Net income 200000", "EBITDA 240000"])),
        headers={"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    )

    async def _run() -> ingest_route.ClassifiedFile:
        return await ingest_route._classify_one(upload, tmp_path, asyncio.get_running_loop())

    classified = asyncio.run(_run())

    assert ocr_calls == ["seller-summary.docx"]
    assert classified.detected_type == "profit_and_loss"
    assert classified.confidence == 0.7
    assert "Falling back to structured parser" in classified.rationale
    assert classified.error is None
