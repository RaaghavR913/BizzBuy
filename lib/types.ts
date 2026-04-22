// TypeScript interfaces matching the PRD data models

export interface AddBack {
  description: string;
  amount: number;
  category: 'owner_salary' | 'one_time_expense' | 'personal_expense' | 'non_cash' | 'other';
}

export interface IncomeStatement {
  revenue: number;
  cogs: number;
  grossProfit: number;
  operatingExpenses: number;
  depreciationAmortization?: number;
  interestExpense?: number;
  netIncome: number;
  ownerSalary?: number;
  addBacks?: AddBack[];
  sde?: number;
  ebitda?: number;
  periods: string[];
  revenueByYear?: Record<string, number>;
  netIncomeByYear?: Record<string, number>;
}

export interface BalanceSheet {
  currentAssets: number;
  cashAndEquivalents?: number;
  accountsReceivable?: number;
  inventory?: number;
  currentLiabilities: number;
  accountsPayable?: number;
  totalAssets: number;
  totalLiabilities: number;
  equity: number;
}

export interface LoanTerms {
  loanAmount: number;
  interestRate: number;
  termMonths: number;
  monthlyPayment?: number;
  downPayment?: number;
  askingPrice: number;
  loanType?: 'sba_7a' | 'sba_504' | 'conventional' | 'seller_financing' | 'other';
  collateralRequired?: boolean;
  askingPriceEstimated?: boolean;
}

export interface CashFlowStatement {
  operatingCashFlow: number;
  investingCashFlow?: number;
  financingCashFlow?: number;
  netCashFlow: number;
  capitalExpenditures?: number;
  freeCashFlow?: number;
}

export interface DealHints {
  yearsInOperation?: number | null;
  detectedLocation?: string | null;
  suggestedBusinessType?: string | null;
}

export interface FinancialData {
  incomeStatement: IncomeStatement | null;
  balanceSheet: BalanceSheet | null;
  loanTerms: LoanTerms | null;
  cashFlow: CashFlowStatement | null;
  parsingNotes: string[];
  dataCompleteness: number;
  dealHints?: DealHints | null;
}

export interface PipelineDocumentPayload {
  document_id: string;
  file_name: string;
  mime_type: string;
  document_type: CanonicalDocumentType;
  declared_type?: CanonicalDocumentType | null;
  canonical_type?: CanonicalDocumentType | null;
  size_bytes?: number | null;
  status?: string;
  confidence?: number | null;
  notes?: string[];
  sections: Array<{
    section_id?: string | null;
    document_id: string;
    document_type: CanonicalDocumentType;
    section_kind?: string | null;
    sectionKind?: string | null;
    timeframe?: {
      start_date?: string | null;
      end_date?: string | null;
      fiscal_year?: number | null;
    };
    extracted_data: Record<string, unknown>;
    raw_text: string;
    confidence: number;
    section_name?: string | null;
    page?: number | null;
    page_start?: number | null;
    page_end?: number | null;
    source_format?: string | null;
    content_type?: string;
    status?: string;
    notes?: string[];
  }>;
}

export type CanonicalDocumentType =
  | 'profit_and_loss'
  | 'balance_sheet'
  | 'cash_flow_statement'
  | 'tax_return_1120s'
  | 'tax_return_1040'
  | 'tax_return_schedule_c'
  | 'tax_return_1065'
  | 'sales_tax_filing'
  | 'payroll_tax_941'
  | 'ar_aging_report'
  | 'customer_list'
  | 'top_customer_concentration'
  | 'contract'
  | 'lease_agreement'
  | 'letter_of_intent'
  | 'asset_purchase_agreement'
  | 'operating_agreement'
  | 'franchise_agreement'
  | 'employment_agreement'
  | 'non_compete_nda'
  | 'employee_roster'
  | 'insurance_policy'
  | 'equipment_list'
  | 'supplier_vendor_list'
  | 'permits_licenses'
  | 'business_overview_memo'
  | 'sde_worksheet'
  | 'financial_projections'
  | 'bank_statement'
  | 'aged_trial_balance'
  | 'loan_term_sheet'
  | 'personal_financial_statement'
  | 'other'
  | 'unknown';

export type ClassificationStatus = 'queued' | 'uploading' | 'classifying' | 'classified' | 'error';

