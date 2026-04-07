import type { AgentResult } from '@/src/types/pipeline';
import type { IngestionOutput } from '@/src/agents/schemas/ingestion.schema';
import type { FinancialAnalysisOutput } from '@/src/agents/schemas/financial-analysis.schema';
import {
  LendingAffordabilityOutputSchema,
  type LendingAffordabilityOutput,
} from '@/src/agents/schemas/lending-affordability.schema';
import { callAgent } from '../utils/claude-client';
import { loadAgentPrompt } from '../utils/prompt-loader';
import { AGENT_REGISTRY } from '../registry';

// ---------------------------------------------------------------------------
// SBA 7(a) constants — update this single object when rates change
// ---------------------------------------------------------------------------
export const SBA_DEFAULTS = {
  MAX_LOAN: 5_000_000,
  INTEREST_RATE: 0.105, // 10.5% = Prime (7.75%) + 2.75%
  TERM_YEARS: 10,
  MIN_DSCR: 1.25,
  MIN_DOWN_PAYMENT_PERCENT: 0.10,
  CLOSING_COST_PERCENT: 0.035,
  GUARANTEE_FEE_PERCENT: 0.03,
  DOWN_PAYMENT_SCENARIOS: [0.10, 0.15, 0.20] as const,
  // SDE multiple range used for suggested price range
  SUGGESTED_MULTIPLE_LOW: 2.5,
  SUGGESTED_MULTIPLE_HIGH: 3.5,
} as const;

// ---------------------------------------------------------------------------
// Amortization math
// ---------------------------------------------------------------------------

/**
 * Standard amortization formula: M = P[r(1+r)^n] / [(1+r)^n - 1]
 * where P = principal, r = monthly rate, n = total months.
 * Returns 0 if rate is 0 (interest-free edge case).
 */
function monthlyPayment(principal: number, annualRate: number, termYears: number): number {
  if (principal <= 0) return 0;
  const r = annualRate / 12;
  const n = termYears * 12;
  if (r === 0) return principal / n;
  return (principal * r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);
}

// ---------------------------------------------------------------------------
// Core lending computation — pure function, no side effects
// ---------------------------------------------------------------------------

export interface SBALendingComputation {
  loanAmount: number;
  monthlyPayment: number;
  annualDebtService: number;
  dscr: number;
  dscrMeetsMinimum: boolean;
  downPaymentScenarios: {
    percent: number;
    amount: number;
    loanAmount: number;
    monthlyPayment: number;
    dscr: number;
  }[];
  maxSupportableLoan: number;
  sdeMultiple: number;
  totalCashNeeded: {
    downPayment: number;
    closingCosts: number;
    workingCapital: number;
    total: number;
  };
  suggestedPriceRange: { low: number; high: number };
}

export function computeSBALending(
  sde: number,
  askingPrice: number,
  interestRate: number = SBA_DEFAULTS.INTEREST_RATE,
  termYears: number = SBA_DEFAULTS.TERM_YEARS
): SBALendingComputation {
  const defaultDownPct = 0.20; // conservative 20% for base case
  const loanAmount = Math.min(askingPrice * (1 - defaultDownPct), SBA_DEFAULTS.MAX_LOAN);
  const payment = monthlyPayment(loanAmount, interestRate, termYears);
  const annualDebtService = payment * 12;
  const dscr = annualDebtService > 0 ? sde / annualDebtService : 0;

  // Per-scenario analysis across down payment options
  const downPaymentScenarios = SBA_DEFAULTS.DOWN_PAYMENT_SCENARIOS.map((pct) => {
    const dp = askingPrice * pct;
    const loan = Math.min(askingPrice - dp, SBA_DEFAULTS.MAX_LOAN);
    const pmt = monthlyPayment(loan, interestRate, termYears);
    const ads = pmt * 12;
    return {
      percent: pct,
      amount: Math.round(dp),
      loanAmount: Math.round(loan),
      monthlyPayment: Math.round(pmt),
      dscr: ads > 0 ? Math.round((sde / ads) * 100) / 100 : 0,
    };
  });

  // Maximum supportable loan: iterate to find max loan where DSCR >= 1.25
  // Binary search between 0 and MAX_LOAN
  let lo = 0;
  let hi = SBA_DEFAULTS.MAX_LOAN;
  for (let i = 0; i < 50; i++) {
    const mid = (lo + hi) / 2;
    const pmt = monthlyPayment(mid, interestRate, termYears);
    const ads = pmt * 12;
    const candidateDscr = ads > 0 ? sde / ads : 0;
    if (candidateDscr >= SBA_DEFAULTS.MIN_DSCR) {
      lo = mid;
    } else {
      hi = mid;
    }
  }
  const maxSupportableLoan = Math.round(lo);

  // Closing costs on the loan amount (not the full purchase price)
  const closingCosts = Math.round(loanAmount * SBA_DEFAULTS.CLOSING_COST_PERCENT);
  // Working capital reserve: 3 months of estimated operating expenses.
  // Estimate as 10% of annual revenue if unavailable; fall back to 10% of SDE.
  // Since we only have SDE here, use 3× monthly SDE as a proxy.
  const workingCapital = Math.round((sde / 12) * 3);
  const downPaymentAmount = Math.round(askingPrice * defaultDownPct);

  const totalCashNeeded = {
    downPayment: downPaymentAmount,
    closingCosts,
    workingCapital,
    total: downPaymentAmount + closingCosts + workingCapital,
  };

  const sdeMultiple = sde > 0 ? Math.round((askingPrice / sde) * 100) / 100 : 0;

  const suggestedPriceRange = {
    low: Math.round(sde * SBA_DEFAULTS.SUGGESTED_MULTIPLE_LOW),
    high: Math.round(sde * SBA_DEFAULTS.SUGGESTED_MULTIPLE_HIGH),
  };

  return {
    loanAmount: Math.round(loanAmount),
    monthlyPayment: Math.round(payment),
    annualDebtService: Math.round(annualDebtService),
    dscr: Math.round(dscr * 100) / 100,
    dscrMeetsMinimum: dscr >= SBA_DEFAULTS.MIN_DSCR,
    downPaymentScenarios,
    maxSupportableLoan,
    sdeMultiple,
    totalCashNeeded,
    suggestedPriceRange,
  };
}

