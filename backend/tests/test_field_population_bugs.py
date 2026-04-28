"""Regression tests for the three field-population bugs discovered after OCR parsing.

Bug 1 – false year-column detection from Notes text ("lease thru 2028")
    caused _latest_year_column to pick the Notes column instead of 2024,
    making every financial lookup return None.

Bug 2 – "Reported SDE" was not matched by the SDE alias list, so sde
    and owner_salary remained None.

Bug 3 – "Total Equity" (and "Retained Earnings") was not matched by the
    balance sheet equity alias list.

Additional follow-on aliases also tested here:
    - "Total OpEx" for operating expenses
    - "Owner Draw / Salary" for owner salary
    - EBITDA fallback for net income when no explicit net-income row exists
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.schemas import DocumentType
from app.services.financial_data_extractor import (
    _year_columns,
    _row_table,
    extract_financial_data,
)
from app.services.intake_service import IntakeDocument
from app.services.ingestion_service import ingest_intake_documents
from app.services.ocr_markdown_parser import build_sections_from_ocr


# ---------------------------------------------------------------------------
# Bug 1 helpers and unit tests
# ---------------------------------------------------------------------------

_NARRATIVE_NOTES_ROW: dict = {
    "row_index": 5,
    "A": "Rent & Facilities",
    "B": "42000",
    "C": "44000",
    "D": "46000",
    "E": "Class B office — lease thru 2028",
}

_HEADER_ROW: dict = {
    "row_index": 1,
    "A": "Line Item",
    "B": "2022",
    "C": "2023",
    "D": "2024",
    "E": "Notes",
}

_DATA_ROW: dict = {
    "row_index": 2,
    "A": "Total Revenue",
    "B": "1980000",
    "C": "2180000",
    "D": "2410000",
    "E": None,
}


def test_year_columns_skips_narrative_notes():
    """Years inside long narrative strings must not register as year columns."""
    rows = [_HEADER_ROW, _DATA_ROW, _NARRATIVE_NOTES_ROW]
    yc = _year_columns(rows)
    # Column E ('Notes') must NOT be registered even though the Rent row mentions 2028
    assert 2028 not in yc, f"2028 (from narrative) must not appear in year columns: {yc}"
    assert 2022 in yc
    assert 2023 in yc
    assert 2024 in yc
    # Latest year must be 2024, NOT 2028
    assert max(yc) == 2024


def test_year_columns_skips_notes_header_column():
    """Column E whose header is 'Notes' is entirely excluded from year detection."""
    rows = [_HEADER_ROW, _NARRATIVE_NOTES_ROW]
    yc = _year_columns(rows)
    assert "E" not in yc.values(), "Notes column (E) must never be a year column"


def test_revenue_maps_correctly_despite_notes_column():
    """End-to-end: Total Revenue must be read from column D (2024), not E."""
    rows = [_HEADER_ROW, _DATA_ROW, _NARRATIVE_NOTES_ROW]
    table = _row_table(rows)
    revenue = table.find(["total revenue", "revenue"])
    assert revenue == 2410000.0, f"Revenue should come from 2024 col D, got {revenue}"


def test_periods_exclude_false_2028():
    """Periods reported to the front-end must not include 2028."""
    rows = [_HEADER_ROW, _DATA_ROW, _NARRATIVE_NOTES_ROW]
    table = _row_table(rows)
    assert "2028" not in table.periods, f"2028 must not appear in periods: {table.periods}"
    assert table.periods == ["2022", "2023", "2024"]


def test_year_columns_rejects_dob_like_identity_date():
    rows = [
        {"row_index": 1, "A": "Taxpayer", "B": "Kyle Hartigan", "C": "DOB", "D": "March 4, 1981"},
        {"row_index": 2, "A": "Address", "B": "Denver, CO", "C": "Occupation", "D": "IT Consultant"},
    ]

    assert _year_columns(rows) == {}


# ---------------------------------------------------------------------------
# Bug 2 – SDE alias tests
# ---------------------------------------------------------------------------

_SDE_ROWS = [
    {"row_index": 1, "A": "Line Item", "B": "2022", "C": "2023", "D": "2024"},
    {"row_index": 2, "A": "Reported SDE", "B": "387700", "C": "469100", "D": "564500"},
    {"row_index": 3, "A": "EBITDA", "B": "655800", "C": "732800", "D": "824800"},
]


def test_reported_sde_alias_matches():
    """'Reported SDE' must be found by the sde alias list."""
    table = _row_table(_SDE_ROWS)
    sde = table.find(["total sde", "total seller's discretionary earnings", "reported sde", "sde"])
    assert sde == 564500.0, f"SDE should be 564500 from 2024 column, got {sde}"


# ---------------------------------------------------------------------------
# Bug 3 – equity alias tests
# ---------------------------------------------------------------------------

_BALANCE_ROWS = [
    {"row_index": 1, "A": "Line Item", "B": "Amount"},
    {"row_index": 2, "A": "Total Current Assets", "B": "465200"},
    {"row_index": 3, "A": "TOTAL ASSETS", "B": "549200"},
    {"row_index": 4, "A": "Total Current Liabilities", "B": "103800"},
    {"row_index": 5, "A": "TOTAL LIABILITIES", "B": "103800"},
    {"row_index": 6, "A": "Total Equity", "B": "445400"},
]

_BALANCE_RETAINED_ROWS = [
    {"row_index": 1, "A": "Line Item", "B": "Amount"},
    {"row_index": 2, "A": "Total Assets", "B": "549200"},
    {"row_index": 3, "A": "Total Liabilities", "B": "103800"},
    {"row_index": 4, "A": "Retained Earnings", "B": "445400"},
]


def test_total_equity_alias_matches():
    """'Total Equity' must be resolved by the equity alias list."""
    table = _row_table(_BALANCE_ROWS)
    equity = table.find(
        ["total owner's equity", "total owners equity", "owner's equity", "owners equity",
         "total equity", "equity", "retained earnings"]
    )
    assert equity == 445400.0, f"Equity should be 445400, got {equity}"


def test_retained_earnings_alias_matches():
    """'Retained Earnings' must also be resolved when no 'equity' row exists."""
    table = _row_table(_BALANCE_RETAINED_ROWS)
    equity = table.find(
        ["total owner's equity", "total owners equity", "owner's equity", "owners equity",
         "total equity", "equity", "retained earnings"]
    )
    assert equity == 445400.0, f"Equity via retained earnings should be 445400, got {equity}"


# ---------------------------------------------------------------------------
# Additional alias tests (follow-on fixes)
# ---------------------------------------------------------------------------

_OPEX_ROWS = [
    {"row_index": 1, "A": "Line Item", "B": "2024"},
    {"row_index": 2, "A": "Total OpEx", "B": "403200"},
]

_OWNER_DRAW_ROWS = [
    {"row_index": 1, "A": "Line Item", "B": "2024"},
    {"row_index": 2, "A": "Owner Draw / Salary", "B": "95000"},
]


def test_total_opex_alias_matches():
    """'Total OpEx' must be resolved for operating expenses."""
    table = _row_table(_OPEX_ROWS)
    opex = table.find(["total operating expenses", "operating expenses", "total opex", "opex"])
    assert opex == 403200.0, f"OpEx should be 403200, got {opex}"


def test_owner_draw_salary_alias_matches():
    """'Owner Draw / Salary' must be resolved for owner salary."""
    table = _row_table(_OWNER_DRAW_ROWS)
    salary = table.find(["owner salary & benefits", "owner salary and benefits", "owner salary",
                          "owner draw salary", "owner draw"])
    assert salary == 95000.0, f"Owner salary should be 95000, got {salary}"


def test_ebitda_fallback_for_net_income():
    """When no net-income row exists, EBITDA should be used as the fallback net income."""
    rows = [
        {"row_index": 1, "A": "Line Item", "B": "2024"},
        {"row_index": 2, "A": "Gross Profit", "B": "1228000"},
        {"row_index": 3, "A": "Total OpEx", "B": "403200"},
        {"row_index": 4, "A": "EBITDA", "B": "824800"},
    ]
    table = _row_table(rows)
    net_income = table.find(["net income", "net profit", "net income loss", "net profit loss"])
    ebitda = table.find(["ebitda"])
    # No explicit net income in this table
    assert net_income is None
    # But ebitda is available as fallback
    assert ebitda == 824800.0


# ---------------------------------------------------------------------------
# Integration test against real OCR artifacts (skipped if not present)
# ---------------------------------------------------------------------------

_ARTIFACT_DIR = Path(__file__).parent.parent / "backend" / ".artifacts" / "ocr"


def _find_artifact(doc_type: str) -> dict | None:
    if not _ARTIFACT_DIR.exists():
        return None
    mistral_map = {
        "profit_and_loss": "pnl_income_statement",
        "balance_sheet": "balance_sheet",
    }
    target = mistral_map.get(doc_type, doc_type)
    for path in _ARTIFACT_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            if data.get("classification", {}).get("document_type") == target:
                return data
        except Exception:
            continue
    return None


@pytest.mark.skipif(_find_artifact("profit_and_loss") is None, reason="No P&L OCR artifact")
def test_real_pnl_populates_all_income_fields():
    """Full end-to-end: real OCR P&L artifact must populate all key income fields."""
    payload = _find_artifact("profit_and_loss")
    sections = build_sections_from_ocr(payload, DocumentType.PROFIT_AND_LOSS)
    doc = IntakeDocument(
        document_id="test-pnl",
        file_name="pnl.pdf",
        mime_type="application/pdf",
        declared_type=DocumentType.PROFIT_AND_LOSS,
        canonical_type=DocumentType.PROFIT_AND_LOSS,
        sections=sections,
        raw_text=payload.get("full_markdown", ""),
    )
    result = extract_financial_data(ingest_intake_documents([doc]))

    assert result.income_statement is not None, "Income statement must be populated"
    is_ = result.income_statement
    assert is_.revenue > 0, f"Revenue must be positive, got {is_.revenue}"
    assert is_.cogs > 0, f"COGS must be positive, got {is_.cogs}"
    assert is_.gross_profit > 0, f"Gross profit must be positive, got {is_.gross_profit}"
    assert is_.operating_expenses > 0, f"Operating expenses must be positive, got {is_.operating_expenses}"
    assert is_.net_income > 0, (
        f"Net income (or EBITDA fallback) must be positive, got {is_.net_income}"
    )
    assert is_.sde is not None and is_.sde > 0, f"SDE must be positive, got {is_.sde}"
    assert len(is_.periods) > 0 and "2028" not in is_.periods, (
        f"Periods must not include spurious 2028: {is_.periods}"
    )


@pytest.mark.skipif(_find_artifact("balance_sheet") is None, reason="No balance sheet OCR artifact")
def test_real_balance_sheet_populates_equity():
    """Full end-to-end: real OCR balance sheet artifact must populate equity."""
    payload = _find_artifact("balance_sheet")
    sections = build_sections_from_ocr(payload, DocumentType.BALANCE_SHEET)
    doc = IntakeDocument(
        document_id="test-bs",
        file_name="balance.pdf",
        mime_type="application/pdf",
        declared_type=DocumentType.BALANCE_SHEET,
        canonical_type=DocumentType.BALANCE_SHEET,
        sections=sections,
        raw_text=payload.get("full_markdown", ""),
    )
    result = extract_financial_data(ingest_intake_documents([doc]))

    assert result.balance_sheet is not None, "Balance sheet must be populated"
    bs = result.balance_sheet
    assert bs.current_assets > 0, f"Current assets must be positive, got {bs.current_assets}"
    assert bs.total_assets > 0, f"Total assets must be positive, got {bs.total_assets}"
    assert bs.equity > 0, (
        f"Equity must be positive (was failing before fix), got {bs.equity}"
    )
    # No equity-related parsing error notes
    assert not any("equity" in n.lower() for n in result.parsing_notes), (
        f"No equity mapping errors expected, got notes: {result.parsing_notes}"
    )
