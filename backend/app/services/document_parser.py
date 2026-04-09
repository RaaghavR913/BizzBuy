from __future__ import annotations

from fastapi import UploadFile

from app.agents.schemas import IngestionOutput
from app.models.schemas import FinancialData
from app.services.ingestion_service import ingest_and_persist_intake_documents
from app.services.intake_service import normalize_upload_files


async def parse_documents(files: list[UploadFile], file_types: list[str]) -> tuple[FinancialData, IngestionOutput]:
    intake_documents = await normalize_upload_files(files, file_types)
    ingestion_output = ingest_and_persist_intake_documents(intake_documents)

    parsing_notes: list[str] = []
    for document in ingestion_output.documents:
        parsing_notes.append(
            f"{document.file_name}: {document.status.value} as {document.canonical_type.value} with {len(document.sections)} section(s)."
        )
        parsing_notes.extend(document.notes)

    for missing_input in ingestion_output.metadata.missing_inputs:
        parsing_notes.append(f"Missing {missing_input.key}: {missing_input.description}")

    for issue in ingestion_output.metadata.failed_artifacts:
        target = issue.file_name or issue.document_id or "document"
        parsing_notes.append(f"{target}: {issue.message}")

    completeness = 0.0
    if ingestion_output.metadata.total_documents:
        completeness = ingestion_output.metadata.successfully_parsed / ingestion_output.metadata.total_documents

    financial_data = FinancialData(
        income_statement=None,
        balance_sheet=None,
        loan_terms=None,
        cash_flow=None,
        parsing_notes=parsing_notes,
        data_completeness=completeness,
    )
    return financial_data, ingestion_output
