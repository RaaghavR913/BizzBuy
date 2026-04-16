from __future__ import annotations

import re
from typing import Any

from app.agents.schemas import DocumentType


def infer_section_kind(
    *,
    document_type: DocumentType | str | None = None,
    section_name: str | None = None,
    raw_text: str | None = None,
    rows: list[dict[str, Any]] | None = None,
) -> str:
    """Infer a lightweight section kind without changing persisted schemas."""
    text = _combined_text(section_name=section_name, raw_text=raw_text, rows=rows)

    if "balance sheet" in text:
        return DocumentType.BALANCE_SHEET.value
    if _has_any(text, "customer list", "% of total rev", "contract type", "owner contact"):
        return DocumentType.CUSTOMER_LIST.value
    if _has_any(text, "property, plant & equipment", "property, plant and equipment", "asset description", "book value", "fmv"):
        return DocumentType.EQUIPMENT_LIST.value
    if _has_any(text, "employee roster", "employee contracts", "employment agreement") or _has_all(text, "employee", "non-compete"):
        return DocumentType.EMPLOYEE_ROSTER.value
    if _has_any(text, "seller's discretionary earnings", "sellers discretionary earnings", "seller discretionary earnings", "sde"):
        return "sde_summary"
    if _has_any(text, "profit and loss", "profit & loss", "p&l", "income statement"):
        return DocumentType.PROFIT_AND_LOSS.value
    if _has_any(text, "schedule c", "gross receipts"):
        return DocumentType.TAX_RETURN_SCHEDULE_C.value
    if "tax return" in text:
        return DocumentType.TAX_RETURN_1120S.value
    if _has_all(text, "lease agreement", "landlord", "tenant") or _has_all(text, "premises", "landlord", "tenant"):
        return DocumentType.LEASE_AGREEMENT.value
    if document_type:
        value = document_type.value if isinstance(document_type, DocumentType) else str(document_type)
        if value != DocumentType.OTHER.value:
            return value

    return DocumentType.OTHER.value


def infer_sheet_kinds(sheets: list[dict[str, Any]]) -> list[str]:
    kinds: list[str] = []
    for sheet in sheets:
        rows = sheet.get("rows") if isinstance(sheet.get("rows"), list) else []
        kind = infer_section_kind(
            section_name=str(sheet.get("name") or ""),
            raw_text=str(sheet.get("text") or ""),
            rows=[row for row in rows if isinstance(row, dict)],
        )
        if kind != DocumentType.OTHER.value and kind not in kinds:
            kinds.append(kind)
    return kinds


def _combined_text(
    *,
    section_name: str | None,
    raw_text: str | None,
    rows: list[dict[str, Any]] | None,
) -> str:
    parts: list[str] = []
    if section_name:
        parts.append(section_name)
    if raw_text:
        parts.append(raw_text)
    for row in rows or []:
        parts.extend(str(value) for key, value in row.items() if key != "row_index" and value not in {None, ""})
    return re.sub(r"\s+", " ", " ".join(parts)).lower()


def _has_any(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def _has_all(text: str, *needles: str) -> bool:
    return all(needle in text for needle in needles)
