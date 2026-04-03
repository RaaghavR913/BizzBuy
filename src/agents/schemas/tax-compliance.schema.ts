import { z } from 'zod';

const severityEnum = z.enum(['low', 'medium', 'high', 'critical']);
const entityTypeEnum = z.enum(['LLC', 'S-Corp', 'C-Corp', 'SoleProp']);

const RevenueComparisonSchema = z.object({
  year: z.number().int(),
  revenuePerFinancials: z
    .number()
    .describe('Revenue per financial statements in USD'),
  revenuePerTaxReturn: z
    .number()
    .describe('Revenue per tax return in USD'),
  discrepancy: z.number().describe('Absolute discrepancy in USD'),
  discrepancyPercent: z
    .number()
    .describe('Discrepancy as percentage of financial revenue'),
  explanation: z.string().optional(),
});

const DeductionAnalysisSchema = z.object({
  category: z.string(),
  amount: z.number().describe('Claimed deduction amount in USD'),
  industryAverage: z
    .number()
    .optional()
    .describe('Industry average for this deduction in USD'),
  flagged: z.boolean().describe('True if deduction appears abnormal'),
  reason: z.string().optional(),
});

const ComplianceFlagSchema = z.object({
  id: z.string(),
  severity: severityEnum,
  title: z.string(),
  description: z.string(),
  taxYearsAffected: z.array(z.number().int()),
  potentialExposure: z
    .number()
    .optional()
    .describe('Estimated tax exposure in USD'),
});

export const TaxComplianceOutputSchema = z
  .object({
    revenueComparison: z.array(RevenueComparisonSchema),
    deductionAnalysis: z.array(DeductionAnalysisSchema),
    entityStructure: z.object({
      type: entityTypeEnum,
      taxFilingType: z.string(),
      stateFilings: z.array(z.string()),
    }),
    complianceFlags: z.array(ComplianceFlagSchema),
    unreportedIncomeRisk: z.enum(['low', 'medium', 'high']),
    overallScore: z
      .number()
      .int()
      .min(1)
      .max(10)
      .describe('Tax compliance score, 1 (worst) to 10 (best)'),
    confidence: z.number().min(0).max(1),
    summary: z.string().describe('Plain-language tax compliance summary'),
  })
  .describe(
    'Tax Compliance agent output — cross-references financials vs. tax returns and flags discrepancies'
  );

export type TaxComplianceOutput = z.infer<typeof TaxComplianceOutputSchema>;
