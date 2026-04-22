import { ANALYSIS_VERSION, DISCLAIMERS } from './constants';
import { assessDSCR, assessValuationMultiple, formatCurrency, formatPercent } from './calculations';
import type {
  AgentFlag,
  AnyReportOutput,
  BuyerFacingDimension,
  FindingSeverity,
  NormalizedFinding,
  NormalizedMetric,
  ReportOutput,
  ReportOutputV2,
  RiskDimensionScore,
} from './types';

const DIMENSION_CATEGORY_MAP: Record<string, Set<string>> = {
  financial_quality: new Set(['earnings_quality', 'cash_flow', 'working_capital', 'tax_compliance', 'lending', 'missing_data']),
  revenue_durability: new Set(['receivables', 'customer_concentration', 'contract_durability', 'market_conditions', 'missing_data']),
  transferability: new Set(['owner_dependence', 'operational_transferability', 'lease_transferability', 'missing_data']),
  bankability: new Set(['lending', 'cash_flow', 'working_capital', 'missing_data']),
};

const DIMENSION_LABEL_OVERRIDES: Record<string, string> = {
  financial_quality: 'Financial Quality',
  revenue_durability: 'Revenue Durability',
  transferability: 'Transferability',
  bankability: 'Bankability',
};

const METRIC_LABELS: Record<string, string> = {
  asking_price: 'Asking Price',
  adjusted_sde: 'Validated SDE',
  sde_multiple: 'SDE Multiple',
  dscr: 'DSCR',
  working_capital: 'Working Capital',
  total_cash_needed: 'Cash Needed at Close',
  top_customer_revenue_pct: 'Top Customer Revenue',
  max_revenue_discrepancy_pct: 'Revenue Discrepancy',
  eligible_for_sba: 'SBA Eligibility',
};

const FINANCIAL_METRIC_KEYS = [
  'asking_price',
  'adjusted_sde',
  'sde_multiple',
  'dscr',
  'working_capital',
  'top_customer_revenue_pct',
  'max_revenue_discrepancy_pct',
  'eligible_for_sba',
] as const;

function clamp(value: number, lower: number, upper: number): number {
  return Math.max(lower, Math.min(upper, value));
}

export function isReportOutputV2(report: AnyReportOutput): report is ReportOutputV2 {
  return 'modeAvailable' in report && 'scorecard' in report;
}