// ---------------------------------------------------------------------------
// Scenario analysis when asking price is unknown
// ---------------------------------------------------------------------------

interface PriceScenario {
  multiple: number;
  askingPrice: number;
  computation: SBALendingComputation;
}

function computeScenarios(sde: number): PriceScenario[] {
  return [2.5, 3.0, 3.5].map((multiple) => ({
    multiple,
    askingPrice: Math.round(sde * multiple),
    computation: computeSBALending(sde, sde * multiple),
  }));
}

// ---------------------------------------------------------------------------
// User message builder
// ---------------------------------------------------------------------------

function buildUserMessage(
  ingestionOutput: IngestionOutput,
  financialAnalysisOutput: FinancialAnalysisOutput,
  askingPrice: number | undefined
): string {
  const sde = financialAnalysisOutput.profitability.sde;
  const addBacks = financialAnalysisOutput.profitability.sdeAddBacks
    .map((a) => `  - ${a.description}: $${a.amount.toLocaleString()} (${a.justification})`)
    .join('\n');

  const financialSummary = `
## Financial Analysis Summary (from upstream agent)
- **Validated SDE:** $${sde.toLocaleString()}
- **EBITDA:** $${financialAnalysisOutput.profitability.ebitda.toLocaleString()}
- **Adjusted EBITDA:** $${financialAnalysisOutput.profitability.adjustedEbitda.toLocaleString()}
- **Gross Margin:** ${(financialAnalysisOutput.profitability.grossMargin * 100).toFixed(1)}%
- **Net Margin:** ${(financialAnalysisOutput.profitability.netMargin * 100).toFixed(1)}%
- **Revenue Trend:** ${financialAnalysisOutput.revenueAnalysis.trend} (${(financialAnalysisOutput.revenueAnalysis.growthRate * 100).toFixed(1)}% YoY)
- **Financial Health Score:** ${financialAnalysisOutput.overallScore}/10
- **Financial Analysis Confidence:** ${financialAnalysisOutput.confidence}
- **SDE Add-Backs:**
${addBacks || '  (none)'}

## SBA 7(a) Constants Used
- Interest Rate: ${(SBA_DEFAULTS.INTEREST_RATE * 100).toFixed(2)}% (Prime 7.75% + 2.75%)
- Term: ${SBA_DEFAULTS.TERM_YEARS} years
- Minimum DSCR: ${SBA_DEFAULTS.MIN_DSCR}x
- Closing Cost Estimate: ${(SBA_DEFAULTS.CLOSING_COST_PERCENT * 100).toFixed(1)}% of loan
`.trim();

  let lendingSection: string;

  if (askingPrice !== undefined && askingPrice > 0) {
    const calc = computeSBALending(sde, askingPrice);
    const scenarioRows = calc.downPaymentScenarios
      .map(
        (s) =>
          `  - ${(s.percent * 100).toFixed(0)}% down ($${s.amount.toLocaleString()}): ` +
          `loan $${s.loanAmount.toLocaleString()}, ` +
          `monthly $${s.monthlyPayment.toLocaleString()}, ` +
          `DSCR ${s.dscr.toFixed(2)}x`
      )
      .join('\n');

    lendingSection = `
## Pre-Computed Lending Figures (DO NOT RECALCULATE — use these numbers)

**Asking Price:** $${askingPrice.toLocaleString()}
**SDE:** $${sde.toLocaleString()}
**SDE Multiple:** ${calc.sdeMultiple.toFixed(2)}x

**Base Case (20% down):**
- Loan Amount: $${calc.loanAmount.toLocaleString()}
- Monthly Payment: $${calc.monthlyPayment.toLocaleString()}
- Annual Debt Service: $${calc.annualDebtService.toLocaleString()}
- DSCR: ${calc.dscr.toFixed(2)}x (minimum required: ${SBA_DEFAULTS.MIN_DSCR}x)
- DSCR Meets Minimum: ${calc.dscrMeetsMinimum ? 'YES' : 'NO'}

**Down Payment Scenarios:**
${scenarioRows}

**Maximum Supportable Loan (DSCR ≥ 1.25):** $${calc.maxSupportableLoan.toLocaleString()}

**Total Cash Needed (20% down):**
- Down Payment: $${calc.totalCashNeeded.downPayment.toLocaleString()}
- Closing Costs (~3.5% of loan): $${calc.totalCashNeeded.closingCosts.toLocaleString()}
- Working Capital Reserve (3 months): $${calc.totalCashNeeded.workingCapital.toLocaleString()}
- **TOTAL: $${calc.totalCashNeeded.total.toLocaleString()}**

**Suggested Price Range:** $${calc.suggestedPriceRange.low.toLocaleString()} – $${calc.suggestedPriceRange.high.toLocaleString()} (${SBA_DEFAULTS.SUGGESTED_MULTIPLE_LOW}–${SBA_DEFAULTS.SUGGESTED_MULTIPLE_HIGH}× SDE)
`.trim();
  } else {
    const scenarios = computeScenarios(sde);
    const scenarioText = scenarios
      .map((s) => {
        const c = s.computation;
        return (
          `**${s.multiple}× SDE = $${s.askingPrice.toLocaleString()} asking price:**\n` +
          `  Monthly payment: $${c.monthlyPayment.toLocaleString()}, ` +
          `DSCR: ${c.dscr.toFixed(2)}x, ` +
          `Total cash needed: $${c.totalCashNeeded.total.toLocaleString()}, ` +
          `Bankable: ${c.dscrMeetsMinimum ? 'YES' : 'NO'}`
        );
      })
      .join('\n');

    lendingSection = `
## Pre-Computed Lending Figures — Scenario Analysis (Asking Price Unknown)
Note: No asking price was provided. Run analysis across these three common SDE multiples.

**SDE:** $${sde.toLocaleString()}

${scenarioText}

**Suggested Price Range:** $${Math.round(sde * SBA_DEFAULTS.SUGGESTED_MULTIPLE_LOW).toLocaleString()} – $${Math.round(sde * SBA_DEFAULTS.SUGGESTED_MULTIPLE_HIGH).toLocaleString()} (${SBA_DEFAULTS.SUGGESTED_MULTIPLE_LOW}–${SBA_DEFAULTS.SUGGESTED_MULTIPLE_HIGH}× SDE)
`.trim();
  }

  const documentList = ingestionOutput.documents
    .map((d) => `- ${d.fileName} (${d.documentType})`)
    .join('\n');

  return `Please assess whether this business acquisition is bankable and affordable for an SBA 7(a) buyer.

${financialSummary}

${lendingSection}

## Source Documents
${documentList}

## Your Task
Using ONLY the pre-computed figures above (do not recalculate), interpret:
1. Is this deal bankable? Cite the specific DSCR and what it means for a lender.
2. Is the price reasonable? Cite the SDE multiple and compare to market benchmarks.
3. What deal structure do you recommend? (SBA-only, seller note, earnout, price reduction?)
4. What is the minimum cash a buyer needs to have liquid before approaching a lender?
5. What are the key lending risks? (DSCR sensitivity, interest rate risk, down payment size)

Then call the structured_output tool with your complete LendingAffordabilityOutput.`;
}

