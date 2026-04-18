from __future__ import annotations

import re

from fastapi import UploadFile

from app.agents.schemas import IngestionOutput
from app.models.schemas import DealHints, FinancialData
from app.services.financial_data_extractor import extract_financial_data
from app.services.ingestion_service import ingest_and_persist_intake_documents
from app.services.intake_service import normalize_upload_files


# Business-type inference: map filename / document-type tokens to canonical values.
# The canonical values must match lib/constants.ts BUSINESS_TYPES[].value.
_BUSINESS_TYPE_TOKENS: list[tuple[list[str], str]] = [
    (["hvac", "plumbing", "electrical", "home service", "roofing", "landscaping"], "home_services"),
    (["restaurant", "food", "beverage", "cafe", "bakery", "catering"], "restaurant"),
    (["retail", "store", "shop", "boutique"], "retail"),
    (["ecommerce", "e-commerce", "online store", "amazon", "shopify"], "ecommerce"),
    (["consulting", "accounting", "cpa", "law", "legal", "professional service"], "professional_services"),
    (["medical", "dental", "healthcare", "clinic", "therapy", "physician"], "healthcare"),
    (["auto", "car repair", "mechanic", "automotive", "body shop"], "auto_services"),
    (["gym", "fitness", "yoga", "crossfit", "personal training"], "fitness"),
    (["childcare", "daycare", "preschool", "education", "tutoring"], "childcare"),
    (["manufacturing", "production", "fabrication"], "manufacturing"),
    (["distribution", "logistics", "warehouse", "trucking", "freight"], "distribution"),
    (["construction", "contractor", "builder", "remodeling"], "construction"),
    (["technology", "software", "saas", "it ", "tech", "managed service", "msp"], "technology"),
    (["franchise"], "franchise"),
]


def _infer_business_type(ingestion_output: IngestionOutput) -> str | None:
    """Best-effort business-type inference from filenames and raw text."""
    corpus: list[str] = []
    for document in ingestion_output.documents:
        corpus.append(document.file_name.lower())
        for section in document.sections:
            if section.raw_text:
                corpus.append(section.raw_text[:500].lower())
    combined = " ".join(corpus)
    for tokens, biz_type in _BUSINESS_TYPE_TOKENS:
        if any(tok in combined for tok in tokens):
            return biz_type
    return None


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
    extraction_notes = _actionable_extraction_notes(extracted_financials.parsing_notes)

    # Suppress notes about sections that ended up populated — only surface
    # genuinely missing data so the demo Review page stays clean.
    income_populated = extracted_financials.income_statement is not None and extracted_financials.income_statement.revenue > 0
    balance_populated = extracted_financials.balance_sheet is not None and extracted_financials.balance_sheet.total_assets > 0
    sde_populated = (
        extracted_financials.income_statement is not None
        and extracted_financials.income_statement.sde is not None
    )

    def _is_suppressed_note(note: str) -> bool:
        lower = note.lower()
        if "worksheet xml could not be parsed" in lower:
            return True  # always suppress xlsx parse-failure noise
        if "could not map income statement" in lower and income_populated:
            return True
        if "could not map balance sheet" in lower and balance_populated:
            return True
        if "recovered income statement fields from sde-tagged section" in lower:
            return True  # internal note — suppress from user-facing list
        return False

    filtered_extraction_notes = [n for n in extraction_notes if not _is_suppressed_note(n)]
    parsing_notes.extend(filtered_extraction_notes)

    # Build deal hints for the frontend
    deal_hints = DealHints(
        years_in_operation=extracted_financials.years_in_operation,
        detected_location=extracted_financials.detected_location,
        suggested_business_type=_infer_business_type(ingestion_output),
    )

    financial_data = FinancialData(
        income_statement=extracted_financials.income_statement,
        balance_sheet=extracted_financials.balance_sheet,
        loan_terms=extracted_financials.loan_terms,
        cash_flow=extracted_financials.cash_flow,
        parsing_notes=parsing_notes,
        data_completeness=completeness,
        deal_hints=deal_hints,
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