export interface ClassifiedFileResult {
  fileId: string;
  originalName: string;
  mimeType: string;
  sizeBytes: number;
  detectedType: CanonicalDocumentType;
  confidence: number;
  rationale: string;
  suggestedAlternatives: string[];
  extractedMetadata: {
    businessName: string | null;
    periodStart: string | null;
    periodEnd: string | null;
    currency: string | null;
    sheetKinds?: CanonicalDocumentType[];
  };
  fileHash?: string | null;
  ocrArtifactRef?: string | null;
  error?: string | null;
}

export interface IngestResponse {
  runId: string;
  files: ClassifiedFileResult[];
}

export type CanonicalAgentName =
  | 'ingestion'
  | 'financial_analysis'
  | 'tax_compliance'
  | 'ar_collections'
  | 'customer_concentration'
  | 'operations_transferability'
  | 'lease_contract'
  | 'market_macro'
  | 'lending_affordability'
  | 'synthesis_report';



export type FindingCategory =
  | 'earnings_quality'
  | 'cash_flow'
  | 'working_capital'
  | 'tax_compliance'
  | 'receivables'
  | 'customer_concentration'
  | 'contract_durability'
  | 'owner_dependence'
  | 'operational_transferability'
  | 'lease_transferability'
  | 'market_conditions'
  | 'lending'
  | 'legal_compliance'
  | 'missing_data'
  | 'conflict';

export type DeterministicTag =
  | 'deal_breaker_candidate'
  | 'sde_adjustment'
  | 'valuation_pressure'
  | 'bankability_pressure'
  | 'transferability_pressure'
  | 'completeness_penalty';

export type FindingSeverity = 'low' | 'medium' | 'high' | 'critical';

export interface EvidenceReference {
  documentId: string;
  fileName?: string;
  sectionId?: string;
  page?: number;
  snippet?: string;
  extractedFields: Record<string, string | number | boolean | null>;
  confidence?: number;
}

export interface NormalizedMetric {
  value: string | number | boolean | null;
  unit?: string;
  displayValue?: string;
  confidence?: number;
  timeframe?: {
    startDate?: string;
    endDate?: string;
    fiscalYear?: number;
  };
  evidence: EvidenceReference[];
}

export interface MissingInput {
  key: string;
  description: string;
  documentType?: CanonicalDocumentType;
  required: boolean;
  reason?: string;
}

export type ClarificationAnswerType = 'boolean' | 'percent' | 'select';

export interface ClarificationOption {
  value: string;
  label: string;
  sublabel?: string;
}

export interface ClarificationQuestion {
  id: string;
  category:
    | 'owner_dependence'
    | 'customer_concentration'
    | 'operational_transferability'
    | 'financial_risk';
  prompt: string;
  helpText: string;
  answerType: ClarificationAnswerType;
  relatedDocumentTypes: CanonicalDocumentType[];
  legacyFieldPath: string;
  options?: ClarificationOption[];
}

export interface ClarificationAnswer {
  questionId: string;
  prompt: string;
  category: ClarificationQuestion['category'];
  answerType: ClarificationAnswerType;
  value: string | number | boolean | null;
  valueLabel?: string;
  relatedDocumentTypes: CanonicalDocumentType[];
  legacyFieldPath: string;
  source: 'user_asserted';
  confidence: number;
  supplemental: true;
}

export interface NormalizedFinding {
  findingId: string;
  sourceAgent: CanonicalAgentName;
  category: FindingCategory;
  severity: FindingSeverity;
  title: string;
  description: string;
  deterministicTags: DeterministicTag[];
  metricImpact: Record<string, string | number | boolean | null>;
  evidence: EvidenceReference[];
  confidence: number;
  missingData: boolean;
}



export interface BuyerFacingDimension {
  key: string;
  label: string;
  score?: number;
  status?: string;
  summary?: string;
}

export interface TechnicalScorecard {
  name: string;
  score?: number;
  recommendation?: string;
  findings: NormalizedFinding[];
  metrics: Record<string, NormalizedMetric>;
}

export interface DeepReviewScoringImpact {
  buyerFacingDimensions: string[];
  riskContribution?: number;
}

