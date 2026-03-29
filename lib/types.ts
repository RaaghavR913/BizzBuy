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
}

export interface CashFlowStatement {
  operatingCashFlow: number;
  investingCashFlow?: number;
  financingCashFlow?: number;
  netCashFlow: number;
  capitalExpenditures?: number;
  freeCashFlow?: number;
}

export interface FinancialData {
  incomeStatement: IncomeStatement | null;
  balanceSheet: BalanceSheet | null;
  loanTerms: LoanTerms | null;
  cashFlow: CashFlowStatement | null;
  parsingNotes: string[];
  dataCompleteness: number;
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
  sourceAgent: AgentId;
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
  dealInfo: DealInfo | null;
  sharedContext: SharedContext | null;
  report: ReportOutput | null;
  isLoading: boolean;
  loadingMessage: string;
  error: string | null;
}
