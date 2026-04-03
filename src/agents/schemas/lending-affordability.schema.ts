import { z } from 'zod';

const severityEnum = z.enum(['low', 'medium', 'high', 'critical']);

const LendingRiskSchema = z.object({
  id: z.string(),
  severity: severityEnum,
  title: z.string(),
  description: z.string(),
  recommendation: z.string(),
});

export const LendingAffordabilityOutputSchema = z
  .object({
    sba7a: z.object({
      eligibleForSBA: z.boolean(),
      maxLoanAmount: z.number().describe('Maximum SBA 7(a) loan amount in USD'),
      interestRate: z.number().describe('Estimated interest rate as decimal'),
      termYears: z.number().int(),
      monthlyPayment: z.number().describe('Estimated monthly payment in USD'),
      annualDebtService: z
        .number()
        .describe('Annual debt service in USD'),
      dscr: z.number().describe('Debt service coverage ratio'),
      dscrMeetsMinimum: z
        .boolean()
        .describe('True if DSCR >= 1.25 (SBA minimum)'),
      downPaymentRequired: z
        .number()
        .describe('Required down payment in USD'),
      downPaymentPercent: z.number().describe('Down payment as percentage'),
      totalProjectCost: z
        .number()
        .describe('Total project cost including fees in USD'),
    }),
    affordabilityAnalysis: z.object({
      askingPrice: z.number().describe('Listing asking price in USD'),
      adjustedSDE: z
        .number()
        .describe("Validated seller's discretionary earnings in USD"),
      sdeMultiple: z.number().describe('Asking price / adjusted SDE'),
      isReasonablyPriced: z.boolean(),
      suggestedPriceRange: z.object({
        low: z.number().describe('Low end of suggested price in USD'),
        high: z.number().describe('High end of suggested price in USD'),
      }),
    }),
    buyerRequirements: z.object({
      minimumDownPayment: z
        .number()
        .describe('Minimum down payment in USD'),
      estimatedClosingCosts: z
        .number()
        .describe('Estimated closing costs in USD'),
      totalCashNeeded: z
        .number()
        .describe('Total cash needed at closing in USD'),
      minimumPostCloseLiquidity: z
        .number()
        .describe('Recommended post-close liquidity in USD'),
    }),
    dealStructure: z.object({
      recommendedStructure: z.string(),
      sellerFinancingComponent: z
        .number()
        .optional()
        .describe('Seller financing portion in USD'),
      earnoutComponent: z
        .number()
        .optional()
        .describe('Earnout portion in USD'),
      rationale: z.string(),
    }),
    risks: z.array(LendingRiskSchema),
    overallScore: z
      .number()
      .int()
      .min(1)
      .max(10)
      .describe('Bankability score, 1 (unbankable) to 10 (highly bankable)'),
    confidence: z.number().min(0).max(1),
    summary: z
      .string()
      .describe('Plain-language lending and affordability summary'),
  })
  .describe(
    'Lending & Affordability agent output — SBA 7(a) eligibility, debt service, affordability, and deal structuring'
  );

export type LendingAffordabilityOutput = z.infer<
  typeof LendingAffordabilityOutputSchema
>;
