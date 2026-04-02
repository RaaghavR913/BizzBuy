from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.title() for part in tail)


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class AddBack(CamelModel):
    description: str
    amount: float = 0
    category: Literal[
        "owner_salary",
        "one_time_expense",
        "personal_expense",
        "non_cash",
        "other",
    ] = "other"


class IncomeStatement(CamelModel):
    revenue: float = 0
    cogs: float = 0
    gross_profit: float = 0
    operating_expenses: float = 0
    depreciation_amortization: float | None = None
    interest_expense: float | None = None
    net_income: float = 0
    owner_salary: float | None = None
    add_backs: list[AddBack] = Field(default_factory=list)
    sde: float | None = None
    ebitda: float | None = None
    periods: list[str] = Field(default_factory=list)
    revenue_by_year: dict[str, float] = Field(default_factory=dict)
    net_income_by_year: dict[str, float] = Field(default_factory=dict)


class BalanceSheet(CamelModel):
    current_assets: float = 0
    cash_and_equivalents: float | None = None
    accounts_receivable: float | None = None
    inventory: float | None = None
    current_liabilities: float = 0
    accounts_payable: float | None = None
    total_assets: float = 0
    total_liabilities: float = 0
    equity: float = 0


class LoanTerms(CamelModel):
    loan_amount: float = 0
    interest_rate: float = 0
    term_months: int = 120
    monthly_payment: float | None = None
    down_payment: float | None = None
    asking_price: float = 0
    loan_type: Literal[
        "sba_7a",
        "sba_504",
        "conventional",
        "seller_financing",
        "other",
    ] | None = None
    collateral_required: bool | None = None


class CashFlowStatement(CamelModel):
    operating_cash_flow: float = 0
    investing_cash_flow: float | None = None
    financing_cash_flow: float | None = None
    net_cash_flow: float = 0
    capital_expenditures: float | None = None
    free_cash_flow: float | None = None


class FinancialData(CamelModel):
    income_statement: IncomeStatement | None = None
    balance_sheet: BalanceSheet | None = None
    loan_terms: LoanTerms | None = None
    cash_flow: CashFlowStatement | None = None
    parsing_notes: list[str] = Field(default_factory=list)
    data_completeness: float = 0


class OwnerDependenceAnswers(CamelModel):
    owner_sales_percentage: float | None = None
    owner_involvement: Literal["full_time", "part_time", "minimal", "unknown"] = "unknown"
    owner_holds_relationships: bool | None = None
    survives_90_day_absence: Literal["yes", "likely", "unlikely", "no", "unknown"] = "unknown"


class CustomerConcentrationAnswers(CamelModel):
    top_customer_revenue_percent: float | None = None
    top5_customers_revenue_percent: float | None = None
    contract_type: Literal["mostly_contracted", "mixed", "mostly_handshake", "unknown"] = "unknown"
    average_customer_tenure: Literal["less_than_1_year", "1_to_3_years", "3_plus_years", "unknown"] = "unknown"


class RevenueQualityAnswers(CamelModel):
    recurring_revenue_percent: float | None = None
    project_based_percent: float | None = None
    revenue_trend: Literal["growing", "flat", "declining", "unknown"] = "unknown"
    known_upcoming_losses: bool | None = None


class EmployeeRiskAnswers(CamelModel):
    total_employees: int | None = None
    mission_critical_employees: int | None = None
    has_sops: bool | None = None
    has_management_layer: bool | None = None


class SupplierRiskAnswers(CamelModel):
    single_supplier_over_30_pct: bool | None = None
    supplier_agreements_documented: bool | None = None
    exclusive_vendor_relationships: bool | None = None


class FinancialRiskAnswers(CamelModel):
    has_add_backs: bool | None = None
    add_backs_exceed_30_pct: bool | None = None
    pending_liabilities: bool | None = None


class QuestionnaireData(CamelModel):
    owner_dependence: OwnerDependenceAnswers
    customer_concentration: CustomerConcentrationAnswers
    revenue_quality: RevenueQualityAnswers
    employee_risk: EmployeeRiskAnswers
    supplier_risk: SupplierRiskAnswers
    financial_risk: FinancialRiskAnswers


