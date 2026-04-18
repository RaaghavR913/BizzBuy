"""Tests for CSV/TSV ingestion through the intake service."""
from __future__ import annotations

import pytest

from app.services.intake_service import _parse_csv_content


PNL_CSV = """\
Line Item,2022,2023,2024
Total Revenue,1980000,2180000,2410000
Total COGS,970000,1068000,1182000
Gross Profit,1010000,1112000,1228000
Total Operating Expenses,354200,379200,403200
Net Income,306200,353200,421200
"""

PNL_TSV = PNL_CSV.replace(",", "\t")

PNL_CSV_QUOTED = """\
Line Item,2022,2023,2024
"Total Revenue (USD)","$1,980,000","$2,180,000","$2,410,000"
"Total COGS",970000,1068000,1182000
"""

EMPTY_CSV = "\n\n\n"

SINGLE_COL_CSV = "Item\nRevenue\nCOGS\n"


def test_csv_basic_rows():
    rows, raw_text, notes = _parse_csv_content(PNL_CSV.encode(), is_tsv=False)
    # Header + 5 data rows
    assert len(rows) == 6
    # Row 1 is the header
    assert rows[0]["A"] == "Line Item"
    assert rows[0]["B"] == "2022"
    # Revenue row
    rev_row = next(r for r in rows if r.get("A") == "Total Revenue")
    assert rev_row["B"] == "1980000"
    assert rev_row["D"] == "2410000"
    assert raw_text == PNL_CSV
    assert notes


def test_tsv_basic_rows():
    rows, _text, _notes = _parse_csv_content(PNL_TSV.encode(), is_tsv=True)
    assert len(rows) == 6
    rev_row = next(r for r in rows if r.get("A") == "Total Revenue")
    assert rev_row["D"] == "2410000"


def test_csv_quoted_cells():
    rows, _text, _notes = _parse_csv_content(PNL_CSV_QUOTED.encode(), is_tsv=False)
    assert len(rows) == 3
    # Quoted label with commas preserved
    assert rows[1]["A"] == "Total Revenue (USD)"
    # Quoted numbers with dollar signs and commas pass through as-is
    assert "$1,980,000" in str(rows[1]["B"])


def test_csv_empty_lines_skipped():
    rows, _text, _notes = _parse_csv_content(EMPTY_CSV.encode(), is_tsv=False)
    assert rows == []


def test_csv_single_column():
    rows, _text, _notes = _parse_csv_content(SINGLE_COL_CSV.encode(), is_tsv=False)
    assert len(rows) == 3
    assert rows[0]["A"] == "Item"
    assert "B" not in rows[0] or rows[0].get("B") is None


def test_csv_bom_stripped():
    bom_csv = b"\xef\xbb\xbfLine Item,2024\nRevenue,100000\n"
    rows, _text, _notes = _parse_csv_content(bom_csv, is_tsv=False)
    assert rows[0]["A"] == "Line Item"


def test_csv_row_dict_format():
    """Rows must use A/B/C column keys for _row_table compatibility."""
    rows, _text, _notes = _parse_csv_content(PNL_CSV.encode(), is_tsv=False)
    for row in rows:
        assert "row_index" in row
        assert "A" in row


def test_csv_empty_cells_become_none():
    sparse = b"Label,2022,,2024\nRevenue,,2180000,2410000\n"
    rows, _text, _notes = _parse_csv_content(sparse, is_tsv=False)
    data_row = rows[1]
    # Row: Revenue | (empty) | 2180000 | 2410000
    # → A=Revenue, B=None, C=2180000, D=2410000
    assert data_row["B"] is None   # empty cell in column B
    assert data_row["C"] == "2180000"