// ---------------------------------------------------------------------------
// Main runner
// ---------------------------------------------------------------------------

/**
 * Lending & Affordability agent runner.
 *
 * UNIQUE: This agent depends on FinancialAnalysisOutput from Phase 2.
 * It runs in Phase 3 (after financial-analysis completes) and reads
 * financialAnalysisOutput.profitability.sde as its primary input.
 *
 * All lending math is computed in TypeScript before calling the LLM.
 * The LLM only interprets the numbers and writes the buyer-facing narrative.
 */
export async function runLendingAffordability(
  ingestionOutput: IngestionOutput,
  financialAnalysisOutput: FinancialAnalysisOutput,
  askingPrice?: number
): Promise<AgentResult<LendingAffordabilityOutput>> {
  const config = AGENT_REGISTRY['lending-affordability'];

  const sde = financialAnalysisOutput?.profitability?.sde;
  if (!sde || sde <= 0) {
    return {
      status: 'error',
      error: {
        agentName: config.name,
        errorType: 'validation',
        message:
          'Lending analysis could not be completed: Financial Analysis did not produce a valid SDE figure. ' +
          'Ensure the financial-analysis agent ran successfully before running lending-affordability.',
        timestamp: new Date().toISOString(),
        retryCount: 0,
      },
    };
  }

  const systemPrompt = loadAgentPrompt(config.promptFile);
  const userMessage = buildUserMessage(ingestionOutput, financialAnalysisOutput, askingPrice);

  return callAgent<LendingAffordabilityOutput>({
    model: config.model,
    systemPrompt,
    userMessage,
    schema: LendingAffordabilityOutputSchema,
    maxTokens: config.maxTokens ?? 4096,
    temperature: 0,
  });
}
