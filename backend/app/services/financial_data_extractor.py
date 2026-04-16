from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.agents.schemas import DocumentSection, DocumentType, IngestionOutput
from app.models.schemas import AddBack, BalanceSheet, CashFlowStatement, IncomeStatement, LoanTerms
from app.services.section_kind import infer_section_kind


@dataclass(slots=True)
class ExtractedFinancialData:
    income_statement: IncomeStatement | None = None
    balance_sheet: BalanceSheet | None = None
    loan_terms: LoanTerms | None = None
    cash_flow: CashFlowStatement | None = None
    parsing_notes: list[str] = field(default_factory=list)


def extract_financial_data(ingestion_output: IngestionOutput) -> ExtractedFinancialData:
    result = ExtractedFinancialData()
    sections = _iter_sections(ingestion_output)

    pnl_section = _first_section(sections, DocumentType.PROFIT_AND_LOSS.value)
    sde_section = _first_section(sections, "sde_summary")
    balance_section = _first_section(sections, DocumentType.BALANCE_SHEET.value)
    cash_flow_section = _first_section(sections, DocumentType.CASH_FLOW_STATEMENT.value)

    if pnl_section:
        result.income_statement = _extract_income_statement(pnl_section, sde_section, result.parsing_notes)
    if balance_section:
        result.balance_sheet = _extract_balance_sheet(balance_section, result.parsing_notes)
    if sde_section:
        result.loan_terms = _extract_loan_terms(sde_section, result.parsing_notes)
    if cash_flow_section:
        result.cash_flow = _extract_cash_flow(cash_flow_section, result.parsing_notes)

    return result


def _iter_sections(ingestion_output: IngestionOutput) -> list[tuple[DocumentSection, str]]:
    sections: list[tuple[DocumentSection, str]] = []
    for document in ingestion_output.documents:
        for section in document.sections:
            rows = _section_rows(section)
            kind = _effective_section_kind(section, rows)
            sections.append((section, kind))
    return sections


def _effective_section_kind(section: DocumentSection, rows: list[dict[str, Any]]) -> str:
    if section.section_kind and section.section_kind != DocumentType.OTHER.value:
        return section.section_kind
    return infer_section_kind(
        document_type=section.document_type,
        section_name=section.section_name,
        raw_text=section.raw_text,
        rows=rows,
    )


def _first_section(
    sections: list[tuple[DocumentSection, str]],
    kind: str,
) -> DocumentSection | None:
    for section, inferred_kind in sections:
        if inferred_kind == kind:
            return section
    return None


def _extract_income_statement(
    pnl_section: DocumentSection,
    sde_section: DocumentSection | None,
    notes: list[str],
) -> IncomeStatement | None:
    rows = _section_rows(pnl_section)
    if not rows:
        notes.append(f"{_section_label(pnl_section)}: no spreadsheet rows were available for income statement extraction.")
        return None

    table = _row_table(rows)
    revenue = table.find(["total revenue", "revenue"])
    cogs = table.find(["total cost of revenue", "total cogs", "cost of goods sold"])
    gross_profit = table.find(["gross profit"])
    operating_expenses = table.find(["total operating expenses", "operating expenses"])
    net_income = table.find(["net income"])
    owner_salary = table.find(["owner salary & benefits", "owner salary and benefits", "owner salary"])
    depreciation = table.find(["depreciation & amortization", "depreciation and amortization", "depreciation"])
    ebitda = table.find(["ebitda"])

    required = {
        "revenue": revenue,
        "cogs": cogs,
        "gross profit": gross_profit,
        "operating expenses": operating_expenses,
        "net income": net_income,
    }
    missing = [label for label, value in required.items() if value is None]
    if missing:
        notes.append(f"{_section_label(pnl_section)}: could not map income statement value(s): {', '.join(missing)}.")

    sde = None
    interest_expense = None
    add_backs: list[AddBack] = []
    if sde_section:
        sde_rows = _section_rows(sde_section)
        sde_table = _row_table(sde_rows)
        sde = sde_table.find(["total sde", "total seller's discretionary earnings"])
        interest_expense = sde_table.find(["interest expense on vehicle loans", "interest expense"])
        depreciation = depreciation or sde_table.find(["depreciation & amortization", "depreciation and amortization"])
        owner_salary = owner_salary or sde_table.find(["owner salary (above market rate)", "owner salary"])
        add_backs = _extract_sde_add_backs(sde_table)
        notes.append(f"{_section_label(sde_section)}: mapped SDE add-backs into income statement review fields.")

    if all(value is None for value in [revenue, cogs, gross_profit, operating_expenses, net_income, sde]):
        return None

    notes.append(f"{_section_label(pnl_section)}: mapped most recent period into income statement review fields.")
    return IncomeStatement(
        revenue=revenue or 0,
        cogs=cogs or 0,
        gross_profit=gross_profit or 0,
        operating_expenses=operating_expenses or 0,
        depreciation_amortization=depreciation,
        interest_expense=interest_expense,
        net_income=net_income or 0,
        owner_salary=owner_salary,
        add_backs=add_backs,
        sde=sde,
        ebitda=ebitda,
        periods=table.periods,
        revenue_by_year=table.values_by_year(["total revenue", "revenue"]),
        net_income_by_year=table.values_by_year(["net income"]),
    )


