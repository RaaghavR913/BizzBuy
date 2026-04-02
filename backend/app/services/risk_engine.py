from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import FinancialData, QuestionnaireData, RiskDimensionScore

WEIGHTS = {
    "owner_dependence": 0.25,
    "customer_concentration": 0.20,
    "revenue_quality": 0.20,
    "employee_risk": 0.15,
    "supplier_risk": 0.10,
    "financial_risk": 0.10,
}


@dataclass
class RiskComputation:
    dimensions: list[RiskDimensionScore]
    overall_score: int
    transferability_score: int
    deal_breakers: list[str]


def _round_score(value: float) -> int:
    return max(1, min(10, round(value)))


def _label_for_score(score: int) -> str:
    if score <= 3:
        return "Low"
    if score <= 5:
        return "Moderate"
    if score <= 7:
        return "High"
    return "Critical"


def get_risk_label(score: int) -> str:
    if score <= 35:
        return "Low"
    if score <= 65:
        return "Moderate"
    if score <= 80:
        return "High"
    return "Very High"


def get_transferability_label(score: int) -> str:
    if score >= 65:
        return "High"
    if score >= 40:
        return "Moderate"
    if score >= 20:
        return "Low"
    return "Very Low"


def _score_owner_dependence(questionnaire: QuestionnaireData) -> tuple[int, list[str]]:
    q = questionnaire.owner_dependence
    score = 1.0
    factors: list[str] = []
    sales_pct = q.owner_sales_percentage if q.owner_sales_percentage is not None else 50

    if sales_pct > 80:
        score += 3
        factors.append(f"Owner personally generates {sales_pct:.0f}% of sales.")
    elif sales_pct > 50:
        score += 2
        factors.append(f"Owner personally generates {sales_pct:.0f}% of sales.")
    elif sales_pct > 25:
        score += 1
        factors.append(f"Owner still influences a material share of sales at {sales_pct:.0f}%.")

    if q.owner_involvement == "full_time":
        score += 2
        factors.append("Owner is deeply embedded in daily operations.")
    elif q.owner_involvement == "part_time":
        score += 1
    elif q.owner_involvement == "unknown":
        score += 1
        factors.append("Owner involvement is unclear.")

    if q.owner_holds_relationships is True:
        score += 2
        factors.append("Key customer relationships appear tied to the owner personally.")
    elif q.owner_holds_relationships is None:
        score += 1

    if q.survives_90_day_absence == "no":
        score += 2
        factors.append("Business likely fails a 90-day owner absence test.")
    elif q.survives_90_day_absence == "unlikely":
        score += 1.5
        factors.append("Business appears fragile without the owner present.")
    elif q.survives_90_day_absence == "unknown":
        score += 1

    return _round_score(score), factors[:3]


def _score_customer_concentration(questionnaire: QuestionnaireData) -> tuple[int, list[str]]:
    q = questionnaire.customer_concentration
    score = 1.0
    factors: list[str] = []
    top_pct = q.top_customer_revenue_percent if q.top_customer_revenue_percent is not None else 20
    top5_pct = q.top5_customers_revenue_percent if q.top5_customers_revenue_percent is not None else 50

    if top_pct > 50:
        score += 3
        factors.append(f"Top customer represents {top_pct:.0f}% of total revenue.")
    elif top_pct > 30:
        score += 2
        factors.append(f"Top customer concentration is elevated at {top_pct:.0f}%.")
    elif top_pct > 20:
        score += 1

    if top5_pct > 80:
        score += 2
        factors.append(f"Top 5 customers account for {top5_pct:.0f}% of revenue.")
    elif top5_pct > 60:
        score += 1.5
    elif top5_pct > 40:
        score += 1

    if q.contract_type == "mostly_handshake":
        score += 2
        factors.append("Customer relationships are mostly handshake-based.")
    elif q.contract_type == "mixed":
        score += 1
    elif q.contract_type == "unknown":
        score += 1

    if q.average_customer_tenure == "less_than_1_year":
        score += 1
        factors.append("Average customer tenure is short.")
    elif q.average_customer_tenure == "unknown":
        score += 0.5

    return _round_score(score), factors[:3]


