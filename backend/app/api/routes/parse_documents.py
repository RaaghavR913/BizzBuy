from __future__ import annotations

import io
import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.models.schemas import ParseDocumentsResponse
from app.core.config import get_settings
from app.core.security import protect_expensive_route, record_upload_bytes
from app.services.document_parser import parse_documents

router = APIRouter()

MAX_PAGES = 1000
_protect_parse_route = protect_expensive_route("parse")


def _max_file_size_bytes() -> int:
    return get_settings().max_upload_file_bytes


def _reject_oversized_or_too_many_files(request: Request | None, files: list[UploadFile]) -> None:
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
    content_length = request.headers.get("content-length") if request is not None else None
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


async def _validate_upload(upload: UploadFile) -> bytes:
    """Read upload bytes, reject if too large or too many pages."""
    file_bytes = await upload.read()
    max_file_size_bytes = _max_file_size_bytes()
    if len(file_bytes) > max_file_size_bytes:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "file_too_large",
                "detail": f"{upload.filename} exceeds {max_file_size_bytes // (1024 * 1024)} MB limit.",
                "limit_mb": max_file_size_bytes // (1024 * 1024),
            },
        )
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            page_count = len(PdfReader(io.BytesIO(file_bytes)).pages)
            if page_count > MAX_PAGES:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "too_many_pages",
                        "detail": f"{upload.filename} has {page_count} pages (limit: {MAX_PAGES}).",
                        "limit": MAX_PAGES,
                    },
                )
        except HTTPException:
            raise
        except Exception:
            pass
    await upload.seek(0)
    return file_bytes


def _json_list(raw: str | None, field_name: str) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be valid JSON.") from exc
    if not isinstance(parsed, list):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a JSON array.")
    return parsed


def _ocr_ref_hash(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if candidate.startswith("ocr:"):
        candidate = candidate.removeprefix("ocr:")
    if len(candidate) != 64:
        return None
    if all(char in "0123456789abcdefABCDEF" for char in candidate):
        return candidate.lower()
    return None


def _trusted_ocr_ref_for_hash(refs: list, index: int, file_hash: str) -> str | None:
    if index >= len(refs):
        return None
    ref_hash = _ocr_ref_hash(refs[index])
    if ref_hash == file_hash:
        return f"ocr:{file_hash}"
    return None


@router.post(
    "/parse-documents",
    response_model=ParseDocumentsResponse,
    dependencies=[Depends(_protect_parse_route)],
)
async def parse_documents_route(
    files: list[UploadFile] = File(...),
    file_types: str | None = Form(default=None),
    fileTypes: str | None = Form(default=None),
    file_hashes: str | None = Form(default=None),
    fileHashes: str | None = Form(default=None),
    ocr_artifact_refs: str | None = Form(default=None),
    ocrArtifactRefs: str | None = Form(default=None),
    request: Request = None,
) -> ParseDocumentsResponse:
    _reject_oversized_or_too_many_files(request, files)
    total_bytes = 0
    computed_file_hashes: list[str] = []
    for upload in files:
        file_bytes = await _validate_upload(upload)
        total_bytes += len(file_bytes)
        computed_file_hashes.append(hashlib.sha256(file_bytes).hexdigest())
        if total_bytes > get_settings().max_upload_request_bytes:
            raise HTTPException(
                status_code=413,
                detail={
                    "error": "request_too_large",
                    "detail": "Upload request exceeds the configured byte limit.",
                    "limit_bytes": get_settings().max_upload_request_bytes,
                },
            )
    record_upload_bytes(request, total_bytes)

    raw_file_types = fileTypes if isinstance(fileTypes, str) else file_types
    if not isinstance(raw_file_types, str):
        raw_file_types = None
    parsed_file_types = _json_list(raw_file_types, "fileTypes")

    raw_file_hashes = fileHashes if isinstance(fileHashes, str) else file_hashes
    if not isinstance(raw_file_hashes, str):
        raw_file_hashes = None
    _json_list(raw_file_hashes, "fileHashes")

    raw_ocr_refs = ocrArtifactRefs if isinstance(ocrArtifactRefs, str) else ocr_artifact_refs
    if not isinstance(raw_ocr_refs, str):
        raw_ocr_refs = None
    parsed_ocr_refs = _json_list(raw_ocr_refs, "ocrArtifactRefs")

    trusted_ocr_refs = [
        _trusted_ocr_ref_for_hash(parsed_ocr_refs, index, file_hash)
        for index, file_hash in enumerate(computed_file_hashes)
    ]

    extracted, ingestion_output = await parse_documents(
        files,
        parsed_file_types,
        file_hashes=computed_file_hashes,
        ocr_artifact_refs=trusted_ocr_refs,
    )
    return ParseDocumentsResponse(
        success=True,
        extracted_data=extracted,
        analysis_id=ingestion_output.metadata.analysis_id,
        pipeline_documents=[document.model_dump(mode="json") for document in ingestion_output.documents],
    )