export interface DeepReviewAgentReview {
  agentName: CanonicalAgentName;
  headline?: string;
  summary?: string;
  technicalScore?: number;
  confidence?: number;
  keyMetrics: Record<string, NormalizedMetric>;
  findings: NormalizedFinding[];
  evidence: EvidenceReference[];
  missingInputs: MissingInput[];
  scoringImpact: DeepReviewScoringImpact;
}

export interface MissingDataDetail {
  key: string;
  description: string;
  documentType?: CanonicalDocumentType;
  required: boolean;
  reason?: string;
  affectedAgents: CanonicalAgentName[];
  relatedFindings: string[];
  impactSummary?: string;
}

export interface ScoreConflict {
  key: string;
  description: string;
  conservativeValue?: string | number | boolean | null;
  conflictingValues: Record<string, string | number | boolean | null>;
  evidence: EvidenceReference[];
}

export interface DeterministicScorecard {
  overallRiskScore?: number;
  overallRecommendation?: string;
  buyerFacingDimensions: BuyerFacingDimension[];
  technicalScorecards: TechnicalScorecard[];
  dealBreakers: NormalizedFinding[];
  conflicts: ScoreConflict[];
  completenessScore?: number;
  confidenceScore?: number;
  validatedMetrics: Record<string, NormalizedMetric>;
}

export interface ReportOutputV2 {
  modeAvailable: {
    summary: boolean;
    deep: boolean;
  };
  summary: {
    headline?: string;
    overview?: string;
    keyFindings: NormalizedFinding[];
    recommendedActions: string[];
  };
  scorecard: DeterministicScorecard;
  deepReview?: {
    agentReviews: DeepReviewAgentReview[];
    evidenceIndex: EvidenceReference[];
    auditTrail: string[];
    missingData: MissingDataDetail[];
  };
  metadata: {
    contractVersion: string;
    generatedAt?: string;
    analysisId?: string;
    pipelineStatus?: string;
    sourceDocumentCount?: number;
  };
}

export type AnyReportOutput = ReportOutput | ReportOutputV2;

export type AnalysisJobStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface AnalysisJobProgress {
  stage: string;
  message: string;
  progress: number;
  updatedAt?: string;
  completedAgents?: string[];
}

export interface AnalysisJobSnapshot {
  analysisId: string;
  status: AnalysisJobStatus;
  createdAt: string;
  updatedAt: string;
  startedAt?: string | null;
  completedAt?: string | null;
  progress: AnalysisJobProgress;
  error?: string | null;
  report?: AnyReportOutput | null;
}

export type AgentId =
  | 'financial'
  | 'tax'
  | 'arCollections'
  | 'customer'
  | 'operations'
  | 'leaseContracts'
  | 'marketMacro';

export interface AgentFlag {
  severity: 'info' | 'warning' | 'critical';
  message: string;
  dimension: string;
  sourceAgent?: AgentId | 'backend';
  metric?: string;
}

export interface AgentOutput {
  agentId: AgentId;
  summary: string;
  flags: AgentFlag[];
  metrics: Record<string, number | string | boolean | null>;
  confidence: number;
  notes: string[];
}

export interface QuestionnaireData {
  ownerDependence: {
    ownerSalesPercentage: number | null;
    ownerInvolvement: 'full_time' | 'part_time' | 'minimal' | 'unknown';
    ownerHoldsRelationships: boolean | null;
    survives90DayAbsence: 'yes' | 'likely' | 'unlikely' | 'no' | 'unknown';
  };
  customerConcentration: {
    topCustomerRevenuePercent: number | null;
    top5CustomersRevenuePercent: number | null;
    contractType: 'mostly_contracted' | 'mixed' | 'mostly_handshake' | 'unknown';
    averageCustomerTenure: 'less_than_1_year' | '1_to_3_years' | '3_plus_years' | 'unknown';
  };
  revenueQuality: {
    recurringRevenuePercent: number | null;
    projectBasedPercent: number | null;
    revenueTrend: 'growing' | 'flat' | 'declining' | 'unknown';
    knownUpcomingLosses: boolean | null;
  };
  employeeRisk: {
    totalEmployees: number | null;
    missionCriticalEmployees: number | null;
    hasSOPs: boolean | null;
    hasManagementLayer: boolean | null;
  };
  supplierRisk: {
    singleSupplierOver30Pct: boolean | null;
    supplierAgreementsDocumented: boolean | null;
    exclusiveVendorRelationships: boolean | null;
  };
  financialRisk: {
    hasAddBacks: boolean | null;
    addBacksExceed30Pct: boolean | null;
    pendingLiabilities: boolean | null;
  };
}

