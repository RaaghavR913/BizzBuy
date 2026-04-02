from __future__ import annotations

from app.models.schemas import (
    AnalysisFlag,
    ChecklistItem,
    DealInfo,
    FinancialData,
    QuestionnaireData,
    SellerQuestionGroup,
    TransferabilityFactor,
    UpsideOpportunity,
)
from app.services.risk_engine import get_risk_label, get_transferability_label


def recommendation_action(overall_score: int, transferability_score: int, dscr: float, deal_breakers: list[str]) -> str:
    if dscr < 1.0 or len(deal_breakers) >= 2 or overall_score > 80:
        return "walk_away"
    if dscr < 1.25 or overall_score > 55 or transferability_score < 40 or deal_breakers:
        return "proceed_with_caution"
    return "proceed"


def recommendation_text(action: str) -> str:
    if action == "walk_away":
        return "Walk Away"
    if action == "proceed_with_caution":
        return "Proceed With Caution"
    return "Proceed"


def build_executive_summary(
    business_type: str,
    overall_score: int,
    transferability_score: int,
    dscr: float,
    deal_breakers: list[str],
) -> str:
    risk_label = get_risk_label(overall_score).lower()
    transfer_label = get_transferability_label(transferability_score).lower()
    debt_sentence = (
        "No debt service was modeled, so affordability depends primarily on earnings quality."
        if dscr == float("inf")
        else f"The modeled debt service coverage ratio is {dscr:.2f}."
    )
    breaker_sentence = (
        f" Key deal breakers include: {'; '.join(deal_breakers[:2])}."
        if deal_breakers
        else ""
    )
    return (
        f"This {business_type.replace('_', ' ')} acquisition currently screens as {risk_label} risk "
        f"with {transfer_label} transferability. {debt_sentence}"
        f"{breaker_sentence} The recommendation below is based on deterministic scoring from the provided inputs."
    )


def build_transferability_factors(questionnaire: QuestionnaireData) -> list[TransferabilityFactor]:
    factors: list[TransferabilityFactor] = []
    owner = questionnaire.owner_dependence
    employee = questionnaire.employee_risk
    customer = questionnaire.customer_concentration

    factors.append(
        TransferabilityFactor(
            factor="Owner Role",
            impact="negative" if owner.owner_involvement in {"full_time", "part_time"} else "positive",
            detail="The more the current owner drives sales and operations personally, the harder the handoff becomes.",
        )
    )
    factors.append(
        TransferabilityFactor(
            factor="Process Maturity",
            impact="positive" if employee.has_sops else "negative",
            detail="Documented SOPs improve transferability because knowledge survives after the owner exits.",
        )
    )
    factors.append(
        TransferabilityFactor(
            factor="Customer Contracts",
            impact="positive" if customer.contract_type == "mostly_contracted" else "negative",
            detail="Contracted relationships transfer more cleanly than handshake revenue.",
        )
    )
    return factors


def build_improvement_suggestions(questionnaire: QuestionnaireData) -> list[str]:
    suggestions: list[str] = []
    if not questionnaire.employee_risk.has_sops:
        suggestions.append("Document core SOPs for sales, operations, service delivery, and customer handoff.")
    if questionnaire.owner_dependence.owner_holds_relationships:
        suggestions.append("Transition top customer relationships to team-based ownership before closing.")
    if questionnaire.customer_concentration.contract_type != "mostly_contracted":
        suggestions.append("Convert key customer relationships into documented, transferable contracts.")
    if questionnaire.employee_risk.has_management_layer is False:
        suggestions.append("Establish a management layer that can operate the business without the owner present.")
    return suggestions[:4]


def build_questions_for_seller(questionnaire: QuestionnaireData) -> list[SellerQuestionGroup]:
    groups: list[SellerQuestionGroup] = [
        SellerQuestionGroup(
            category="Owner Dependence",
            questions=[
                "Which customer relationships would be at risk if the current owner exited immediately?",
                "What tasks does the owner handle weekly that no one else can perform today?",
            ],
        ),
        SellerQuestionGroup(
            category="Financial Quality",
            questions=[
                "Please provide support for every add-back included in adjusted EBITDA or SDE.",
                "Are there any pending tax liabilities, legal disputes, or off-books obligations not reflected here?",
            ],
        ),
    ]

    if questionnaire.customer_concentration.top_customer_revenue_percent and questionnaire.customer_concentration.top_customer_revenue_percent > 30:
        groups.append(
            SellerQuestionGroup(
                category="Customer Concentration",
                questions=[
                    "What would happen if the top customer reduced volume by 25% after the acquisition?",
                    "How long is the top customer committed, and is the relationship contractually transferable?",
                ],
            )
        )

    return groups


def build_diligence_checklist(
    financials: FinancialData,
    questionnaire: QuestionnaireData,
    flags: list[AnalysisFlag],
) -> list[ChecklistItem]:
    items: list[ChecklistItem] = [
        ChecklistItem(
            item="Reconcile seller-reported earnings to tax returns and bank statements.",
            category="Financial Validation",
            priority="critical",
            reason="Normalized earnings quality drives affordability and valuation.",
        ),
        ChecklistItem(
            item="Review customer contracts, renewal language, and assignability provisions.",
            category="Revenue Transferability",
            priority="important",
            reason="Revenue concentration and handshake relationships increase post-close fragility.",
        ),
    ]

    if questionnaire.employee_risk.has_sops is False:
        items.append(
            ChecklistItem(
                item="Request process documentation and interview key operators.",
                category="Operations",
                priority="critical",
                reason="Low process maturity makes transition risk materially worse.",
            )
        )

    if financials.balance_sheet and (financials.balance_sheet.accounts_receivable or 0) > 0:
        items.append(
            ChecklistItem(
                item="Review aged receivables and collections history.",
                category="Working Capital",
                priority="important",
                reason="Receivables quality affects true working capital and earnings quality.",
            )
        )

    if any(flag.severity == "critical" for flag in flags):
        items.append(
            ChecklistItem(
                item="Resolve all critical flags before entering definitive documents.",
                category="Deal Decision",
                priority="critical",
                reason="Critical unresolved issues should block commitment until validated.",
            )
        )

    return items[:6]


def build_upside_opportunities(questionnaire: QuestionnaireData, deal_info: DealInfo) -> list[UpsideOpportunity]:
    opportunities: list[UpsideOpportunity] = []

    if (questionnaire.revenue_quality.recurring_revenue_percent or 0) < 30:
        opportunities.append(
            UpsideOpportunity(
                opportunity="Increase recurring revenue mix",
                estimated_impact="Could improve predictability and justify a better multiple over time.",
                difficulty="moderate",
                detail="Introduce maintenance plans, retainers, or service contracts where the business model allows.",
            )
        )

    if questionnaire.owner_dependence.owner_sales_percentage and questionnaire.owner_dependence.owner_sales_percentage > 50:
        opportunities.append(
            UpsideOpportunity(
                opportunity="Reduce owner dependence",
                estimated_impact="Can materially improve transferability and financing confidence.",
                difficulty="hard",
                detail="Move sales, customer retention, and key approvals into repeatable team workflows.",
            )
        )

    opportunities.append(
        UpsideOpportunity(
            opportunity=f"Operationalize {deal_info.business_type.replace('_', ' ')} reporting",
            estimated_impact="Improves buyer confidence and future lender diligence readiness.",
            difficulty="easy",
            detail="Standard monthly KPI dashboards can tighten controls and make earnings more believable.",
        )
    )

    return opportunities[:4]
