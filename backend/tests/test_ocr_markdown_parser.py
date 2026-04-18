"""Tests for the OCR markdown parser."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.schemas import DocumentType
from app.services.ocr_markdown_parser import (
    _col_letter,
    _is_section_header_row,
    _is_separator_row,
    _parse_pipe_row,
    build_sections_from_ocr,
    parse_markdown_tables,
    split_financial_subtables,
)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def test_col_letter_basic():
    assert _col_letter(1) == "A"
    assert _col_letter(2) == "B"
    assert _col_letter(26) == "Z"
    assert _col_letter(27) == "AA"
    assert _col_letter(28) == "AB"


def test_parse_pipe_row():
    cells = _parse_pipe_row("| Foo | Bar | Baz |")
    assert cells == ["Foo", "Bar", "Baz"]


def test_parse_pipe_row_no_outer_pipes():
    cells = _parse_pipe_row("Foo | Bar | Baz")
    assert cells == ["Foo", "Bar", "Baz"]


def test_separator_row():
    assert _is_separator_row(["---", "---", "---"])
    assert _is_separator_row([":---:", "---", "---:"])
    assert not _is_separator_row(["Foo", "Bar"])
    assert not _is_separator_row(["---", "Bar"])


def test_section_header_row():
    assert _is_section_header_row(["SDE RECONCILIATION", "", "", "", ""])
    assert _is_section_header_row(["BALANCE SHEET", ""])
    assert not _is_section_header_row(["Total Revenue", "1000", "2000"])
    assert not _is_section_header_row(["", "", ""])


# ---------------------------------------------------------------------------
# Table parsing
# ---------------------------------------------------------------------------

PNL_MARKDOWN = """\
## Income Statement

| Line Item | 2022 | 2023 | 2024 | Notes |
| --- | --- | --- | --- | --- |
| REVENUE |  |  |  |  |
| Managed Services | 1284000 | 1408000 | 1562000 | MRR |
| Total Revenue | 1980000 | 2180000 | 2410000 |  |
| COST OF REVENUE |  |  |  |  |
| Total COGS | 970000 | 1068000 | 1182000 |  |
| Gross Profit | 1010000 | 1112000 | 1228000 |  |
| OPERATING EXPENSES |  |  |  |  |
| Total Operating Expenses | 354200 | 379200 | 403200 |  |
| Net Income | 306200 | 353200 | 421200 |  |
| SDE RECONCILIATION |  |  |  |  |
| EBITDA | 655800 | 732800 | 824800 |  |
| Add Back: Owner Draw | 88000 | 92000 | 95000 |  |
| Reported SDE | 387700 | 469100 | 564500 |  |
"""

BALANCE_MARKDOWN = """\
## Balance Sheet

