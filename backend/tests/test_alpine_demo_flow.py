"""End-to-end smoke test: Alpine IT Solutions demo document set.

This test synthesises the exact spreadsheet row structure of the two XLSX
files the user uploads for the hackathon demo:
  - IncomeStatement_AlpineITSolutions.xlsx (Income Statement + SDE Reconciliation)
  - BalanceSheet_AlpineITSolutions.xlsx

It runs the full parse-documents service pipeline and asserts that every
demo-critical Review field is populated so the user can press Continue
without typing anything.
"""

from __future__ import annotations

import pytest

from app.agents.schemas import DocumentType
from app.services.financial_data_extractor import extract_financial_data
from app.services.intake_service import IntakeDocument
from app.services.ingestion_service import ingest_intake_documents


# ---------------------------------------------------------------------------
# Alpine Income Statement + SDE rows (exact structure from the uploaded file)
# ---------------------------------------------------------------------------

INCOME_ROWS = [
    # Banner rows
    {"row_index": 1, "A": "Alpine IT Solutions LLC — Income Statement", "B": "", "C": "", "D": "", "E": ""},
    {"row_index": 2, "A": "Denver, CO  |  Fiscal Year End: December 31  |  All figures in USD", "B": "", "C": "", "D": "", "E": ""},
    # Year header
    {"row_index": 3, "A": "Line Item", "B": "2022", "C": "2023", "D": "2024", "E": "Notes"},
    # Revenue
    {"row_index": 4, "A": "REVENUE", "B": "", "C": "", "D": "", "E": ""},
    {"row_index": 5, "A": "Managed Services (MRR contracts)", "B": "1284000", "C": "1408000", "D": "1562000", "E": "67%+ recurring"},
    {"row_index": 6, "A": "Project & Implementation Work", "B": "486000", "C": "528000", "D": "578000", "E": "One-time engagements"},
    {"row_index": 7, "A": "Hardware & Software Resale", "B": "128000", "C": "148000", "D": "168000", "E": "Pass-through margin ~18%"},
    {"row_index": 8, "A": "Training & Consulting", "B": "82000", "C": "96000", "D": "102000", "E": ""},
    {"row_index": 9, "A": "Total Revenue", "B": "1980000", "C": "2180000", "D": "2410000", "E": ""},
    {"row_index": 10, "A": "Revenue Growth YOY", "B": "", "C": "0.15625", "D": "0.135135135135135", "E": "10.1% → 10.6%"},
    {"row_index": 11, "A": "", "B": "", "C": "", "D": "", "E": ""},
    # COGS
    {"row_index": 12, "A": "COST OF REVENUE", "B": "", "C": "", "D": "", "E": ""},
    {"row_index": 13, "A": "Technical Staff Labor", "B": "634000", "C": "694000", "D": "766000", "E": "3 senior engineers + 2 techs"},
    {"row_index": 14, "A": "Subcontractors / Specialists", "B": "142000", "C": "154000", "D": "168000", "E": ""},
    {"row_index": 15, "A": "Hardware / Software COGS", "B": "106000", "C": "122000", "D": "138000", "E": ""},
    {"row_index": 16, "A": "Cloud Infrastructure (AWS/Azure)", "B": "88000", "C": "98000", "D": "110000", "E": "Passed through to clients"},
    {"row_index": 17, "A": "Total COGS", "B": "970000", "C": "1068000", "D": "1182000", "E": ""},
    {"row_index": 18, "A": "", "B": "", "C": "", "D": "", "E": ""},
    # Gross profit
    {"row_index": 19, "A": "Gross Profit", "B": "1010000", "C": "1112000", "D": "1228000", "E": ""},
    {"row_index": 20, "A": "Gross Margin", "B": "1.99588477366255", "C": "2.02272727272727", "D": "2.04498269896194", "E": "~51%"},
    {"row_index": 21, "A": "", "B": "", "C": "", "D": "", "E": ""},
    # Operating expenses
    {"row_index": 22, "A": "OPERATING EXPENSES", "B": "", "C": "", "D": "", "E": ""},
    {"row_index": 23, "A": "Owner Draw / Salary", "B": "88000", "C": "92000", "D": "95000", "E": "Market replacement ~$120K"},
    {"row_index": 24, "A": "Admin / Office Manager", "B": "52000", "C": "55000", "D": "58000", "E": ""},
    {"row_index": 25, "A": "Rent & Facilities", "B": "42000", "C": "44000", "D": "46000", "E": "Class B office — lease thru 2028"},
    {"row_index": 26, "A": "Insurance (E&O / GL / Cyber)", "B": "38000", "C": "42000", "D": "46000", "E": "E&O + cyber mandatory for MSP"},
    {"row_index": 27, "A": "Software Tools & Licenses", "B": "48000", "C": "52000", "D": "56000", "E": "RMM, PSA, backup, security stack"},
    {"row_index": 28, "A": "Owner Vehicle", "B": "14200", "C": "14200", "D": "14200", "E": "Toyota Land Cruiser — business use ~60%"},
    {"row_index": 29, "A": "Marketing & Lead Gen", "B": "18000", "C": "20000", "D": "22000", "E": ""},
    {"row_index": 30, "A": "Professional Fees", "B": "22000", "C": "24000", "D": "26000", "E": "CPA + attorney"},
    {"row_index": 31, "A": "Depreciation", "B": "18000", "C": "20000", "D": "22000", "E": ""},
    {"row_index": 32, "A": "Misc / Office", "B": "14000", "C": "16000", "D": "18000", "E": ""},
    {"row_index": 33, "A": "Total OpEx", "B": "354200", "C": "379200", "D": "403200", "E": ""},
    {"row_index": 34, "A": "", "B": "", "C": "", "D": "", "E": ""},
    # EBITDA
    {"row_index": 35, "A": "EBITDA", "B": "655800", "C": "732800", "D": "824800", "E": ""},
    {"row_index": 36, "A": "EBITDA Margin", "B": "0.72880658436214", "C": "0.718181818181818", "D": "0.69757785467128", "E": "~34.2%"},
    {"row_index": 37, "A": "", "B": "", "C": "", "D": "", "E": ""},
    # SDE Reconciliation (embedded in same sheet)
    {"row_index": 38, "A": "SDE RECONCILIATION", "B": "", "C": "", "D": "", "E": ""},
    {"row_index": 39, "A": "EBITDA", "B": "655800", "C": "732800", "D": "824800", "E": ""},
    {"row_index": 40, "A": "Add Back: Owner Draw", "B": "88000", "C": "92000", "D": "95000", "E": ""},
    {"row_index": 41, "A": "Add Back: Owner Health Insurance", "B": "10400", "C": "10800", "D": "11200", "E": ""},
    {"row_index": 42, "A": "Add Back: Owner Vehicle (partial)", "B": "8500", "C": "8500", "D": "8500", "E": "60% business use allocation"},
    {"row_index": 43, "A": "Less: Market-Rate Tech Director", "B": "-120,000", "C": "-120,000", "D": "-120,000", "E": "Replace owner's technical role"},
    {"row_index": 44, "A": "Less: Market-Rate Admin", "B": "-55,000", "C": "-55,000", "D": "-55,000", "E": ""},
    {"row_index": 45, "A": "Reported SDE", "B": "387700", "C": "469100", "D": "564500", "E": ""},
]


