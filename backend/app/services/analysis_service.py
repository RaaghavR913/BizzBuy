from __future__ import annotations

from datetime import datetime, timezone

from app.models.schemas import (
    AnalysisFlag,
    DealInfo,
    DebtServiceAnalysis,
    ExecutiveSummary,
    FinalRecommendation,
    FinancialData,
    FinancialSnapshot,
    LoanSizing,
    MetricDisplay,
    QuestionnaireData,
    ReportMetadata,
    ReportOutput,
    RiskAssessment,
    TransferabilityAnalysis,
)
from app.services.calculations import (
    assess_dscr,
    assess_valuation_multiple,
    calculate_break_even_monthly_revenue,
    calculate_dscr,
    calculate_ebitda,
    calculate_gross_margin,
    calculate_minimum_revenue,
    calculate_monthly_payment,
    calculate_sde,
    calculate_valuation_multiple,
    calculate_working_capital,
    format_currency,
    generate_scenarios,
)
from app.services.report_writer import (
    build_diligence_checklist,
    build_executive_summary,
    build_improvement_suggestions,
    build_questions_for_seller,
    build_transferability_factors,
    build_upside_opportunities,
    recommendation_action,
    recommendation_text,
)
from app.services.risk_engine import compute_risk_scores, get_risk_label, get_transferability_label

ANALYSIS_VERSION = "python-backend-v0.1"
DISCLAIMERS = [
    "This analysis is informational only and is not legal, tax, accounting, or investment advice.",
    "All acquisition decisions should be reviewed with qualified professionals.",
]
WSJ_PRIME_RATE = 0.085
SBA_SPREAD = 0.0275


def _build_flags(
    dscr: float,
    working_capital: float | None,
    valuation_multiple: float,
    risk_result,
) -> list[AnalysisFlag]:
    flags: list[AnalysisFlag] = []

    if dscr != float("inf") and dscr < 1.25:
        flags.append(
            AnalysisFlag(
                severity="critical" if dscr < 1.0 else "warning",
                dimension="Debt Service & Affordability",
                metric="DSCR",
                message=f"Modeled DSCR is {dscr:.2f}, below the preferred 1.25 threshold.",
            )
        )

    if working_capital is not None and working_capital < 0:
        flags.append(
            AnalysisFlag(
                severity="warning",
                dimension="Working Capital",
                metric="workingCapital",
                message="Working capital is negative.",
            )
        )

    if valuation_multiple != float("inf") and valuation_multiple > 4.0:
        flags.append(
            AnalysisFlag(
                severity="warning",
                dimension="Valuation",
                metric="valuationMultiple",
                message=f"Valuation multiple is {valuation_multiple:.2f}x, which is elevated for many small businesses.",
            )
        )

    for deal_breaker in risk_result.deal_breakers:
        flags.append(
            AnalysisFlag(
                severity="critical",
                dimension="Risk Assessment",
                message=deal_breaker,
            )
        )

    return flags


def _compute_financial_metrics(financials: FinancialData, deal_info: DealInfo) -> dict[str, object]:
    income_statement = financials.income_statement
    balance_sheet = financials.balance_sheet
    loan_terms = financials.loan_terms

    revenue = income_statement.revenue if income_statement else 0
    cogs = income_statement.cogs if income_statement else 0
    operating_expenses = income_statement.operating_expenses if income_statement else 0
    net_income = income_statement.net_income if income_statement else 0
    owner_salary = income_statement.owner_salary if income_statement and income_statement.owner_salary is not None else 0
    add_back_total = sum(item.amount for item in income_statement.add_backs) if income_statement else 0
    depreciation_amortization = (
        income_statement.depreciation_amortization
        if income_statement and income_statement.depreciation_amortization is not None
        else 0
    )
    interest_expense = (
        income_statement.interest_expense
        if income_statement and income_statement.interest_expense is not None
        else 0
    )

    gross_profit = income_statement.gross_profit if income_statement else revenue - cogs
    gross_margin = calculate_gross_margin(revenue, cogs)
    sde = (
        income_statement.sde
        if income_statement and income_statement.sde is not None
        else calculate_sde(net_income, owner_salary, add_back_total, depreciation_amortization, interest_expense)
    )
    ebitda = (
        income_statement.ebitda
        if income_statement and income_statement.ebitda is not None
        else calculate_ebitda(net_income, interest_expense, 0, depreciation_amortization, 0)
    )
    working_capital = (
        calculate_working_capital(balance_sheet.current_assets, balance_sheet.current_liabilities)
        if balance_sheet
        else None
    )

    asking_price = deal_info.asking_price or (loan_terms.asking_price if loan_terms else 0)
    loan_amount = loan_terms.loan_amount if loan_terms else 0
    interest_rate = loan_terms.interest_rate if loan_terms else 0
    term_months = loan_terms.term_months if loan_terms else 120
    monthly_debt_service = (
        loan_terms.monthly_payment
        if loan_terms and loan_terms.monthly_payment is not None
        else calculate_monthly_payment(loan_amount, interest_rate, term_months)
    )
    annual_debt_service = monthly_debt_service * 12
    dscr = calculate_dscr(sde, annual_debt_service) if annual_debt_service > 0 else float("inf")
    valuation_multiple = calculate_valuation_multiple(asking_price, sde)
    minimum_revenue = calculate_minimum_revenue(annual_debt_service, operating_expenses)
    break_even_monthly = calculate_break_even_monthly_revenue(
        monthly_debt_service,
        operating_expenses / 12 if operating_expenses else 0,
    )
    scenarios = generate_scenarios(revenue, annual_debt_service, operating_expenses, term_months) if annual_debt_service > 0 else []

    return {
        "revenue": revenue,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "gross_margin": gross_margin,
        "operating_expenses": operating_expenses,
        "net_income": net_income,
        "sde": sde,
        "ebitda": ebitda,
        "working_capital": working_capital,
        "asking_price": asking_price,
        "loan_amount": loan_amount,
        "interest_rate": interest_rate,
        "term_months": term_months,
        "monthly_debt_service": monthly_debt_service,
        "annual_debt_service": annual_debt_service,
        "dscr": dscr,
        "valuation_multiple": valuation_multiple,
        "minimum_revenue": minimum_revenue,
        "break_even_monthly": break_even_monthly,
        "scenarios": scenarios,
    }