def _score_revenue_quality(questionnaire: QuestionnaireData) -> tuple[int, list[str]]:
    q = questionnaire.revenue_quality
    score = 1.0
    factors: list[str] = []
    recurring = q.recurring_revenue_percent if q.recurring_revenue_percent is not None else 30

    if recurring < 10:
        score += 3
        factors.append("Recurring revenue base is extremely low.")
    elif recurring < 20:
        score += 2
        factors.append(f"Recurring revenue is weak at {recurring:.0f}%.")
    elif recurring < 40:
        score += 1

    if q.revenue_trend == "declining":
        score += 3
        factors.append("Revenue has been declining.")
    elif q.revenue_trend == "flat":
        score += 1
        factors.append("Revenue has been flat.")
    elif q.revenue_trend == "unknown":
        score += 1

    if q.known_upcoming_losses is True:
        score += 2
        factors.append("Known upcoming customer losses or expirations are present.")
    elif q.known_upcoming_losses is None:
        score += 1

    return _round_score(score), factors[:3]


def _score_employee_risk(questionnaire: QuestionnaireData) -> tuple[int, list[str]]:
    q = questionnaire.employee_risk
    score = 1.0
    factors: list[str] = []
    total = q.total_employees if q.total_employees is not None else 5
    critical = q.mission_critical_employees if q.mission_critical_employees is not None else 2
    critical_ratio = critical / total if total > 0 else 0.5

    if critical_ratio > 0.4:
        score += 2
        factors.append("Too much know-how sits with a small number of critical employees.")
    elif critical_ratio > 0.25:
        score += 1

    if q.has_sops is False:
        score += 2.5
        factors.append("No documented SOPs were reported.")
    elif q.has_sops is None:
        score += 1.5

    if q.has_management_layer is False:
        score += 2
        factors.append("There is no management layer between owner and frontline staff.")
    elif q.has_management_layer is None:
        score += 1

    return _round_score(score), factors[:3]


def _score_supplier_risk(questionnaire: QuestionnaireData) -> tuple[int, list[str]]:
    q = questionnaire.supplier_risk
    score = 1.0
    factors: list[str] = []

    if q.single_supplier_over_30_pct is True:
        score += 4
        factors.append("A single supplier appears to control more than 30% of operations or COGS.")
    elif q.single_supplier_over_30_pct is None:
        score += 2

    if q.supplier_agreements_documented is False:
        score += 3
        factors.append("Supplier agreements are not clearly documented or transferable.")
    elif q.supplier_agreements_documented is None:
        score += 1.5

    if q.exclusive_vendor_relationships is True:
        score += 2
        factors.append("Exclusive or difficult-to-replace vendor relationships exist.")
    elif q.exclusive_vendor_relationships is None:
        score += 1

    return _round_score(score), factors[:3]


def _score_financial_risk(questionnaire: QuestionnaireData, financials: FinancialData) -> tuple[int, list[str]]:
    q = questionnaire.financial_risk
    score = 1.0
    factors: list[str] = []

    if q.add_backs_exceed_30_pct is True:
        score += 3
        factors.append("Add-backs exceed 30% of EBITDA.")
    elif q.has_add_backs is True:
        score += 1.5
        factors.append("Seller has presented add-backs that require validation.")
    elif q.has_add_backs is None:
        score += 1

    if q.pending_liabilities is True:
        score += 4
        factors.append("Pending legal, tax, or environmental liabilities were disclosed.")
    elif q.pending_liabilities is None:
        score += 2

    if financials.income_statement and financials.income_statement.revenue_by_year:
        years = sorted(financials.income_statement.revenue_by_year.keys())
        if len(years) >= 2:
            previous = financials.income_statement.revenue_by_year[years[-2]]
            current = financials.income_statement.revenue_by_year[years[-1]]
            if current < previous:
                score += 1
                factors.append("Revenue trend in the financials is declining.")

    return _round_score(score), factors[:3]


