"""Convert Mistral OCR markdown output into structured section dicts.

Mistral OCR returns pipe-delimited markdown tables. This module parses those
tables into the ``{"row_index": N, "A": label, "B": col1, ...}`` row format
that ``_row_table`` / ``_year_columns`` in financial_data_extractor.py
already understands, so the rest of the extraction pipeline works unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.agents.schemas import DocumentType
from app.services.section_kind import infer_section_kind


def _col_letter(n: int) -> str:
    """Convert 1-based column index to spreadsheet column letter (A, B, ..., Z, AA, ...)."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


@dataclass
class ParsedTable:
    rows: list[dict[str, Any]]
    raw_lines: list[str] = field(default_factory=list)

    @property
    def raw_text(self) -> str:
        return "\n".join(self.raw_lines)


def _parse_pipe_row(line: str) -> list[str]:
    """Split a markdown table row on ``|`` separators, stripping outer pipes."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    """Return True for markdown separator rows like ``| --- | --- |``."""
    has_dash = False
    for cell in cells:
        text = cell.strip()
        if not text:
            continue
        if re.fullmatch(r":?-{2,}:?", text):
            has_dash = True
        else:
            return False
    return has_dash


def _is_banner_row(cells: list[str]) -> bool:
    """Return True for Mistral banner rows.

    Mistral often emits a first row like:
    ``| Alpine IT Solutions LLC — Income Statement | | | | |``
    whose only non-empty cell contains an em-dash or en-dash.
    """
    non_empty = [c for c in cells if c]
    if len(non_empty) == 1 and (" \u2014 " in non_empty[0] or " \u2013 " in non_empty[0]):
        return True
    return False


def _row_cells(row: dict[str, Any]) -> list[str]:
    """Extract cell values from a row dict in ascending column order."""
    cells: list[str] = []
    i = 1
    while True:
        col = _col_letter(i)
        if col not in row:
            break
        val = row.get(col)
        cells.append(str(val).strip() if val is not None else "")
        i += 1
    return cells


def _is_section_header_row(cells: list[str]) -> bool:
    """Return True when only the first cell has content (visual section header).

    Example: ``| SDE RECONCILIATION |  |  |  |  |``
    """
    if not cells or not cells[0]:
        return False
    return all(not c for c in cells[1:])


def _build_table(lines: list[str]) -> ParsedTable:
    """Build a ParsedTable from raw pipe-delimited lines."""
    rows: list[dict[str, Any]] = []
    row_index = 0
    # Determine the maximum number of columns from the first non-separator line.
    n_cols = 0
    for line in lines:
        cells = _parse_pipe_row(line)
        if not _is_separator_row(cells):
            n_cols = max(n_cols, len(cells))
            break

    for line in lines:
        cells = _parse_pipe_row(line)
        if not cells:
            continue
        if _is_separator_row(cells):
            continue
        if _is_banner_row(cells):
            continue
        # Pad to uniform width so every row has the same column keys.
        while len(cells) < n_cols:
            cells.append("")
        row_index += 1
        row: dict[str, Any] = {"row_index": row_index}
        for col_idx, cell in enumerate(cells, start=1):
            row[_col_letter(col_idx)] = cell if cell else None
        rows.append(row)
    return ParsedTable(rows=rows, raw_lines=lines)


def parse_markdown_tables(markdown: str) -> list[ParsedTable]:
    """Extract all pipe-delimited tables from Mistral OCR markdown.

    Non-table lines are ignored here; they are collected separately by
    ``build_sections_from_ocr`` and emitted as a prose section.
    """
    tables: list[ParsedTable] = []
    current_lines: list[str] = []
    in_table = False

    for line in markdown.splitlines():
        stripped = line.strip()
        is_table_line = "|" in stripped and stripped.startswith("|")

        if is_table_line:
            in_table = True
            current_lines.append(stripped)
        else:
            if in_table and current_lines:
                table = _build_table(current_lines)
                if table.rows:
                    tables.append(table)
                current_lines = []
                in_table = False

    if in_table and current_lines:
        table = _build_table(current_lines)
        if table.rows:
            tables.append(table)

    return tables


_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")

_SECTION_SPLIT_KEYWORDS: list[tuple[str, str]] = [
    # (lowercase trigger, section_kind)
    ("sde reconciliation", "sde_summary"),
    ("seller's discretionary earnings", "sde_summary"),
    ("sellers discretionary earnings", "sde_summary"),
    ("seller discretionary earnings", "sde_summary"),
    ("sde summary", "sde_summary"),
    ("balance sheet", DocumentType.BALANCE_SHEET.value),
    ("cash flow", DocumentType.CASH_FLOW_STATEMENT.value),
]


def _detect_split_kind(label: str) -> str | None:
    """Return a section_kind if ``label`` triggers a known split point, else None."""
    lower = label.lower()
    for trigger, kind in _SECTION_SPLIT_KEYWORDS:
        if trigger in lower:
            return kind
    return None


def split_financial_subtables(
    table: ParsedTable,
    parent_doc_type: DocumentType,
) -> list[tuple[str, ParsedTable]]:
    """Split a table into sub-tables whenever an embedded section header changes context.

    Delegates to the unified ``split_rows_into_sections`` helper so that all
    input formats (OCR markdown, XLSX sheets, CSV rows, DOCX tables) share
    identical splitting logic.

    Returns a list of (section_kind, ParsedTable) tuples.
    """
    from app.services.section_splitter import split_rows_into_sections

    if not table.rows:
        initial = infer_section_kind(document_type=parent_doc_type)
        return [(initial, table)]

    segments = split_rows_into_sections(table.rows, parent_doc_type)

    result: list[tuple[str, ParsedTable]] = []
    for kind, seg_rows in segments:
        sub = ParsedTable(rows=seg_rows, raw_lines=table.raw_lines)
        result.append((kind, sub))
    return result


_KIND_NAMES: dict[str, str] = {
    DocumentType.PROFIT_AND_LOSS.value: "Income Statement / P&L",
    DocumentType.BALANCE_SHEET.value: "Balance Sheet",
    DocumentType.CASH_FLOW_STATEMENT.value: "Cash Flow Statement",
    DocumentType.AR_AGING_REPORT.value: "A/R Aging Report",
    DocumentType.CUSTOMER_LIST.value: "Customer List",
    DocumentType.EQUIPMENT_LIST.value: "Equipment List",
    DocumentType.EMPLOYEE_ROSTER.value: "Employee Roster",
    DocumentType.LEASE_AGREEMENT.value: "Lease Agreement",
    DocumentType.CONTRACT.value: "Contract",
    "sde_summary": "SDE Reconciliation",
}


def _kind_to_section_name(kind: str) -> str:
    return _KIND_NAMES.get(kind, kind.replace("_", " ").title())


def build_sections_from_ocr(
    payload: dict[str, Any],
    default_type: DocumentType,
) -> list[dict[str, Any]]:
    """Convert a Mistral OCR artifact payload into section dicts.

    Each markdown table becomes one or more section dicts with::

        {
            "section_kind": str | None,
            "section_name": str,
            "raw_text": str,
            "extracted_data": {"rows": [...]},
            "confidence": float,
            "notes": [...],
        }

    Non-table prose lines are collected into a single trailing text section so
    that narrative content (e.g. lease agreements, employment contracts) is
    preserved for downstream Claude agents.
    """
    full_markdown: str = (
        payload.get("full_markdown")
        or payload.get("fullMarkdown")
        or ""
    )
    if not full_markdown.strip():
        return []

    confidence: float = 0.8
    classification = payload.get("classification")
    if isinstance(classification, dict):
        try:
            confidence = float(classification.get("confidence", 0.8))
        except (TypeError, ValueError):
            pass

    tables = parse_markdown_tables(full_markdown)
    sections: list[dict[str, Any]] = []

    for table in tables:
        for kind, sub_table in split_financial_subtables(table, default_type):
            if not sub_table.rows:
                continue
            # Filter out rows that are all-empty (no data value anywhere)
            data_rows = [
                r for r in sub_table.rows
                if any(v for k, v in r.items() if k != "row_index")
            ]
            if not data_rows:
                continue
            section_name = _kind_to_section_name(kind)
            sections.append(
                {
                    "section_kind": kind if kind != DocumentType.OTHER.value else None,
                    "section_name": section_name,
                    "raw_text": sub_table.raw_text,
                    "extracted_data": {"rows": data_rows},
                    "confidence": confidence,
                    "notes": [],
                }
            )

    # Collect non-table prose lines for narrative-only documents (leases, contracts, etc.)
    prose_lines: list[str] = []
    in_table = False
    for line in full_markdown.splitlines():
        stripped = line.strip()
        if "|" in stripped and stripped.startswith("|"):
            in_table = True
        else:
            if in_table:
                in_table = False
            if stripped:
                prose_lines.append(stripped)

    if prose_lines:
        sections.append(
            {
                "section_kind": None,
                "section_name": "Document Text",
                "raw_text": "\n".join(prose_lines),
                "extracted_data": {},
                "confidence": 0.6,
                "notes": ["Narrative text extracted from OCR output."],
            }
        )

    return sections
