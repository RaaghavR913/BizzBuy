import { z } from 'zod';

const severityEnum = z.enum(['low', 'medium', 'high', 'critical']);
const recommendationEnum = z.enum([
  'strong_buy',
  'buy',
  'conditional_buy',
  'caution',
  'do_not_buy',
]);

const agentSourceEnum = z.enum([
  'financial',
  'tax',
  'ar',
  'customer',
  'operations',
  'lease',
  'market',
  'lending',
]);

const RedFlagSchema = z.object({
  id: z.string(),
  severity: severityEnum,
  source: agentSourceEnum.describe('Which agent identified this flag'),
  title: z.string(),
  description: z.string(),
  financialImpact: z
    .number()
    .optional()
    .describe('Estimated financial impact in USD'),
});

const GreenFlagSchema = z.object({
  id: z.string(),
  source: agentSourceEnum,
  title: z.string(),
  description: z.string(),
});

const SectionSummarySchema = z.object({
  score: z.number().int().min(1).max(10),
  summary: z.string(),
  topRisks: z.array(z.string()),
});

const NextStepSchema = z.object({
  priority: z.number().int().min(1).max(5),
  action: z.string(),
  reason: z.string(),
});

export const SynthesisReportOutputSchema = z
  .object({
    executiveSummary: z
      .string()
      .describe(
        '3-5 sentence plain-language summary suitable for a first-time buyer'
      ),
    overallRiskScore: z
      .number()
      .int()
      .min(1)
      .max(100)
      .describe('Composite risk score, 1 (lowest risk) to 100 (highest risk)'),
    recommendation: recommendationEnum,
    redFlags: z.array(RedFlagSchema),
    greenFlags: z.array(GreenFlagSchema),
    sectionSummaries: z.object({
      financial: SectionSummarySchema,
      tax: SectionSummarySchema,
      ar: SectionSummarySchema,
      customer: SectionSummarySchema,
      operations: SectionSummarySchema,
      lease: SectionSummarySchema,
      market: SectionSummarySchema,
      lending: SectionSummarySchema,
    }),
    nextSteps: z.array(NextStepSchema),
    dealTermsSuggestion: z
      .string()
      .describe(
        'Suggested deal terms based on the analysis'
      ),
    confidence: z.number().min(0).max(1),
    dataCompleteness: z.object({
      availableAnalyses: z
        .array(z.string())
        .describe('Agent names that completed successfully'),
      failedAnalyses: z
        .array(z.string())
        .describe('Agent names that failed or were skipped'),
      overallCompleteness: z
        .number()
        .min(0)
        .max(1)
        .describe('Fraction of agents that completed successfully'),
    }),
  })
  .describe(
    'Synthesis Report agent output — final acquisition recommendation combining all upstream agent analyses'
  );

export type SynthesisReportOutput = z.infer<
  typeof SynthesisReportOutputSchema
>;
