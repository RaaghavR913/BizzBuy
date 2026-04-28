from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from app.agents.schemas import AgentEnvelope, AgentResult, AgentSource, DocumentSection, IngestionOutput, NormalizedFinding, Severity
from app.services.calculations import (
    calculate_dscr,
    calculate_ebitda,
    calculate_monthly_payment,
    calculate_sde,
    calculate_valuation_multiple,
    calculate_working_capital,
)
from app.services.section_data_normalizer import normalize_section_extracted_data


SBA_DEFAULTS = {
    "MAX_LOAN": 5_000_000,
    "INTEREST_RATE": 0.105,
    "TERM_YEARS": 10,
    "MIN_DSCR": 1.25,
    "MIN_DOWN_PAYMENT_PERCENT": 0.10,
    "DEFAULT_DOWN_PAYMENT_PERCENT": 0.20,
    "CLOSING_COST_PERCENT": 0.035,
    "DOWN_PAYMENT_SCENARIOS": (0.10, 0.15, 0.20),
    "SUGGESTED_MULTIPLE_LOW": 2.5,
    "SUGGESTED_MULTIPLE_HIGH": 3.5,
}

AGENT_WEIGHTS: dict[str, float] = {
    "financial_analysis": 0.25,
    "tax_compliance": 0.10,
    "ar_collections": 0.10,
    "customer_concentration": 0.15,
    "operations_transferability": 0.15,
    "lease_contract": 0.10,
    "market_macro": 0.05,
    "lending_affordability": 0.10,
}

AGENT_DISPLAY_NAMES: dict[str, str] = {
    "financial_analysis": "Financial Analysis",
    "tax_compliance": "Tax Compliance",
    "ar_collections": "AR/Collections",
    "customer_concentration": "Customer Concentration",
    "operations_transferability": "Operations & Transferability",
    "lease_contract": "Lease & Contract",
    "market_macro": "Market & Macro",
    "lending_affordability": "Lending & Affordability",
}

AGENT_SOURCES: dict[str, AgentSource] = {
    "financial_analysis": AgentSource.FINANCIAL,
    "tax_compliance": AgentSource.TAX,
    "ar_collections": AgentSource.AR,
    "customer_concentration": AgentSource.CUSTOMER,
    "operations_transferability": AgentSource.OPERATIONS,
    "lease_contract": AgentSource.LEASE,
    "market_macro": AgentSource.MARKET,
    "lending_affordability": AgentSource.LENDING,
}

SEVERITY_ORDER = {
    Severity.CRITICAL.value: 0,
    Severity.HIGH.value: 1,
    Severity.MEDIUM.value: 2,
    Severity.LOW.value: 3,
}


def safe_num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in (float("inf"), float("-inf")) else None


def safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _is_plausible_reporting_year(value: int | None) -> bool:
    return isinstance(value, int) and 1990 <= value <= datetime.now(timezone.utc).year + 2


def section_kind(section: DocumentSection) -> str:
    return getattr(section, "section_kind", None) or section.document_type.value


def section_is(section: DocumentSection, *kinds: str) -> bool:
    effective = section_kind(section)
    if effective in kinds:
        return True
    if effective == "sde_summary":
        return "sde_summary" in kinds
    return section.document_type.value in kinds


def extract_revenue_by_year(sections: Sequence[DocumentSection]) -> dict[int, float]:
    revenue_by_year: dict[int, float] = {}
    for section in sections:
        year = section.timeframe.fiscal_year
        if not _is_plausible_reporting_year(year) or year in revenue_by_year:
            continue
        revenue = safe_num(
            section.extracted_data.get("revenue")
            or section.extracted_data.get("gross_revenue")
            or section.extracted_data.get("net_revenue")
            or section.extracted_data.get("total_revenue")
            or section.extracted_data.get("gross_receipts")
            or section.extracted_data.get("gross_sales")
        )
        if revenue is not None:
            revenue_by_year[year] = revenue
    return dict(sorted(revenue_by_year.items()))


