import { z } from 'zod';

const severityEnum = z.enum(['low', 'medium', 'high', 'critical']);
const trendEnum = z.enum(['increasing', 'stable', 'declining']);

const AnnualRevenueSchema = z.object({
  year: z.number().int(),
  revenue: z.number().describe('Total revenue in USD'),
  cogs: z.number().describe('Cost of goods sold in USD'),
  grossProfit: z.number().describe('Gross profit in USD'),
});

const AnnualExpenseSchema = z.object({
  year: z.number().int(),
  totalExpenses: z.number().describe('Total operating expenses in USD'),
  breakdown: z
    .record(z.string(), z.number())
    .describe('Expense category → amount in USD'),
});

const SdeAddBackSchema = z.object({
  description: z.string(),
  amount: z.number().describe('Add-back amount in USD'),
  justification: z.string(),
});

const FinancialRiskSchema = z.object({
  id: z.string(),
  category: z.string(),
  severity: severityEnum,
  title: z.string(),
  description: z.string(),
  evidence: z.string(),
  financialImpact: z
    .number()
    .optional()
    .describe('Estimated financial impact in USD'),
  recommendation: z.string(),
});

export const FinancialAnalysisOutputSchema = z
  .object({
    revenueAnalysis: z.object({
      annualFigures: z.array(AnnualRevenueSchema),
      growthRate: z.number().describe('Year-over-year growth rate as decimal'),
      trend: trendEnum,
      seasonalityNotes: z.string(),
    }),
    expenseAnalysis: z.object({
      annualFigures: z.array(AnnualExpenseSchema),
      largestCategories: z
        .array(z.string())
        .describe('Top expense categories by size'),
    }),
    profitability: z.object({
      grossMargin: z.number().describe('Gross margin as decimal'),
      netMargin: z.number().describe('Net margin as decimal'),
      ebitda: z.number().describe('EBITDA in USD'),
      adjustedEbitda: z.number().describe('Adjusted EBITDA in USD'),
      sde: z.number().describe("Seller's discretionary earnings in USD"),
      sdeAddBacks: z.array(SdeAddBackSchema),
    }),
    cashFlow: z.object({
      operatingCashFlow: z.number().describe('Operating cash flow in USD'),
      freeCashFlow: z.number().describe('Free cash flow in USD'),
      cashFlowVsNetIncome: z
        .boolean()
        .describe(
          'True if significant discrepancy between cash flow and net income'
        ),
    }),
    balanceSheet: z.object({
      totalAssets: z.number().describe('Total assets in USD'),
      totalLiabilities: z.number().describe('Total liabilities in USD'),
      equity: z.number().describe("Owner's equity in USD"),
      currentRatio: z.number(),
      debtToEquity: z.number(),
      workingCapital: z.number().describe('Working capital in USD'),
    }),
    risks: z.array(FinancialRiskSchema),
    overallScore: z
      .number()
      .int()
      .min(1)
      .max(10)
      .describe('Financial health score, 1 (worst) to 10 (best)'),
    confidence: z.number().min(0).max(1),
    summary: z
      .string()
      .describe('2-3 sentence plain-language financial summary'),
  })
  .describe(
    'Financial Analysis agent output — revenue, expense, profitability, cash flow, and balance sheet analysis'
  );

export type FinancialAnalysisOutput = z.infer<
  typeof FinancialAnalysisOutputSchema
>;
