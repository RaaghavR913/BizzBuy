from __future__ import annotations

import io
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.models.schemas import ParseDocumentsResponse
from app.core.security import protect_expensive_route, record_upload_bytes
from app.services.document_parser import parse_documents

router = APIRouter()

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_PAGES = 1000
_protect_parse_route = protect_expensive_route("parse")


async def _validate_upload(upload: UploadFile) -> bytes:
    """Read upload bytes, reject if too large or too many pages."""
    file_bytes = await upload.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "file_too_large",
                "detail": f"{upload.filename} exceeds {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB limit.",
                "limit_mb": MAX_FILE_SIZE_BYTES // (1024 * 1024),
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
    total_bytes = 0
    for upload in files:
        total_bytes += len(await _validate_upload(upload))
    record_upload_bytes(request, total_bytes)

    raw_file_types = fileTypes if isinstance(fileTypes, str) else file_types
    if not isinstance(raw_file_types, str):
        raw_file_types = None
    parsed_file_types = _json_list(raw_file_types, "fileTypes")

    raw_file_hashes = fileHashes if isinstance(fileHashes, str) else file_hashes
    if not isinstance(raw_file_hashes, str):
        raw_file_hashes = None
    parsed_file_hashes = _json_list(raw_file_hashes, "fileHashes")

    raw_ocr_refs = ocrArtifactRefs if isinstance(ocrArtifactRefs, str) else ocr_artifact_refs
    if not isinstance(raw_ocr_refs, str):
        raw_ocr_refs = None
    parsed_ocr_refs = _json_list(raw_ocr_refs, "ocrArtifactRefs")

    extracted, ingestion_output = await parse_documents(
        files,
        parsed_file_types,
        file_hashes=parsed_file_hashes,
        ocr_artifact_refs=parsed_ocr_refs,
    )
    return ParseDocumentsResponse(
        success=True,
        extracted_data=extracted,
        analysis_id=ingestion_output.metadata.analysis_id,
        pipeline_documents=[document.model_dump(mode="json") for document in ingestion_output.documents],
    )