def compute_financial_metrics(sections: Sequence[DocumentSection]) -> dict[str, Any]:
    pl_sections = [
        section
        for section in sections
        if section_is(section, "profit_and_loss", "cash_flow_statement") and section_kind(section) != "sde_summary"
    ]
    yearly_raw: dict[int, dict[str, Any]] = {}
    for section in pl_sections:
        year = section.timeframe.fiscal_year
        if year:
            yearly_raw.setdefault(year, {}).update(section.extracted_data)

    annual_financials: list[dict[str, Any]] = []
    for year, data in sorted(yearly_raw.items()):
        revenue = safe_num(data.get("revenue") or data.get("gross_revenue") or data.get("net_revenue") or data.get("total_revenue"))
        cogs = safe_num(data.get("cogs") or data.get("cost_of_goods_sold") or data.get("cost_of_revenue"))
        gross_profit = safe_num(data.get("gross_profit"))
        if gross_profit is None and revenue is not None and cogs is not None:
            gross_profit = revenue - cogs
        net_income = safe_num(data.get("net_income") or data.get("net_profit") or data.get("net_earnings"))
        depreciation = safe_num(data.get("depreciation") or data.get("depreciation_amortization"))
        amortization = safe_num(data.get("amortization"))
        interest_expense = safe_num(data.get("interest_expense") or data.get("interest"))
        taxes = safe_num(data.get("income_tax") or data.get("taxes") or data.get("tax_expense"))
        operating_expenses = safe_num(data.get("operating_expenses") or data.get("total_operating_expenses") or data.get("opex"))
        ebitda = None
        if net_income is not None:
            ebitda = calculate_ebitda(
                net_income,
                interest_expense=interest_expense or 0,
                taxes=taxes or 0,
                depreciation=depreciation or 0,
                amortization=amortization or 0,
            )
        annual_financials.append(
            {
                "year": year,
                "revenue": revenue,
                "cogs": cogs,
                "gross_profit": gross_profit,
                "net_income": net_income,
                "ebitda": ebitda,
                "operating_expenses": operating_expenses,
                "depreciation": depreciation,
                "amortization": amortization,
                "interest_expense": interest_expense,
                "taxes": taxes,
            }
        )

    most_recent_year = annual_financials[-1] if annual_financials else None
    revenue_growth_rates: list[dict[str, Any]] = []
    for index in range(1, len(annual_financials)):
        prior = annual_financials[index - 1]
        current = annual_financials[index]
        growth = None
        if prior["revenue"] not in (None, 0) and current["revenue"] is not None:
            growth = (current["revenue"] - prior["revenue"]) / prior["revenue"]
        revenue_growth_rates.append({"from_year": prior["year"], "to_year": current["year"], "rate": growth})

    balance_sections = [section for section in sections if section_is(section, "balance_sheet")]
    balance_sections.sort(key=lambda item: item.timeframe.fiscal_year or 0, reverse=True)
    balance_data = balance_sections[0].extracted_data if balance_sections else {}
    balance_sheet = {
        "total_assets": safe_num(balance_data.get("total_assets")),
        "total_liabilities": safe_num(balance_data.get("total_liabilities")),
        "current_assets": safe_num(balance_data.get("current_assets") or balance_data.get("total_current_assets")),
        "current_liabilities": safe_num(balance_data.get("current_liabilities") or balance_data.get("total_current_liabilities")),
        "equity": safe_num(
            balance_data.get("total_equity")
            or balance_data.get("owner's_equity")
            or balance_data.get("shareholders_equity")
            or balance_data.get("equity")
        ),
        "total_debt": safe_num(balance_data.get("total_debt") or balance_data.get("long_term_debt")),
    }

    cash_flow_sections = [section for section in sections if section_is(section, "cash_flow_statement")]
    cash_flow_sections.sort(key=lambda item: item.timeframe.fiscal_year or 0, reverse=True)
    cash_data = cash_flow_sections[0].extracted_data if cash_flow_sections else {}
    operating_cash_flow = safe_num(
        cash_data.get("operating_cash_flow")
        or cash_data.get("cash_from_operations")
        or cash_data.get("net_cash_from_operating_activities")
    )
    capital_expenditures = safe_num(
        cash_data.get("capital_expenditures")
        or cash_data.get("capex")
        or cash_data.get("purchase_of_property_equipment")
    )
    free_cash_flow = operating_cash_flow
    if operating_cash_flow is not None and capital_expenditures is not None:
        free_cash_flow = operating_cash_flow - abs(capital_expenditures)

    pl_only = [section for section in sections if section_is(section, "profit_and_loss", "sde_summary")]
    latest_pl_year = max((section.timeframe.fiscal_year or 0 for section in pl_only), default=0)
    sde_data: dict[str, Any] = {}
    for section in pl_only:
        if (section.timeframe.fiscal_year or 0) == latest_pl_year:
            sde_data.update(section.extracted_data)
    reported_net_income = safe_num(sde_data.get("net_income") or sde_data.get("net_profit"))
    owner_salary = safe_num(sde_data.get("owner_salary") or sde_data.get("officer_compensation") or sde_data.get("owners_compensation"))
    owner_benefits = safe_num(sde_data.get("owner_benefits") or sde_data.get("officer_benefits"))
    depreciation = safe_num(sde_data.get("depreciation") or sde_data.get("depreciation_amortization"))
    interest_expense = safe_num(sde_data.get("interest_expense") or sde_data.get("interest"))
    one_time_expenses = safe_num(sde_data.get("one_time_expenses") or sde_data.get("nonrecurring_expenses"))
    total_add_backs = sum(value or 0 for value in [owner_salary, owner_benefits, depreciation, interest_expense, one_time_expenses])
    sde_value = None
    if reported_net_income is not None:
        sde_value = calculate_sde(
            reported_net_income,
            owner_salary=owner_salary or 0,
            add_backs=(owner_benefits or 0) + (one_time_expenses or 0),
            depreciation=depreciation or 0,
            interest_expense=interest_expense or 0,
        )

    current_ratio = safe_div(balance_sheet["current_assets"], balance_sheet["current_liabilities"])
    debt_to_equity = safe_div(balance_sheet["total_liabilities"], balance_sheet["equity"])
    working_capital = None
    if balance_sheet["current_assets"] is not None and balance_sheet["current_liabilities"] is not None:
        working_capital = calculate_working_capital(balance_sheet["current_assets"], balance_sheet["current_liabilities"])

    divergence = None
    if operating_cash_flow is not None and most_recent_year and most_recent_year["net_income"] not in (None, 0):
        divergence = abs(operating_cash_flow - most_recent_year["net_income"]) / abs(most_recent_year["net_income"])

    return {
        "annual_financials": annual_financials,
        "revenue_growth_rates": revenue_growth_rates,
        "most_recent_year": most_recent_year,
        "gross_margin": safe_div(most_recent_year["gross_profit"], most_recent_year["revenue"]) if most_recent_year else None,
        "net_margin": safe_div(most_recent_year["net_income"], most_recent_year["revenue"]) if most_recent_year else None,
        "ebitda_margin": safe_div(most_recent_year["ebitda"], most_recent_year["revenue"]) if most_recent_year else None,
        "balance_sheet": balance_sheet,
        "current_ratio": current_ratio,
        "debt_to_equity": debt_to_equity,
        "working_capital": working_capital,
        "cash_flow": {
            "operating_cash_flow": operating_cash_flow,
            "capital_expenditures": capital_expenditures,
            "free_cash_flow": free_cash_flow,
        },
        "cash_flow_vs_net_income_divergence": divergence,
        "sde": {
            "reported_net_income": reported_net_income,
            "owner_salary": owner_salary,
            "owner_benefits": owner_benefits,
            "depreciation": depreciation,
            "interest_expense": interest_expense,
            "one_time_expenses": one_time_expenses,
            "total_add_backs": total_add_backs if total_add_backs > 0 else None,
            "sde": sde_value,
        },
        "data_years_available": len(annual_financials),
        "document_types": sorted({section_kind(section) for section in sections}),
    }


