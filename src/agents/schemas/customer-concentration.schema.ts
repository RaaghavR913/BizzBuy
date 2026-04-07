import { z } from 'zod';

const severityEnum = z.enum(['low', 'medium', 'high', 'critical']);
const contractTypeEnum = z.enum([
  'month-to-month',
  'annual',
  'multi-year',
  'no-contract',
]);
const riskLevelEnum = z.enum(['low', 'medium', 'high']);

const CustomerSchema = z.object({
  name: z.string(),
  annualRevenue: z
    .number()
    .describe('Annual revenue from this customer in USD'),
  revenuePercent: z
    .number()
    .describe('Percentage of total revenue from this customer'),
  contractType: contractTypeEnum,
  contractExpiry: z.string().optional(),
  autoRenew: z.boolean(),
  churnRisk: riskLevelEnum,
});

const ContractRiskSchema = z.object({
  id: z.string(),
  severity: severityEnum,
  customerName: z.string(),
  title: z.string(),
  description: z.string(),
});

export const CustomerConcentrationOutputSchema = z
  .object({
    customers: z.array(CustomerSchema),
    concentrationMetrics: z.object({
      herfindahlIndex: z
        .number()
        .describe('Herfindahl-Hirschman Index (0-10000)'),
      topCustomerPercent: z.number(),
      top5Percent: z.number(),
      top10Percent: z.number(),
    }),
    contractRisks: z.array(ContractRiskSchema),
    singleCustomerDependency: z
      .boolean()
      .describe(
        'True if any single customer accounts for >25% of revenue'
      ),
    overallScore: z
      .number()
      .int()
      .min(1)
      .max(10)
      .describe(
        'Customer concentration score, 1 (worst — highly concentrated) to 10 (best — diversified)'
      ),
    confidence: z.number().min(0).max(1),
    summary: z
      .string()
      .describe('Plain-language customer concentration summary'),
  })
  .describe(
    'Customer Concentration agent output — customer revenue distribution, contract analysis, and churn risk'
  );

export type CustomerConcentrationOutput = z.infer<
  typeof CustomerConcentrationOutputSchema
>;