function formatTitleCase(value: string): string {
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function metricNumber(metric?: NormalizedMetric | null): number | null {
  if (!metric) return null;
  const value = metric.value;
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function metricBoolean(metric?: NormalizedMetric | null): boolean | null {
  if (!metric) return null;
  return typeof metric.value === 'boolean' ? metric.value : null;
}

function formatMetricValue(metric: NormalizedMetric | undefined, key: string): string {
  if (!metric) return 'N/A';
  if (metric.displayValue) return metric.displayValue;

  const { value, unit } = metric;

  if (typeof value === 'number') {
    if (unit === 'usd' || key.includes('price') || key.includes('cash') || key.includes('sde') || key.includes('capital')) {
      return formatCurrency(value);
    }
    if (unit === 'ratio' || key === 'dscr' || key.endsWith('_multiple')) {
      return `${value.toFixed(2)}x`;
    }
    if (unit === 'x') {
      return `${value.toFixed(2)}x`;
    }
    if (key.endsWith('_pct') || key.includes('pct')) {
      return formatPercent(value, value < 10 ? 1 : 0);
    }
    return value.toLocaleString('en-US', { maximumFractionDigits: 2 });
  }

  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }

  if (typeof value === 'string') {
    return value;
  }

  return 'N/A';
}

function findingSeverityToFlagSeverity(severity: FindingSeverity): AgentFlag['severity'] {
  if (severity === 'critical') return 'critical';
  if (severity === 'high' || severity === 'medium') return 'warning';
  return 'info';
}

function overallRiskLabel(score: number): ReportOutput['executiveSummary']['riskLabel'] {
  if (score <= 35) return 'Low';
  if (score <= 65) return 'Moderate';
  if (score <= 80) return 'High';
  return 'Very High';
}

function transferabilityLabel(score: number): ReportOutput['executiveSummary']['transferabilityLabel'] {
  if (score >= 65) return 'High';
  if (score >= 40) return 'Moderate';
  if (score >= 20) return 'Low';
  return 'Very Low';
}

function bankabilityLabel(score: number): ReportOutput['sbaLoanSizing']['bankabilityLabel'] {
  if (score >= 75) return 'Strong';
  if (score >= 55) return 'Bankable';
  if (score >= 35) return 'Borderline';
  return 'Weak';
}

function legacyAction(recommendation?: string | null): ReportOutput['finalRecommendation']['action'] {
  switch (recommendation) {
    case 'strong_buy':
    case 'buy':
      return 'proceed';
    case 'conditional_buy':
    case 'caution':
      return 'proceed_with_caution';
    default:
      return 'walk_away';
  }
}

function recommendationVerdict(recommendation?: string | null): string {
  switch (recommendation) {
    case 'strong_buy':
      return 'The overall signal is strong, but the remaining diligence items should still be verified before closing.';
    case 'buy':
      return 'The deal looks workable based on the current evidence, assuming the remaining diligence confirms the same picture.';
    case 'conditional_buy':
      return 'The deal may work, but only if the seller can resolve the open diligence issues and support the reported economics.';
    case 'caution':
      return 'Proceed carefully. Material risks or evidence gaps still need to be resolved before this deal is dependable.';
    case 'do_not_buy':
    default:
      return 'The current evidence suggests the risks outweigh the upside unless several major issues are disproved.';
  }
}

function riskDimensionLabel(score: number): RiskDimensionScore['label'] {
  if (score <= 3) return 'Low';
  if (score <= 5) return 'Moderate';
  if (score <= 7) return 'High';
  return 'Critical';
}

function relatedFindings(findings: NormalizedFinding[], dimensionKey: string): NormalizedFinding[] {
  const categories = DIMENSION_CATEGORY_MAP[dimensionKey];
  if (!categories) return findings;
  return findings.filter((finding) => categories.has(finding.category));
}

function buildRiskDimensions(report: ReportOutputV2): RiskDimensionScore[] {
  const dimensions = report.scorecard.buyerFacingDimensions;
  if (!dimensions.length) {
    return [
      {
        dimension: 'Overall Diligence',
        score: 5,
        label: 'Moderate',
        explanation: report.summary.overview || 'No buyer-facing risk dimensions were returned by the pipeline.',
        keyFactors: report.summary.keyFindings.slice(0, 3).map((finding) => finding.title),
        isDealBreaker: report.scorecard.dealBreakers.length > 0,
      },
    ];
  }

  return dimensions.map((dimension) => {
    const rawScore = typeof dimension.score === 'number' ? dimension.score : 5;
    const riskScore = clamp(Math.round((11 - rawScore) * 10) / 10, 1, 10);
    const findings = relatedFindings(report.summary.keyFindings, dimension.key);

    return {
      dimension: dimension.label || DIMENSION_LABEL_OVERRIDES[dimension.key] || formatTitleCase(dimension.key),
      score: riskScore,
      label: riskDimensionLabel(riskScore),
      explanation: dimension.summary || `${dimension.label} was only partially supported by the current evidence.`,
      keyFactors: findings.slice(0, 3).map((finding) => finding.title),
      isDealBreaker: findings.some((finding) => finding.severity === 'critical'),
    };
  });
}

function findDimension(dimensions: BuyerFacingDimension[], key: string): BuyerFacingDimension | undefined {
  return dimensions.find((dimension) => dimension.key === key);
}

function buildQuestions(report: ReportOutputV2): ReportOutput['questionsForSeller'] {
  const recommended = report.summary.recommendedActions.slice(0, 5);
  const missingInputs = report.deepReview?.missingData ?? [];
  const findingQuestions = report.summary.keyFindings.slice(0, 3).map((finding) => `What evidence can the seller provide to address: ${finding.title}?`);

  return [
    {
      category: 'Priority follow-up',
      questions: recommended.length ? recommended.map((action) => `Can the seller address this next step: ${action}`) : findingQuestions,
    },
    {
      category: 'Missing support',
      questions: missingInputs.length
        ? missingInputs.slice(0, 5).map((item) => `Can the seller provide the missing support for ${item.description.toLowerCase()}?`)
        : findingQuestions,
    },
  ].filter((section) => section.questions.length > 0);
}

function buildChecklist(report: ReportOutputV2): ReportOutput['diligenceChecklist'] {
  const missingInputs = report.deepReview?.missingData ?? [];
  const fromMissingInputs = missingInputs.map((item) => ({
    item: item.description,
    category: item.documentType ? formatTitleCase(item.documentType) : 'Supporting evidence',
    priority: item.required ? ('critical' as const) : ('important' as const),
    reason: item.impactSummary || item.reason || 'This support is needed to validate the current summary report.',
  }));

  const fromActions = report.summary.recommendedActions
    .filter((action) => !fromMissingInputs.some((item) => item.item === action))
    .slice(0, 5)
    .map((action) => ({
      item: action,
      category: 'Recommended follow-up',
      priority: 'important' as const,
      reason: 'This action comes directly from the pipeline summary recommendation list.',
    }));

  const fromFindings = report.summary.keyFindings
    .filter((finding) => !fromMissingInputs.some((item) => item.item === finding.title))
    .slice(0, 3)
    .map((finding) => ({
      item: finding.title,
      category: formatTitleCase(finding.category),
      priority: finding.severity === 'critical' ? 'critical' as const : 'important' as const,
      reason: finding.description,
    }));

  return [...fromMissingInputs, ...fromActions, ...fromFindings];
}

function buildUpsideOpportunities(report: ReportOutputV2): ReportOutput['upsideOpportunities'] {
  const positiveDimensions = report.scorecard.buyerFacingDimensions.filter((dimension) => (dimension.score ?? 0) >= 7);
  const positiveScorecards = report.scorecard.technicalScorecards.filter((scorecard) => (scorecard.score ?? 0) >= 8);

  const opportunities = positiveDimensions.map((dimension) => ({
    opportunity: `Lean into ${dimension.label}`,
    estimatedImpact: `Current pipeline score: ${(dimension.score ?? 0).toFixed(1)}/10`,
    difficulty: 'moderate' as const,
    detail: dimension.summary || 'This area scored better than the rest of the diligence profile and may support the acquisition thesis.',
  }));

  for (const scorecard of positiveScorecards) {
    if (opportunities.length >= 4) break;
    opportunities.push({
      opportunity: `Preserve strength in ${scorecard.name}`,
      estimatedImpact: `Technical score: ${(scorecard.score ?? 0).toFixed(1)}/10`,
      difficulty: 'moderate',
      detail: scorecard.recommendation
        ? `Current recommendation: ${scorecard.recommendation.replace(/_/g, ' ')}.`
        : 'This specialist area scored well in the pipeline output.',
    });
  }

  if (!opportunities.length) {
    opportunities.push({
      opportunity: 'Resolve the top diligence blockers',
      estimatedImpact: 'Could materially improve lender and buyer confidence',
      difficulty: 'hard',
      detail: 'The current summary report emphasizes risk reduction before upside expansion.',
    });
  }

  return opportunities.slice(0, 4);
}

function buildFinancialSnapshot(report: ReportOutputV2): ReportOutput['financialSnapshot'] {
  const metrics = report.scorecard.validatedMetrics;
  const askingPrice = metricNumber(metrics.asking_price);
  const adjustedSde = metricNumber(metrics.adjusted_sde);
  const rawMultiple = metricNumber(metrics.sde_multiple);
  const valuationMultiple = rawMultiple ?? (askingPrice !== null && adjustedSde ? askingPrice / adjustedSde : Infinity);

  const financialMetrics: ReportOutput['financialSnapshot']['metrics'] = {};

  for (const key of FINANCIAL_METRIC_KEYS) {
    const metric = metrics[key];
    if (!metric) continue;
    const numericValue = metricNumber(metric);
    financialMetrics[METRIC_LABELS[key] || formatTitleCase(key)] = {
      value: numericValue ?? 0,
      formatted: formatMetricValue(metric, key),
      note: metric.confidence ? `${Math.round(metric.confidence * 100)}% confidence` : undefined,
    };
  }

  if (report.scorecard.completenessScore !== undefined) {
    financialMetrics['Completeness'] = {
      value: report.scorecard.completenessScore ?? 0,
      formatted: formatPercent((report.scorecard.completenessScore ?? 0) * 100, 0),
      note: 'Derived from completed agent coverage and missing required inputs.',
    };
  }

  if (report.scorecard.confidenceScore !== undefined) {
    financialMetrics['Confidence'] = {
      value: report.scorecard.confidenceScore ?? 0,
      formatted: formatPercent((report.scorecard.confidenceScore ?? 0) * 100, 0),
      note: 'Pipeline confidence after missing-data and conflict penalties.',
    };
  }

  return {
    metrics: financialMetrics,
    valuationMultiple,
    multipleAssessment: assessValuationMultiple(valuationMultiple, 'other'),
  };
}

function buildDebtService(report: ReportOutputV2): ReportOutput['debtServiceAnalysis'] {
  const metrics = report.scorecard.validatedMetrics;
  const dscr = metricNumber(metrics.dscr) ?? 0;
  const adjustedSde = metricNumber(metrics.adjusted_sde) ?? 0;
  const annualDebtService = dscr > 0 ? adjustedSde / dscr : 0;
  const monthlyDebtService = annualDebtService / 12;
  const bankability = findDimension(report.scorecard.buyerFacingDimensions, 'bankability');
  const askingPrice = metricNumber(metrics.asking_price) ?? 0;
  const totalCashNeeded = metricNumber(metrics.total_cash_needed) ?? askingPrice;

  return {
    loanSummary: {
      'Asking Price': askingPrice ? formatCurrency(askingPrice) : 'N/A',
      'Cash Needed': totalCashNeeded ? formatCurrency(totalCashNeeded) : 'N/A',
      'SBA Eligible': metricBoolean(metrics.eligible_for_sba) === null ? 'Unknown' : metricBoolean(metrics.eligible_for_sba) ? 'Yes' : 'No',
    },
    monthlyDebtService,
    annualDebtService,
    dscr,
    dscrAssessment: dscr ? assessDSCR(dscr) : 'Debt service inputs were not fully included in the summary contract.',
    minimumRevenueRequired: annualDebtService,
    breakEvenMonthlyRevenue: monthlyDebtService,
    scenarios: [],
    affordabilityVerdict: bankability?.summary || report.summary.overview || 'Bankability depends on completing the remaining diligence steps.',
  };
}

function buildAgentFlags(report: ReportOutputV2): AgentFlag[] {
  return report.summary.keyFindings.slice(0, 8).map((finding) => ({
    severity: findingSeverityToFlagSeverity(finding.severity),
    message: finding.description,
    dimension: formatTitleCase(finding.category),
    sourceAgent: 'backend',
  }));
}

export function normalizeReportOutput(report: AnyReportOutput): ReportOutput {
  if (!isReportOutputV2(report)) {
    return report;
  }

  const overallRiskScore = report.scorecard.overallRiskScore ?? 50;
  const riskLabel = overallRiskLabel(overallRiskScore);
  const transferability = findDimension(report.scorecard.buyerFacingDimensions, 'transferability');
  const transferabilityScore = clamp(Math.round((transferability?.score ?? 0) * 10), 0, 100);
  const transferLabel = transferabilityLabel(transferabilityScore);
  const action = legacyAction(report.scorecard.overallRecommendation);
  const keyFindings = report.summary.keyFindings;
  const debtService = buildDebtService(report);
  const bankabilityScore = clamp(Math.round((findDimension(report.scorecard.buyerFacingDimensions, 'bankability')?.score ?? 0) * 10), 0, 100);
  const riskDimensions = buildRiskDimensions(report);
  const strengths = report.scorecard.buyerFacingDimensions
    .filter((dimension) => (dimension.score ?? 0) >= 7)
    .map((dimension) => dimension.summary || `${dimension.label} scored well in the current pipeline run.`)
    .slice(0, 3);
  const risks = keyFindings.map((finding) => finding.title).slice(0, 4);

  return {
    executiveSummary: {
      text: [report.summary.headline, report.summary.overview].filter(Boolean).join(' '),
      riskScore: overallRiskScore,
      riskLabel,
      transferabilityScore,
      transferabilityLabel: transferLabel,
      verdict: recommendationVerdict(report.scorecard.overallRecommendation),
    },
    financialSnapshot: buildFinancialSnapshot(report),
    debtServiceAnalysis: debtService,
    riskAssessment: {
      overallScore: overallRiskScore,
      dimensions: riskDimensions,
      dealBreakers: report.scorecard.dealBreakers.map((finding) => finding.title),
    },
    transferabilityAnalysis: {
      score: transferabilityScore,
      explanation: transferability?.summary || 'Transferability evidence was limited in the summary payload.',
      keyFactors: relatedFindings(keyFindings, 'transferability').slice(0, 4).map((finding) => ({
        factor: finding.title,
        impact: finding.severity === 'low' ? 'positive' : finding.severity === 'medium' ? 'neutral' : 'negative',
        detail: finding.description,
      })),
      improvementSuggestions: report.summary.recommendedActions.slice(0, 5),
    },
    questionsForSeller: buildQuestions(report),
    diligenceChecklist: buildChecklist(report),
    upsideOpportunities: buildUpsideOpportunities(report),
    finalRecommendation: {
      action,
      strengths: strengths.length ? strengths : ['No standout strengths were surfaced beyond the current summary overview.'],
      risks: risks.length ? risks : ['No detailed risk list was returned; review the summary findings directly.'],
      nextSteps: report.summary.recommendedActions.length
        ? report.summary.recommendedActions
        : ['Request more supporting evidence before relying on the current summary report.'],
      summaryStatement: report.summary.headline || report.summary.overview || recommendationVerdict(report.scorecard.overallRecommendation),
    },
    agentFlags: buildAgentFlags(report),
    sbaLoanSizing: {
      maxSupportedLoan: metricNumber(report.scorecard.validatedMetrics.total_cash_needed) ?? metricNumber(report.scorecard.validatedMetrics.asking_price) ?? 0,
      estimatedInterestRate: 0,
      estimatedMonthlyPayment: 0,
      estimatedAnnualDebtService: debtService.annualDebtService,
      estimatedDSCR: metricNumber(report.scorecard.validatedMetrics.dscr) ?? 0,
      bankabilityScore,
      bankabilityLabel: bankabilityLabel(bankabilityScore),
      explanation: findDimension(report.scorecard.buyerFacingDimensions, 'bankability')?.summary || 'Bankability will improve as the remaining missing diligence inputs are resolved.',
    },
    metadata: {
      generatedAt: report.metadata.generatedAt || new Date().toISOString(),
      analysisVersion: `${ANALYSIS_VERSION}-summary-v2`,
      dataCompleteness: report.scorecard.completenessScore ?? 0,
      disclaimers: DISCLAIMERS,
    },
  };
}