def compute_tax_metrics(sections: Sequence[DocumentSection]) -> dict[str, Any]:
    tax_types = {"tax_return_1120s", "tax_return_1040", "tax_return_schedule_c"}
    financial_sections = [section for section in sections if section_is(section, "profit_and_loss") and section_kind(section) != "sde_summary"]
    tax_sections = [section for section in sections if section_is(section, *tax_types)]
    revenue_from_financials = extract_revenue_by_year(financial_sections)
    revenue_from_tax_returns = extract_revenue_by_year(tax_sections)
    financial_years = sorted(revenue_from_financials.keys())
    tax_return_years = sorted(revenue_from_tax_returns.keys())
    overlapping_years = [year for year in financial_years if year in tax_return_years]
    missing_tax_years = [year for year in financial_years if year not in tax_return_years]

    discrepancies: list[dict[str, Any]] = []
    for year in overlapping_years:
        financial_revenue = revenue_from_financials.get(year)
        tax_revenue = revenue_from_tax_returns.get(year)
        absolute_discrepancy = None
        percentage_discrepancy = None
        if financial_revenue is not None and tax_revenue is not None:
            absolute_discrepancy = financial_revenue - tax_revenue
            if financial_revenue != 0:
                percentage_discrepancy = absolute_discrepancy / financial_revenue
        discrepancies.append(
            {
                "year": year,
                "revenue_per_financials": financial_revenue,
                "revenue_per_tax_return": tax_revenue,
                "absolute_discrepancy": absolute_discrepancy,
                "percentage_discrepancy": percentage_discrepancy,
                "flagged": percentage_discrepancy is not None and abs(percentage_discrepancy) > 0.05,
            }
        )

    absolute_values = [abs(item["absolute_discrepancy"]) for item in discrepancies if item["absolute_discrepancy"] is not None]
    percentage_values = [abs(item["percentage_discrepancy"]) for item in discrepancies if item["percentage_discrepancy"] is not None]
    return {
        "revenue_discrepancies": discrepancies,
        "year_coverage": {
            "financial_years": financial_years,
            "tax_return_years": tax_return_years,
            "overlapping_years": overlapping_years,
            "missing_tax_years": missing_tax_years,
        },
        "has_tax_returns": bool(tax_sections),
        "has_financials": bool(financial_sections),
        "tax_revenue_exceeds_financials": any(
            item["absolute_discrepancy"] is not None and item["absolute_discrepancy"] < 0 for item in discrepancies
        ),
        "max_absolute_discrepancy": max(absolute_values) if absolute_values else None,
        "max_percentage_discrepancy": max(percentage_values) if percentage_values else None,
    }


