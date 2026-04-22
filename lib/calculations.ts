
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