def _extract_balance_sheet(section: DocumentSection, notes: list[str]) -> BalanceSheet | None:
    rows = _section_rows(section)
    if not rows:
        notes.append(f"{_section_label(section)}: no spreadsheet rows were available for balance sheet extraction.")
        return None

    table = _row_table(rows)
    current_assets = table.find(["total current assets"])
    cash = table.find(["cash & cash equivalents", "cash and cash equivalents", "cash"])
    receivables = table.find(["accounts receivable"])
    inventory = table.find(["inventory - parts & supplies", "inventory parts supplies", "inventory"])
    current_liabilities = table.find(["total current liabilities"])
    accounts_payable = table.find(["accounts payable"])
    total_assets = table.find(["total assets"])
    total_liabilities = table.find(["total liabilities"])
    equity = table.find(["total owner's equity", "total owners equity", "owner's equity", "owners equity"])

    required = {
        "current assets": current_assets,
        "current liabilities": current_liabilities,
        "total assets": total_assets,
        "total liabilities": total_liabilities,
        "equity": equity,
    }
    missing = [label for label, value in required.items() if value is None]
    if missing:
        notes.append(f"{_section_label(section)}: could not map balance sheet value(s): {', '.join(missing)}.")

    if all(value is None for value in required.values()):
        return None

    notes.append(f"{_section_label(section)}: mapped most recent period into balance sheet review fields.")
    return BalanceSheet(
        current_assets=current_assets or 0,
        cash_and_equivalents=cash,
        accounts_receivable=receivables,
        inventory=inventory,
        current_liabilities=current_liabilities or 0,
        accounts_payable=accounts_payable,
        total_assets=total_assets or 0,
        total_liabilities=total_liabilities or 0,
        equity=equity or 0,
    )


def _extract_loan_terms(section: DocumentSection, notes: list[str]) -> LoanTerms | None:
    rows = _section_rows(section)
    table = _row_table(rows)
    asking_price = table.find(["asking price (per listing)", "asking price"])
    if asking_price is None:
        return None

    notes.append(f"{_section_label(section)}: mapped asking price into loan terms review fields.")
    return LoanTerms(
        loan_amount=0,
        interest_rate=0,
        term_months=120,
        asking_price=asking_price,
    )


def _extract_cash_flow(section: DocumentSection, notes: list[str]) -> CashFlowStatement | None:
    rows = _section_rows(section)
    table = _row_table(rows)
    operating_cash_flow = table.find(["operating cash flow", "net cash provided by operating activities"])
    investing_cash_flow = table.find(["investing cash flow", "net cash used in investing activities"])
    financing_cash_flow = table.find(["financing cash flow", "net cash provided by financing activities"])
    net_cash_flow = table.find(["net cash flow", "net change in cash"])
    capital_expenditures = table.find(["capital expenditures", "capex"])
    free_cash_flow = table.find(["free cash flow"])

    if all(value is None for value in [operating_cash_flow, investing_cash_flow, financing_cash_flow, net_cash_flow]):
        return None

    notes.append(f"{_section_label(section)}: mapped most recent period into cash flow review fields.")
    return CashFlowStatement(
        operating_cash_flow=operating_cash_flow or 0,
        investing_cash_flow=investing_cash_flow,
        financing_cash_flow=financing_cash_flow,
        net_cash_flow=net_cash_flow or 0,
        capital_expenditures=capital_expenditures,
        free_cash_flow=free_cash_flow,
    )