def compute_ar_metrics(sections: Sequence[DocumentSection]) -> dict[str, Any]:
    ar_sections = [section for section in sections if section_is(section, "ar_aging_report")]
    if not ar_sections:
        return {
            "total_ar": 0.0,
            "aging_buckets": {"current": 0.0, "thirty_day": 0.0, "sixty_day": 0.0, "ninety_day": 0.0, "over_90": 0.0},
            "aging_percentages": {"current": 0.0, "thirty_day": 0.0, "sixty_day": 0.0, "ninety_day": 0.0, "over_90": 0.0},
            "dso": None,
            "annual_revenue_used_for_dso": None,
            "customer_concentrations": [],
            "top_customer_percent": 0.0,
            "top5_customers_percent": 0.0,
            "estimated_write_off_amount": 0.0,
            "estimated_write_off_percent": 0.0,
            "has_ar_data": False,
        }

    merged: dict[str, Any] = {}
    for section in ar_sections:
        section_data = section.extracted_data
        if isinstance(section_data.get("rows"), list) and not section_data.get("customers"):
            section_data = normalize_section_extracted_data(section)
        merged.update(section_data)

    total_ar = safe_num(merged.get("total_ar") or merged.get("total_accounts_receivable") or merged.get("ar_total") or merged.get("total")) or 0.0
    current = safe_num(merged.get("current") or merged.get("current_amount")) or 0.0
    thirty_day = safe_num(merged.get("30_days") or merged.get("30day") or merged.get("days_30") or merged.get("bucket_30")) or 0.0
    sixty_day = safe_num(merged.get("60_days") or merged.get("60day") or merged.get("days_60") or merged.get("bucket_60")) or 0.0
    ninety_day = safe_num(merged.get("90_days") or merged.get("90day") or merged.get("days_90") or merged.get("bucket_90")) or 0.0
    over_90 = safe_num(merged.get("over_90") or merged.get("over90") or merged.get("90plus") or merged.get("bucket_over90")) or 0.0
    computed_total = current + thirty_day + sixty_day + ninety_day + over_90
    effective_total = total_ar if total_ar > 0 else computed_total
    customers = merged.get("customers")
    if effective_total <= 0 and isinstance(customers, list):
        effective_total = sum(
            safe_num(customer.get("total") or customer.get("balance") or customer.get("amount")) or 0.0
            for customer in customers
            if isinstance(customer, dict)
        )

    annual_revenue_used_for_dso = None
    pl_sections = sorted(
        [section for section in sections if section_is(section, "profit_and_loss") and section_kind(section) != "sde_summary"],
        key=lambda item: item.timeframe.fiscal_year or 0,
        reverse=True,
    )
    for section in pl_sections:
        annual_revenue_used_for_dso = safe_num(
            section.extracted_data.get("revenue")
            or section.extracted_data.get("gross_revenue")
            or section.extracted_data.get("net_revenue")
            or section.extracted_data.get("total_revenue")
        )
        if annual_revenue_used_for_dso is not None:
            break

    customer_concentrations: list[dict[str, Any]] = []
    grouped_customer_buckets: list[dict[str, Any]] = []
    if isinstance(customers, list):
        for index, customer in enumerate(customers):
            if not isinstance(customer, dict):
                continue
            amount = safe_num(customer.get("total") or customer.get("balance") or customer.get("amount")) or 0.0
            customer_payload = {
                "customer_id": str(customer.get("id") or customer.get("customer_id") or f"customer_{index}"),
                "customer_name": str(customer.get("name")) if customer.get("name") else None,
                "amount": amount,
                "percentage": (amount / effective_total) if effective_total else 0.0,
                "is_grouped": _is_grouped_customer_bucket(customer),
            }
            if customer_payload["is_grouped"]:
                grouped_customer_buckets.append(customer_payload)
            else:
                customer_concentrations.append(customer_payload)
    customer_concentrations.sort(key=lambda item: item["amount"], reverse=True)
    grouped_customer_buckets.sort(key=lambda item: item["amount"], reverse=True)

    if not any([current, thirty_day, sixty_day, ninety_day, over_90]) and isinstance(customers, list):
        current = sum(safe_num(customer.get("current")) or safe_num(customer.get("0_30")) or 0.0 for customer in customers if isinstance(customer, dict))
        thirty_day = sum(safe_num(customer.get("30_days")) or safe_num(customer.get("31_60")) or 0.0 for customer in customers if isinstance(customer, dict))
        sixty_day = sum(safe_num(customer.get("60_days")) or safe_num(customer.get("61_90")) or 0.0 for customer in customers if isinstance(customer, dict))
        ninety_day = sum(safe_num(customer.get("90_days")) or safe_num(customer.get("91_120")) or 0.0 for customer in customers if isinstance(customer, dict))
        over_90 = sum(safe_num(customer.get("over_90")) or safe_num(customer.get("120_plus")) or 0.0 for customer in customers if isinstance(customer, dict))

    aging_percentages = {
        "current": (current / effective_total) if effective_total else 0.0,
        "thirty_day": (thirty_day / effective_total) if effective_total else 0.0,
        "sixty_day": (sixty_day / effective_total) if effective_total else 0.0,
        "ninety_day": (ninety_day / effective_total) if effective_total else 0.0,
        "over_90": (over_90 / effective_total) if effective_total else 0.0,
    }
    estimated_write_off_amount = ninety_day * 0.5 + over_90 * 0.9
    return {
        "total_ar": effective_total,
        "aging_buckets": {
            "current": current,
            "thirty_day": thirty_day,
            "sixty_day": sixty_day,
            "ninety_day": ninety_day,
            "over_90": over_90,
        },
        "aging_percentages": aging_percentages,
        "dso": ((effective_total / annual_revenue_used_for_dso) * 365) if annual_revenue_used_for_dso and effective_total else None,
        "annual_revenue_used_for_dso": annual_revenue_used_for_dso,
        "customer_concentrations": customer_concentrations,
        "grouped_customer_buckets": grouped_customer_buckets,
        "aggregated_customer_bucket_percent": sum(item["percentage"] for item in grouped_customer_buckets),
        "top_customer_percent": customer_concentrations[0]["percentage"] if customer_concentrations else 0.0,
        "top5_customers_percent": sum(item["percentage"] for item in customer_concentrations[:5]),
        "estimated_write_off_amount": estimated_write_off_amount,
        "estimated_write_off_percent": (estimated_write_off_amount / effective_total) if effective_total else 0.0,
        "has_ar_data": True,
    }