| Line Item | Amount (USD) | Notes |
| --- | --- | --- |
| ASSETS |  |  |
| Cash & Cash Equivalents | 284600 |  |
| Accounts Receivable (net) | 148400 |  |
| Total Current Assets | 465200 |  |
| Total Assets | 549200 |  |
| LIABILITIES & EQUITY |  |  |
| Total Current Liabilities | 103800 |  |
| Total Liabilities | 103800 |  |
| Total Owner's Equity | 445400 |  |
"""


def test_parse_markdown_tables_pnl():
    tables = parse_markdown_tables(PNL_MARKDOWN)
    assert len(tables) == 1
    rows = tables[0].rows
    # Header row should be present with year labels
    header = next((r for r in rows if r.get("B") == "2022"), None)
    assert header is not None, "Year header row not found"
    # Total Revenue row present
    rev_row = next((r for r in rows if r.get("A") == "Total Revenue"), None)
    assert rev_row is not None
    assert rev_row.get("D") == "2410000"


def test_split_pnl_produces_pnl_and_sde():
    tables = parse_markdown_tables(PNL_MARKDOWN)
    assert tables
    splits = split_financial_subtables(tables[0], DocumentType.PROFIT_AND_LOSS)
    kinds = [k for k, _ in splits]
    assert DocumentType.PROFIT_AND_LOSS.value in kinds, "P&L section missing"
    assert "sde_summary" in kinds, "SDE section missing after split"


def test_split_pnl_sde_rows():
    tables = parse_markdown_tables(PNL_MARKDOWN)
    splits = split_financial_subtables(tables[0], DocumentType.PROFIT_AND_LOSS)
    sde_table = next(t for k, t in splits if k == "sde_summary")
    labels = [r.get("A") for r in sde_table.rows if r.get("A")]
    assert any("sde" in str(lbl).lower() or "EBITDA" in str(lbl) for lbl in labels)


def test_parse_balance_sheet_no_year_columns():
    tables = parse_markdown_tables(BALANCE_MARKDOWN)
    assert len(tables) == 1
    rows = tables[0].rows
    cash_row = next((r for r in rows if "Cash" in str(r.get("A") or "")), None)
    assert cash_row is not None
    # Without year column, value is in column B
    assert cash_row.get("B") == "284600"


# ---------------------------------------------------------------------------
# build_sections_from_ocr
# ---------------------------------------------------------------------------

def _make_payload(markdown: str, doc_type: str = "pnl_income_statement") -> dict:
    return {
        "full_markdown": markdown,
        "classification": {"document_type": doc_type, "confidence": 0.95, "reasoning": "test"},
    }


def test_build_sections_pnl_populates_rows():
    payload = _make_payload(PNL_MARKDOWN)
    sections = build_sections_from_ocr(payload, DocumentType.PROFIT_AND_LOSS)
    assert len(sections) >= 1
    # At least one section should have extracted rows
    row_counts = [len(s["extracted_data"].get("rows", [])) for s in sections]
    assert max(row_counts) > 3


def test_build_sections_pnl_and_sde():
    payload = _make_payload(PNL_MARKDOWN)
    sections = build_sections_from_ocr(payload, DocumentType.PROFIT_AND_LOSS)
    kinds = [s.get("section_kind") for s in sections]
    assert DocumentType.PROFIT_AND_LOSS.value in kinds


def test_build_sections_balance_sheet():
    payload = _make_payload(BALANCE_MARKDOWN, doc_type="balance_sheet")
    sections = build_sections_from_ocr(payload, DocumentType.BALANCE_SHEET)
    assert sections
    rows = sections[0]["extracted_data"].get("rows", [])
    labels = [r.get("A") for r in rows]
    assert any("Total Current Assets" in str(lbl) for lbl in labels)


def test_build_sections_prose_only():
    prose_payload = _make_payload(
        "This is a lease agreement.\n\nLandlord and tenant agree to the following terms.",
        doc_type="other",
    )
    sections = build_sections_from_ocr(prose_payload, DocumentType.OTHER)
    # Should get a text section with no rows
    text_sections = [s for s in sections if s.get("section_name") == "Document Text"]
    assert len(text_sections) == 1
    assert "Landlord" in text_sections[0]["raw_text"]


def test_build_sections_empty_payload():
    sections = build_sections_from_ocr({}, DocumentType.PROFIT_AND_LOSS)
    assert sections == []


# ---------------------------------------------------------------------------
# Integration with real OCR artifacts (optional – skipped if not present)
# ---------------------------------------------------------------------------

_ARTIFACT_DIR = (
    Path(__file__).parent.parent / "backend" / ".artifacts" / "ocr"
)


def _pnl_artifact() -> dict | None:
    if not _ARTIFACT_DIR.exists():
        return None
    for path in _ARTIFACT_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            if data.get("classification", {}).get("document_type") == "pnl_income_statement":
                return data
        except Exception:
            continue
    return None


@pytest.mark.skipif(_pnl_artifact() is None, reason="No P&L OCR artifact available")
def test_real_pnl_artifact_extracts_revenue():
    payload = _pnl_artifact()
    assert payload is not None
    sections = build_sections_from_ocr(payload, DocumentType.PROFIT_AND_LOSS)
    all_rows = [r for s in sections for r in s["extracted_data"].get("rows", [])]
    labels = [str(r.get("A") or "").lower() for r in all_rows]
    assert any("total revenue" in lbl or "revenue" in lbl for lbl in labels), (
        "Expected a 'Total Revenue' row in the parsed P&L artifact"
    )