class DealInfo(CamelModel):
    asking_price: float = 0
    business_type: str = "small_business"
    years_in_operation: int | None = None
    reason_for_sale: str | None = None
    location: str | None = None
    industry: str | None = None


class RiskDimensionScore(CamelModel):
    dimension: str
    score: int
    label: Literal["Low", "Moderate", "High", "Critical"]
    explanation: str
    key_factors: list[str] = Field(default_factory=list)
    is_deal_breaker: bool = False


class ScenarioAnalysis(CamelModel):
    label: str
    annual_revenue: int
    annual_debt_service: int
    remaining_cash_flow: int
    dscr: float
    payoff_months: int
    annual_owner_income: int


class MetricDisplay(CamelModel):
    value: float
    formatted: str
    note: str | None = None


class ExecutiveSummary(CamelModel):
    text: str
    risk_score: int
    risk_label: Literal["Low", "Moderate", "High", "Very High"]
    transferability_score: int
    transferability_label: Literal["High", "Moderate", "Low", "Very Low"]
    verdict: str


class FinancialSnapshot(CamelModel):
    metrics: dict[str, MetricDisplay]
    valuation_multiple: float
    multiple_assessment: str


class DebtServiceAnalysis(CamelModel):
    loan_summary: dict[str, str]
    monthly_debt_service: float
    annual_debt_service: float
    dscr: float
    dscr_assessment: str
    minimum_revenue_required: float
    break_even_monthly_revenue: float
    scenarios: list[ScenarioAnalysis] = Field(default_factory=list)
    affordability_verdict: str


class RiskAssessment(CamelModel):
    overall_score: int
    dimensions: list[RiskDimensionScore]
    deal_breakers: list[str] = Field(default_factory=list)


class TransferabilityFactor(CamelModel):
    factor: str
    impact: Literal["positive", "negative", "neutral"]
    detail: str


class TransferabilityAnalysis(CamelModel):
    score: int
    explanation: str
    key_factors: list[TransferabilityFactor] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)


class SellerQuestionGroup(CamelModel):
    category: str
    questions: list[str] = Field(default_factory=list)


class ChecklistItem(CamelModel):
    item: str
    category: str
    priority: Literal["critical", "important", "nice_to_have"]
    reason: str


class UpsideOpportunity(CamelModel):
    opportunity: str
    estimated_impact: str
    difficulty: Literal["easy", "moderate", "hard"]
    detail: str


class FinalRecommendation(CamelModel):
    action: Literal["proceed", "proceed_with_caution", "walk_away"]
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    summary_statement: str


class AnalysisFlag(CamelModel):
    severity: Literal["info", "warning", "critical"]
    dimension: str
    message: str
    metric: str | None = None


class LoanSizing(CamelModel):
    max_supported_loan: float
    estimated_interest_rate: float
    estimated_monthly_payment: float
    estimated_annual_debt_service: float
    estimated_dscr: float
    bankability_score: int
    bankability_label: Literal["Weak", "Borderline", "Bankable", "Strong"]
    explanation: str


class ReportMetadata(CamelModel):
    generated_at: str
    analysis_version: str
    data_completeness: float
    disclaimers: list[str] = Field(default_factory=list)


class ReportOutput(CamelModel):
    executive_summary: ExecutiveSummary
    financial_snapshot: FinancialSnapshot
    debt_service_analysis: DebtServiceAnalysis
    risk_assessment: RiskAssessment
    transferability_analysis: TransferabilityAnalysis
    questions_for_seller: list[SellerQuestionGroup] = Field(default_factory=list)
    diligence_checklist: list[ChecklistItem] = Field(default_factory=list)
    upside_opportunities: list[UpsideOpportunity] = Field(default_factory=list)
    final_recommendation: FinalRecommendation
    agent_flags: list[AnalysisFlag] = Field(default_factory=list)
    sba_loan_sizing: LoanSizing
    metadata: ReportMetadata


class AnalyzeRequest(CamelModel):
    financials: FinancialData
    questionnaire: QuestionnaireData
    deal_info: DealInfo


class AnalyzeResponse(CamelModel):
    success: bool
    report: ReportOutput | None = None
    error: str | None = None


class ParseDocumentsResponse(CamelModel):
    success: bool
    extracted_data: FinancialData | None = None
    error: str | None = None
