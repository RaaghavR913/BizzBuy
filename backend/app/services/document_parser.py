from __future__ import annotations

from fastapi import UploadFile

from app.models.schemas import FinancialData


async def parse_documents(files: list[UploadFile], file_types: list[str]) -> FinancialData:
    parsing_notes: list[str] = []

    for index, file in enumerate(files):
        declared_type = file_types[index] if index < len(file_types) else "unknown"
        parsing_notes.append(
            f"Received {file.filename} as {declared_type}. Deterministic analysis is ready; AI document extraction is the next backend phase."
        )

    completeness = 0.0
    if any(file_types):
        completeness = min(0.15 * len(file_types), 0.5)

    return FinancialData(
        income_statement=None,
        balance_sheet=None,
        loan_terms=None,
        cash_flow=None,
        parsing_notes=parsing_notes,
        data_completeness=completeness,
    )
