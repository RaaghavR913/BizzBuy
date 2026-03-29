import { formatCurrency, formatPercent, formatMultiple } from './calculations';

export function formatMetricValue(key: string, value: number): string {
  const currencyKeys = [
    'revenue', 'cogs', 'grossProfit', 'operatingExpenses', 'netIncome',
    'sde', 'ebitda', 'workingCapital', 'askingPrice', 'monthlyDebtService',
    'annualDebtService', 'minimumRevenue', 'breakEvenMonthly',
    'ownerSalary', 'loanAmount', 'downPayment',
  ];
  const percentKeys = [
    'grossMargin', 'netMargin', 'ebitdaMargin',
  ];
  const multipleKeys = ['valuationMultiple', 'dscr'];

  if (currencyKeys.some(k => key.toLowerCase().includes(k.toLowerCase()))) {
    return formatCurrency(value);
  }
  if (percentKeys.some(k => key.toLowerCase().includes(k.toLowerCase()))) {
    return formatPercent(value);
  }
  if (multipleKeys.some(k => key.toLowerCase().includes(k.toLowerCase()))) {
    return formatMultiple(value);
  }
  return value.toLocaleString();
}

export function formatDuration(months: number): string {
  if (months < 12) return `${months} months`;
  const years = Math.floor(months / 12);
  const rem = months % 12;
  if (rem === 0) return `${years} year${years > 1 ? 's' : ''}`;
  return `${years}y ${rem}m`;
}

export function getRiskColor(score: number): string {
  if (score <= 3) return '#10b981';
  if (score <= 5) return '#f59e0b';
  if (score <= 7) return '#f97316';
  return '#ef4444';
}

export function getOverallRiskColor(score: number): string {
  if (score <= 35) return '#10b981';
  if (score <= 65) return '#f59e0b';
  if (score <= 80) return '#f97316';
  return '#ef4444';
}

export function getTransferabilityColor(score: number): string {
  if (score >= 65) return '#10b981';
  if (score >= 40) return '#f59e0b';
  if (score >= 20) return '#f97316';
  return '#ef4444';
}

export function getRiskBgClass(score: number): string {
  if (score <= 35) return 'bg-emerald-50 border-emerald-200';
  if (score <= 65) return 'bg-yellow-50 border-yellow-200';
  if (score <= 80) return 'bg-orange-50 border-orange-200';
  return 'bg-red-50 border-red-200';
}

export function getRiskTextClass(score: number): string {
  if (score <= 35) return 'text-emerald-700';
  if (score <= 65) return 'text-yellow-700';
  if (score <= 80) return 'text-orange-700';
  return 'text-red-700';
}

export function getDimensionRiskBg(score: number): string {
  if (score <= 3) return 'bg-emerald-500';
  if (score <= 5) return 'bg-yellow-500';
  if (score <= 7) return 'bg-orange-500';
  return 'bg-red-500';
}
