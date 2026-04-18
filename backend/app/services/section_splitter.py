"""Split a flat list of spreadsheet/CSV rows into multiple financial sections.

When a single XLSX sheet or CSV file contains multiple stacked financial
statements (e.g., Income Statement + SDE Reconciliation, or P&L + Balance Sheet
+ Cash Flow), the rows need to be split at the boundary headers before
classification can work correctly.

The same logic is also used by ``split_financial_subtables`` in
``ocr_markdown_parser.py`` so that all formats share one code path.
"""

from __future__ import annotations

import re
from typing import Any

from app.agents.schemas import DocumentType


# ---------------------------------------------------------------------------
# Split-point definitions
# ---------------------------------------------------------------------------

# Each entry is a (trigger_keywords, section_kind) pair.
# A row whose column-A value matches any trigger keyword starts a new section.
# Matched case-insensitively against the stripped label.
_SPLIT_POINTS: list[tuple[list[str], str]] = [
    (
        ["sde reconciliation", "sde summary", "seller's discretionary earnings",
         "sellers discretionary earnings", "seller discretionary earnings",
         "sde reconciliation summary"],
        "sde_summary",
    ),
    (
        ["balance sheet", "statement of financial position"],
        DocumentType.BALANCE_SHEET.value,
    ),
    (
        ["cash flow statement", "statement of cash flows", "cash flows",
         "cash flow"],
        DocumentType.CASH_FLOW_STATEMENT.value,
    ),
    (
        ["income statement", "profit and loss", "profit & loss", "p&l",
         "income statement / p&l"],
        DocumentType.PROFIT_AND_LOSS.value,
    ),
]

# Sub-headers that label groups within one statement — they must NOT trigger a split.
_NON_SPLIT_HEADERS = frozenset(
    [
        "revenue", "cost of revenue", "cost of goods sold", "cogs",
        "operating expenses", "opex", "gross profit", "ebitda", "ebitda margin",
        "assets", "current assets", "fixed assets", "intangible assets",
        "liabilities", "current liabilities", "long-term liabilities",
        "member equity", "equity", "liabilities & equity", "liabilities and equity",
    ]
)


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace for keyword matching."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _cell_a(row: dict[str, Any]) -> str:
    """Return the normalized label from column A."""
    return _normalize(str(row.get("A") or ""))


def _row_is_empty(row: dict[str, Any]) -> bool:
    """Return True when every data column in the row is empty/None."""
    return not any(
        v for k, v in row.items() if k != "row_index" and v not in {None, ""}
    )


def _classify_split_row(label: str) -> str | None:
    """Return the target section_kind if this label starts a new section."""
    normalized = _normalize(label)
    if not normalized:
        return None
    # A non-split header can never start a new section.
    if normalized in _NON_SPLIT_HEADERS:
        return None
    for triggers, kind in _SPLIT_POINTS:
        for trigger in triggers:
            if trigger in normalized:
                return kind
    return None


def _find_year_header_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return rows that act as year-column headers (contain 4-digit years in non-A columns)."""
    year_re = re.compile(r"\b(19|20)\d{2}\b")
    header_rows: list[dict[str, Any]] = []
    for row in rows:
        for key, val in row.items():
            if key in {"row_index", "A"}:
                continue
            if val and year_re.search(str(val)):
                header_rows.append(row)
                break
    return header_rows


def _is_all_cells_empty_except_a(row: dict[str, Any]) -> bool:
    """True when all columns except A are empty — classic section-header pattern."""
    for key, val in row.items():
        if key in {"row_index", "A"}:
            continue
        if val not in {None, ""}:
            return False
    return True


def split_rows_into_sections(
    rows: list[dict[str, Any]],
    parent_doc_type: DocumentType,
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Split a flat row list into (section_kind, rows) segments.

    The year-header row (the one containing year columns like 2022/2023/2024) is
    prepended to every sub-section so that ``_year_columns`` can still find year
    headers in each segment.

    Returns a single segment with the parent document type when no splits are found.
    """
    if not rows:
        return [(parent_doc_type.value, rows)]

    year_header_rows = _find_year_header_rows(rows)

    # Initial kind: infer from the first few rows of data.
    initial_kind = parent_doc_type.value

    segments: list[tuple[str, list[dict[str, Any]]]] = []
    current_kind = initial_kind
    current_rows: list[dict[str, Any]] = list(year_header_rows)

    for row in rows:
        # Skip year-header rows in the main loop — we prepend them ourselves.
        if any(row is h for h in year_header_rows):
            continue

        label = _cell_a(row)
        # Only rows where all non-A columns are empty can be split-point headers.
        if label and _is_all_cells_empty_except_a(row):
            candidate_kind = _classify_split_row(label)
            if candidate_kind and candidate_kind != current_kind:
                # Flush current segment if it has data rows beyond the headers.
                data_rows = [
                    r for r in current_rows if not any(r is h for h in year_header_rows)
                ]
                if data_rows:
                    segments.append((current_kind, current_rows))
                # Start a new segment, carrying year headers forward.
                current_rows = list(year_header_rows) + [row]
                current_kind = candidate_kind
                continue

        current_rows.append(row)

    # Flush the final segment.
    final_data_rows = [
        r for r in current_rows if not any(r is h for h in year_header_rows)
    ]
    if final_data_rows:
        segments.append((current_kind, current_rows))

    if not segments:
        return [(parent_doc_type.value, rows)]

    return segments