def _compute_bankability(sde: float, flags: list[AnalysisFlag]) -> LoanSizing:
    interest_rate = WSJ_PRIME_RATE + SBA_SPREAD
    max_supported_loan = max(0, sde * 5)
    estimated_monthly_payment = calculate_monthly_payment(max_supported_loan, interest_rate, 120)
    estimated_annual_debt_service = estimated_monthly_payment * 12
    estimated_dscr = calculate_dscr(sde, estimated_annual_debt_service) if estimated_annual_debt_service > 0 else float("inf")

    bankability_score = 55
    if estimated_dscr >= 2:
        bankability_score += 25
    elif estimated_dscr >= 1.5:
        bankability_score += 15
    elif estimated_dscr >= 1.25:
        bankability_score += 5
    elif estimated_dscr < 1:
        bankability_score -= 20

    for flag in flags:
        if flag.severity == "critical":
            bankability_score -= 8
        elif flag.severity == "warning":
            bankability_score -= 3

    bankability_score = max(0, min(100, bankability_score))
    if bankability_score >= 80:
        label = "Strong"
    elif bankability_score >= 65:
        label = "Bankable"
    elif bankability_score >= 45:
        label = "Borderline"
    else:
        label = "Weak"

    explanation = (
        "No modeled SBA payment was required, so bankability is driven mostly by diligence quality."
        if estimated_dscr == float("inf")
        else (
            f"Using a 10-year SBA-style amortization at {interest_rate * 100:.2f}%, "
            f"the current normalized SDE supports about {format_currency(max_supported_loan)} "
            f"of debt with an estimated DSCR of {estimated_dscr:.2f}."
        )
    )

    return LoanSizing(
        max_supported_loan=max_supported_loan,
        estimated_interest_rate=interest_rate,
        estimated_monthly_payment=estimated_monthly_payment,
        estimated_annual_debt_service=estimated_annual_debt_service,
        estimated_dscr=999 if estimated_dscr == float("inf") else round(estimated_dscr, 2),
        bankability_score=bankability_score,
        bankability_label=label,  # type: ignore[arg-type]
        explanation=explanation,
    )


