from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import mimetypes
import re
import shutil
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.agents.mistral_ocr_client import MistralOCRError, ocr_document
from app.core.config import get_settings
from app.core.path_safety import resolve_backend_env_path, safe_child_path, validate_sha256_hex
from app.core.security import protect_expensive_route, record_upload_bytes
from app.services.intake_service import decode_text_content, extract_docx_text, extract_xlsx_workbook
from app.services.section_kind import infer_sheet_kinds

router = APIRouter()

UPLOAD_ROOT = resolve_backend_env_path("BIZBUY_UPLOAD_DIR", default_relative="uploads")
OCR_ARTIFACT_ROOT = resolve_backend_env_path("BIZBUY_ARTIFACT_DIR", default_relative=".artifacts") / "ocr"
OCR_ARTIFACT_REF_PREFIX = "ocr:"
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_PAGES = 1000

_STRUCTURED_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls", ".docx"}
_SAFE_EXTENSION_RE = re.compile(r"^\.[a-z0-9]{1,16}$")
_protect_upload_route = protect_expensive_route("upload")

_MISTRAL_TO_DETECTED_TYPE: dict[str, str] = {
    "pnl_income_statement": "profit_and_loss",
    "balance_sheet": "balance_sheet",
    "cash_flow_statement": "cash_flow_statement",
    "tax_return": "tax_return_1120s",
    "lease_contract": "lease_agreement",
    "ar_aging_report": "ar_aging_report",
    "customer_list": "customer_list",
    "employee_roster": "employee_roster",
    "insurance_policy": "insurance_policy",
    "equipment_list": "equipment_list",
    "bank_statement": "other",
    "business_acquisition_document": "contract",
    "other": "other",
}


class ClassifiedFile(BaseModel):
    file_id: str = Field(..., alias="fileId")
    original_name: str = Field(..., alias="originalName")
    mime_type: str = Field(..., alias="mimeType")
    size_bytes: int = Field(..., alias="sizeBytes")
    detected_type: str = Field(..., alias="detectedType")
    confidence: float
    rationale: str
    suggested_alternatives: list[str] = Field(default_factory=list, alias="suggestedAlternatives")
    extracted_metadata: dict[str, Any] = Field(default_factory=dict, alias="extractedMetadata")
    file_hash: str | None = Field(default=None, alias="fileHash")
    ocr_artifact_ref: str | None = Field(default=None, alias="ocrArtifactRef")
    error: str | None = None

    class Config:
        populate_by_name = True


class IngestResponse(BaseModel):
    run_id: str = Field(..., alias="runId")
    files: list[ClassifiedFile]

    class Config:
        populate_by_name = True


def _guess_mime(filename: str | None) -> str:
    guessed, _ = mimetypes.guess_type(filename or "")
    return guessed or "application/octet-stream"


