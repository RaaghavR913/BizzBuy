# Monte Carlo Simulation: Implementation Guide for BizzBuy

## Overview

A Monte Carlo simulation will replace (or augment) the current `generateScenarios()` function in `lib/calculations.ts`, which today only runs four hard-coded growth scenarios. Instead, we run thousands of randomized trials across uncertain inputs and produce a probabilistic picture of cash flow, DSCR, and deal viability.

This doc covers:

1. What we are simulating and why
2. Which inputs get randomized and how
3. The algorithm and implementation plan
4. Where it fits in the current architecture
5. Concrete issues in the existing codebase that must be fixed first
6. Output shape and how it maps to the existing `ReportOutput` type

---

## 1. What We Are Simulating

The current scenario analysis answers: "what happens if revenue grows 0%, 10%, or -10%?" That is deterministic and incomplete. It ignores the fact that multiple variables are uncertain at the same time.

Monte Carlo answers: "across 10,000 random futures, what is the probability that this deal stays cash-flow positive, covers its debt service, and delivers a return to the buyer?"

Outputs a buyer actually cares about:

- P(DSCR >= 1.25) -- probability the deal is SBA-bankable
- P(DSCR >= 1.0) -- probability the deal does not blow up
- Median, 10th percentile, 90th percentile remaining cash flow
- Probability of a shortfall in any given year
- Distribution of 5-year cumulative owner income

---

## 2. Which Inputs Get Randomized

Each input is modeled as a probability distribution. The parameters for each distribution are derived from existing data in `SharedContext` and `QuestionnaireData`.

### Revenue Growth Rate (per year)

```
Distribution: Normal
Mean: derived from revenueByYear trend (if available), else 0%
Std Dev: 8% baseline, scaled up if:
  - revenueTrend === 'declining'    -> +5% std dev
  - revenueTrend === 'flat'         -> +2% std dev
  - customerConcentration is high   -> +4% std dev
  - recurringRevenuePercent < 30%   -> +3% std dev
Clamp: floor at -40%, ceiling at +50%
```

### Operating Expense Ratio (OpEx / Revenue)

```
Distribution: Normal
Mean: current operatingExpenses / revenue
Std Dev: 3% baseline, scaled up if:
  - no SOPs (hasSOPs === false)     -> +2%
  - single critical supplier        -> +2%
```

### SDE Add-Back Recapture Risk

The seller's stated add-backs may not all be legitimate. We discount them probabilistically.

```
Distribution: Uniform
Range: [0%, 30%] reduction applied to addBackTotal if addBacksExceed30Pct === true
Range: [0%, 10%] reduction if hasAddBacks === true but not flagged as excessive
```

### Customer Attrition (one-time revenue shock)

If customer concentration is high, there is a probability of a sudden revenue drop in any given year.

```
Modeled as: Bernoulli trial each year
P(attrition event) per year:
  topCustomerRevenuePercent > 50%   -> 12% per year
  topCustomerRevenuePercent > 30%   -> 7% per year
  else                              -> 3% per year
If event fires: revenue reduced by topCustomerRevenuePercent * 0.85 that year
```

### Interest Rate Drift (if variable rate loan)

```
Distribution: Normal
Mean: current interestRate
Std Dev: 0.5% per year
Only applies if loanType !== 'fixed' (most SBA 7a loans are variable)
Clamp: floor at current rate - 1%, ceiling at current rate + 3%
```

---

## 3. The Algorithm

```
INPUTS:
  baseRevenue, validatedSDE, annualDebtService, operatingExpenses,
  addBackTotal, loanTerms, questionnaire, N (number of trials = 10,000)

FOR each trial i in 1..N:
  
  adjustedSDE_i = validatedSDE - sampleAddBackReduction()
  
  FOR each year y in 1..5:
    growthRate_y     = sampleNormal(mu_growth, sigma_growth)
    opexRatio_y      = sampleNormal(mu_opex, sigma_opex)
    attritionFired_y = sampleBernoulli(p_attrition)
    rateAdj_y        = sampleNormal(0, 0.005) * y  -- cumulative drift

    revenue_y = baseRevenue * product(1 + growthRate_1..y)
    if attritionFired_y: revenue_y *= (1 - topCustomerPct * 0.85)

    opex_y         = revenue_y * opexRatio_y
    debtService_y  = recalcPayment(loanAmount, interestRate + rateAdj_y, remainingMonths_y)
    cashFlow_y     = adjustedSDE_i - opex_y - debtService_y + (adjustedSDE_i portion already net of opex)
    dscr_y         = (revenue_y - opex_y) / debtService_y
  
  Record per trial:
    - DSCR array across 5 years
    - min DSCR across 5 years
    - cumulative owner income across 5 years
    - whether any year had DSCR < 1.0

AGGREGATE across all N trials:
  - P(minDSCR >= 1.25)
  - P(minDSCR >= 1.0)
  - Percentiles [p10, p25, p50, p75, p90] for:
      - Year 1 DSCR
      - Year 3 DSCR
      - Cumulative 5yr owner income
  - Mean and std dev of remaining cash flow in year 1
  - Distribution histogram data (20 buckets) for charting
```

