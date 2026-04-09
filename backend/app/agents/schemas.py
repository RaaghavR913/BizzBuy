from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    PROFIT_AND_LOSS = "profit_and_loss"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW_STATEMENT = "cash_flow_statement"
    TAX_RETURN_1120S = "tax_return_1120s"
    TAX_RETURN_1040 = "tax_return_1040"
    TAX_RETURN_SCHEDULE_C = "tax_return_schedule_c"
    AR_AGING_REPORT = "ar_aging_report"
    CUSTOMER_LIST = "customer_list"
    CONTRACT = "contract"
    LEASE_AGREEMENT = "lease_agreement"
    EMPLOYEE_ROSTER = "employee_roster"
    INSURANCE_POLICY = "insurance_policy"
    EQUIPMENT_LIST = "equipment_list"
    OTHER = "other"


class Timeframe(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    fiscal_year: Optional[int] = None


class DocumentSection(BaseModel):
    document_id: str = Field(..., description="References the source UploadedDocument id")
    document_type: DocumentType
    timeframe: Timeframe
    extracted_data: Dict[str, Any] = Field(..., description="Raw key-value pairs extracted from this section")
    raw_text: str = Field(..., description="Original text from the document section")
    confidence: float = Field(..., ge=0, le=1, description="Model confidence in extraction accuracy, 0-1")


class DocumentInfo(BaseModel):
    document_id: str
    file_name: str
    mime_type: str
    document_type: DocumentType
    sections: List[DocumentSection]


class IngestionMetadata(BaseModel):
    total_documents: int
    successfully_parsed: int
    failed_documents: List[str] = Field(..., description="Document IDs that could not be parsed")
    warnings: List[str]


class IngestionOutput(BaseModel):
    documents: List[DocumentInfo]
    metadata: IngestionMetadata


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Trend(str, Enum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECLINING = "declining"


class AnnualRevenue(BaseModel):
    year: int
    revenue: float = Field(..., description="Total revenue in USD")
    cogs: float = Field(..., description="Cost of goods sold in USD")
    gross_profit: float = Field(..., description="Gross profit in USD")


class AnnualExpense(BaseModel):
    year: int
    total_expenses: float = Field(..., description="Total operating expenses in USD")
    breakdown: Dict[str, float] = Field(..., description="Expense category -> amount in USD")


class SdeAddBack(BaseModel):
    description: str
    amount: float = Field(..., description="Add-back amount in USD")
    justification: str


class FinancialRisk(BaseModel):
    id: str
    category: str
    severity: Severity
    title: str
    description: str
    evidence: str
    financial_impact: Optional[float] = Field(None, description="Estimated financial impact in USD")
    recommendation: str


class RevenueAnalysis(BaseModel):
    annual_figures: List[AnnualRevenue]
    growth_rate: float = Field(..., description="Year-over-year growth rate as decimal")
    trend: Trend
    seasonality_notes: str


class ExpenseAnalysis(BaseModel):
    annual_figures: List[AnnualExpense]
    largest_categories: List[str] = Field(..., description="Top expense categories by size")


class Profitability(BaseModel):
    gross_margin: float = Field(..., description="Gross margin as decimal")
    net_margin: float = Field(..., description="Net margin as decimal")
    ebitda: float = Field(..., description="EBITDA in USD")
    adjusted_ebitda: float = Field(..., description="Adjusted EBITDA in USD")
    sde: float = Field(..., description="Seller's discretionary earnings in USD")
    sde_add_backs: List[SdeAddBack]


class CashFlow(BaseModel):
    operating_cash_flow: float = Field(..., description="Operating cash flow in USD")
    free_cash_flow: float = Field(..., description="Free cash flow in USD")
    cash_flow_vs_net_income: bool = Field(..., description="True if significant discrepancy between cash flow and net income")


class BalanceSheet(BaseModel):
    total_assets: float = Field(..., description="Total assets in USD")
    total_liabilities: float = Field(..., description="Total liabilities in USD")
    equity: float = Field(..., description="Owner's equity in USD")
    current_ratio: float
    debt_to_equity: float
    working_capital: float = Field(..., description="Working capital in USD")


class FinancialAnalysisOutput(BaseModel):
    revenue_analysis: RevenueAnalysis
    expense_analysis: ExpenseAnalysis
    profitability: Profitability
    cash_flow: CashFlow
    balance_sheet: BalanceSheet
    risks: List[FinancialRisk]
    overall_score: int = Field(..., ge=1, le=10, description="Financial health score, 1 (worst) to 10 (best)")
    confidence: float = Field(..., ge=0, le=1)
    summary: str = Field(..., description="2-3 sentence plain-language financial summary")


class EntityType(str, Enum):
    LLC = "LLC"
    S_CORP = "S-Corp"
    C_CORP = "C-Corp"
    SOLE_PROP = "SoleProp"


class RevenueComparison(BaseModel):
    year: int
    revenue_per_financials: float = Field(..., description="Revenue per financial statements in USD")
    revenue_per_tax_return: float = Field(..., description="Revenue per tax return in USD")
    discrepancy: float = Field(..., description="Absolute discrepancy in USD")
    discrepancy_percent: float = Field(..., description="Discrepancy as percentage of financial revenue")
    explanation: Optional[str] = None


class DeductionAnalysis(BaseModel):
    category: str
    amount: float = Field(..., description="Claimed deduction amount in USD")
    industry_average: Optional[float] = Field(None, description="Industry average for this deduction in USD")
    flagged: bool = Field(..., description="True if deduction appears abnormal")
    reason: Optional[str] = None


class ComplianceFlag(BaseModel):
    id: str
    severity: Severity
    title: str
    description: str
    tax_years_affected: List[int]
    potential_exposure: Optional[float] = Field(None, description="Estimated tax exposure in USD")


class EntityStructure(BaseModel):
    type: EntityType
    tax_filing_type: str
    state_filings: List[str]


class TaxComplianceOutput(BaseModel):
    revenue_comparison: List[RevenueComparison]
    deduction_analysis: List[DeductionAnalysis]
    entity_structure: EntityStructure
    compliance_flags: List[ComplianceFlag]
    unreported_income_risk: str  # 'low', 'medium', 'high'
    overall_score: int = Field(..., ge=1, le=10, description="Tax compliance score, 1 (worst) to 10 (best)")
    confidence: float = Field(..., ge=0, le=1)
    summary: str = Field(..., description="Plain-language tax compliance summary")


class AgentSource(str, Enum):
    FINANCIAL = "financial"
    TAX = "tax"
    AR = "ar"
    CUSTOMER = "customer"
    OPERATIONS = "operations"
    LEASE = "lease"
    MARKET = "market"
    LENDING = "lending"


class Recommendation(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    CONDITIONAL_BUY = "conditional_buy"
    CAUTION = "caution"
    DO_NOT_BUY = "do_not_buy"


class RedFlag(BaseModel):
    id: str
    severity: Severity
    source: AgentSource = Field(..., description="Which agent identified this flag")
    title: str
    description: str
    financial_impact: Optional[float] = Field(None, description="Estimated financial impact in USD")


class GreenFlag(BaseModel):
    id: str
    source: AgentSource
    title: str
    description: str


class SectionSummary(BaseModel):
    score: int = Field(..., ge=1, le=10)
    summary: str
    top_risks: List[str]


class NextStep(BaseModel):
    priority: int = Field(..., ge=1, le=5)
    action: str
    reason: str


class SectionSummaries(BaseModel):
    financial: SectionSummary
    tax: SectionSummary
    ar: SectionSummary
    customer: SectionSummary
    operations: SectionSummary
    lease: SectionSummary
    market: SectionSummary
    lending: SectionSummary


class DataCompleteness(BaseModel):
    available_analyses: List[str] = Field(..., description="Agent names that completed successfully")
    failed_analyses: List[str] = Field(..., description="Agent names that failed or were skipped")
    overall_completeness: float = Field(..., ge=0, le=1, description="Fraction of agents that completed successfully")


class SynthesisReportOutput(BaseModel):
    executive_summary: str = Field(..., description="3-5 sentence plain-language summary suitable for a first-time buyer")
    overall_risk_score: int = Field(..., ge=1, le=100, description="Composite risk score, 1 (lowest risk) to 100 (highest risk)")
    recommendation: Recommendation
    red_flags: List[RedFlag]
    green_flags: List[GreenFlag]
    section_summaries: SectionSummaries
    next_steps: List[NextStep]
    deal_terms_suggestion: str = Field(..., description="Suggested deal terms based on the analysis")
    confidence: float = Field(..., ge=0, le=1)
    data_completeness: DataCompleteness


class AgingBucketName(str, Enum):
    CURRENT = "current"
    THIRTY_DAY = "30day"
    SIXTY_DAY = "60day"
    NINETY_DAY = "90day"
    OVER_90 = "over90"


class AgingBucket(BaseModel):
    bucket: AgingBucketName
    amount: float = Field(..., description="Amount in this aging bucket in USD")
    percentage: float = Field(..., description="Percentage of total AR in this bucket")


class CollectibilityFlag(BaseModel):
    id: str
    severity: Severity
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    amount: float = Field(..., description="Amount at risk in USD")
    days_past_due: int
    description: str


class ConcentrationRisk(BaseModel):
    top_customer_percent: float = Field(..., description="Percentage of AR from the largest customer")
    top5_customers_percent: float = Field(..., description="Percentage of AR from top 5 customers")


class WriteOffRisk(BaseModel):
    amount: float = Field(..., description="Estimated uncollectable amount in USD")
    percent_of_total_ar: float


class ARCollectionsOutput(BaseModel):
    total_ar: float = Field(..., description="Total accounts receivable in USD")
    aging_buckets: List[AgingBucket]
    dso: float = Field(..., description="Days sales outstanding")
    dso_industry_benchmark: Optional[float] = Field(None, description="Industry benchmark DSO for comparison")
    concentration_risk: ConcentrationRisk
    collectibility_flags: List[CollectibilityFlag]
    write_off_risk: WriteOffRisk
    overall_score: int = Field(..., ge=1, le=10, description="AR quality score, 1 (worst) to 10 (best)")
    confidence: float = Field(..., ge=0, le=1)
    summary: str = Field(..., description="Plain-language AR and collections summary")


class ContractType(str, Enum):
    MONTH_TO_MONTH = "month-to-month"
    ANNUAL = "annual"
    MULTI_YEAR = "multi-year"
    NO_CONTRACT = "no-contract"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CustomerRecord(BaseModel):
    name: str
    annual_revenue: float = Field(..., description="Annual revenue from this customer in USD")
    revenue_percent: float = Field(..., description="Percentage of total revenue from this customer")
    contract_type: ContractType
    contract_expiry: Optional[str] = None
    auto_renew: bool
    churn_risk: RiskLevel


class CustomerContractRisk(BaseModel):
    id: str
    severity: Severity
    customer_name: str
    title: str
    description: str


class CustomerMetrics(BaseModel):
    herfindahl_index: float = Field(..., description="Herfindahl-Hirschman Index (0-10000)")
    top_customer_percent: float
    top5_percent: float
    top10_percent: float


class CustomerConcentrationOutput(BaseModel):
    customers: List[CustomerRecord]
    concentration_metrics: CustomerMetrics
    contract_risks: List[CustomerContractRisk]
    single_customer_dependency: bool = Field(..., description="True if any single customer accounts for >25% of revenue")
    overall_score: int = Field(..., ge=1, le=10, description="Customer concentration score, 1 (worst) to 10 (best)")
    confidence: float = Field(..., ge=0, le=1)
    summary: str = Field(..., description="Plain-language customer concentration summary")


class Criticality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Condition(str, Enum):
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class KeyPersonnel(BaseModel):
    name: str
    role: str
    tenure: str = Field(..., description="How long this person has been in the role")
    criticality: Criticality
    retention_risk: Criticality


class LicenseInfo(BaseModel):
    type: str
    holder: str
    transferable: bool
    expiry_date: Optional[str] = None
    renewal_process: Optional[str] = None


class InsuranceInfo(BaseModel):
    type: str
    provider: str
    annual_premium: float = Field(..., description="Annual premium in USD")
    adequate: bool
    notes: Optional[str] = None


class EquipmentItem(BaseModel):
    name: str
    condition: Condition
    estimated_age: str
    estimated_value: float = Field(..., description="Estimated current value in USD")
    replacement_needed: bool


class OpsRisk(BaseModel):
    id: str
    severity: Severity
    category: str
    title: str
    description: str
    recommendation: str


class OwnerDependence(BaseModel):
    weekly_hours_worked: float
    roles_performed: List[str]
    has_delegated_management: bool
    transition_time_estimate: str = Field(..., description="Estimated time for a new owner to take over")
    score: int = Field(..., ge=1, le=10, description="Owner dependence score, 1 (owner does everything) to 10 (fully delegated)")


class EmployeeSummary(BaseModel):
    headcount: int
    key_personnel: List[KeyPersonnel]
    turnover_rate: Optional[float] = Field(None, description="Annual turnover rate as decimal")


class EquipmentSummary(BaseModel):
    total_estimated_value: float = Field(..., description="Total estimated equipment value in USD")
    items: List[EquipmentItem]


class OpsTransferabilityOutput(BaseModel):
    owner_dependence: OwnerDependence
    employees: EmployeeSummary
    licenses: List[LicenseInfo]
    insurance: List[InsuranceInfo]
    equipment: EquipmentSummary
    risks: List[OpsRisk]
    overall_score: int = Field(..., ge=1, le=10, description="Operations transferability score, 1 (very difficult) to 10 (seamless)")
    confidence: float = Field(..., ge=0, le=1)
    summary: str = Field(..., description="Plain-language operations and transferability summary")


class Enforceability(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EscalationType(str, Enum):
    FIXED = "fixed"
    CPI = "CPI"
    PERCENTAGE = "percentage"


class RenewalOption(BaseModel):
    term: str
    conditions: str


class RentEscalation(BaseModel):
    type: EscalationType
    rate: Optional[float] = Field(None, description="Escalation rate as decimal")
    schedule: Optional[str] = None


class LeaseDetails(BaseModel):
    landlord: str
    monthly_rent: float = Field(..., description="Monthly rent in USD")
    annual_rent: float = Field(..., description="Annual rent in USD")
    lease_start: str
    lease_end: str
    remaining_months: int
    is_transferable: bool
    assignment_clause: Optional[str] = None
    rent_escalation: RentEscalation
    renewal_options: List[RenewalOption]
    restrictions: List[str]


class NonCompete(BaseModel):
    exists: bool
    scope: Optional[str] = None
    duration: Optional[str] = None
    geographic_area: Optional[str] = None
    enforceability: Enforceability


class OtherContract(BaseModel):
    type: str
    counterparty: str
    term: str
    transferable: bool
    key_terms: List[str]
    risks: List[str]


class LeaseRisk(BaseModel):
    id: str
    severity: Severity
    title: str
    description: str
    recommendation: str


class LeaseContractOutput(BaseModel):
    lease: Optional[LeaseDetails] = Field(None, description="Primary business lease details, null if no lease exists")
    non_compete: Optional[NonCompete] = Field(None, description="Non-compete agreement details, null if none exists")
    other_contracts: List[OtherContract]
    risks: List[LeaseRisk]
    overall_score: int = Field(..., ge=1, le=10, description="Lease and contract score, 1 (major issues) to 10 (favorable terms)")
    confidence: float = Field(..., ge=0, le=1)
    summary: str = Field(..., description="Plain-language lease and contract summary")


class MarketTrend(str, Enum):
    GROWING = "growing"
    STABLE = "stable"
    DECLINING = "declining"


class Impact(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Density(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Horizon(str, Enum):
    NEAR_TERM = "near-term"
    MEDIUM_TERM = "medium-term"
    LONG_TERM = "long-term"


class MacroFactor(BaseModel):
    factor: str
    impact: Impact
    description: str


class MarketThreat(BaseModel):
    id: str
    severity: Severity
    title: str
    description: str
    timeframe: Horizon


class MarketOpportunity(BaseModel):
    id: str
    title: str
    description: str
    timeframe: Horizon


class IndustryOverview(BaseModel):
    name: str
    size_estimate: Optional[str] = Field(None, description='Estimated market size (for example "$50B")')
    growth_rate: Optional[float] = Field(None, description="Annual industry growth rate as decimal")
    trend: MarketTrend
    key_drivers: List[str]


class LocalMarket(BaseModel):
    area: str
    population_trend: Optional[str] = None
    competitor_density: Density
    demand_outlook: str


class MarketMacroOutput(BaseModel):
    industry_overview: IndustryOverview
    local_market: LocalMarket
    macro_factors: List[MacroFactor]
    threats: List[MarketThreat]
    opportunities: List[MarketOpportunity]
    overall_score: int = Field(..., ge=1, le=10, description="Market and macro score, 1 (hostile environment) to 10 (highly favorable)")
    confidence: float = Field(..., ge=0, le=1)
    summary: str = Field(..., description="Plain-language market and macro environment summary")


class LendingRisk(BaseModel):
    id: str
    severity: Severity
    title: str
    description: str
    recommendation: str


class SBA7aAnalysis(BaseModel):
    eligible_for_sba: bool
    max_loan_amount: float = Field(..., description="Maximum SBA 7(a) loan amount in USD")
    interest_rate: float = Field(..., description="Estimated interest rate as decimal")
    term_years: int
    monthly_payment: float = Field(..., description="Estimated monthly payment in USD")
    annual_debt_service: float = Field(..., description="Annual debt service in USD")
    dscr: float = Field(..., description="Debt service coverage ratio")
    dscr_meets_minimum: bool = Field(..., description="True if DSCR >= 1.25 (SBA minimum)")
    down_payment_required: float = Field(..., description="Required down payment in USD")
    down_payment_percent: float = Field(..., description="Down payment as percentage")
    total_project_cost: float = Field(..., description="Total project cost including fees in USD")


class SuggestedPriceRange(BaseModel):
    low: float = Field(..., description="Low end of suggested price in USD")
    high: float = Field(..., description="High end of suggested price in USD")


class AffordabilityAnalysis(BaseModel):
    asking_price: float = Field(..., description="Listing asking price in USD")
    adjusted_sde: float = Field(..., description="Validated seller's discretionary earnings in USD")
    sde_multiple: float = Field(..., description="Asking price / adjusted SDE")
    is_reasonably_priced: bool
    suggested_price_range: SuggestedPriceRange


class BuyerRequirements(BaseModel):
    minimum_down_payment: float = Field(..., description="Minimum down payment in USD")
    estimated_closing_costs: float = Field(..., description="Estimated closing costs in USD")
    total_cash_needed: float = Field(..., description="Total cash needed at closing in USD")
    minimum_post_close_liquidity: float = Field(..., description="Recommended post-close liquidity in USD")


class DealStructure(BaseModel):
    recommended_structure: str
    seller_financing_component: Optional[float] = Field(None, description="Seller financing portion in USD")
    earnout_component: Optional[float] = Field(None, description="Earnout portion in USD")
    rationale: str


class LendingAffordabilityOutput(BaseModel):
    sba7a: SBA7aAnalysis
    affordability_analysis: AffordabilityAnalysis
    buyer_requirements: BuyerRequirements
    deal_structure: DealStructure
    risks: List[LendingRisk]
    overall_score: int = Field(..., ge=1, le=10, description="Bankability score, 1 (unbankable) to 10 (highly bankable)")
    confidence: float = Field(..., ge=0, le=1)
    summary: str = Field(..., description="Plain-language lending and affordability summary")


class PipelineInput(BaseModel):
    documents: List[Dict[str, Any]]
    asking_price: Optional[float] = None
    business_type: Optional[str] = None
    location: Optional[str] = None


class TokenUsage(BaseModel):
    input: int = 0
    output: int = 0


class AgentErrorPayload(BaseModel):
    agent_name: str
    error_type: str
    message: str
    timestamp: str
    retry_count: int


T = TypeVar("T")


class AgentResult(BaseModel, Generic[T]):
    status: str
    data: Optional[Any] = None
    error: Optional[AgentErrorPayload] = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    latency_ms: Optional[int] = None


class PipelineMetadata(BaseModel):
    started_at: str
    completed_at: Optional[str] = None
    total_tokens: int = 0
    estimated_cost: float = 0.0


class PipelineState(BaseModel):
    input: PipelineInput
    ingestion: Optional[AgentResult[IngestionOutput]] = None
    financial_analysis: Optional[AgentResult[FinancialAnalysisOutput]] = None
    tax_compliance: Optional[AgentResult[TaxComplianceOutput]] = None
    ar_collections: Optional[AgentResult[ARCollectionsOutput]] = None
    customer_concentration: Optional[AgentResult[CustomerConcentrationOutput]] = None
    operations_transferability: Optional[AgentResult[OpsTransferabilityOutput]] = None
    lease_contract: Optional[AgentResult[LeaseContractOutput]] = None
    market_macro: Optional[AgentResult[MarketMacroOutput]] = None
    lending_affordability: Optional[AgentResult[LendingAffordabilityOutput]] = None
    synthesis_report: Optional[AgentResult[SynthesisReportOutput]] = None
    metadata: PipelineMetadata