def _is_grouped_customer_bucket(customer: Mapping[str, Any]) -> bool:
    explicit = customer.get("is_grouped")
    if isinstance(explicit, bool):
        return explicit
    name = str(customer.get("name") or customer.get("customer_name") or customer.get("customerName") or "")
    normalized = name.lower()
    return bool(
        "other" in normalized
        or "misc" in normalized
        or "various" in normalized
        or "remaining" in normalized
        or "all other" in normalized
        or "accounts)" in normalized
        or "clients)" in normalized
        or "customers)" in normalized
    )


def compute_customer_metrics(ingestion_output: IngestionOutput) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for doc in ingestion_output.documents:
        for section in doc.sections:
            if not section_is(section, "customer_list"):
                continue
            candidates = section.extracted_data.get("customers") or section.extracted_data.get("rows") or section.extracted_data.get("items") or []
            if not isinstance(candidates, list):
                continue
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("customer") or item.get("customerName")
                revenue = safe_num(item.get("annualRevenue") or item.get("revenue") or item.get("annual_revenue"))
                if name and revenue is not None and revenue >= 0:
                    rows.append({"name": str(name), "annual_revenue": revenue})

    total_revenue = sum(item["annual_revenue"] for item in rows)
    customers = [
        {
            **item,
            "revenue_percent": ((item["annual_revenue"] / total_revenue) * 100) if total_revenue else 0.0,
        }
        for item in rows
    ]
    customers.sort(key=lambda item: item["revenue_percent"], reverse=True)
    return {
        "total_revenue": total_revenue,
        "customers": customers,
        "herfindahl_index": sum(item["revenue_percent"] ** 2 for item in customers),
        "top_customer_percent": customers[0]["revenue_percent"] if customers else 0.0,
        "top5_percent": sum(item["revenue_percent"] for item in customers[:5]),
        "top10_percent": sum(item["revenue_percent"] for item in customers[:10]),
        "single_customer_dependency": bool(customers and customers[0]["revenue_percent"] > 25),
    }


