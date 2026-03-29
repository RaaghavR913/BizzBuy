import type { ScenarioAnalysis } from './types';

export function calculateMonthlyPayment(
  principal: number,
  annualRate: number,
  termMonths: number
): number {
  const monthlyRate = annualRate / 12;
  if (monthlyRate === 0) return principal / termMonths;
  return (
    (principal * (monthlyRate * Math.pow(1 + monthlyRate, termMonths))) /
    (Math.pow(1 + monthlyRate, termMonths) - 1)
  );
}

export function calculateDSCR(
  annualCashFlow: number,
  annualDebtService: number
): number {
  if (annualDebtService === 0) return Infinity;
  return annualCashFlow / annualDebtService;
}

export function calculateWorkingCapital(
  currentAssets: number,
  currentLiabilities: number
): number {
  return currentAssets - currentLiabilities;
}

export function calculateGrossMargin(revenue: number, cogs: number): number {
  if (revenue === 0) return 0;
  return ((revenue - cogs) / revenue) * 100;
}

export function calculateEBITDA(
  netIncome: number,
  interestExpense: number = 0,
  taxes: number = 0,
  depreciation: number = 0,
  amortization: number = 0
): number {
  return netIncome + interestExpense + taxes + depreciation + amortization;
}

export function calculateSDE(
  netIncome: number,
  ownerSalary: number = 0,
  addBacks: number = 0,
  depreciation: number = 0,
  interestExpense: number = 0
): number {
  return netIncome + ownerSalary + addBacks + depreciation + interestExpense;
}

export function calculateValuationMultiple(
  askingPrice: number,
  sde: number
): number {
  if (sde === 0) return Infinity;
  return askingPrice / sde;
}

export function calculateMinimumRevenue(
  annualDebtService: number,
  operatingExpenses: number,
  desiredOwnerIncome: number = 0
): number {
  return annualDebtService + operatingExpenses + desiredOwnerIncome;
}

export function calculateBreakEvenMonthlyRevenue(
  monthlyDebtService: number,
  monthlyOperatingExpenses: number
): number {
  return monthlyDebtService + monthlyOperatingExpenses;
}

export function generateScenarios(
  baseRevenue: number,
  annualDebtService: number,
  operatingExpenses: number,
  termMonths: number
): ScenarioAnalysis[] {
  const growthRates = [
    { label: 'Current Performance (0% growth)', rate: 0 },
    { label: 'Moderate Growth (+10%)', rate: 0.1 },
    { label: 'Decline (-10%)', rate: -0.1 },
    { label: 'Strong Growth (+20%)', rate: 0.2 },
  ];

  return growthRates.map(({ label, rate }) => {
    const projectedRevenue = baseRevenue * (1 + rate);
    const remainingCashFlow =
      projectedRevenue - operatingExpenses - annualDebtService;
    const dscr = calculateDSCR(
      projectedRevenue - operatingExpenses,
      annualDebtService
    );
    return {
      label,
      annualRevenue: Math.round(projectedRevenue),
      annualDebtService: Math.round(annualDebtService),
      remainingCashFlow: Math.round(remainingCashFlow),
      dscr: Math.round(dscr * 100) / 100,
      payoffMonths: termMonths,
      annualOwnerIncome: Math.round(Math.max(0, remainingCashFlow)),
    };
  });
}

export function assessDSCR(dscr: number): string {
  if (dscr === Infinity) return 'No debt — business is fully cash-flow positive.';
  if (dscr >= 2.0) return 'Excellent — the business generates more than twice the cash needed to service the debt.';
  if (dscr >= 1.5) return 'Strong — the business comfortably covers its debt obligations with meaningful cushion.';
  if (dscr >= 1.25) return 'Adequate — the business meets SBA minimum standards, but has limited cushion for downturns.';
  if (dscr >= 1.0) return 'Marginal — the business barely covers its debt service. Any revenue dip creates a shortfall.';
  return 'Critical — the business does not generate enough cash to service its debt at current performance.';
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function assessValuationMultiple(multiple: number, _businessType: string): string {
  if (multiple === Infinity) return 'Unable to assess — SDE is zero or unknown.';
  if (multiple <= 2.0) return 'Attractive multiple — below typical market range, may indicate upside or hidden risk.';
  if (multiple <= 3.5) return 'Market multiple — within the typical 2–3.5x SDE range for small businesses.';
  if (multiple <= 4.5) return 'Premium multiple — above average, justified only if recurring revenue or strong growth.';
  return 'Very high multiple — exceeds 4.5x SDE, warrants close scrutiny of growth assumptions.';
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatPercent(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`;
}

export function formatMultiple(value: number): string {
  if (value === Infinity) return '∞';
  return `${value.toFixed(2)}x`;
}
