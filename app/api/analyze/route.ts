import { NextRequest, NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';
import type {
  AgentOutput,
  DealInfo,
  FinancialData,
  QuestionnaireData,
  ReportOutput,
  SharedContext,
} from '@/lib/types';
import {
  calculateBreakEvenMonthlyRevenue,
  calculateDSCR,
  calculateGrossMargin,
  calculateMonthlyPayment,
  calculateSDE,
  calculateValuationMultiple,
  calculateWorkingCapital,
  generateScenarios,
  assessDSCR,
  assessValuationMultiple,
  formatCurrency,
} from '@/lib/calculations';
import { buildSharedContext } from '@/lib/merge-context';
import { computeRiskScores, getRiskLabel, getTransferabilityLabel } from '@/lib/risk-scoring';
import { RISK_ANALYSIS_PROMPT, REPORT_NARRATIVE_SCHEMA } from '@/lib/prompts';
import { ANALYSIS_VERSION, DISCLAIMERS } from '@/lib/constants';

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
const WSJ_PRIME_RATE = 0.085;
const SBA_SPREAD = 0.0275;

interface AnalyzeRequest {
  financials?: FinancialData;
  questionnaire?: QuestionnaireData;
  dealInfo?: DealInfo;
  sharedContext?: SharedContext;
}

function computeFinancialMetrics(financials: FinancialData, dealInfo: DealInfo, validatedSDE?: number) {
  const incomeStatement = financials.incomeStatement;
  const balanceSheet = financials.balanceSheet;
  const loanTerms = financials.loanTerms;

  const revenue = incomeStatement?.revenue ?? 0;
  const cogs = incomeStatement?.cogs ?? 0;
  const operatingExpenses = incomeStatement?.operatingExpenses ?? 0;
  const netIncome = incomeStatement?.netIncome ?? 0;
  const ownerSalary = incomeStatement?.ownerSalary ?? 0;
  const addBackTotal = incomeStatement?.addBacks?.reduce((sum, item) => sum + item.amount, 0) ?? 0;
  const depreciationAmortization = incomeStatement?.depreciationAmortization ?? 0;
  const interestExpense = incomeStatement?.interestExpense ?? 0;

  const baseSDE = incomeStatement?.sde ?? calculateSDE(netIncome, ownerSalary, addBackTotal, depreciationAmortization, interestExpense);
  const sde = validatedSDE ?? baseSDE;
  const ebitda = incomeStatement?.ebitda ?? (netIncome + interestExpense + depreciationAmortization);
  const grossProfit = incomeStatement?.grossProfit ?? (revenue - cogs);
  const grossMargin = calculateGrossMargin(revenue, cogs);
  const workingCapital = balanceSheet ? calculateWorkingCapital(balanceSheet.currentAssets, balanceSheet.currentLiabilities) : null;
  const debtToEquity = balanceSheet && balanceSheet.equity > 0 ? balanceSheet.totalLiabilities / balanceSheet.equity : null;

  const loanAmount = loanTerms?.loanAmount ?? 0;
  const interestRate = loanTerms?.interestRate ?? 0;
  const termMonths = loanTerms?.termMonths ?? 120;
  const monthlyDebtService = loanTerms?.monthlyPayment ?? (loanAmount > 0 ? calculateMonthlyPayment(loanAmount, interestRate, termMonths) : 0);
  const annualDebtService = monthlyDebtService * 12;
  const dscr = annualDebtService > 0 ? calculateDSCR(sde, annualDebtService) : Infinity;
  const askingPrice = dealInfo.askingPrice || loanTerms?.askingPrice || 0;
  const valuationMultiple = calculateValuationMultiple(askingPrice, sde);
  const minimumRevenue = annualDebtService > 0 ? annualDebtService + operatingExpenses : operatingExpenses;
  const breakEvenMonthly = calculateBreakEvenMonthlyRevenue(monthlyDebtService, operatingExpenses / 12);
  const scenarios = annualDebtService > 0 ? generateScenarios(revenue, annualDebtService, operatingExpenses, termMonths) : [];

  return {
    revenue,
    cogs,
    grossProfit,
    grossMargin,
    operatingExpenses,
    netIncome,
    sde,
    ebitda,
    ownerSalary,
    addBackTotal,
    depreciationAmortization,
    workingCapital,
    debtToEquity,
    loanAmount,
    interestRate,
    termMonths,
    monthlyDebtService,
    annualDebtService,
    dscr,
    askingPrice,
    valuationMultiple,
    minimumRevenue,
    breakEvenMonthly,
    scenarios,
  };
}

function buildDefaultSharedContext(
  financials: FinancialData,
  questionnaire: QuestionnaireData,
  dealInfo: DealInfo
): SharedContext {
  const agentOutputs: Partial<Record<AgentOutput['agentId'], AgentOutput>> = {};
  return buildSharedContext(financials, questionnaire, dealInfo, agentOutputs);
}

function computeBankability(sharedContext: SharedContext) {
  const interestRate = WSJ_PRIME_RATE + SBA_SPREAD;
  const maxSupportedLoan = Math.max(0, sharedContext.validatedSDE * 5);
  const estimatedMonthlyPayment = maxSupportedLoan > 0
    ? calculateMonthlyPayment(maxSupportedLoan, interestRate, 120)
    : 0;
  const estimatedAnnualDebtService = estimatedMonthlyPayment * 12;
  const estimatedDSCR = estimatedAnnualDebtService > 0
    ? calculateDSCR(sharedContext.validatedSDE, estimatedAnnualDebtService)
    : Infinity;

  let bankabilityScore = 55;
  if (estimatedDSCR >= 2) bankabilityScore += 25;
  else if (estimatedDSCR >= 1.5) bankabilityScore += 15;
  else if (estimatedDSCR >= 1.25) bankabilityScore += 5;
  else if (estimatedDSCR < 1) bankabilityScore -= 20;

  if (sharedContext.sdeConflict) bankabilityScore -= 15;

  const criticalFlags = sharedContext.mergedFlags.filter((flag) => flag.severity === 'critical').length;
  const warningFlags = sharedContext.mergedFlags.filter((flag) => flag.severity === 'warning').length;
  bankabilityScore -= criticalFlags * 8;
  bankabilityScore -= warningFlags * 3;
  bankabilityScore = Math.max(0, Math.min(100, bankabilityScore));

  const bankabilityLabel =
    bankabilityScore >= 80 ? 'Strong' :
      bankabilityScore >= 65 ? 'Bankable' :
        bankabilityScore >= 45 ? 'Borderline' : 'Weak';

  return {
    maxSupportedLoan,
    estimatedInterestRate: interestRate,
    estimatedMonthlyPayment,
    estimatedAnnualDebtService,
    estimatedDSCR,
    bankabilityScore,
    bankabilityLabel,
    explanation: estimatedDSCR === Infinity
      ? 'No modeled SBA payment was required, so bankability is driven mainly by diligence quality and risk flags.'
      : `Using a 10-year SBA-style amortization at ${(interestRate * 100).toFixed(2)}%, the current validated SDE supports about ${formatCurrency(maxSupportedLoan)} of debt with an estimated DSCR of ${estimatedDSCR.toFixed(2)}.`,
  } as ReportOutput['sbaLoanSizing'];
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as AnalyzeRequest;
    const sharedContext = body.sharedContext ?? (
      body.financials && body.questionnaire && body.dealInfo
        ? buildDefaultSharedContext(body.financials, body.questionnaire, body.dealInfo)
        : null
    );

    if (!sharedContext) {
      return NextResponse.json({ success: false, error: 'Missing shared context or analysis inputs' }, { status: 400 });
    }

    const { financialData, questionnaire, dealInfo } = sharedContext;
    const metrics = computeFinancialMetrics(financialData, dealInfo, sharedContext.validatedSDE);
    const riskResult = computeRiskScores(questionnaire, financialData);
    const bankability = computeBankability(sharedContext);

    const computedMetricsStr = JSON.stringify({
      ...metrics,
      validatedSDE: sharedContext.validatedSDE,
      sdeConflict: sharedContext.sdeConflict,
      bankability,
      scenarios: metrics.scenarios,
      agentFindings: {
        mergedFlags: sharedContext.mergedFlags,
        agentOutputs: sharedContext.agentOutputs,
      },
      riskScores: {
        overall: riskResult.overallScore,
        transferability: riskResult.transferabilityScore,
        dimensions: riskResult.dimensions.map((dimension) => ({
          dimension: dimension.dimension,
          score: dimension.score,
          label: dimension.label,
          keyFactors: dimension.keyFactors,
          isDealBreaker: dimension.isDealBreaker,
        })),
        dealBreakers: riskResult.dealBreakers,
      },
    }, null, 2);

    const prompt = RISK_ANALYSIS_PROMPT(
      JSON.stringify(financialData, null, 2),
      computedMetricsStr,
      JSON.stringify(questionnaire, null, 2),
      JSON.stringify(dealInfo, null, 2),
      REPORT_NARRATIVE_SCHEMA
    );

    const aiResponse = await client.messages.create({
      model: 'claude-opus-4-5',
      max_tokens: 8000,
      messages: [{ role: 'user', content: prompt }],
    });

    const aiText = aiResponse.content[0].type === 'text' ? aiResponse.content[0].text : '{}';
    const clean = aiText.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
    const narrative = JSON.parse(clean) as {
      executiveSummaryText: string;
      verdict: string;
      riskDimensionExplanations: Record<string, string>;
      transferabilityExplanation: string;
      transferabilityKeyFactors: { factor: string; impact: 'positive' | 'negative' | 'neutral'; detail: string }[];
      transferabilityImprovements: string[];
      questionsForSeller: { category: string; questions: string[] }[];
      diligenceChecklist: { item: string; category: string; priority: 'critical' | 'important' | 'nice_to_have'; reason: string }[];
      upsideOpportunities: { opportunity: string; estimatedImpact: string; difficulty: 'easy' | 'moderate' | 'hard'; detail: string }[];
      recommendation: 'proceed' | 'proceed_with_caution' | 'walk_away';
      strengths: string[];
      risks: string[];
      nextSteps: string[];
      summaryStatement: string;
      dscrAssessment: string;
      affordabilityVerdict: string;
      multipleAssessment: string;
    };

    const riskLabel = getRiskLabel(riskResult.overallScore);
    const transferabilityLabel = getTransferabilityLabel(riskResult.transferabilityScore);
    const dimensionKeyMap: Record<string, string> = {
      'Owner Dependence': 'ownerDependence',
      'Customer Concentration': 'customerConcentration',
      'Revenue Quality': 'revenueQuality',
      'Employee & Operational Risk': 'employeeRisk',
      'Supplier & Vendor Risk': 'supplierRisk',
      'Financial & Add-Back Risk': 'financialRisk',
    };

    const enrichedDimensions = riskResult.dimensions.map((dimension) => ({
      ...dimension,
      explanation: narrative.riskDimensionExplanations[dimensionKeyMap[dimension.dimension]] ?? dimension.explanation,
    }));

    const report: ReportOutput = {
      executiveSummary: {
        text: narrative.executiveSummaryText,
        riskScore: riskResult.overallScore,
        riskLabel,
        transferabilityScore: riskResult.transferabilityScore,
        transferabilityLabel,
        verdict: narrative.verdict,
      },
      financialSnapshot: {
        metrics: {
          Revenue: { value: metrics.revenue, formatted: formatCurrency(metrics.revenue) },
          COGS: { value: metrics.cogs, formatted: formatCurrency(metrics.cogs) },
          'Gross Profit': { value: metrics.grossProfit, formatted: formatCurrency(metrics.grossProfit) },
          'Gross Margin': { value: metrics.grossMargin, formatted: `${metrics.grossMargin.toFixed(1)}%` },
          'Operating Expenses': { value: metrics.operatingExpenses, formatted: formatCurrency(metrics.operatingExpenses) },
          'Net Income': { value: metrics.netIncome, formatted: formatCurrency(metrics.netIncome) },
          SDE: {
            value: metrics.sde,
            formatted: formatCurrency(metrics.sde),
            note: sharedContext.sdeConflict ? 'Validated conservatively after Phase 2 conflict review' : 'Seller\'s Discretionary Earnings',
          },
          EBITDA: { value: metrics.ebitda, formatted: formatCurrency(metrics.ebitda) },
          ...(metrics.workingCapital !== null ? {
            'Working Capital': {
              value: metrics.workingCapital,
              formatted: formatCurrency(metrics.workingCapital),
              note: metrics.workingCapital < 0 ? 'Negative — flag' : undefined,
            },
          } : {}),
        },
        valuationMultiple: metrics.valuationMultiple,
        multipleAssessment: narrative.multipleAssessment ?? assessValuationMultiple(metrics.valuationMultiple, dealInfo.businessType),
      },
      debtServiceAnalysis: {
        loanSummary: {
          'Loan Amount': formatCurrency(metrics.loanAmount),
          'Interest Rate': `${(metrics.interestRate * 100).toFixed(2)}%`,
          'Loan Term': `${metrics.termMonths} months (${Math.round(metrics.termMonths / 12)} years)`,
          'Down Payment': metrics.loanAmount > 0 ? formatCurrency(financialData.loanTerms?.downPayment ?? 0) : 'N/A',
          'Asking Price': formatCurrency(metrics.askingPrice),
          'Loan Type': financialData.loanTerms?.loanType?.toUpperCase().replace('_', ' ') ?? 'Unknown',
          'SBA Max Loan': formatCurrency(bankability.maxSupportedLoan),
          'Bankability Score': `${bankability.bankabilityScore}/100 (${bankability.bankabilityLabel})`,
        },
        monthlyDebtService: metrics.monthlyDebtService,
        annualDebtService: metrics.annualDebtService,
        dscr: metrics.dscr === Infinity ? 999 : metrics.dscr,
        dscrAssessment: narrative.dscrAssessment ?? assessDSCR(metrics.dscr),
        minimumRevenueRequired: metrics.minimumRevenue,
        breakEvenMonthlyRevenue: metrics.breakEvenMonthly,
        scenarios: metrics.scenarios,
        affordabilityVerdict: `${narrative.affordabilityVerdict} ${bankability.explanation}`,
      },
      riskAssessment: {
        overallScore: riskResult.overallScore,
        dimensions: enrichedDimensions,
        dealBreakers: sharedContext.mergedFlags
          .filter((flag) => flag.severity === 'critical')
          .map((flag) => `${flag.dimension}: ${flag.message}`)
          .concat(riskResult.dealBreakers),
      },
      transferabilityAnalysis: {
        score: riskResult.transferabilityScore,
        explanation: narrative.transferabilityExplanation,
        keyFactors: narrative.transferabilityKeyFactors ?? [],
        improvementSuggestions: narrative.transferabilityImprovements ?? [],
      },
      questionsForSeller: narrative.questionsForSeller ?? [],
      diligenceChecklist: narrative.diligenceChecklist ?? [],
      upsideOpportunities: narrative.upsideOpportunities ?? [],
      finalRecommendation: {
        action: narrative.recommendation,
        strengths: narrative.strengths ?? [],
        risks: narrative.risks ?? [],
        nextSteps: narrative.nextSteps ?? [],
        summaryStatement: narrative.summaryStatement ?? '',
      },
      agentFlags: sharedContext.mergedFlags,
      sbaLoanSizing: bankability,
      metadata: {
        generatedAt: new Date().toISOString(),
        analysisVersion: ANALYSIS_VERSION,
        dataCompleteness: sharedContext.dataCompleteness,
        disclaimers: DISCLAIMERS,
      },
    };

    return NextResponse.json({ success: true, report });
  } catch (error) {
    console.error('Analysis error:', error);
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : 'Analysis failed' },
      { status: 500 }
    );
  }
}
