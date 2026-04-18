"""Unit tests for the section_splitter unified helper."""
from __future__ import annotations

from app.agents.schemas import DocumentType
from app.services.section_splitter import split_rows_into_sections


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row(idx: int, label: str, *values: str) -> dict:
    row: dict = {"row_index": idx, "A": label}
    for i, v in enumerate(values):
        row[chr(ord("B") + i)] = v
    return row


YEAR_HEADER = _make_row(1, "Line Item", "2022", "2023", "2024")


# ---------------------------------------------------------------------------
# Basic: single section (no split)
# ---------------------------------------------------------------------------

def test_single_section_no_split():
    rows = [
        YEAR_HEADER,
        _make_row(2, "Total Revenue", "1980000", "2180000", "2410000"),
        _make_row(3, "Total COGS", "970000", "1068000", "1182000"),
    ]
    segments = split_rows_into_sections(rows, DocumentType.PROFIT_AND_LOSS)
    assert len(segments) == 1
    assert segments[0][0] == DocumentType.PROFIT_AND_LOSS.value


def test_empty_rows_returns_single_segment():
    segments = split_rows_into_sections([], DocumentType.PROFIT_AND_LOSS)
    assert len(segments) == 1
    assert segments[0][1] == []


# ---------------------------------------------------------------------------
# Core: P&L sheet with embedded SDE reconciliation
# ---------------------------------------------------------------------------

def test_pnl_plus_sde_splits_into_two():
    rows = [
        YEAR_HEADER,
        _make_row(2, "Total Revenue", "1980000", "2180000", "2410000"),
        _make_row(3, "Total COGS", "970000", "1068000", "1182000"),
        _make_row(4, "Gross Profit", "1010000", "1112000", "1228000"),
        _make_row(5, "Total OpEx", "354200", "379200", "403200"),
        _make_row(6, "EBITDA", "655800", "732800", "824800"),
        # SDE split point
        {"row_index": 7, "A": "SDE RECONCILIATION", "B": "", "C": "", "D": ""},
        _make_row(8, "EBITDA", "655800", "732800", "824800"),
        _make_row(9, "Add Back: Owner Draw", "88000", "92000", "95000"),
        _make_row(10, "Reported SDE", "387700", "469100", "564500"),
    ]
    segments = split_rows_into_sections(rows, DocumentType.PROFIT_AND_LOSS)
    kinds = [k for k, _ in segments]

    assert len(segments) == 2, f"Expected 2 segments, got {len(segments)}: {kinds}"
    assert DocumentType.PROFIT_AND_LOSS.value in kinds
    assert "sde_summary" in kinds


def test_pnl_segment_has_revenue_row():
    rows = [
        YEAR_HEADER,
        _make_row(2, "Total Revenue", "1980000", "2180000", "2410000"),
        _make_row(3, "EBITDA", "655800", "732800", "824800"),
        {"row_index": 4, "A": "SDE RECONCILIATION", "B": "", "C": "", "D": ""},
        _make_row(5, "Reported SDE", "387700", "469100", "564500"),
    ]
    segments = split_rows_into_sections(rows, DocumentType.PROFIT_AND_LOSS)
    pnl_rows = next(seg_rows for kind, seg_rows in segments if kind == DocumentType.PROFIT_AND_LOSS.value)
    labels = [r.get("A") for r in pnl_rows]
    assert "Total Revenue" in labels


def test_sde_segment_has_reported_sde_row():
    rows = [
        YEAR_HEADER,
        _make_row(2, "Total Revenue", "1980000", "2180000", "2410000"),
        {"row_index": 3, "A": "SDE RECONCILIATION", "B": "", "C": "", "D": ""},
        _make_row(4, "Reported SDE", "387700", "469100", "564500"),
    ]
    segments = split_rows_into_sections(rows, DocumentType.PROFIT_AND_LOSS)
    sde_rows = next(seg_rows for kind, seg_rows in segments if kind == "sde_summary")
    labels = [r.get("A") for r in sde_rows]
    assert "Reported SDE" in labels


# ---------------------------------------------------------------------------
# Year-header propagation
# ---------------------------------------------------------------------------