def compute_ops_metrics(ingestion_output: IngestionOutput) -> dict[str, Any]:
    employees: list[dict[str, Any]] = []
    equipment: list[dict[str, Any]] = []
    insurance: list[dict[str, Any]] = []
    licenses: list[dict[str, Any]] = []
    for doc in ingestion_output.documents:
        for section in doc.sections:
            data = section.extracted_data
            if section_is(section, "employee_roster"):
                for item in data.get("employees") or data.get("roster") or data.get("rows") or []:
                    if isinstance(item, dict):
                        employees.append(item)
            if section_is(section, "equipment_list"):
                for item in data.get("equipment") or data.get("items") or data.get("rows") or []:
                    if isinstance(item, dict):
                        equipment.append(item)
            if section_is(section, "insurance_policy"):
                policies = data.get("policies") if isinstance(data.get("policies"), list) else [data]
                for item in policies:
                    if isinstance(item, dict):
                        insurance.append(item)
            if isinstance(data.get("licenses"), list):
                for item in data["licenses"]:
                    if isinstance(item, dict):
                        licenses.append(item)

    known_tenures = [safe_num(item.get("tenureYears")) for item in employees]
    known_tenures = [value for value in known_tenures if value is not None]
    average_tenure = (sum(known_tenures) / len(known_tenures)) if known_tenures else None
    return {
        "headcount": len(employees),
        "average_tenure_years": average_tenure,
        "total_equipment_value": sum(safe_num(item.get("estimatedValue") or item.get("value")) or 0.0 for item in equipment),
        "total_annual_premiums": sum(safe_num(item.get("annualPremium") or item.get("premium")) or 0.0 for item in insurance),
        "license_count": len(licenses),
        "transferable_license_count": sum(1 for item in licenses if item.get("transferable") is True),
        "employees": employees,
        "equipment": equipment,
        "insurance": insurance,
        "licenses": licenses,
        "has_operational_docs": bool(employees or equipment or insurance or licenses),
    }


def compute_lease_metrics(ingestion_output: IngestionOutput, now: datetime | None = None) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    lease_data: dict[str, Any] | None = None
    contracts: list[dict[str, Any]] = []
    for doc in ingestion_output.documents:
        for section in doc.sections:
            if section_is(section, "lease_agreement") and lease_data is None:
                lease_data = section.extracted_data
            if section_is(section, "contract"):
                contracts.append(section.extracted_data)

    monthly_rent = safe_num((lease_data or {}).get("monthlyRent") or (lease_data or {}).get("monthly_rent") or (lease_data or {}).get("rent"))
    lease_end = (lease_data or {}).get("leaseEnd") or (lease_data or {}).get("lease_end") or (lease_data or {}).get("endDate") or (lease_data or {}).get("expirationDate")
    remaining_months = None
    if isinstance(lease_end, str):
        try:
            lease_end_dt = datetime.fromisoformat(lease_end.replace("Z", "+00:00"))
            remaining_months = max(0, round((lease_end_dt - current_time).days / 30.44))
        except ValueError:
            remaining_months = None

    return {
        "has_lease": lease_data is not None,
        "has_contracts": bool(contracts),
        "monthly_rent": monthly_rent,
        "annual_rent": monthly_rent * 12 if monthly_rent is not None else None,
        "lease_end": lease_end,
        "remaining_months": remaining_months,
        "raw_lease": lease_data,
        "contracts": contracts,
    }


