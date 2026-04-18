from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agents.schemas import (
    AgentExecutionStatus,
    AgentName,
    ClarificationAnswer,
    DeterministicTag,
    DocumentType,
    FindingCategory,
    Severity,
)


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.title() for part in tail)


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class EvidenceReference(CamelModel):
    document_id: str
    file_name: str | None = None
    section_id: str | None = None
    page: int | None = None
    snippet: str | None = None
    extracted_fields: dict[str, str | float | int | bool | None] = Field(default_factory=dict)
    confidence: float | None = Field(None, ge=0, le=1)

    @field_validator("extracted_fields", mode="before")
    @classmethod
    def _drop_non_primitive_fields(cls, value: object) -> dict[str, str | float | int | bool | None]:
        if not isinstance(value, dict):
            return {}
        return {
            (key if isinstance(key, str) else str(key)): val
            for key, val in value.items()
            if val is None or isinstance(val, (str, int, float, bool))
        }


class NormalizedMetric(CamelModel):
    value: str | float | int | bool | None = None
    unit: str | None = None
    display_value: str | None = None
    confidence: float | None = Field(None, ge=0, le=1)
    timeframe: dict[str, str | int | None] | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)


class MissingInput(CamelModel):
    key: str
    description: str
    document_type: DocumentType | None = None
    required: bool = True
    reason: str | None = None


class NormalizedFinding(CamelModel):
    finding_id: str
    source_agent: AgentName
    category: FindingCategory
    severity: Severity
    title: str
    description: str
    deterministic_tags: list[DeterministicTag] = Field(default_factory=list)
    metric_impact: dict[str, str | float | int | bool | None] = Field(default_factory=dict)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    confidence: float = Field(..., ge=0, le=1)
    missing_data: bool = False


class AgentEnvelope(CamelModel):
    agent_name: AgentName
    status: AgentExecutionStatus
    summary: str | None = None
    confidence: float | None = Field(None, ge=0, le=1)
    overall_score: int | None = Field(None, ge=1, le=10)
    normalized_metrics: dict[str, NormalizedMetric] = Field(default_factory=dict)
    findings: list[NormalizedFinding] = Field(default_factory=list)
    missing_inputs: list[MissingInput] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    raw_domain_output: dict[str, object] | None = None


class BuyerFacingDimension(CamelModel):
    key: str
    label: str
    score: float | None = None
    status: str | None = None
    summary: str | None = None


class TechnicalScorecard(CamelModel):
    name: str
    score: float | None = None
    recommendation: str | None = None
    findings: list[NormalizedFinding] = Field(default_factory=list)
    metrics: dict[str, NormalizedMetric] = Field(default_factory=dict)


class ScoreConflict(CamelModel):
    key: str
    description: str
    conservative_value: str | float | int | bool | None = None
    conflicting_values: dict[str, str | float | int | bool | None] = Field(default_factory=dict)
    evidence: list[EvidenceReference] = Field(default_factory=list)


class DeterministicScorecard(CamelModel):
    overall_risk_score: int | None = Field(None, ge=1, le=100)
    overall_recommendation: str | None = None
    buyer_facing_dimensions: list[BuyerFacingDimension] = Field(default_factory=list)
    technical_scorecards: list[TechnicalScorecard] = Field(default_factory=list)
    deal_breakers: list[NormalizedFinding] = Field(default_factory=list)
    conflicts: list[ScoreConflict] = Field(default_factory=list)
    completeness_score: float | None = Field(None, ge=0, le=1)
    confidence_score: float | None = Field(None, ge=0, le=1)
    validated_metrics: dict[str, NormalizedMetric] = Field(default_factory=dict)


class ReportModeAvailability(CamelModel):
    summary: bool = True
    deep: bool = False


class ReportSummaryV2(CamelModel):
    headline: str | None = None
    overview: str | None = None
    key_findings: list[NormalizedFinding] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class DeepReviewScoringImpactV2(CamelModel):
    buyer_facing_dimensions: list[str] = Field(default_factory=list)
    risk_contribution: float | None = None