def run_analysis(financials: FinancialData, questionnaire: QuestionnaireData, deal_info: DealInfo) -> ReportOutput:
    metrics = _compute_financial_metrics(financials, deal_info)
    risk_result = compute_risk_scores(questionnaire, financials)
    flags = _build_flags(
        metrics["dscr"],
        metrics["working_capital"],
        metrics["valuation_multiple"],
        risk_result,
    )
    bankability = _compute_bankability(metrics["sde"], flags)

    action = recommendation_action(
        risk_result.overall_score,
        risk_result.transferability_score,
        metrics["dscr"],
        risk_result.deal_breakers,
    )
    verdict = recommendation_text(action)
    executive_text = build_executive_summary(
        deal_info.business_type,
        risk_result.overall_score,
        risk_result.transferability_score,
        metrics["dscr"],
        risk_result.deal_breakers,
    )

    strengths = [
        "Deterministic financial analysis was completed from structured inputs.",
        "The report separates raw facts from derived risk judgments.",
    ]
    if metrics["dscr"] >= 1.25 or metrics["dscr"] == float("inf"):
        strengths.append("Debt service coverage is at or above a generally acceptable threshold.")
    if risk_result.transferability_score >= 65:
        strengths.append("Transferability screens positively relative to the weighted rubric.")

    risks = [flag.message for flag in flags[:3]]
    if not risks:
        risks.append("No critical deterministic flags were triggered from the supplied data.")

    next_steps = [
        "Validate earnings with source documents before relying on seller-adjusted numbers.",
        "Pressure-test transition risk with customer, employee, and process diligence.",
        "Review financing assumptions with an SBA lender or acquisition advisor.",
    ]

    report = ReportOutput(
        executive_summary=ExecutiveSummary(
            text=executive_text,
            risk_score=risk_result.overall_score,
            risk_label=get_risk_label(risk_result.overall_score),  # type: ignore[arg-type]
            transferability_score=risk_result.transferability_score,
            transferability_label=get_transferability_label(risk_result.transferability_score),  # type: ignore[arg-type]
            verdict=verdict,
        ),
        financial_snapshot=FinancialSnapshot(
            metrics={
                "Revenue": MetricDisplay(value=metrics["revenue"], formatted=format_currency(metrics["revenue"])),
                "COGS": MetricDisplay(value=metrics["cogs"], formatted=format_currency(metrics["cogs"])),
                "Gross Profit": MetricDisplay(value=metrics["gross_profit"], formatted=format_currency(metrics["gross_profit"])),
                "Gross Margin": MetricDisplay(value=metrics["gross_margin"], formatted=f"{metrics['gross_margin']:.1f}%"),
                "Operating Expenses": MetricDisplay(value=metrics["operating_expenses"], formatted=format_currency(metrics["operating_expenses"])),
                "Net Income": MetricDisplay(value=metrics["net_income"], formatted=format_currency(metrics["net_income"])),
                "SDE": MetricDisplay(
                    value=metrics["sde"],
                    formatted=format_currency(metrics["sde"]),
                    note="Deterministically normalized from the structured inputs.",
                ),
                "EBITDA": MetricDisplay(value=metrics["ebitda"], formatted=format_currency(metrics["ebitda"])),
                **(
                    {
                        "Working Capital": MetricDisplay(
                            value=metrics["working_capital"],
                            formatted=format_currency(metrics["working_capital"]),
                            note="Negative working capital is a warning sign." if metrics["working_capital"] < 0 else None,
                        )
                    }
                    if metrics["working_capital"] is not None
                    else {}
                ),
            },
            valuation_multiple=metrics["valuation_multiple"],
            multiple_assessment=assess_valuation_multiple(metrics["valuation_multiple"]),
        ),
        debt_service_analysis=DebtServiceAnalysis(
            loan_summary={
                "Loan Amount": format_currency(metrics["loan_amount"]),
                "Interest Rate": f"{metrics['interest_rate'] * 100:.2f}%" if metrics["interest_rate"] <= 1 else f"{metrics['interest_rate']:.2f}%",
                "Loan Term": f"{metrics['term_months']} months",
                "Asking Price": format_currency(metrics["asking_price"]),
                "SBA Max Loan": format_currency(bankability.max_supported_loan),
                "Bankability Score": f"{bankability.bankability_score}/100 ({bankability.bankability_label})",
            },
            monthly_debt_service=metrics["monthly_debt_service"],
            annual_debt_service=metrics["annual_debt_service"],
            dscr=999 if metrics["dscr"] == float("inf") else round(metrics["dscr"], 2),
            dscr_assessment=assess_dscr(metrics["dscr"]),
            minimum_revenue_required=metrics["minimum_revenue"],
            break_even_monthly_revenue=metrics["break_even_monthly"],
            scenarios=metrics["scenarios"],
            affordability_verdict=bankability.explanation,
        ),
        risk_assessment=RiskAssessment(
            overall_score=risk_result.overall_score,
            dimensions=risk_result.dimensions,
            deal_breakers=risk_result.deal_breakers,
        ),
        transferability_analysis=TransferabilityAnalysis(
            score=risk_result.transferability_score,
            explanation="Transferability is driven mainly by owner dependence, process maturity, contract quality, and management depth.",
            key_factors=build_transferability_factors(questionnaire),
            improvement_suggestions=build_improvement_suggestions(questionnaire),
        ),
        questions_for_seller=build_questions_for_seller(questionnaire),
        diligence_checklist=build_diligence_checklist(financials, questionnaire, flags),
        upside_opportunities=build_upside_opportunities(questionnaire, deal_info),
        final_recommendation=FinalRecommendation(
            action=action,  # type: ignore[arg-type]
            strengths=strengths[:3],
            risks=risks[:3],
            next_steps=next_steps,
            summary_statement=f"{verdict} based on the current deterministic affordability, risk, and transferability outputs.",
        ),
        agent_flags=flags,
        sba_loan_sizing=bankability,
        metadata=ReportMetadata(
            generated_at=datetime.now(timezone.utc).isoformat(),
            analysis_version=ANALYSIS_VERSION,
            data_completeness=financials.data_completeness,
            disclaimers=DISCLAIMERS,
        ),
    )
    return report