def infer_business_context(ingestion_output: IngestionOutput) -> dict[str, str | None]:
    all_text = "\n".join(section.raw_text for doc in ingestion_output.documents for section in doc.sections if section.raw_text)
    location = None
    business_type = None
    revenue_values: list[float] = []
    employee_counts: list[float] = []

    for doc in ingestion_output.documents:
        for section in doc.sections:
            revenue = safe_num(section.extracted_data.get("revenue") or section.extracted_data.get("totalRevenue"))
            if revenue and revenue > 0:
                revenue_values.append(revenue)
            employees = safe_num(section.extracted_data.get("employees") or section.extracted_data.get("employeeCount"))
            if employees and employees > 0:
                employee_counts.append(employees)
        for section in doc.sections:
            if section_is(section, "lease_agreement"):
                lease_text = section.raw_text
                marker = "Tenant:"
                if marker in lease_text:
                    business_type = lease_text.split(marker, 1)[1].splitlines()[0].split(",")[0].strip() or business_type
                break

    revenue_range = f"${(max(revenue_values) / 1_000_000):.1f}M" if revenue_values else None
    employee_count = f"approximately {int(max(employee_counts))}" if employee_counts else None
    if "," in all_text:
        import re

        match = re.search(r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*([A-Z]{2})\b", all_text)
        if match:
            location = f"{match.group(1)}, {match.group(2)}"

    return {
        "business_type": business_type,
        "location": location,
        "revenue_range": revenue_range,
        "employee_count": employee_count,
    }


def compute_sba_lending(sde: float, asking_price: float, interest_rate: float | None = None, term_years: int | None = None) -> dict[str, Any]:
    rate = interest_rate if interest_rate is not None else SBA_DEFAULTS["INTEREST_RATE"]
    years = term_years if term_years is not None else SBA_DEFAULTS["TERM_YEARS"]
    down_payment = asking_price * SBA_DEFAULTS["DEFAULT_DOWN_PAYMENT_PERCENT"]
    loan_amount = min(asking_price - down_payment, SBA_DEFAULTS["MAX_LOAN"])
    monthly_payment = calculate_monthly_payment(loan_amount, rate, years * 12)
    annual_debt_service = monthly_payment * 12
    dscr = calculate_dscr(sde, annual_debt_service)

    scenarios: list[dict[str, Any]] = []
    for percent in SBA_DEFAULTS["DOWN_PAYMENT_SCENARIOS"]:
        scenario_down_payment = asking_price * percent
        scenario_loan = min(asking_price - scenario_down_payment, SBA_DEFAULTS["MAX_LOAN"])
        scenario_monthly = calculate_monthly_payment(scenario_loan, rate, years * 12)
        scenario_annual = scenario_monthly * 12
        scenarios.append(
            {
                "percent": percent,
                "amount": round(scenario_down_payment),
                "loan_amount": round(scenario_loan),
                "monthly_payment": round(scenario_monthly),
                "dscr": round(calculate_dscr(sde, scenario_annual), 2) if scenario_annual > 0 else 0.0,
            }
        )

    lower = 0.0
    upper = SBA_DEFAULTS["MAX_LOAN"]
    for _ in range(50):
        candidate = (lower + upper) / 2
        candidate_monthly = calculate_monthly_payment(candidate, rate, years * 12)
        candidate_dscr = calculate_dscr(sde, candidate_monthly * 12)
        if candidate_dscr >= SBA_DEFAULTS["MIN_DSCR"]:
            lower = candidate
        else:
            upper = candidate

    closing_costs = loan_amount * SBA_DEFAULTS["CLOSING_COST_PERCENT"]
    working_capital = (sde / 12) * 3
    total_cash_needed = down_payment + closing_costs + working_capital
    return {
        "loan_amount": round(loan_amount),
        "monthly_payment": round(monthly_payment),
        "annual_debt_service": round(annual_debt_service),
        "dscr": round(dscr, 2) if dscr != float("inf") else 999.0,
        "dscr_meets_minimum": dscr >= SBA_DEFAULTS["MIN_DSCR"],
        "down_payment_scenarios": scenarios,
        "max_supportable_loan": round(lower),
        "sde_multiple": round(calculate_valuation_multiple(asking_price, sde), 2) if sde > 0 else 0.0,
        "total_cash_needed": {
            "down_payment": round(down_payment),
            "closing_costs": round(closing_costs),
            "working_capital": round(working_capital),
            "total": round(total_cash_needed),
        },
        "suggested_price_range": {
            "low": round(sde * SBA_DEFAULTS["SUGGESTED_MULTIPLE_LOW"]),
            "high": round(sde * SBA_DEFAULTS["SUGGESTED_MULTIPLE_HIGH"]),
        },
        "interest_rate": rate,
        "term_years": years,
        "eligible_for_sba": loan_amount <= SBA_DEFAULTS["MAX_LOAN"],
        "down_payment_percent": SBA_DEFAULTS["DEFAULT_DOWN_PAYMENT_PERCENT"],
    }


def _agent_payload(result: AgentResult[Any] | None) -> Any:
    if not result or result.status != "success" or not result.data:
        return None
    data = result.data
    if isinstance(data, AgentEnvelope):
        raw = data.raw_domain_output
        return raw if raw is not None else data
    return data


def _agent_summary(result: AgentResult[Any] | None) -> str:
    if not result or result.status != "success" or not result.data:
        return ""
    data = result.data
    if isinstance(data, AgentEnvelope):
        return data.summary or ""
    return getattr(data, "summary", "") or ""


def _agent_score(result: AgentResult[Any] | None) -> int | None:
    if not result or result.status != "success" or not result.data:
        return None
    data = result.data
    if isinstance(data, AgentEnvelope):
        return data.overall_score
    return getattr(data, "overall_score", None)


def _normalized_finding_financial_impact(finding: NormalizedFinding) -> float | int | None:
    for key in ("financial_impact_usd", "potential_tax_exposure", "amount_at_risk", "validated_sde_delta"):
        value = finding.metric_impact.get(key)
        if isinstance(value, (int, float)):
            return value
    return None


def extract_risks(agent_results: Mapping[str, AgentResult[Any]], agent_key: str) -> list[Any]:
    result = agent_results.get(agent_key)
    if not result or result.status != "success" or not result.data:
        return []
    if isinstance(result.data, AgentEnvelope) and result.data.findings:
        return result.data.findings
    payload = _agent_payload(result)
    if payload is None:
        return []
    if agent_key == "tax_compliance":
        return getattr(payload, "compliance_flags", []) or []
    if agent_key == "ar_collections":
        return getattr(payload, "collectibility_flags", []) or []
    if agent_key == "customer_concentration":
        return getattr(payload, "contract_risks", []) or []
    if agent_key == "market_macro":
        return getattr(payload, "threats", []) or []
    return getattr(payload, "risks", []) or []


def compute_synthesis_metrics(agent_results: Mapping[str, AgentResult[Any]]) -> dict[str, Any]:
    successful_agents = [key for key in AGENT_WEIGHTS if agent_results.get(key) and agent_results[key].status == "success"]
    failed_agents = [key for key in AGENT_WEIGHTS if key not in successful_agents]
    total_available_weight = sum(AGENT_WEIGHTS[key] for key in successful_agents)

    if not successful_agents or total_available_weight == 0:
        composite_score = 100
    else:
        weighted_sum = 0.0
        for key in successful_agents:
            score = _agent_score(agent_results.get(key))
            if score is None:
                continue
            weighted_sum += score * (AGENT_WEIGHTS[key] / total_available_weight)
        composite_score = round((11 - weighted_sum) * 10)

    red_flags: list[dict[str, Any]] = []
    green_flags: list[dict[str, Any]] = []
    section_summaries: dict[str, Any] = {}
    for key in AGENT_WEIGHTS:
        result = agent_results.get(key)
        display_name = AGENT_DISPLAY_NAMES[key]
        if result and result.status == "success" and result.data:
            score = _agent_score(result) or 0
            summary = _agent_summary(result)
            risks = extract_risks(agent_results, key)
            section_summaries[key] = {
                "score": score,
                "summary": summary,
                "top_risks": [
                    f"[{str(getattr(risk, 'severity', 'unknown')).replace('Severity.', '').upper()}] {getattr(risk, 'title', getattr(risk, 'description', 'Risk'))}"
                    for risk in risks[:3]
                ],
            }
            if score >= 7:
                green_flags.append(
                    {
                        "id": f"{key}-green",
                        "source": AGENT_SOURCES[key],
                        "title": f"{display_name} - Strong",
                        "description": summary,
                    }
                )
            for risk in risks:
                severity = getattr(risk, "severity", Severity.LOW)
                severity_value = severity.value if isinstance(severity, Severity) else str(severity)
                if severity_value in {Severity.HIGH.value, Severity.CRITICAL.value}:
                    financial_impact = (
                        _normalized_finding_financial_impact(risk)
                        if isinstance(risk, NormalizedFinding)
                        else getattr(risk, "financial_impact", None)
                        or getattr(risk, "potential_exposure", None)
                        or getattr(risk, "amount", None)
                    )
                    red_flags.append(
                        {
                            "id": getattr(risk, "id", getattr(risk, "finding_id", f"{key}-{len(red_flags) + 1}")),
                            "severity": severity_value,
                            "source": AGENT_SOURCES[key],
                            "title": getattr(risk, "title", getattr(risk, "description", "Risk")),
                            "description": getattr(risk, "description", ""),
                            "financial_impact": financial_impact,
                        }
                    )
        else:
            section_summaries[key] = {
                "score": 1,
                "summary": "Analysis unavailable.",
                "top_risks": ["Analysis did not complete."],
            }

    red_flags.sort(key=lambda item: (SEVERITY_ORDER.get(item["severity"], 99), -(item["financial_impact"] or 0)))
    return {
        "composite_score": composite_score,
        "successful_agents": successful_agents,
        "failed_agents": failed_agents,
        "completeness": len(successful_agents) / len(AGENT_WEIGHTS),
        "red_flags": red_flags,
        "green_flags": green_flags,
        "section_summaries": section_summaries,
    }