### Sampling Helpers

```typescript
function sampleNormal(mean: number, stdDev: number): number {
  // Box-Muller transform -- no external dependency needed
  const u1 = Math.random();
  const u2 = Math.random();
  const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  return mean + stdDev * z;
}

function sampleBernoulli(p: number): boolean {
  return Math.random() < p;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
```

No external libraries needed. Box-Muller gives us normally distributed samples from two uniform random draws.

---

## 4. Where This Fits in the Architecture

### Current flow (relevant section)

```
analyze/route.ts
  -> computeFinancialMetrics()         (lib/calculations.ts)
      -> generateScenarios()           <-- replaces this
  -> builds ReportOutput.debtServiceAnalysis.scenarios
```

### Proposed flow

```
analyze/route.ts
  -> computeFinancialMetrics()
  -> runMonteCarloSimulation()         (new: lib/monte-carlo.ts)
      returns MonteCarloResult
  -> builds ReportOutput.debtServiceAnalysis.scenarios  (keep as-is for table display)
  -> builds ReportOutput.monteCarloAnalysis             (new field on ReportOutput)
```

The four hard-coded scenarios in `generateScenarios()` are still useful as a readable table. Monte Carlo is additive, not a replacement for the summary table.

---

## 5. Issues in the Existing Codebase

These are real problems that will either break the Monte Carlo implementation or produce misleading results if not fixed first.

### Issue 1: `generateScenarios()` uses revenue as a proxy for cash flow (CRITICAL)

**File:** `lib/calculations.ts`, line ~80

```typescript
const dscr = calculateDSCR(
  projectedRevenue - operatingExpenses,  // this is gross profit, not SDE
  annualDebtService
);
```

`projectedRevenue - operatingExpenses` is not SDE. SDE adds back owner salary, depreciation, and interest. The DSCR calculation here understates cash flow available for debt service for any business where the owner draws a salary, which is most of them.

**Fix before Monte Carlo:** The numerator for DSCR should be `validatedSDE` scaled by the growth factor, not `projectedRevenue - operatingExpenses`.

```typescript
// Correct DSCR numerator
const scaledSDE = baseSDE * (1 + rate);
const dscr = calculateDSCR(scaledSDE, annualDebtService);
```

### Issue 2: `operatingExpenses` double-counts owner salary in some paths

**File:** `analyze/route.ts`, `computeFinancialMetrics()`

When `sde` is computed via `calculateSDE()`, it adds back `ownerSalary`. But `operatingExpenses` pulled from the income statement likely already includes owner salary as a line item. If you then use `operatingExpenses` to compute DSCR in parallel with SDE, you are subtracting salary twice.

This will cause the Monte Carlo to simulate cash flows that are too pessimistic.

**Fix:** When computing OpEx for the simulation, use `operatingExpenses - ownerSalary` to get a normalized operating cost base, then model the buyer's owner compensation separately.

### Issue 3: No handling for `annualDebtService === 0` in scenario generation

**File:** `lib/calculations.ts`, `generateScenarios()`

If `annualDebtService` is 0 (all-cash deal or no loan data), `generateScenarios()` still runs and returns scenarios with DSCR of Infinity. The Monte Carlo needs an explicit check:

```typescript
if (annualDebtService <= 0) {
  return { skipped: true, reason: 'No debt service -- all-cash or missing loan terms' };
}
```

Otherwise you will get `NaN` propagation in percentile calculations.

### Issue 4: `validatedSDE` can be 0 when financial parsing fails

**File:** `lib/merge-context.ts`, `computeValidatedSDE()`

```typescript
const financialSDE =
  numericMetric(outputs.financial, 'sde') ??
  financialData.incomeStatement?.sde ??
  0;  // <-- falls back to 0
```

If both sources fail, SDE is 0. The Monte Carlo will simulate 10,000 trials all showing negative cash flow, producing a misleading "100% chance of failure" result for a business that just had incomplete document parsing.

**Fix:** Before running Monte Carlo, check `dataCompleteness` and surface a warning if SDE is 0 or below a confidence threshold. Do not run the simulation if `dataCompleteness < 0.4`.