BALANCE_ROWS = [
    {"row_index": 1, "A": "Denver, CO", "B": "As of December 31, 2024", "C": "All figures in USD", "D": None, "E": None},
    {"row_index": 2, "A": "Line Item", "B": "Amount (USD)", "C": "Notes"},
    {"row_index": 3, "A": "ASSETS", "B": None, "C": None},
    {"row_index": 4, "A": "Current Assets", "B": None, "C": None},
    {"row_index": 5, "A": "Cash & Cash Equivalents", "B": "284600", "C": None},
    {"row_index": 6, "A": "Accounts Receivable (net)", "B": "148400", "C": "14-day DSO — excellent"},
    {"row_index": 7, "A": "Prepaid Expenses & Deposits", "B": "32200", "C": None},
    {"row_index": 8, "A": "Total Current Assets", "B": "465200", "C": None},
    {"row_index": 10, "A": "Fixed Assets", "B": None, "C": None},
    {"row_index": 11, "A": "IT Infrastructure & Lab Equipment", "B": "68000", "C": None},
    {"row_index": 12, "A": "Computers & Workstations", "B": "42000", "C": None},
    {"row_index": 13, "A": "Office Furniture & Fixtures", "B": "18000", "C": None},
    {"row_index": 14, "A": "Owner Vehicle", "B": "38000", "C": None},
    {"row_index": 15, "A": "Less: Accumulated Depreciation", "B": "-82000", "C": None},
    {"row_index": 16, "A": "Net Fixed Assets", "B": "84000", "C": None},
    {"row_index": 18, "A": "Intangible Assets", "B": None, "C": None},
    {"row_index": 19, "A": "Customer Contracts (MRR)", "B": "0", "C": "Not capitalized — significant buyer value"},
    {"row_index": 20, "A": "Software Licenses / IP", "B": "0", "C": None},
    {"row_index": 21, "A": "Total Intangible Assets", "B": "0", "C": None},
    {"row_index": 23, "A": "TOTAL ASSETS", "B": "549200", "C": None},
    {"row_index": 25, "A": "LIABILITIES & EQUITY", "B": None, "C": None},
    {"row_index": 26, "A": "Current Liabilities", "B": None, "C": None},
    {"row_index": 27, "A": "Accounts Payable", "B": "22400", "C": None},
    {"row_index": 28, "A": "Accrued Payroll", "B": "18600", "C": None},
    {"row_index": 29, "A": "Deferred Revenue (prepaid MSAs)", "B": "62800", "C": "Annual MSA clients — normalizes by Q2"},
    {"row_index": 30, "A": "Total Current Liabilities", "B": "103800", "C": None},
    {"row_index": 32, "A": "Long-Term Liabilities", "B": None, "C": None},
    {"row_index": 33, "A": "Long-Term Debt", "B": "0", "C": "No debt — clean balance sheet"},
    {"row_index": 34, "A": "Total Long-Term Liabilities", "B": "0", "C": None},
    {"row_index": 36, "A": "TOTAL LIABILITIES", "B": "103800", "C": None},
    {"row_index": 38, "A": "Member Equity", "B": None, "C": None},
    {"row_index": 39, "A": "Retained Earnings", "B": "445400", "C": None},
    {"row_index": 40, "A": "Total Equity", "B": "445400", "C": None},
    {"row_index": 42, "A": "TOTAL LIABILITIES & EQUITY", "B": "549200", "C": None},
]


