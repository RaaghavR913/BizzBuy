import type { AgentResult } from '@/src/types/pipeline';
import type { IngestionOutput, DocumentSection } from '@/src/agents/schemas/ingestion.schema';
import type { FinancialAnalysisOutput } from '@/src/agents/schemas/financial-analysis.schema';
import { FinancialAnalysisOutputSchema } from '@/src/agents/schemas/financial-analysis.schema';
import { loadAgentPrompt } from '@/src/agents/utils/prompt-loader';
import { callAgent } from '@/src/agents/utils/claude-client';
import { AGENT_REGISTRY } from '@/src/agents/registry';

// ---------------------------------------------------------------------------
// Types for pre-computed metrics
// ---------------------------------------------------------------------------

interface AnnualFinancials {
  year: number;
  revenue: number | null;
  cogs: number | null;
  grossProfit: number | null;
  netIncome: number | null;
  ebitda: number | null;
  operatingExpenses: number | null;
  depreciation: number | null;
  amortization: number | null;
  interestExpense: number | null;
  taxes: number | null;
}

interface BalanceSheetMetrics {
  totalAssets: number | null;
  totalLiabilities: number | null;
  currentAssets: number | null;
  currentLiabilities: number | null;
  equity: number | null;
  totalDebt: number | null;
}

interface CashFlowMetrics {
  operatingCashFlow: number | null;
  capitalExpenditures: number | null;
  freeCashFlow: number | null;
}

interface SdeMetrics {
  reportedNetIncome: number | null;
  ownerSalary: number | null;
  ownerBenefits: number | null;
  depreciation: number | null;
  interestExpense: number | null;
  oneTimeExpenses: number | null;
  totalAddBacks: number | null;
  sde: number | null;
}

export interface ComputedFinancialMetrics {
  annualFinancials: AnnualFinancials[];
  revenueGrowthRates: Array<{ fromYear: number; toYear: number; rate: number | null }>;
  mostRecentYear: AnnualFinancials | null;
  grossMargin: number | null;
  netMargin: number | null;
  ebitdaMargin: number | null;
  balanceSheet: BalanceSheetMetrics;
  currentRatio: number | null;
  debtToEquity: number | null;
  workingCapital: number | null;
  cashFlow: CashFlowMetrics;
  cashFlowVsNetIncomeDivergence: number | null;
  sde: SdeMetrics;
  dataYearsAvailable: number;
  documentTypes: string[];
}

// ---------------------------------------------------------------------------
// Deterministic computation helpers
// ---------------------------------------------------------------------------

function safeNum(val: unknown): number | null {
  if (val === null || val === undefined || val === '') return null;
  const n = Number(val);
  return isFinite(n) ? n : null;
}

function safeDiv(numerator: number | null, denominator: number | null): number | null {
  if (numerator === null || denominator === null || denominator === 0) return null;
  return numerator / denominator;
}

/**
 * Extracts annual P&L figures from all P&L and cash-flow document sections.
 * Groups sections by fiscal year and merges fields.
 */
function extractAnnualFinancials(sections: DocumentSection[]): AnnualFinancials[] {
  const plSections = sections.filter(
    (s) => s.documentType === 'profit_and_loss' || s.documentType === 'cash_flow_statement'
  );

  const byYear = new Map<number, Record<string, unknown>>();

  for (const section of plSections) {
    const year = section.timeframe.fiscalYear;
    if (!year) continue;

    const existing = byYear.get(year) ?? {};
    byYear.set(year, { ...existing, ...section.extractedData });
  }

  return Array.from(byYear.entries())
    .sort(([a], [b]) => a - b)
    .map(([year, data]) => {
      const revenue = safeNum(data['revenue'] ?? data['gross_revenue'] ?? data['net_revenue'] ?? data['total_revenue']);
      const cogs = safeNum(data['cogs'] ?? data['cost_of_goods_sold'] ?? data['cost_of_revenue']);
      const grossProfit = safeNum(data['gross_profit']) ?? (revenue !== null && cogs !== null ? revenue - cogs : null);
      const netIncome = safeNum(data['net_income'] ?? data['net_profit'] ?? data['net_earnings']);
      const depreciation = safeNum(data['depreciation'] ?? data['depreciation_amortization']);
      const amortization = safeNum(data['amortization']);
      const interestExpense = safeNum(data['interest_expense'] ?? data['interest']);
      const taxes = safeNum(data['income_tax'] ?? data['taxes'] ?? data['tax_expense']);
      const operatingExpenses = safeNum(data['operating_expenses'] ?? data['total_operating_expenses'] ?? data['opex']);

      // EBITDA = Net Income + Interest + Taxes + Depreciation + Amortization
      let ebitda: number | null = null;
      if (netIncome !== null) {
        ebitda = netIncome
          + (interestExpense ?? 0)
          + (taxes ?? 0)
          + (depreciation ?? 0)
          + (amortization ?? 0);
      }

      return { year, revenue, cogs, grossProfit, netIncome, ebitda, operatingExpenses, depreciation, amortization, interestExpense, taxes };
    });
}

