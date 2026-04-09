from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, UploadFile

from app.models.schemas import ParseDocumentsResponse
from app.services.document_parser import parse_documents

router = APIRouter()


@router.post("/parse-documents", response_model=ParseDocumentsResponse)
async def parse_documents_route(
    files: list[UploadFile] = File(...),
    file_types: str = Form(default="[]"),
) -> ParseDocumentsResponse:
    parsed_file_types = json.loads(file_types) if file_types else []
    extracted, ingestion_output = await parse_documents(files, parsed_file_types)
    return ParseDocumentsResponse(
        success=True,
        extracted_data=extracted,
        analysis_id=ingestion_output.metadata.analysis_id,
        pipeline_documents=[document.model_dump(mode="json") for document in ingestion_output.documents],
    )