def test_year_header_prepended_to_every_segment():
    """Each sub-section must start with the year-header row so _year_columns works."""
    rows = [
        YEAR_HEADER,
        _make_row(2, "Total Revenue", "1980000", "2180000", "2410000"),
        {"row_index": 3, "A": "SDE RECONCILIATION", "B": "", "C": "", "D": ""},
        _make_row(4, "Reported SDE", "387700", "469100", "564500"),
    ]
    segments = split_rows_into_sections(rows, DocumentType.PROFIT_AND_LOSS)
    for kind, seg_rows in segments:
        header = seg_rows[0]
        assert header.get("B") == "2022", (
            f"Year header not prepended to '{kind}' segment. First row: {header}"
        )


# ---------------------------------------------------------------------------
# Non-split sub-headers must not create new segments
# ---------------------------------------------------------------------------

def test_revenue_sub_header_does_not_split():
    rows = [
        YEAR_HEADER,
        {"row_index": 2, "A": "REVENUE", "B": "", "C": "", "D": ""},
        _make_row(3, "Total Revenue", "1980000", "2180000", "2410000"),
    ]
    segments = split_rows_into_sections(rows, DocumentType.PROFIT_AND_LOSS)
    assert len(segments) == 1


def test_assets_sub_header_does_not_split():
    rows = [
        {"row_index": 1, "A": "Line Item", "B": "Amount"},
        {"row_index": 2, "A": "ASSETS", "B": ""},
        {"row_index": 3, "A": "Total Current Assets", "B": "465200"},
    ]
    segments = split_rows_into_sections(rows, DocumentType.BALANCE_SHEET)
    assert len(segments) == 1


def test_operating_expenses_sub_header_does_not_split():
    rows = [
        YEAR_HEADER,
        {"row_index": 2, "A": "OPERATING EXPENSES", "B": "", "C": "", "D": ""},
        _make_row(3, "Total OpEx", "354200", "379200", "403200"),
    ]
    segments = split_rows_into_sections(rows, DocumentType.PROFIT_AND_LOSS)
    assert len(segments) == 1


# ---------------------------------------------------------------------------
# Multi-statement sheet (P&L + Balance Sheet + Cash Flow)
# ---------------------------------------------------------------------------

def test_three_statement_sheet_splits_into_three():
    rows = [
        YEAR_HEADER,
        _make_row(2, "Total Revenue", "1980000", "2180000", "2410000"),
        _make_row(3, "EBITDA", "655800", "732800", "824800"),
        {"row_index": 4, "A": "BALANCE SHEET", "B": "", "C": "", "D": ""},
        {"row_index": 5, "A": "Total Current Assets", "B": "465200"},
        {"row_index": 6, "A": "TOTAL ASSETS", "B": "549200"},
        {"row_index": 7, "A": "CASH FLOW STATEMENT", "B": "", "C": "", "D": ""},
        {"row_index": 8, "A": "Operating Cash Flow", "B": "700000"},
    ]
    segments = split_rows_into_sections(rows, DocumentType.PROFIT_AND_LOSS)
    kinds = [k for k, _ in segments]
    assert len(segments) == 3, f"Expected 3 segments, got {len(segments)}: {kinds}"
    assert DocumentType.PROFIT_AND_LOSS.value in kinds
    assert DocumentType.BALANCE_SHEET.value in kinds
    assert DocumentType.CASH_FLOW_STATEMENT.value in kinds


# ---------------------------------------------------------------------------
# Classification precedence: P&L beats SDE when both keywords present
# ---------------------------------------------------------------------------

def test_classification_pnl_beats_sde_in_combined_text():
    from app.services.section_kind import infer_section_kind
    text = "income statement total revenue gross profit sde reconciliation reported sde"
    kind = infer_section_kind(raw_text=text)
    assert kind == DocumentType.PROFIT_AND_LOSS.value, (
        f"P&L must beat SDE when income-statement keywords are present; got '{kind}'"
    )


def test_classification_sde_only_when_no_income_signals():
    from app.services.section_kind import infer_section_kind
    text = "sde reconciliation reported sde ebitda add back owner draw"
    kind = infer_section_kind(raw_text=text)
    assert kind == "sde_summary", f"Expected sde_summary when no P&L keywords; got '{kind}'"


def test_classification_income_statement_sheet_name_wins():
    from app.services.section_kind import infer_section_kind
    # Even if the text also has 'sde', 'income statement' should win
    kind = infer_section_kind(
        section_name="Income Statement",
        raw_text="total revenue gross profit operating expenses sde reconciliation",
    )
    assert kind == DocumentType.PROFIT_AND_LOSS.value
