import { z } from 'zod';

const severityEnum = z.enum(['low', 'medium', 'high', 'critical']);
const trendEnum = z.enum(['growing', 'stable', 'declining']);
const impactEnum = z.enum(['positive', 'neutral', 'negative']);
const densityEnum = z.enum(['low', 'medium', 'high']);
const timeframeEnum = z.enum(['near-term', 'medium-term', 'long-term']);

const MacroFactorSchema = z.object({
  factor: z.string(),
  impact: impactEnum,
  description: z.string(),
});

const ThreatSchema = z.object({
  id: z.string(),
  severity: severityEnum,
  title: z.string(),
  description: z.string(),
  timeframe: timeframeEnum,
});

const OpportunitySchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  timeframe: timeframeEnum,
});

export const MarketMacroOutputSchema = z
  .object({
    industryOverview: z.object({
      name: z.string(),
      sizeEstimate: z
        .string()
        .optional()
        .describe('Estimated market size (e.g. "$50B")'),
      growthRate: z
        .number()
        .optional()
        .describe('Annual industry growth rate as decimal'),
      trend: trendEnum,
      keyDrivers: z.array(z.string()),
    }),
    localMarket: z.object({
      area: z.string(),
      populationTrend: z.string().optional(),
      competitorDensity: densityEnum,
      demandOutlook: z.string(),
    }),
    macroFactors: z.array(MacroFactorSchema),
    threats: z.array(ThreatSchema),
    opportunities: z.array(OpportunitySchema),
    overallScore: z
      .number()
      .int()
      .min(1)
      .max(10)
      .describe(
        'Market and macro score, 1 (hostile environment) to 10 (highly favorable)'
      ),
    confidence: z.number().min(0).max(1),
    summary: z
      .string()
      .describe('Plain-language market and macro environment summary'),
  })
  .describe(
    'Market & Macro agent output — industry trends, local market conditions, macroeconomic factors, threats, and opportunities'
  );

export type MarketMacroOutput = z.infer<typeof MarketMacroOutputSchema>;