def _make_income_doc() -> IntakeDocument:
    return IntakeDocument(
        document_id="alpine-income",
        file_name="IncomeStatement_AlpineITSolutions.xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        declared_type=DocumentType.PROFIT_AND_LOSS,
        canonical_type=DocumentType.PROFIT_AND_LOSS,
        sheets=[{"name": "Income Statement", "rows": INCOME_ROWS, "text": "", "confidence": 0.8}],
    )


def _make_balance_doc() -> IntakeDocument:
    return IntakeDocument(
        document_id="alpine-balance",
        file_name="BalanceSheet_AlpineITSolutions.xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        declared_type=DocumentType.BALANCE_SHEET,
        canonical_type=DocumentType.BALANCE_SHEET,
        sheets=[{"name": "Balance Sheet", "rows": BALANCE_ROWS, "text": "", "confidence": 0.8}],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_income_statement_all_fields_populated():
    """All required income statement fields must be extracted from the Alpine P&L sheet."""
    output = ingest_intake_documents([_make_income_doc()])
    result = extract_financial_data(output)

    assert result.income_statement is not None, "Income statement must not be None"
    is_ = result.income_statement

    assert is_.revenue == 2410000.0, f"revenue: expected 2410000, got {is_.revenue}"
    assert is_.cogs == 1182000.0, f"cogs: expected 1182000, got {is_.cogs}"
    assert is_.gross_profit == 1228000.0, f"gross_profit: expected 1228000, got {is_.gross_profit}"
    assert is_.operating_expenses == 403200.0, f"opex: expected 403200, got {is_.operating_expenses}"
    assert is_.net_income > 0, f"net_income must be positive (EBITDA fallback), got {is_.net_income}"
    assert is_.owner_salary == 95000.0, f"owner_salary: expected 95000, got {is_.owner_salary}"
    assert is_.depreciation_amortization == 22000.0, f"depreciation: expected 22000, got {is_.depreciation_amortization}"
    assert is_.ebitda == 824800.0, f"ebitda: expected 824800, got {is_.ebitda}"
    assert is_.sde == 564500.0, f"sde: expected 564500, got {is_.sde}"
    assert "2028" not in is_.periods, f"2028 must not appear in periods: {is_.periods}"
    assert {"2022", "2023", "2024"}.issubset(set(is_.periods)), f"Expected 2022/2023/2024 in periods: {is_.periods}"


def test_income_statement_add_backs_populated():
    """SDE add-backs from the reconciliation sub-section must be captured."""
    output = ingest_intake_documents([_make_income_doc()])
    result = extract_financial_data(output)

    assert result.income_statement is not None
    add_backs = result.income_statement.add_backs
    assert len(add_backs) > 0, "Expected at least one add-back from SDE reconciliation"
    # Owner health insurance and vehicle are explicitly listed as add-backs.
    descriptions = [ab.description.lower() for ab in add_backs]
    assert any("health" in d or "insurance" in d for d in descriptions), (
        f"Expected owner health insurance add-back, got: {descriptions}"
    )


def test_balance_sheet_all_fields_populated():
    """All balance sheet fields must be extracted from the Alpine Balance Sheet sheet."""
    output = ingest_intake_documents([_make_balance_doc()])
    result = extract_financial_data(output)

    assert result.balance_sheet is not None, "Balance sheet must not be None"
    bs = result.balance_sheet

    assert bs.current_assets == 465200.0, f"current_assets: expected 465200, got {bs.current_assets}"
    assert bs.total_assets == 549200.0, f"total_assets: expected 549200, got {bs.total_assets}"
    assert bs.current_liabilities == 103800.0, f"current_liabilities: expected 103800, got {bs.current_liabilities}"
    assert bs.total_liabilities == 103800.0, f"total_liabilities: expected 103800, got {bs.total_liabilities}"
    assert bs.equity == 445400.0, f"equity: expected 445400, got {bs.equity}"
    assert bs.cash_and_equivalents == 284600.0, f"cash: expected 284600, got {bs.cash_and_equivalents}"
    assert bs.accounts_payable == 22400.0, f"AP: expected 22400, got {bs.accounts_payable}"


def test_asking_price_auto_estimated_from_sde():
    """With no listing document, asking_price must be auto-estimated at 3x SDE."""
    output = ingest_intake_documents([_make_income_doc(), _make_balance_doc()])
    result = extract_financial_data(output)

    assert result.loan_terms is not None, "loan_terms must be set via 3x SDE estimate"
    assert result.loan_terms.asking_price > 0, f"asking_price must be > 0, got {result.loan_terms.asking_price}"
    expected = round(564500 * 3 / 1000) * 1000  # 1,693,500 → 1694000 after rounding
    assert result.loan_terms.asking_price == expected, (
        f"asking_price: expected {expected}, got {result.loan_terms.asking_price}"
    )
    assert result.loan_terms.asking_price_estimated is True


def test_years_in_operation_derived():
    """years_in_operation must equal the number of distinct fiscal years found (3 for Alpine)."""
    output = ingest_intake_documents([_make_income_doc()])
    result = extract_financial_data(output)
    assert result.years_in_operation == 3, f"Expected 3 years of operation, got {result.years_in_operation}"


def test_location_detected():
    """'Denver, CO' must be extracted from the raw_text of the income sheet."""
    output = ingest_intake_documents([_make_income_doc()])
    result = extract_financial_data(output)
    assert result.detected_location is not None, "Location should be detected"
    assert "Denver" in result.detected_location, f"Expected Denver in location, got {result.detected_location}"


def test_combined_upload_income_and_balance_both_populated():
    """Uploading P&L + Balance Sheet must populate both extraction results."""
    output = ingest_intake_documents([_make_income_doc(), _make_balance_doc()])
    result = extract_financial_data(output)
    assert result.income_statement is not None
    assert result.balance_sheet is not None
    assert result.income_statement.revenue == 2410000.0
    assert result.balance_sheet.total_assets == 549200.0


def test_no_parsing_errors_for_clean_upload():
    """A clean Alpine upload must produce no actionable extraction error notes."""
    output = ingest_intake_ductions([_make_income_doc(), _make_balance_doc()])
    result = extract_financial_data(output)
    error_notes = [n for n in result.parsing_notes if "could not map" in n.lower()]
    assert not error_notes, f"Unexpected error notes: {error_notes}"


def ingest_intake_ductions(docs: list[IntakeDocument]):
    """Alias to keep test lines short."""
    return ingest_intake_documents(docs)
