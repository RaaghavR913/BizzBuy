import { z } from 'zod';

const severityEnum = z.enum(['low', 'medium', 'high', 'critical']);
const bucketEnum = z.enum([
  'current',
  '30day',
  '60day',
  '90day',
  'over90',
]);

const AgingBucketSchema = z.object({
  bucket: bucketEnum,
  amount: z.number().describe('Amount in this aging bucket in USD'),
  percentage: z
    .number()
    .describe('Percentage of total AR in this bucket'),
});

const CollectibilityFlagSchema = z.object({
  id: z.string(),
  severity: severityEnum,
  customerId: z.string().optional(),
  customerName: z.string().optional(),
  amount: z.number().describe('Amount at risk in USD'),
  daysPastDue: z.number().int(),
  description: z.string(),
});

export const ARCollectionsOutputSchema = z
  .object({
    totalAR: z.number().describe('Total accounts receivable in USD'),
    agingBuckets: z.array(AgingBucketSchema),
    dso: z.number().describe('Days sales outstanding'),
    dsoIndustryBenchmark: z
      .number()
      .optional()
      .describe('Industry benchmark DSO for comparison'),
    concentrationRisk: z.object({
      topCustomerPercent: z
        .number()
        .describe('Percentage of AR from the largest customer'),
      top5CustomersPercent: z
        .number()
        .describe('Percentage of AR from top 5 customers'),
    }),
    collectibilityFlags: z.array(CollectibilityFlagSchema),
    writeOffRisk: z.object({
      amount: z
        .number()
        .describe('Estimated uncollectable amount in USD'),
      percentOfTotalAR: z.number(),
    }),
    overallScore: z
      .number()
      .int()
      .min(1)
      .max(10)
      .describe('AR quality score, 1 (worst) to 10 (best)'),
    confidence: z.number().min(0).max(1),
    summary: z
      .string()
      .describe('Plain-language AR and collections summary'),
  })
  .describe(
    'AR & Collections agent output — accounts receivable aging, DSO, concentration, and collectibility analysis'
  );

export type ARCollectionsOutput = z.infer<typeof ARCollectionsOutputSchema>;