function extractBalanceSheet(sections: DocumentSection[]): BalanceSheetMetrics {
  const bsSections = sections.filter((s) => s.documentType === 'balance_sheet');

  // Use the most recent balance sheet
  const sorted = bsSections.sort((a, b) => {
    const ay = a.timeframe.fiscalYear ?? 0;
    const by = b.timeframe.fiscalYear ?? 0;
    return by - ay;
  });

  const data = sorted[0]?.extractedData ?? {};

  const totalAssets = safeNum(data['total_assets']);
  const totalLiabilities = safeNum(data['total_liabilities']);
  const currentAssets = safeNum(data['current_assets'] ?? data['total_current_assets']);
  const currentLiabilities = safeNum(data['current_liabilities'] ?? data['total_current_liabilities']);
  const equity = safeNum(data['total_equity'] ?? data["owner's_equity"] ?? data['shareholders_equity'] ?? data['equity']);
  const totalDebt = safeNum(data['total_debt'] ?? data['long_term_debt']);

  return { totalAssets, totalLiabilities, currentAssets, currentLiabilities, equity, totalDebt };
}

function extractCashFlow(sections: DocumentSection[]): CashFlowMetrics {
  const cfSections = sections.filter((s) => s.documentType === 'cash_flow_statement');
  const sorted = cfSections.sort((a, b) => {
    const ay = a.timeframe.fiscalYear ?? 0;
    const by = b.timeframe.fiscalYear ?? 0;
    return by - ay;
  });

  const data = sorted[0]?.extractedData ?? {};

  const operatingCashFlow = safeNum(data['operating_cash_flow'] ?? data['cash_from_operations'] ?? data['net_cash_from_operating_activities']);
  const capitalExpenditures = safeNum(data['capital_expenditures'] ?? data['capex'] ?? data['purchase_of_property_equipment']);
  const freeCashFlow = operatingCashFlow !== null && capitalExpenditures !== null
    ? operatingCashFlow - Math.abs(capitalExpenditures)
    : operatingCashFlow;

  return { operatingCashFlow, capitalExpenditures, freeCashFlow };
}

function extractSde(sections: DocumentSection[]): SdeMetrics {
  const plSections = sections.filter((s) => s.documentType === 'profit_and_loss');
  const sorted = plSections.sort((a, b) => {
    const ay = a.timeframe.fiscalYear ?? 0;
    const by = b.timeframe.fiscalYear ?? 0;
    return by - ay;
  });

  const data = sorted[0]?.extractedData ?? {};

  const reportedNetIncome = safeNum(data['net_income'] ?? data['net_profit']);
  const ownerSalary = safeNum(data['owner_salary'] ?? data['officer_compensation'] ?? data['owners_compensation']);
  const ownerBenefits = safeNum(data['owner_benefits'] ?? data['officer_benefits']);
  const depreciation = safeNum(data['depreciation'] ?? data['depreciation_amortization']);
  const interestExpense = safeNum(data['interest_expense'] ?? data['interest']);
  const oneTimeExpenses = safeNum(data['one_time_expenses'] ?? data['nonrecurring_expenses']);

  const totalAddBacks =
    (ownerSalary ?? 0) +
    (ownerBenefits ?? 0) +
    (depreciation ?? 0) +
    (interestExpense ?? 0) +
    (oneTimeExpenses ?? 0);

  const sde = reportedNetIncome !== null ? reportedNetIncome + totalAddBacks : null;

  return {
    reportedNetIncome,
    ownerSalary,
    ownerBenefits,
    depreciation,
    interestExpense,
    oneTimeExpenses,
    totalAddBacks: totalAddBacks > 0 ? totalAddBacks : null,
    sde,
  };
}

/**
 * Computes all deterministic financial metrics from ingested document sections.
 * Returns null for any metric that cannot be derived from available data.
 */
