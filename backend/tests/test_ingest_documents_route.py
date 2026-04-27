from __future__ import annotations

import asyncio
import shutil
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import UploadFile

from app.agents.mistral_ocr_client import (
    DocumentClassification,
    IngestionResult,
    MistralOCRError,
    PageContent,
)
from app.api.routes import ingest_documents as ingest_route


def _workspace_run_dir(name: str) -> Path:
    run_dir = Path(__file__).resolve().parents[1] / ".test-artifacts" / "ingest-documents-route" / name
    shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


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


def test_structured_upload_attempts_ocr_then_falls_back(monkeypatch) -> None:
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
        return await ingest_route._classify_one(upload, _workspace_run_dir("structured-fallback"), asyncio.get_running_loop())

    classified = asyncio.run(_run())

    assert ocr_calls == ["seller-pnl.csv"]
    assert classified.detected_type == "profit_and_loss"
    assert classified.confidence == 0.7
    assert "Falling back to structured parser" in classified.rationale
    assert classified.error is None


def test_structured_upload_merges_sheet_metadata_when_ocr_succeeds(monkeypatch) -> None:
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
        return await ingest_route._classify_one(upload, _workspace_run_dir("structured-ocr-success"), asyncio.get_running_loop())

    classified = asyncio.run(_run())

    assert classified.detected_type == "ar_aging_report"
    assert classified.confidence == 0.82
    assert classified.extracted_metadata["periodStart"] == "2025-Q4"
    assert classified.extracted_metadata["rowCount"] == 1
    assert "columns" in classified.extracted_metadata
    assert classified.file_hash
    assert classified.ocr_artifact_ref
    assert classified.ocr_artifact_ref == f"ocr:{classified.file_hash}"


def test_ocr_result_is_cached_by_file_hash(monkeypatch) -> None:
    cache_root = Path(__file__).resolve().parents[1] / ".test-artifacts" / f"ocr-cache-{uuid4()}"
    shutil.rmtree(cache_root, ignore_errors=True)
    monkeypatch.setattr(ingest_route, "OCR_ARTIFACT_ROOT", cache_root)
    ocr_calls: list[str] = []

    def _fake_ocr(file_bytes: bytes, filename: str) -> IngestionResult:
        ocr_calls.append(filename)
        return IngestionResult(
            filename=filename,
            file_hash="cached-hash",
            page_count=1,
            classification=DocumentClassification(
                document_type="pnl_income_statement",
                confidence=0.9,
                reasoning="Detected by OCR.",
                detected_period="FY 2024",
            ),
            pages=[PageContent(page_number=1, markdown="Revenue 100", image_refs=[])],
            full_markdown="Revenue 100",
            processing_time_ms=12,
            cost_usd=0.002,
        )

    monkeypatch.setattr(ingest_route, "ocr_document", _fake_ocr)

    async def _run(filename: str) -> ingest_route.ClassifiedFile:
        upload = UploadFile(
            filename=filename,
            file=BytesIO(b"Revenue,Net Income\n100,50\n"),
            headers={"content-type": "text/csv"},
        )
        return await ingest_route._classify_one(upload, _workspace_run_dir(filename), asyncio.get_running_loop())

    try:
        first = asyncio.run(_run("first.csv"))
        second = asyncio.run(_run("second.csv"))

        assert ocr_calls == ["first.csv"]
        assert first.detected_type == "profit_and_loss"
        assert second.detected_type == "profit_and_loss"
        assert second.rationale.startswith("Cached OCR result.")
        assert first.ocr_artifact_ref == second.ocr_artifact_ref
        assert first.ocr_artifact_ref == f"ocr:{first.file_hash}"
    finally:
        shutil.rmtree(cache_root, ignore_errors=True)


def test_docx_upload_attempts_ocr_then_falls_back(monkeypatch) -> None:
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
        return await ingest_route._classify_one(upload, _workspace_run_dir("docx-fallback"), asyncio.get_running_loop())

    classified = asyncio.run(_run())

    assert ocr_calls == ["seller-summary.docx"]
    assert classified.detected_type == "profit_and_loss"
    assert classified.confidence == 0.7
    assert "Falling back to structured parser" in classified.rationale
    assert classified.error is None


def test_upload_filename_traversal_is_not_used_for_storage(monkeypatch, tmp_path) -> None:
    def _raise_ocr_error(_file_bytes: bytes, filename: str) -> IngestionResult:
        assert filename == "../../escape.txt"
        raise MistralOCRError("unsupported mime")

    monkeypatch.setattr(ingest_route, "ocr_document", _raise_ocr_error)

    run_dir = tmp_path / "uploads" / "run"
    upload = UploadFile(
        filename="../../escape.txt",
        file=BytesIO(b"Revenue,Net Income,EBITDA\n100,50,30\n"),
        headers={"content-type": "text/csv"},
    )

    async def _run() -> ingest_route.ClassifiedFile:
        return await ingest_route._classify_one(upload, run_dir, asyncio.get_running_loop())

    classified = asyncio.run(_run())

    assert classified.original_name == "../../escape.txt"
    assert classified.detected_type == "profit_and_loss"
    assert not (tmp_path / "escape.txt").exists()
    stored_files = list(run_dir.iterdir())
    assert len(stored_files) == 1
    assert stored_files[0].name.endswith(".txt")


def test_upload_backslash_traversal_is_not_used_for_storage(monkeypatch, tmp_path) -> None:
    def _raise_ocr_error(_file_bytes: bytes, filename: str) -> IngestionResult:
        assert filename == r"..\..\escape.csv"
        raise MistralOCRError("unsupported mime")

    monkeypatch.setattr(ingest_route, "ocr_document", _raise_ocr_error)

    run_dir = tmp_path / "uploads" / "run"
    upload = UploadFile(
        filename=r"..\..\escape.csv",
        file=BytesIO(b"Revenue,Net Income,EBITDA\n100,50,30\n"),
        headers={"content-type": "text/csv"},
    )

    async def _run() -> ingest_route.ClassifiedFile:
        return await ingest_route._classify_one(upload, run_dir, asyncio.get_running_loop())

    classified = asyncio.run(_run())

    assert classified.detected_type == "profit_and_loss"
    assert not (tmp_path / "escape.csv").exists()
    stored_files = list(run_dir.iterdir())
    assert len(stored_files) == 1
    assert stored_files[0].name.endswith(".csv")


def test_absolute_upload_filename_is_not_used_for_storage(monkeypatch, tmp_path) -> None:
    def _raise_ocr_error(_file_bytes: bytes, filename: str) -> IngestionResult:
        assert filename == "/tmp/escape.csv"
        raise MistralOCRError("unsupported mime")

    monkeypatch.setattr(ingest_route, "ocr_document", _raise_ocr_error)

    run_dir = tmp_path / "uploads" / "run"
    upload = UploadFile(
        filename="/tmp/escape.csv",
        file=BytesIO(b"Revenue,Net Income,EBITDA\n100,50,30\n"),
        headers={"content-type": "text/csv"},
    )

    async def _run() -> ingest_route.ClassifiedFile:
        return await ingest_route._classify_one(upload, run_dir, asyncio.get_running_loop())

    classified = asyncio.run(_run())

    assert classified.detected_type == "profit_and_loss"
    assert not Path("/tmp/escape.csv").exists()
    stored_files = list(run_dir.iterdir())
    assert len(stored_files) == 1
    assert stored_files[0].name.endswith(".csv")