### Issue 5: Add-back reduction sampling needs a ceiling based on addBackTotal

If `addBackTotal` is large relative to SDE, the reduction sampling can push adjusted SDE below zero or even negative. A negative SDE going into 10,000 trials will make the entire distribution nonsensical.

**Fix:**

```typescript
const maxReduction = Math.min(addBackReduction, validatedSDE * 0.5);
// Never reduce SDE by more than 50% via add-back haircut alone
```

### Issue 6: `revenueByYear` is `Record<string, number>` but year ordering is lexicographic

**File:** `lib/types.ts`

When computing trend from `revenueByYear`, the code in `risk-scoring.ts` does:

```typescript
const years = Object.keys(is.revenueByYear).sort();
```

`Object.keys().sort()` sorts lexicographically, which works for "2021", "2022", "2023" but breaks for any non-standard format ("FY2022", "Year 1", etc.). The Monte Carlo growth rate baseline will be wrong if the trend is computed from mis-sorted years.

**Fix:** Normalize year keys during document ingestion, or sort by parsed integer:

```typescript
const years = Object.keys(is.revenueByYear).sort((a, b) => parseInt(a) - parseInt(b));
```

---

## 6. Output Type

Add this to `lib/types.ts`:

```typescript
export interface MonteCarloResult {
  trialsRun: number;
  probDSCRAbove125: number;       // 0.0 to 1.0
  probDSCRAbove100: number;       // 0.0 to 1.0
  probAnyYearShortfall: number;   // 0.0 to 1.0

  year1DSCR: {
    p10: number;
    p25: number;
    p50: number;
    p75: number;
    p90: number;
  };

  year3DSCR: {
    p10: number;
    p25: number;
    p50: number;
    p75: number;
    p90: number;
  };

  cumulativeOwnerIncome5yr: {
    p10: number;
    p25: number;
    p50: number;
    p75: number;
    p90: number;
  };

  cashFlowYear1: {
    mean: number;
    stdDev: number;
    histogram: { bucket: string; count: number }[];  // 20 buckets for charting
  };

  assumptionsUsed: {
    revenueGrowthMean: number;
    revenueGrowthStdDev: number;
    opexRatioMean: number;
    opexRatioStdDev: number;
    attritionProbPerYear: number;
    addBackReductionRange: [number, number];
  };

  skipped: boolean;
  skipReason?: string;
}
```

Add `monteCarloAnalysis: MonteCarloResult` to `ReportOutput` in `lib/types.ts`.

---

## 7. File Structure

```
lib/
  monte-carlo.ts        <-- new file, core simulation logic
  calculations.ts       <-- fix Issues 1, 2, 3
  types.ts              <-- add MonteCarloResult, update ReportOutput
  merge-context.ts      <-- fix Issue 4

app/api/analyze/route.ts   <-- call runMonteCarloSimulation(), add to report
components/report/         <-- new MonteCarloPanel component for visualization
```

---

## 8. Performance Note

10,000 trials x 5 years is 50,000 iterations. In JavaScript this runs in roughly 50-150ms depending on the machine. This is fine for a server-side API route. Do not run this client-side.

If the team moves toward edge functions or Vercel's 10s timeout is a concern, reducing to 5,000 trials is acceptable. The percentile estimates stabilize well before 10,000 trials for the variance levels we are dealing with.

---

## 9. Implementation Order

1. Fix Issues 1 and 2 in `calculations.ts` first. Running the existing scenarios with incorrect DSCR will produce wrong baselines for the simulation.
2. Fix Issue 4 in `merge-context.ts` to guard against SDE = 0.
3. Fix Issue 6 in the ingestion layer (year sort).
4. Create `lib/monte-carlo.ts` with `runMonteCarloSimulation()`.
5. Update `lib/types.ts` with `MonteCarloResult`.
6. Wire into `app/api/analyze/route.ts`.
7. Build `components/report/MonteCarloPanel.tsx` to visualize the histogram and probability outputs.

---

## 10. Plain-Language Output for the Report

The simulation result should be surfaced to the buyer in plain English, not just percentile tables. Example:

> Based on 10,000 simulated futures, this deal has a **72% chance of maintaining a DSCR above 1.25** over the first three years. In the worst 10% of scenarios, the business generates a cumulative owner income of only $48,000 over five years. The largest driver of downside risk in this simulation is customer concentration -- a single attrition event drops year-one DSCR to 0.87 in roughly 1 in 8 trials.

This narrative should be generated by passing `MonteCarloResult` into the synthesis agent prompt, not hard-coded.
