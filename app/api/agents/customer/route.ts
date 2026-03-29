import { NextRequest, NextResponse } from 'next/server';
import type { AgentOutput, DealInfo, FinancialData, QuestionnaireData } from '@/lib/types';

interface AgentRequest {
  financialData: FinancialData;
  questionnaire: QuestionnaireData;
  dealInfo: DealInfo;
}

function calculateApproximateHHI(topCustomerPct: number | null, top5Pct: number | null): number | null {
  if (topCustomerPct === null && top5Pct === null) return null;

  const top = topCustomerPct ?? 0;
  const top5 = Math.max(top5Pct ?? top, top);
  const remainderTopFive = Math.max(top5 - top, 0);
  const eachOfNextFour = remainderTopFive / 4;

  return Math.round(
    Math.pow(top / 100, 2) * 10000 +
    4 * Math.pow(eachOfNextFour / 100, 2) * 10000
  );
}

function buildCustomerOutput(questionnaire: QuestionnaireData): AgentOutput {
  const topCustomerPct = questionnaire.customerConcentration.topCustomerRevenuePercent;
  const top5Pct = questionnaire.customerConcentration.top5CustomersRevenuePercent;
  const contractType = questionnaire.customerConcentration.contractType;
  const averageTenure = questionnaire.customerConcentration.averageCustomerTenure;
  const hhiIndex = calculateApproximateHHI(topCustomerPct, top5Pct);

  let churnRiskScore = 25;
  if ((topCustomerPct ?? 0) > 50) churnRiskScore += 35;
  else if ((topCustomerPct ?? 0) > 30) churnRiskScore += 20;
  else if ((topCustomerPct ?? 0) > 20) churnRiskScore += 10;

  if ((top5Pct ?? 0) > 80) churnRiskScore += 20;
  else if ((top5Pct ?? 0) > 60) churnRiskScore += 10;

  if (contractType === 'mostly_handshake') churnRiskScore += 20;
  else if (contractType === 'mixed') churnRiskScore += 10;

  if (averageTenure === 'less_than_1_year') churnRiskScore += 10;

  const flags: AgentOutput['flags'] = [];

  if ((topCustomerPct ?? 0) > 30) {
    flags.push({
      severity: (topCustomerPct ?? 0) > 50 ? 'critical' : 'warning',
      dimension: 'Customer Concentration',
      sourceAgent: 'customer',
      metric: 'topCustomerRevenuePercent',
      message: `Top customer concentration is ${topCustomerPct}% of revenue.`,
    });
  }

  if (contractType === 'mostly_handshake') {
    flags.push({
      severity: 'warning',
      dimension: 'Customer Contracts',
      sourceAgent: 'customer',
      metric: 'contractType',
      message: 'Most customer relationships are informal, reducing revenue durability after a transition.',
    });
  }

  if (averageTenure === 'less_than_1_year') {
    flags.push({
      severity: 'warning',
      dimension: 'Customer Retention',
      sourceAgent: 'customer',
      metric: 'averageCustomerTenure',
      message: 'Average customer tenure is under one year, which may signal weaker retention.',
    });
  }

  return {
    agentId: 'customer',
    summary: `Customer agent estimated a churn and concentration risk score of ${Math.min(100, churnRiskScore)}${hhiIndex !== null ? ` with an approximate HHI of ${hhiIndex}` : ''}.`,
    confidence: topCustomerPct !== null || top5Pct !== null ? 0.8 : 0.4,
    flags,
    notes: hhiIndex === null ? ['Customer concentration percentages were incomplete, so the HHI estimate could not be calculated.'] : [],
    metrics: {
      topCustomerRevenuePercent: topCustomerPct,
      top5CustomersRevenuePercent: top5Pct,
      hhiIndex,
      churnRiskScore: Math.min(100, churnRiskScore),
      contractStrengthScore: contractType === 'mostly_contracted' ? 85 : contractType === 'mixed' ? 60 : contractType === 'mostly_handshake' ? 30 : null,
    },
  };
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as AgentRequest;
    const output = buildCustomerOutput(body.questionnaire);
    return NextResponse.json({ success: true, output });
  } catch (error) {
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : 'Customer agent failed' },
      { status: 500 }
    );
  }
}