def compute_risk_scores(questionnaire: QuestionnaireData, financials: FinancialData) -> RiskComputation:
    owner_score, owner_factors = _score_owner_dependence(questionnaire)
    customer_score, customer_factors = _score_customer_concentration(questionnaire)
    revenue_score, revenue_factors = _score_revenue_quality(questionnaire)
    employee_score, employee_factors = _score_employee_risk(questionnaire)
    supplier_score, supplier_factors = _score_supplier_risk(questionnaire)
    financial_score, financial_factors = _score_financial_risk(questionnaire, financials)

    weighted_score = (
        owner_score * WEIGHTS["owner_dependence"]
        + customer_score * WEIGHTS["customer_concentration"]
        + revenue_score * WEIGHTS["revenue_quality"]
        + employee_score * WEIGHTS["employee_risk"]
        + supplier_score * WEIGHTS["supplier_risk"]
        + financial_score * WEIGHTS["financial_risk"]
    )
    overall_score = round(weighted_score * 10)

    transferability_raw = (
        (10 - owner_score) * 0.35
        + (10 if questionnaire.employee_risk.has_sops else 5) * 0.25
        + (
            10
            if questionnaire.customer_concentration.contract_type == "mostly_contracted"
            else 6
            if questionnaire.customer_concentration.contract_type == "mixed"
            else 3
        )
        * 0.25
        + (10 if questionnaire.employee_risk.has_management_layer else 4) * 0.15
    )
    transferability_score = round(transferability_raw * 10)

    dimensions = [
        RiskDimensionScore(
            dimension="Owner Dependence",
            score=owner_score,
            label=_label_for_score(owner_score),  # type: ignore[arg-type]
            explanation="Measures how much revenue generation, relationships, and operations rely on the current owner.",
            key_factors=owner_factors,
            is_deal_breaker=owner_score >= 9,
        ),
        RiskDimensionScore(
            dimension="Customer Concentration",
            score=customer_score,
            label=_label_for_score(customer_score),  # type: ignore[arg-type]
            explanation="Measures how exposed the business is to losing a few customers or undocumented relationships.",
            key_factors=customer_factors,
            is_deal_breaker=customer_score >= 9,
        ),
        RiskDimensionScore(
            dimension="Revenue Quality",
            score=revenue_score,
            label=_label_for_score(revenue_score),  # type: ignore[arg-type]
            explanation="Measures how durable and predictable revenue is, including recurring mix and trend quality.",
            key_factors=revenue_factors,
            is_deal_breaker=revenue_score >= 9,
        ),
        RiskDimensionScore(
            dimension="Employee & Operational Risk",
            score=employee_score,
            label=_label_for_score(employee_score),  # type: ignore[arg-type]
            explanation="Measures process maturity, management depth, and fragility tied to key employees.",
            key_factors=employee_factors,
            is_deal_breaker=employee_score >= 9,
        ),
        RiskDimensionScore(
            dimension="Supplier & Vendor Risk",
            score=supplier_score,
            label=_label_for_score(supplier_score),  # type: ignore[arg-type]
            explanation="Measures supplier concentration, transferability, and replacement difficulty.",
            key_factors=supplier_factors,
            is_deal_breaker=supplier_score >= 9,
        ),
        RiskDimensionScore(
            dimension="Financial & Add-Back Risk",
            score=financial_score,
            label=_label_for_score(financial_score),  # type: ignore[arg-type]
            explanation="Measures earnings quality, add-back credibility, and pending liability exposure.",
            key_factors=financial_factors,
            is_deal_breaker=financial_score >= 9,
        ),
    ]

    deal_breakers = [
        f"{dimension.dimension}: {dimension.key_factors[0] if dimension.key_factors else 'Critical risk identified.'}"
        for dimension in dimensions
        if dimension.is_deal_breaker
    ]

    return RiskComputation(
        dimensions=dimensions,
        overall_score=overall_score,
        transferability_score=transferability_score,
        deal_breakers=deal_breakers,
    )
