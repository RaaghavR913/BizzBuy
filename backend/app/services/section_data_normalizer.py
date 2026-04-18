from __future__ import annotations

import re
from typing import Any

from app.agents.schemas import DocumentSection, DocumentType
from app.services.financial_data_extractor import _parse_number, _row_table, _section_rows, _year_columns


FINANCIAL_ALIASES: dict[str, list[str]] = {
    "revenue": ["total revenue", "revenue", "gross revenue"],
    "cogs": ["total cost of revenue", "total cogs", "cost of goods sold"],
    "gross_profit": ["gross profit"],
    "operating_expenses": ["total operating expenses", "operating expenses", "total opex", "opex"],
    "net_income": ["net income", "net profit", "net income loss", "net profit loss"],
    "owner_salary": ["owner salary & benefits", "owner salary and benefits", "owner salary", "owner draw salary", "owner draw"],
    "depreciation_amortization": ["depreciation & amortization", "depreciation and amortization", "depreciation"],
    "interest_expense": ["interest expense on vehicle loans", "interest expense"],
    "ebitda": ["ebitda", "ebitda before owner add backs"],
}

SDE_ALIASES: dict[str, list[str]] = {
    "sde": ["total sde", "total seller's discretionary earnings", "reported sde", "sde"],
    "interest_expense": ["interest expense on vehicle loans", "interest expense"],
    "owner_salary": ["owner salary (above market rate)", "owner salary"],
    "depreciation_amortization": ["depreciation & amortization", "depreciation and amortization"],
    "asking_price": ["asking price (per listing)", "asking price"],
}

BALANCE_ALIASES: dict[str, list[str]] = {
    "current_assets": ["total current assets"],
    "cash_and_equivalents": ["cash & cash equivalents", "cash and cash equivalents", "cash"],
    "accounts_receivable": ["accounts receivable"],
    "inventory": ["inventory - parts & supplies", "inventory parts supplies", "inventory"],
    "current_liabilities": ["total current liabilities"],
    "accounts_payable": ["accounts payable"],
    "total_assets": ["total assets"],
    "total_liabilities": ["total liabilities"],
    "equity": ["total owner's equity", "total owners equity", "owner's equity", "owners equity", "total equity", "equity", "retained earnings"],
}

CASH_FLOW_ALIASES: dict[str, list[str]] = {
    "operating_cash_flow": ["operating cash flow", "net cash provided by operating activities"],
    "investing_cash_flow": ["investing cash flow", "net cash used in investing activities"],
    "financing_cash_flow": ["financing cash flow", "net cash provided by financing activities"],
    "net_cash_flow": ["net cash flow", "net change in cash"],
    "capital_expenditures": ["capital expenditures", "capex"],
    "free_cash_flow": ["free cash flow"],
}


def normalize_section_extracted_data(section: DocumentSection) -> dict[str, Any]:
    data = dict(section.extracted_data or {})
    rows = _section_rows(section)
    if not rows:
        return data

    kind = section.section_kind or section.document_type.value
    if kind == DocumentType.PROFIT_AND_LOSS.value:
        data.update(_mapped_table_values(rows, FINANCIAL_ALIASES))
    elif kind == "sde_summary":
        data.update(_mapped_table_values(rows, SDE_ALIASES))
        add_backs = _sde_add_backs(rows)
        if add_backs:
            data["add_backs"] = add_backs
    elif kind == DocumentType.BALANCE_SHEET.value:
        data.update(_mapped_table_values(rows, BALANCE_ALIASES))
    elif kind == DocumentType.CASH_FLOW_STATEMENT.value:
        data.update(_mapped_table_values(rows, CASH_FLOW_ALIASES))
    elif kind == DocumentType.CUSTOMER_LIST.value:
        customers = _customer_rows(rows)
        if customers:
            data["customers"] = customers
    elif kind == DocumentType.EQUIPMENT_LIST.value:
        equipment = _equipment_rows(rows)
        if equipment:
            data["equipment"] = equipment
    return data


def infer_latest_fiscal_year(rows: list[dict[str, Any]]) -> int | None:
    year_columns = _year_columns(rows)
    if year_columns:
        return max(year_columns)
    for row in rows:
        for value in row.values():
            match = re.search(r"\b(19\d{2}|20\d{2})\b", str(value or ""))
            if match:
                return int(match.group(1))
    return None


def _mapped_table_values(rows: list[dict[str, Any]], aliases_by_key: dict[str, list[str]]) -> dict[str, float]:
    table = _row_table(rows)
    values: dict[str, float] = {}
    for key, aliases in aliases_by_key.items():
        value = table.find(aliases)
        if value is not None:
            values[key] = value
    return values


def _sde_add_backs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table = _row_table(rows)
    specs = [
        ("one-time legal fees", "one_time_expense"),
        ("owner health insurance", "personal_expense"),
        ("owner vehicle", "personal_expense"),
        ("owner cell phone", "personal_expense"),
        ("owner retirement contributions", "personal_expense"),
    ]
    add_backs: list[dict[str, Any]] = []
    for alias, category in specs:
        row = table.find_row([alias])
        if row is None or row.latest_value in (None, 0):
            continue
        add_backs.append({"description": row.label, "amount": row.latest_value, "category": category})
    return add_backs


def _customer_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    header = _header_map(rows, ["customer name", "revenue"])
    if not header:
        return []
    customers: list[dict[str, Any]] = []
    name_col = header.get("customer name") or header.get("name")
    revenue_col = _first_header_containing(header, "revenue")
    for row in rows[header["_index"] + 1 :]:
        name = str(row.get(name_col) or "").strip() if name_col else ""
        if not name or "total" in name.lower() or "summary" in name.lower():
            continue
        revenue = _parse_number(row.get(revenue_col)) if revenue_col else None
        if revenue is None:
            continue
        customers.append(
            {
                "name": name,
                "annualRevenue": revenue,
                "type": row.get(header.get("type", "")),
                "contractType": row.get(header.get("contract type", "")),
                "location": row.get(header.get("location", "")),
            }
        )
    return customers


def _equipment_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    header = _header_map(rows, ["asset description"])
    if not header:
        return []
    equipment: list[dict[str, Any]] = []
    name_col = header.get("asset description")
    value_col = header.get("est fmv") or header.get("fmv") or header.get("book value")
    for row in rows[header["_index"] + 1 :]:
        name = str(row.get(name_col) or "").strip() if name_col else ""
        if not name or "total" in name.lower():
            continue
        value = _parse_number(row.get(value_col)) if value_col else None
        item: dict[str, Any] = {
            "name": name,
            "estimatedValue": value,
            "yearAcquired": row.get(header.get("year acquired", "")),
            "includedInSale": row.get(header.get("included in sale", "")),
            "notes": row.get(header.get("notes", "")),
        }
        equipment.append(item)
    return equipment


def _header_map(rows: list[dict[str, Any]], required_labels: list[str]) -> dict[str, Any]:
    required = [_normalize_header(label) for label in required_labels]
    for index, row in enumerate(rows):
        labels = {
            _normalize_header(str(value)): str(column)
            for column, value in row.items()
            if column != "row_index" and value not in {None, ""}
        }
        if all(any(required_label in label for label in labels) for required_label in required):
            labels["_index"] = index
            return labels
    return {}


def _first_header_containing(header: dict[str, Any], needle: str) -> str | None:
    normalized = _normalize_header(needle)
    for label, column in header.items():
        if label == "_index":
            continue
        if normalized in label:
            return str(column)
    return None


def _normalize_header(value: str) -> str:
    normalized = value.lower().replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()
