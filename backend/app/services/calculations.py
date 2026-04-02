from __future__ import annotations

from app.models.schemas import ScenarioAnalysis


def normalize_rate(annual_rate: float) -> float:
    if annual_rate > 1:
        return annual_rate / 100
    return annual_rate


def calculate_monthly_payment(principal: float, annual_rate: float, term_months: int) -> float:
    if principal <= 0 or term_months <= 0:
        return 0
    monthly_rate = normalize_rate(annual_rate) / 12
    if monthly_rate == 0:
        return principal / term_months
    numerator = principal * (monthly_rate * ((1 + monthly_rate) ** term_months))
    denominator = ((1 + monthly_rate) ** term_months) - 1
    return numerator / denominator


def calculate_dscr(annual_cash_flow: float, annual_debt_service: float) -> float:
    if annual_debt_service <= 0:
        return float("inf")
    return annual_cash_flow / annual_debt_service


def calculate_working_capital(current_assets: float, current_liabilities: float) -> float:
    return current_assets - current_liabilities


def calculate_gross_margin(revenue: float, cogs: float) -> float:
    if revenue <= 0:
        return 0
    return ((revenue - cogs) / revenue) * 100


def calculate_ebitda(
    net_income: float,
    interest_expense: float = 0,
    taxes: float = 0,
    depreciation: float = 0,
    amortization: float = 0,
) -> float:
    return net_income + interest_expense + taxes + depreciation + amortization


def calculate_sde(
    net_income: float,
    owner_salary: float = 0,
    add_backs: float = 0,
    depreciation: float = 0,
    interest_expense: float = 0,
) -> float:
    return net_income + owner_salary + add_backs + depreciation + interest_expense


def calculate_valuation_multiple(asking_price: float, sde: float) -> float:
    if sde <= 0:
        return float("inf")
    return asking_price / sde


def calculate_minimum_revenue(
    annual_debt_service: float,
    operating_expenses: float,
    desired_owner_income: float = 0,
) -> float:
    return annual_debt_service + operating_expenses + desired_owner_income


def calculate_break_even_monthly_revenue(
    monthly_debt_service: float,
    monthly_operating_expenses: float,
) -> float:
    return monthly_debt_service + monthly_operating_expenses


def generate_scenarios(
    base_revenue: float,
    annual_debt_service: float,
    operating_expenses: float,
    term_months: int,
) -> list[ScenarioAnalysis]:
    growth_rates = [
        ("Current Performance (0% growth)", 0.0),
        ("Moderate Growth (+10%)", 0.10),
        ("Decline (-10%)", -0.10),
        ("Strong Growth (+20%)", 0.20),
    ]
    scenarios: list[ScenarioAnalysis] = []
    for label, rate in growth_rates:
        projected_revenue = base_revenue * (1 + rate)
        remaining_cash_flow = projected_revenue - operating_expenses - annual_debt_service
        dscr = calculate_dscr(projected_revenue - operating_expenses, annual_debt_service)
        scenarios.append(
            ScenarioAnalysis(
                label=label,
                annual_revenue=round(projected_revenue),
                annual_debt_service=round(annual_debt_service),
                remaining_cash_flow=round(remaining_cash_flow),
                dscr=round(dscr, 2) if dscr != float("inf") else 999.0,
                payoff_months=term_months,
                annual_owner_income=round(max(0, remaining_cash_flow)),
            )
        )
    return scenarios


def assess_dscr(dscr: float) -> str:
    if dscr == float("inf"):
        return "No debt service is modeled, so affordability risk is low unless earnings quality is weak."
    if dscr >= 2.0:
        return "Excellent. The business generates more than twice the cash needed to service the debt."
    if dscr >= 1.5:
        return "Strong. The business covers debt service with meaningful cushion."
    if dscr >= 1.25:
        return "Adequate. The business meets typical SBA expectations but does not have much room for error."
    if dscr >= 1.0:
        return "Marginal. The business barely covers debt service and is sensitive to even mild underperformance."
    return "Critical. The business does not currently generate enough cash to service the modeled debt."


def assess_valuation_multiple(multiple: float) -> str:
    if multiple == float("inf"):
        return "Unable to assess valuation multiple because SDE is zero or negative."
    if multiple <= 2.0:
        return "Attractive multiple. This is below the common range, though it may also signal hidden risk."
    if multiple <= 3.5:
        return "Within a typical small-business market range."
    if multiple <= 4.5:
        return "Premium multiple. This only makes sense if transferability and earnings quality are strong."
    return "Very high multiple. This deal needs unusually strong quality and growth assumptions to hold up."


def format_currency(value: float) -> str:
    if value == float("inf"):
        return "N/A"
    return f"${value:,.0f}"
