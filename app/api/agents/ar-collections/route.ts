import { NextRequest, NextResponse } from 'next/server';
import type { AgentOutput, DealInfo, FinancialData, QuestionnaireData } from '@/lib/types';

interface AgentRequest {
  financialData: FinancialData;
  questionnaire: QuestionnaireData;
  dealInfo: DealInfo;
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}

function buildArCollectionsOutput(financialData: FinancialData, questionnaire: QuestionnaireData): AgentOutput {
  const revenue = financialData.incomeStatement?.revenue ?? 0;
  const accountsReceivable = financialData.balanceSheet?.accountsReceivable ?? null;
  const impliedDSO = accountsReceivable !== null && revenue > 0
    ? (accountsReceivable / revenue) * 365
    : null;
  const arToRevenuePct = accountsReceivable !== null && revenue > 0
    ? (accountsReceivable / revenue) * 100
    : null;

  let badDebtRiskScore = 35;
  if (impliedDSO !== null && impliedDSO > 75) badDebtRiskScore += 35;
  else if (impliedDSO !== null && impliedDSO > 55) badDebtRiskScore += 20;
  else if (impliedDSO !== null && impliedDSO > 40) badDebtRiskScore += 10;

  if ((questionnaire.customerConcentration.topCustomerRevenuePercent ?? 0) > 30) badDebtRiskScore += 10;
  if (questionnaire.customerConcentration.contractType === 'mostly_handshake') badDebtRiskScore += 10;
  if (questionnaire.revenueQuality.knownUpcomingLosses) badDebtRiskScore += 10;

  const flags: AgentOutput['flags'] = [];
  const notes: string[] = [];

  if (accountsReceivable === null) {
    flags.push({
      severity: 'warning',
      dimension: 'AR & Collections',
      sourceAgent: 'arCollections',
      metric: 'accountsReceivable',
      message: 'Accounts receivable was not provided, so DSO and bad-debt risk are estimated with low confidence.',
    });
    notes.push('No AR aging schedule or receivables balance was available.');
  }

  if (impliedDSO !== null && impliedDSO > 60) {
    flags.push({
      severity: impliedDSO > 75 ? 'critical' : 'warning',
      dimension: 'AR & Collections',
      sourceAgent: 'arCollections',
      metric: 'impliedDSO',
      message: `Implied DSO is ${Math.round(impliedDSO)} days, suggesting collections may be slow.`,
    });
  }

  if ((questionnaire.customerConcentration.topCustomerRevenuePercent ?? 0) > 30) {
    flags.push({
      severity: 'warning',
      dimension: 'AR & Collections',
      sourceAgent: 'arCollections',
      metric: 'topCustomerRevenuePercent',
      message: 'Receivables risk is amplified by customer concentration above 30% with the top account.',
    });
  }

  return {
    agentId: 'arCollections',
    summary: impliedDSO !== null
      ? `AR agent estimated ${Math.round(impliedDSO)} days sales outstanding with a bad-debt risk score of ${Math.min(100, badDebtRiskScore)}.`
      : 'AR agent could not fully model collections risk because receivables detail is incomplete.',
    confidence: accountsReceivable !== null ? 0.75 : 0.35,
    flags,
    notes,
    metrics: {
      impliedDSO: impliedDSO !== null ? round(impliedDSO) : null,
      arToRevenuePct: arToRevenuePct !== null ? round(arToRevenuePct) : null,
      badDebtRiskScore: Math.min(100, badDebtRiskScore),
    },
  };
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as AgentRequest;
    const output = buildArCollectionsOutput(body.financialData, body.questionnaire);
    return NextResponse.json({ success: true, output });
  } catch (error) {
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : 'AR & Collections agent failed' },
      { status: 500 }
    );
  }
}