export function computeFinancialMetrics(sections: DocumentSection[]): ComputedFinancialMetrics {
  const annualFinancials = extractAnnualFinancials(sections);
  const balanceSheet = extractBalanceSheet(sections);
  const cashFlow = extractCashFlow(sections);
  const sde = extractSde(sections);

  const mostRecentYear = annualFinancials.length > 0
    ? annualFinancials[annualFinancials.length - 1]
    : null;

  // YoY revenue growth rates
  const revenueGrowthRates = annualFinancials.slice(1).map((current, i) => {
    const prior = annualFinancials[i];
    const rate = safeDiv(
      current.revenue !== null && prior.revenue !== null ? current.revenue - prior.revenue : null,
      prior.revenue
    );
    return { fromYear: prior.year, toYear: current.year, rate };
  });

  const grossMargin = mostRecentYear
    ? safeDiv(mostRecentYear.grossProfit, mostRecentYear.revenue)
    : null;

  const netMargin = mostRecentYear
    ? safeDiv(mostRecentYear.netIncome, mostRecentYear.revenue)
    : null;

  const ebitdaMargin = mostRecentYear
    ? safeDiv(mostRecentYear.ebitda, mostRecentYear.revenue)
    : null;

  const currentRatio = safeDiv(balanceSheet.currentAssets, balanceSheet.currentLiabilities);

  const debtToEquity = safeDiv(balanceSheet.totalLiabilities, balanceSheet.equity);

  const workingCapital =
    balanceSheet.currentAssets !== null && balanceSheet.currentLiabilities !== null
      ? balanceSheet.currentAssets - balanceSheet.currentLiabilities
      : null;

  // Cash flow vs net income divergence (as fraction of net income)
  const cashFlowVsNetIncomeDivergence =
    cashFlow.operatingCashFlow !== null && mostRecentYear?.netIncome
      ? Math.abs(cashFlow.operatingCashFlow - mostRecentYear.netIncome) / Math.abs(mostRecentYear.netIncome)
      : null;

  const documentTypes = [...new Set(sections.map((s) => s.documentType))];

  return {
    annualFinancials,
    revenueGrowthRates,
    mostRecentYear,
    grossMargin,
    netMargin,
    ebitdaMargin,
    balanceSheet,
    currentRatio,
    debtToEquity,
    workingCapital,
    cashFlow,
    cashFlowVsNetIncomeDivergence,
    sde,
    dataYearsAvailable: annualFinancials.length,
    documentTypes,
  };
}

// ---------------------------------------------------------------------------
// Runner
// ---------------------------------------------------------------------------

export async function runFinancialAnalysis(
  ingestionOutput: IngestionOutput
): Promise<AgentResult<FinancialAnalysisOutput>> {
  const config = AGENT_REGISTRY['financial-analysis'];

  const relevantDocTypes = new Set([
    'profit_and_loss',
    'balance_sheet',
    'cash_flow_statement',
  ]);

  const allSections: DocumentSection[] = ingestionOutput.documents
    .filter((doc) => relevantDocTypes.has(doc.documentType))
    .flatMap((doc) => doc.sections);

  const metrics = computeFinancialMetrics(allSections);

  const confidence =
    metrics.dataYearsAvailable >= 3
      ? 0.85
      : metrics.dataYearsAvailable >= 1
        ? 0.6
        : 0.3;

  const systemPrompt = loadAgentPrompt('financial-analysis');

  const rawDataSummary = ingestionOutput.documents
    .filter((doc) => relevantDocTypes.has(doc.documentType))
    .map((doc) => {
      const sectionSummaries = doc.sections
        .map((s) => `  [FY${s.timeframe.fiscalYear ?? 'unknown'}] ${JSON.stringify(s.extractedData)}`)
        .join('\n');
      return `### ${doc.fileName} (${doc.documentType})\n${sectionSummaries}`;
    })
    .join('\n\n');

  const noDataWarning =
    metrics.dataYearsAvailable === 0
      ? '\n\n⚠️ WARNING: No profit & loss, balance sheet, or cash flow documents were found. ' +
        'All financial fields will have null values. Set confidence to 0.2 and note the data gap in your summary.'
      : '';

  const userMessage =
    `## Pre-Computed Financial Metrics\n` +
    JSON.stringify(metrics, null, 2) +
    `\n\n## Raw Extracted Financial Data\n` +
    (rawDataSummary || '(No financial documents found)') +
    noDataWarning;

  return callAgent<FinancialAnalysisOutput>({
    model: config.model,
    systemPrompt,
    userMessage,
    schema: FinancialAnalysisOutputSchema,
    maxTokens: config.maxTokens,
    temperature: 0,
  });
}