class DeepReviewAgentReviewV2(CamelModel):
    agent_name: AgentName
    headline: str | None = None
    summary: str | None = None
    technical_score: float | None = None
    confidence: float | None = Field(None, ge=0, le=1)
    key_metrics: dict[str, NormalizedMetric] = Field(default_factory=dict)
    findings: list[NormalizedFinding] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    missing_inputs: list[MissingInput] = Field(default_factory=list)
    scoring_impact: DeepReviewScoringImpactV2 = Field(default_factory=DeepReviewScoringImpactV2)


class MissingDataDetailV2(CamelModel):
    key: str
    description: str
    document_type: DocumentType | None = None
    required: bool = True
    reason: str | None = None
    affected_agents: list[AgentName] = Field(default_factory=list)
    related_findings: list[str] = Field(default_factory=list)
    impact_summary: str | None = None


class DeepReviewV2(CamelModel):
    agent_reviews: list[DeepReviewAgentReviewV2] = Field(default_factory=list)
    evidence_index: list[EvidenceReference] = Field(default_factory=list)
    audit_trail: list[str] = Field(default_factory=list)
    missing_data: list[MissingDataDetailV2] = Field(default_factory=list)


class ReportMetadataV2(CamelModel):
    contract_version: str = "2.0"
    generated_at: str | None = None
    analysis_id: str | None = None
    pipeline_status: str | None = None
    source_document_count: int | None = None
    total_tokens: int | None = None
    estimated_cost: float | None = None
    total_latency_ms: int | None = None
    audit_metadata: dict[str, object] | None = None


class ReportOutputV2(CamelModel):
    mode_available: ReportModeAvailability = Field(default_factory=ReportModeAvailability)
    summary: ReportSummaryV2 = Field(default_factory=ReportSummaryV2)
    scorecard: DeterministicScorecard = Field(default_factory=DeterministicScorecard)
    deep_review: DeepReviewV2 | None = None
    metadata: ReportMetadataV2 = Field(default_factory=ReportMetadataV2)


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
    asking_price_estimated: bool = False


class CashFlowStatement(CamelModel):
    operating_cash_flow: float = 0
    investing_cash_flow: float | None = None
    financing_cash_flow: float | None = None
    net_cash_flow: float = 0
    capital_expenditures: float | None = None
    free_cash_flow: float | None = None


class DealHints(CamelModel):
    """Optional derivations exposed so the Review page can pre-fill Deal Info."""
    years_in_operation: int | None = None
    detected_location: str | None = None
    suggested_business_type: str | None = None


class FinancialData(CamelModel):
    income_statement: IncomeStatement | None = None
    balance_sheet: BalanceSheet | None = None
    loan_terms: LoanTerms | None = None
    cash_flow: CashFlowStatement | None = None
    parsing_notes: list[str] = Field(default_factory=list)
    data_completeness: float = 0
    deal_hints: DealHints | None = None


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


class AnalysisJobProgress(CamelModel):
    stage: str = "queued"
    message: str = "Analysis queued."
    progress: float = Field(0, ge=0, le=1)
    updated_at: str | None = None


class AnalysisJobRecord(CamelModel):
    analysis_id: str
    status: Literal["queued", "running", "completed", "failed"]
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
    progress: AnalysisJobProgress = Field(default_factory=AnalysisJobProgress)
    error: str | None = None


class AnalysisJobRequest(CamelModel):
    financials: FinancialData | None = None
    questionnaire: QuestionnaireData | None = None
    deal_info: DealInfo | None = None
    documents: list[dict[str, object]] = Field(default_factory=list)
    analysis_id: str | None = None
    clarifications: list[ClarificationAnswer] = Field(default_factory=list)
    report_depth: Literal["summary", "deep"] | None = "summary"


class AnalysisJobResponse(CamelModel):
    analysis_id: str
    status: Literal["queued", "running", "completed", "failed"]
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
    progress: AnalysisJobProgress = Field(default_factory=AnalysisJobProgress)
    error: str | None = None
    report: dict[str, object] | None = None


class ParseDocumentsResponse(CamelModel):
    success: bool
    extracted_data: FinancialData | None = None
    analysis_id: str | None = None
    pipeline_documents: list[dict[str, object]] = Field(default_factory=list)
    error: str | None = None