def _count_pdf_pages(file_bytes: bytes) -> int | None:
    """Return page count for PDFs, None for non-PDFs."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        return len(reader.pages)
    except Exception:
        return None


def _ocr_artifact_path(file_hash: str) -> Path:
    safe_hash = validate_sha256_hex(file_hash)
    return safe_child_path(OCR_ARTIFACT_ROOT, f"{safe_hash}.json")


def _ocr_artifact_ref(file_hash: str) -> str:
    safe_hash = validate_sha256_hex(file_hash)
    return f"{OCR_ARTIFACT_REF_PREFIX}{safe_hash}"


def _safe_storage_filename(file_id: str, original_name: str) -> str:
    suffixes = (
        PurePosixPath(original_name).suffix.lower(),
        PureWindowsPath(original_name).suffix.lower(),
    )
    suffix = next((candidate for candidate in suffixes if _SAFE_EXTENSION_RE.fullmatch(candidate)), "")
    return f"{file_id}{suffix}"


def _max_file_size_bytes() -> int:
    return get_settings().max_upload_file_bytes


def _load_cached_ocr_result(file_hash: str):
    artifact_path = _ocr_artifact_path(file_hash)
    if not artifact_path.exists():
        return None
    try:
        raw = artifact_path.read_text(encoding="utf-8")
        from app.agents.mistral_ocr_client import IngestionResult

        return IngestionResult.model_validate_json(raw)
    except Exception:
        return None


def _save_ocr_result(file_hash: str, result: Any) -> str:
    artifact_path = _ocr_artifact_path(file_hash)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    payload = result.model_dump(mode="json")
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return _ocr_artifact_ref(file_hash)


def _reject_oversized_or_too_many_files(request: Request, files: list[UploadFile]) -> None:
    settings = get_settings()
    if len(files) > settings.max_upload_files:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "too_many_files",
                "detail": f"Upload request includes {len(files)} files (limit: {settings.max_upload_files}).",
                "limit": settings.max_upload_files,
            },
        )

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            request_bytes = int(content_length)
        except ValueError:
            request_bytes = 0
        if request_bytes > settings.max_upload_request_bytes:
            raise HTTPException(
                status_code=413,
                detail={
                    "error": "request_too_large",
                    "detail": "Upload request exceeds the configured byte limit.",
                    "limit_bytes": settings.max_upload_request_bytes,
                },
            )


async def _classify_one(
    upload: UploadFile,
    run_dir: Path,
    loop: asyncio.AbstractEventLoop,
) -> ClassifiedFile:
    file_id = str(uuid4())
    original_name = upload.filename or f"upload_{file_id}"
    mime_type = upload.content_type or _guess_mime(original_name)

    file_bytes = await upload.read()
    size_bytes = len(file_bytes)
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    max_file_size_bytes = _max_file_size_bytes()
    if size_bytes > max_file_size_bytes:
        return ClassifiedFile(
            fileId=file_id,
            originalName=original_name,
            mimeType=mime_type,
            sizeBytes=size_bytes,
            detectedType="unknown",
            confidence=0.0,
            rationale=f"File exceeds {max_file_size_bytes // (1024 * 1024)} MB size limit.",
            suggestedAlternatives=[],
            extractedMetadata={},
            fileHash=file_hash,
            error="file_too_large",
        )

    if mime_type == "application/pdf" or Path(original_name).suffix.lower() == ".pdf":
        page_count = _count_pdf_pages(file_bytes)
        if page_count is not None and page_count > MAX_PAGES:
            return ClassifiedFile(
                fileId=file_id,
                originalName=original_name,
                mimeType=mime_type,
                sizeBytes=size_bytes,
                detectedType="unknown",
                confidence=0.0,
                rationale=f"PDF exceeds {MAX_PAGES} page limit ({page_count} pages).",
                suggestedAlternatives=[],
                extractedMetadata={},
                error="too_many_pages",
                fileHash=file_hash,
            )

    dest = safe_child_path(run_dir, _safe_storage_filename(file_id, original_name))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(file_bytes)

    ext = Path(original_name).suffix.lower()
    structured_fallback: tuple[str, float, str, dict[str, Any]] | None = None
    if ext in _STRUCTURED_EXTENSIONS or mime_type.startswith("text/"):
        structured_fallback = _parse_structured_file(file_bytes, original_name, mime_type)

    try:
        result = _load_cached_ocr_result(file_hash)
        cached = result is not None
        if result is None:
            result = await loop.run_in_executor(None, ocr_document, file_bytes, original_name)
            artifact_ref = _save_ocr_result(file_hash, result)
        else:
            artifact_ref = _ocr_artifact_ref(file_hash)
        detected = _MISTRAL_TO_DETECTED_TYPE.get(
            result.classification.document_type, "other",
        )
        metadata: dict[str, Any] = {
            "businessName": None,
            "periodStart": result.classification.detected_period or None,
            "periodEnd": None,
            "currency": None,
        }
        # Keep spreadsheet metadata (columns/rowCount/sheetCount) when available.
        if structured_fallback is not None:
            for key, value in structured_fallback[3].items():
                if value is not None or key not in metadata:
                    metadata[key] = value

        return ClassifiedFile(
            fileId=file_id,
            originalName=original_name,
            mimeType=mime_type,
            sizeBytes=size_bytes,
            detectedType=detected,
            confidence=result.classification.confidence,
            rationale=("Cached OCR result. " if cached else "") + result.classification.reasoning,
            suggestedAlternatives=[],
            extractedMetadata=metadata,
            fileHash=file_hash,
            ocrArtifactRef=artifact_ref,
        )
    except (MistralOCRError, Exception) as exc:
        if structured_fallback is not None:
            detected_type, confidence, rationale, metadata = structured_fallback
            return ClassifiedFile(
                fileId=file_id,
                originalName=original_name,
                mimeType=mime_type,
                sizeBytes=size_bytes,
                detectedType=detected_type,
                confidence=confidence,
                rationale=f"OCR classification was unavailable. Falling back to structured parser. {rationale}",
                suggestedAlternatives=[],
                extractedMetadata=metadata,
                fileHash=file_hash,
            )

        return ClassifiedFile(
            fileId=file_id,
            originalName=original_name,
            mimeType=mime_type,
            sizeBytes=size_bytes,
            detectedType="unknown",
            confidence=0.0,
            rationale="Classification failed. Try a smaller file or a supported document format.",
            suggestedAlternatives=[],
            extractedMetadata={},
            fileHash=file_hash,
            error="classification_failed",
        )


_KEYWORD_TYPE_RULES: list[tuple[set[str], str]] = [
    ({"customer name", "contract type", "% of total rev"}, "customer_list"),
    ({"customer list", "owner contact"}, "customer_list"),
    ({"asset description", "book value", "fmv"}, "equipment_list"),
    ({"property, plant", "equipment schedule"}, "equipment_list"),
    ({"employee", "technician", "salary"}, "employee_roster"),
    ({"employee", "non-compete"}, "employee_roster"),
    ({"insurance policy", "premium", "coverage"}, "insurance_policy"),
    ({"revenue", "cogs", "net income", "gross profit", "operating expenses"}, "profit_and_loss"),
    ({"revenue", "net income", "ebitda"}, "profit_and_loss"),
    ({"total assets", "total liabilities", "equity"}, "balance_sheet"),
    ({"assets", "liabilities", "owners equity"}, "balance_sheet"),
    ({"operating activities", "investing activities", "financing activities"}, "cash_flow_statement"),
    ({"cash flow", "net cash"}, "cash_flow_statement"),
    ({"taxable income", "tax return", "form 1120"}, "tax_return_1120s"),
    ({"tax return", "schedule c"}, "tax_return_schedule_c"),
    ({"gross receipts", "schedule c"}, "tax_return_schedule_c"),
    ({"current", "30 days", "60 days", "90 days", "aging"}, "ar_aging_report"),
    ({"lease", "rent", "landlord", "tenant"}, "lease_agreement"),
]


def _classify_by_keywords(text: str) -> tuple[str, float]:
    """Classify a structured file by scanning its text for financial keywords.

    Returns (detected_type, confidence).
    """
    lower = text.lower()
    for required_keywords, doc_type in _KEYWORD_TYPE_RULES:
        if all(kw in lower for kw in required_keywords):
            return doc_type, 0.7
    return "other", 0.4


def _empty_extracted_metadata() -> dict[str, Any]:
    return {"businessName": None, "periodStart": None, "periodEnd": None, "currency": None}


def _parse_structured_file(
    file_bytes: bytes, filename: str, mime_type: str,
) -> tuple[str, float, str, dict[str, Any]]:
    """Parse a CSV/TSV/XLSX file and classify it by content.

    Returns (detected_type, confidence, rationale, extracted_metadata).
    """
    ext = Path(filename).suffix.lower()
    text_content = ""
    row_count = 0
    columns: list[str] = []
    sheet_count = 0
    sheet_kinds: list[str] = []

    try:
        if ext in {".csv", ".tsv"} or mime_type.startswith("text/"):
            decoded = decode_text_content(file_bytes)
            text_content = decoded
            delimiter = "\t" if ext == ".tsv" or "tab" in mime_type else ","
            reader = csv.reader(io.StringIO(decoded), delimiter=delimiter)
            rows = list(reader)
            if rows:
                columns = [str(c).strip() for c in rows[0]]
                row_count = len(rows) - 1  # exclude header

        elif ext == ".xlsx" or "spreadsheetml" in mime_type:
            sheets, _notes = extract_xlsx_workbook(file_bytes)
            sheet_count = len(sheets)
            sheet_kinds = infer_sheet_kinds(sheets)
            for sheet in sheets:
                if sheet.get("text"):
                    text_content += sheet["text"] + "\n"
                sheet_rows = sheet.get("rows", [])
                row_count += len(sheet_rows)
                if sheet_rows and not columns:
                    columns = [str(v) for v in sheet_rows[0].values() if v not in {None, ""}]

        elif ext == ".xls":
            text_content = decode_text_content(file_bytes)
        elif ext == ".docx":
            text_content = extract_docx_text(file_bytes)

    except Exception:
        return "other", 0.2, f"Failed to parse {ext} file.", _empty_extracted_metadata()

    if not text_content.strip() and row_count == 0:
        return "other", 0.2, f"File appears empty or could not be parsed ({ext}).", _empty_extracted_metadata()

    combined = " ".join(columns).lower() + " " + text_content.lower()
    detected_type, confidence = _classify_by_keywords(combined)

    parts = [f"Parsed {ext} file"]
    if row_count > 0:
        parts.append(f"with {row_count} data row(s)")
    if columns:
        parts.append(f"columns: {', '.join(columns[:8])}")
    if sheet_count > 1:
        parts.append(f"across {sheet_count} sheet(s)")
    rationale = "; ".join(parts) + "."

    metadata: dict[str, Any] = {
        "businessName": None,
        "periodStart": None,
        "periodEnd": None,
        "currency": None,
    }
    if columns:
        metadata["columns"] = columns[:20]
    if row_count:
        metadata["rowCount"] = row_count
    if sheet_count:
        metadata["sheetCount"] = sheet_count
    if sheet_kinds:
        metadata["sheetKinds"] = sheet_kinds

    return detected_type, confidence, rationale, metadata


@router.post(
    "/documents/ingest",
    response_model=IngestResponse,
    dependencies=[Depends(_protect_upload_route)],
)
async def ingest_documents(
    request: Request,
    files: list[UploadFile] = File(...),
) -> IngestResponse:
    _reject_oversized_or_too_many_files(request, files)
    run_id = str(uuid4())
    run_dir = UPLOAD_ROOT / run_id

    loop = asyncio.get_event_loop()

    semaphore = asyncio.Semaphore(get_settings().max_concurrent_ocr_classifications)

    async def classify_with_limit(upload: UploadFile) -> ClassifiedFile:
        async with semaphore:
            return await _classify_one(upload, run_dir, loop)

    tasks = [classify_with_limit(upload) for upload in files]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    classified: list[ClassifiedFile] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            upload = files[i]
            classified.append(
                ClassifiedFile(
                    fileId=str(uuid4()),
                    originalName=upload.filename or f"upload_{i}",
                    mimeType=upload.content_type or "application/octet-stream",
                    sizeBytes=0,
                    detectedType="unknown",
                    confidence=0.0,
                    rationale="Unexpected error while classifying file.",
                    suggestedAlternatives=[],
                    extractedMetadata={},
                    error="classification_failed",
                )
            )
        else:
            classified.append(result)

    total_bytes = sum(file.size_bytes for file in classified)
    if total_bytes > get_settings().max_upload_request_bytes:
        shutil.rmtree(run_dir, ignore_errors=True)
        raise HTTPException(
            status_code=413,
            detail={
                "error": "request_too_large",
                "detail": "Upload request exceeds the configured byte limit.",
                "limit_bytes": get_settings().max_upload_request_bytes,
            },
        )
    record_upload_bytes(request, total_bytes)
    if get_settings().delete_uploads_after_ingest:
        shutil.rmtree(run_dir, ignore_errors=True)

    return IngestResponse(runId=run_id, files=classified)
