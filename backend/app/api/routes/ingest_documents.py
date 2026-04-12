from __future__ import annotations

import asyncio
import mimetypes
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, Field

from app.agents.document_classifier import (
    DocumentClassification,
    classify_single_file,
    detected_type_to_document_type,
)

router = APIRouter()

UPLOAD_ROOT = Path(os.getenv("BIZBUY_UPLOAD_DIR", "uploads"))


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

    dest = run_dir / original_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(file_bytes)

    try:
        classification = await loop.run_in_executor(
            None,
            classify_single_file,
            file_bytes,
            original_name,
            mime_type,
        )
        return ClassifiedFile(
            fileId=file_id,
            originalName=original_name,
            mimeType=mime_type,
            sizeBytes=size_bytes,
            detectedType=classification.detected_type,
            confidence=classification.confidence,
            rationale=classification.rationale,
            suggestedAlternatives=classification.suggested_alternatives,
            extractedMetadata=classification.extracted_metadata.model_dump(by_alias=True),
        )
    except Exception as exc:
        return ClassifiedFile(
            fileId=file_id,
            originalName=original_name,
            mimeType=mime_type,
            sizeBytes=size_bytes,
            detectedType="unknown",
            confidence=0.0,
            rationale=f"Classification failed: {exc}",
            suggestedAlternatives=[],
            extractedMetadata={
                "businessName": None,
                "periodStart": None,
                "periodEnd": None,
                "currency": None,
            },
            error=str(exc),
        )


@router.post("/documents/ingest", response_model=IngestResponse)
async def ingest_documents(
    files: list[UploadFile] = File(...),
) -> IngestResponse:
    run_id = str(uuid4())
    run_dir = UPLOAD_ROOT / run_id

    loop = asyncio.get_event_loop()

    tasks = [_classify_one(upload, run_dir, loop) for upload in files]
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
                    rationale=f"Unexpected error: {result}",
                    suggestedAlternatives=[],
                    extractedMetadata={
                        "businessName": None,
                        "periodStart": None,
                        "periodEnd": None,
                        "currency": None,
                    },
                    error=str(result),
                )
            )
        else:
            classified.append(result)

    return IngestResponse(runId=run_id, files=classified)