def _extract_sde_add_backs(table: "RowTable") -> list[AddBack]:
    specs = [
        ("one-time legal fees", "one_time_expense"),
        ("owner health insurance", "personal_expense"),
        ("owner vehicle", "personal_expense"),
        ("owner cell phone", "personal_expense"),
        ("owner retirement contributions", "personal_expense"),
    ]
    add_backs: list[AddBack] = []
    for alias, category in specs:
        row = table.find_row([alias])
        if row is None or row.latest_value is None:
            continue
        amount = row.latest_value
        if amount == 0:
            continue
        add_backs.append(
            AddBack(
                description=row.label,
                amount=amount,
                category=category,  # type: ignore[arg-type]
            )
        )
    return add_backs


@dataclass(slots=True)
class RowValue:
    label: str
    normalized_label: str
    latest_value: float | None
    values_by_year: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class RowTable:
    rows: list[RowValue]
    periods: list[str]

    def find(self, aliases: list[str]) -> float | None:
        row = self.find_row(aliases)
        return row.latest_value if row else None

    def find_row(self, aliases: list[str]) -> RowValue | None:
        normalized_aliases = [_normalize_label(alias) for alias in aliases]
        for alias in normalized_aliases:
            for row in self.rows:
                if row.normalized_label == alias:
                    return row
        for alias in normalized_aliases:
            for row in self.rows:
                if alias in row.normalized_label:
                    return row
        return None

    def values_by_year(self, aliases: list[str]) -> dict[str, float]:
        row = self.find_row(aliases)
        return row.values_by_year if row else {}


def _row_table(rows: list[dict[str, Any]]) -> RowTable:
    year_columns = _year_columns(rows)
    latest_column = _latest_year_column(year_columns)
    periods = _periods(year_columns)

    parsed_rows: list[RowValue] = []
    for row in rows:
        label = _row_label(row)
        if not label:
            continue
        latest_value = _parse_number(row.get(latest_column)) if latest_column else _rightmost_numeric(row)
        values_by_year = {
            str(year): value
            for year, column in year_columns.items()
            if (value := _parse_number(row.get(column))) is not None
        }
        if latest_value is None and not values_by_year:
            continue
        parsed_rows.append(
            RowValue(
                label=label,
                normalized_label=_normalize_label(label),
                latest_value=latest_value,
                values_by_year=values_by_year,
            )
        )
    return RowTable(rows=parsed_rows, periods=periods)


def _year_columns(rows: list[dict[str, Any]]) -> dict[int, str]:
    columns: dict[int, str] = {}
    for row in rows:
        for column, value in row.items():
            if column in {"row_index", "A"}:
                continue
            text = str(value or "")
            if "%" in text:
                continue
            match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
            if not match:
                continue
            year = int(match.group(1))
            columns[year] = str(column)
    return columns


def _latest_year_column(year_columns: dict[int, str]) -> str | None:
    if not year_columns:
        return None
    latest_year = max(year_columns)
    return year_columns[latest_year]


def _periods(year_columns: dict[int, str]) -> list[str]:
    return [str(year) for year in sorted(year_columns)]


def _row_label(row: dict[str, Any]) -> str:
    value = row.get("A")
    if value not in {None, ""}:
        return str(value).strip()
    for column in _ordered_columns(row):
        value = row.get(column)
        if value not in {None, ""} and _parse_number(value) is None:
            return str(value).strip()
    return ""


def _rightmost_numeric(row: dict[str, Any]) -> float | None:
    for column in reversed(_ordered_columns(row)):
        value = _parse_number(row.get(column))
        if value is not None:
            return value
    return None


def _ordered_columns(row: dict[str, Any]) -> list[str]:
    return sorted(
        [str(column) for column in row.keys() if column != "row_index"],
        key=_column_index,
    )


def _column_index(column: str) -> int:
    total = 0
    for char in column.upper():
        if "A" <= char <= "Z":
            total = total * 26 + (ord(char) - ord("A") + 1)
    return total


def _parse_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None

    negative = text.startswith("(") and text.endswith(")")
    cleaned = text.replace("$", "").replace(",", "").replace("(", "").replace(")", "")
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    number = float(match.group(0))
    if negative:
        number = -abs(number)
    suffix_text = cleaned[match.end() : match.end() + 1].lower()
    if suffix_text == "k":
        number *= 1_000
    elif suffix_text == "m":
        number *= 1_000_000
    return number


def _normalize_label(value: str) -> str:
    normalized = value.lower().replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _section_rows(section: DocumentSection) -> list[dict[str, Any]]:
    rows = section.extracted_data.get("rows") if isinstance(section.extracted_data, dict) else None
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _section_label(section: DocumentSection) -> str:
    return section.section_name or section.section_id or section.document_id
