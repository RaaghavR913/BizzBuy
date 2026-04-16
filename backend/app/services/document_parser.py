from __future__ import annotations

from fastapi import UploadFile

from app.agents.schemas import IngestionOutput
from app.models.schemas import FinancialData
from app.services.financial_data_extractor import extract_financial_data
from app.services.ingestion_service import ingest_and_persist_intake_documents
from app.services.intake_service import normalize_upload_files


async def parse_documents(
    files: list[UploadFile],
    file_types: list[str],
    *,
    file_hashes: list[str] | None = None,
    ocr_artifact_refs: list[str] | None = None,
) -> tuple[FinancialData, IngestionOutput]:
    intake_documents = await normalize_upload_files(
        files,
        file_types,
        file_hashes=file_hashes,
        ocr_artifact_refs=ocr_artifact_refs,
    )
    ingestion_output = ingest_and_persist_intake_documents(intake_documents)

    parsing_notes: list[str] = []
    for document in ingestion_output.documents:
        if document.status.value == "failed":
            parsing_notes.append(f"{document.file_name}: could not be parsed.")
        parsing_notes.extend(_actionable_document_notes(document.notes))

    for missing_input in ingestion_output.metadata.missing_inputs:
        priority = "Required" if missing_input.required else "Optional"
        parsing_notes.append(f"{priority} missing {missing_input.key}: {missing_input.description}")

    for issue in ingestion_output.metadata.failed_artifacts:
        target = issue.file_name or issue.document_id or "document"
        parsing_notes.append(f"{target}: {issue.message}")

    completeness = 0.0
    if ingestion_output.metadata.total_documents:
        completeness = ingestion_output.metadata.successfully_parsed / ingestion_output.metadata.total_documents

    extracted_financials = extract_financial_data(ingestion_output)
    parsing_notes.extend(_actionable_extraction_notes(extracted_financials.parsing_notes))

    financial_data = FinancialData(
        income_statement=extracted_financials.income_statement,
        balance_sheet=extracted_financials.balance_sheet,
        loan_terms=extracted_financials.loan_terms,
        cash_flow=extracted_financials.cash_flow,
        parsing_notes=parsing_notes,
        data_completeness=completeness,
    )
    return financial_data, ingestion_output


def _actionable_document_notes(notes: list[str]) -> list[str]:
    actionable_markers = (
        "could not",
        "failed",
        "missing",
        "no structured text",
        "no extractable content",
    )
    return [
        note
        for note in notes
        if any(marker in note.lower() for marker in actionable_markers)
    ]


def _actionable_extraction_notes(notes: list[str]) -> list[str]:
    actionable_markers = (
        "could not",
        "no spreadsheet rows",
        "missing",
    )
    return [
        note
        for note in notes
        if any(marker in note.lower() for marker in actionable_markers)
    ]