export interface DealInfo {
  askingPrice: number;
  businessType: string;
  yearsInOperation: number | null;
  reasonForSale: string | null;
  location?: string;
  industry?: string;
}

export interface RiskDimensionScore {
  dimension: string;
  score: number;
  label: 'Low' | 'Moderate' | 'High' | 'Critical';
  explanation: string;
  keyFactors: string[];
  isDealBreaker: boolean;
}

export interface ScenarioAnalysis {
  label: string;
  annualRevenue: number;
  annualDebtService: number;
  remainingCashFlow: number;
  dscr: number;
  payoffMonths: number;
  annualOwnerIncome: number;
}

export interface ReportOutput {
  executiveSummary: {
    text: string;
    riskScore: number;
    riskLabel: 'Low' | 'Moderate' | 'High' | 'Very High';
    transferabilityScore: number;
    transferabilityLabel: 'High' | 'Moderate' | 'Low' | 'Very Low';
    verdict: string;
  };
  financialSnapshot: {
    metrics: Record<string, { value: number; formatted: string; note?: string }>;
    valuationMultiple: number;
    multipleAssessment: string;
  };
  debtServiceAnalysis: {
    loanSummary: Record<string, string>;
    monthlyDebtService: number;
    annualDebtService: number;
    dscr: number;
    dscrAssessment: string;
    minimumRevenueRequired: number;
    breakEvenMonthlyRevenue: number;
    scenarios: ScenarioAnalysis[];
    affordabilityVerdict: string;
  };
  riskAssessment: {
    overallScore: number;
    dimensions: RiskDimensionScore[];
    dealBreakers: string[];
  };
  transferabilityAnalysis: {
    score: number;
    explanation: string;
    keyFactors: { factor: string; impact: 'positive' | 'negative' | 'neutral'; detail: string }[];
    improvementSuggestions: string[];
  };
  questionsForSeller: {
    category: string;
    questions: string[];
  }[];
  diligenceChecklist: {
    item: string;
    category: string;
    priority: 'critical' | 'important' | 'nice_to_have';
    reason: string;
  }[];
  upsideOpportunities: {
    opportunity: string;
    estimatedImpact: string;
    difficulty: 'easy' | 'moderate' | 'hard';
    detail: string;
  }[];
  finalRecommendation: {
    action: 'proceed' | 'proceed_with_caution' | 'walk_away';
    strengths: string[];
    risks: string[];
    nextSteps: string[];
    summaryStatement: string;
  };
  agentFlags: AgentFlag[];
  sbaLoanSizing: {
    maxSupportedLoan: number;
    estimatedInterestRate: number;
    estimatedMonthlyPayment: number;
    estimatedAnnualDebtService: number;
    estimatedDSCR: number;
    bankabilityScore: number;
    bankabilityLabel: 'Weak' | 'Borderline' | 'Bankable' | 'Strong';
    explanation: string;
  };
  metadata: {
    generatedAt: string;
    analysisVersion: string;
    dataCompleteness: number;
    disclaimers: string[];
  };
}

export interface SharedContext {
  financialData: FinancialData;
  questionnaire: QuestionnaireData;
  dealInfo: DealInfo;
  agentOutputs: Partial<Record<AgentId, AgentOutput>>;
  mergedFlags: AgentFlag[];
  validatedSDE: number;
  sdeConflict: boolean;
  dataCompleteness: number;
}

export interface AnalysisState {
  step: 1 | 2 | 3 | 4;
  financialData: FinancialData | null;
  questionnaire: QuestionnaireData | null;
  clarifications: ClarificationAnswer[];
  dealInfo: DealInfo | null;
  analysisId: string | null;
  analysisJob: AnalysisJobSnapshot | null;
  pipelineDocuments: PipelineDocumentPayload[];
  sharedContext: SharedContext | null;
  report: AnyReportOutput | null;
  isLoading: boolean;
  loadingMessage: string;
  error: string | null;
}
