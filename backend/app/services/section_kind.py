from __future__ import annotations

import re
from typing import Any

from app.agents.schemas import DocumentType


SECTION_KIND_TO_DOCUMENT_TYPE: dict[str, DocumentType] = {
    DocumentType.PROFIT_AND_LOSS.value: DocumentType.PROFIT_AND_LOSS,
    DocumentType.BALANCE_SHEET.value: DocumentType.BALANCE_SHEET,
    DocumentType.CASH_FLOW_STATEMENT.value: DocumentType.CASH_FLOW_STATEMENT,
    DocumentType.TAX_RETURN_1120S.value: DocumentType.TAX_RETURN_1120S,
    DocumentType.TAX_RETURN_1040.value: DocumentType.TAX_RETURN_1040,
    DocumentType.TAX_RETURN_SCHEDULE_C.value: DocumentType.TAX_RETURN_SCHEDULE_C,
    DocumentType.AR_AGING_REPORT.value: DocumentType.AR_AGING_REPORT,
    DocumentType.CUSTOMER_LIST.value: DocumentType.CUSTOMER_LIST,
    DocumentType.CONTRACT.value: DocumentType.CONTRACT,
    DocumentType.LEASE_AGREEMENT.value: DocumentType.LEASE_AGREEMENT,
    DocumentType.EMPLOYEE_ROSTER.value: DocumentType.EMPLOYEE_ROSTER,
    DocumentType.INSURANCE_POLICY.value: DocumentType.INSURANCE_POLICY,
    DocumentType.EQUIPMENT_LIST.value: DocumentType.EQUIPMENT_LIST,
    "sde_summary": DocumentType.PROFIT_AND_LOSS,
}


SECTION_KIND_ALIASES: dict[str, str] = {
    "income_statement": DocumentType.PROFIT_AND_LOSS.value,
    "profit_and_loss_statement": DocumentType.PROFIT_AND_LOSS.value,
    "pnl": DocumentType.PROFIT_AND_LOSS.value,
    "p&l": DocumentType.PROFIT_AND_LOSS.value,
    "cash_flow": DocumentType.CASH_FLOW_STATEMENT.value,
    "tax_return": DocumentType.TAX_RETURN_1120S.value,
    "tax_returns": DocumentType.TAX_RETURN_1120S.value,
    "ar_aging": DocumentType.AR_AGING_REPORT.value,
    "accounts_receivable_aging": DocumentType.AR_AGING_REPORT.value,
    "seller_discretionary_earnings": "sde_summary",
    "sellers_discretionary_earnings": "sde_summary",
    "seller's_discretionary_earnings": "sde_summary",
    "sde": "sde_summary",
    "ppe": DocumentType.EQUIPMENT_LIST.value,
    "pp_e": DocumentType.EQUIPMENT_LIST.value,
}


def infer_section_kind(
    *,
    document_type: DocumentType | str | None = None,
    section_name: str | None = None,
    raw_text: str | None = None,
    rows: list[dict[str, Any]] | None = None,
) -> str:
    """Infer a lightweight section kind without changing persisted schemas."""
    text = _combined_text(section_name=section_name, raw_text=raw_text, rows=rows)

    if _looks_like_balance_sheet(section_name=section_name, text=text, rows=rows):
        return DocumentType.BALANCE_SHEET.value
    if _has_any(text, "customer list", "% of total rev", "contract type", "owner contact"):
        return DocumentType.CUSTOMER_LIST.value
    if _has_any(text, "property, plant & equipment", "property, plant and equipment", "asset description", "book value", "fmv"):
        return DocumentType.EQUIPMENT_LIST.value
    if _has_any(text, "employee roster", "employee contracts", "employment agreement") or _has_all(text, "employee", "non-compete"):
        return DocumentType.EMPLOYEE_ROSTER.value
    # Income-statement check runs BEFORE SDE: a sheet that contains both "income statement"
    # and "sde reconciliation" (stacked sections) is a P&L, not a pure SDE summary.
    # Deliberately exclude "p&l" abbreviation because it appears in references like
    # "Net Income (from P&L)" inside SDE summary sheets.
    _has_income_signals = _has_any(
        text,
        "profit and loss", "profit & loss statement", "income statement",
        "total revenue", "gross profit", "cost of revenue",
    )
    if _has_income_signals:
        return DocumentType.PROFIT_AND_LOSS.value
    # SDE-only: only tag sde_summary when no income-statement signals are present.
    # "sde" alone is kept here because the income-signal guard above already handles
    # the case where a P&L sheet has an embedded SDE section.
    if _has_any(text, "seller's discretionary earnings", "sellers discretionary earnings", "seller discretionary earnings", "sde reconciliation", "sde"):
        return "sde_summary"
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


def normalize_section_kind(value: Any) -> str:
    if isinstance(value, DocumentType):
        return value.value
    if value is None:
        return DocumentType.OTHER.value

    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return DocumentType.OTHER.value
    normalized = SECTION_KIND_ALIASES.get(normalized, normalized)
    if normalized in SECTION_KIND_TO_DOCUMENT_TYPE or normalized == DocumentType.OTHER.value:
        return normalized
    if normalized in DocumentType._value2member_map_:
        return normalized
    return DocumentType.OTHER.value


def document_type_for_section_kind(
    section_kind: str,
    *,
    fallback: DocumentType,
) -> DocumentType:
    normalized = normalize_section_kind(section_kind)
    if normalized == DocumentType.OTHER.value:
        return fallback
    return SECTION_KIND_TO_DOCUMENT_TYPE.get(normalized, fallback)


def infer_effective_section_identity(
    *,
    parent_document_type: DocumentType,
    explicit_section_kind: str | None = None,
    explicit_document_type: DocumentType | str | None = None,
    section_name: str | None = None,
    raw_text: str | None = None,
    rows: list[dict[str, Any]] | None = None,
) -> tuple[DocumentType, str]:
    section_kind = normalize_section_kind(explicit_section_kind)
    explicit_type = _normalize_document_type(explicit_document_type)

    if section_kind == DocumentType.OTHER.value:
        inferred = infer_section_kind(
            document_type=None,
            section_name=section_name,
            raw_text=raw_text,
            rows=rows,
        )
        section_kind = normalize_section_kind(inferred)

    if section_kind == DocumentType.OTHER.value and explicit_type != DocumentType.OTHER:
        section_kind = explicit_type.value

    if section_kind == DocumentType.OTHER.value:
        return parent_document_type, DocumentType.OTHER.value

    return (
        document_type_for_section_kind(section_kind, fallback=parent_document_type),
        section_kind,
    )


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


def _looks_like_balance_sheet(
    *,
    section_name: str | None,
    text: str,
    rows: list[dict[str, Any]] | None,
) -> bool:
    if section_name and "balance sheet" in section_name.lower():
        return True
    if rows and _has_any(text, "total assets", "total liabilities", "owner's equity", "owners equity", "total equity"):
        return True
    return False


def _normalize_document_type(value: Any) -> DocumentType:
    if isinstance(value, DocumentType):
        return value
    normalized = normalize_section_kind(value)
    if normalized in DocumentType._value2member_map_:
        return DocumentType(normalized)
    return DocumentType.OTHER
