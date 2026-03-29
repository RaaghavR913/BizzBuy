import { NextRequest, NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';
import { calculateSDE } from '@/lib/calculations';
import { cleanAgentJson, TAX_AGENT_PROMPT } from '@/lib/agent-prompts';
import type { AgentOutput, DealInfo, FinancialData, QuestionnaireData } from '@/lib/types';

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

interface AgentRequest {
  financialData: FinancialData;
  questionnaire: QuestionnaireData;
  dealInfo: DealInfo;
}

function fallbackTaxOutput(financialData: FinancialData): AgentOutput {
  const incomeStatement = financialData.incomeStatement;
  const addBacks = incomeStatement?.addBacks?.reduce((sum, item) => sum + item.amount, 0) ?? 0;
  const normalizedSDE = incomeStatement
    ? calculateSDE(
      incomeStatement.netIncome,
      incomeStatement.ownerSalary ?? 0,
      addBacks,
      incomeStatement.depreciationAmortization ?? 0,
      incomeStatement.interestExpense ?? 0
    )
    : 0;

  return {
    agentId: 'tax',
    summary: 'Tax agent used a fallback normalization because the AI review could not be completed.',
    confidence: 0.25,
    notes: [
      'Tax-return-specific reconciliation is limited by the current structured input.',
      'Separate statement-versus-return comparison may require preserving tax documents independently from the income statement payload.',
    ],
    flags: [
      {
        severity: 'warning',
        dimension: 'Tax',
        sourceAgent: 'tax',
        metric: 'normalizedSDE',
        message: 'Tax reconciliation confidence is low because dedicated tax-return fields are not preserved separately in the current workflow.',
      },
    ],
    metrics: {
      revenueVariancePct: null,
      netIncomeVariancePct: null,
      ownerCompVariancePct: null,
      normalizedSDE: Math.round(normalizedSDE),
      deductionRiskScore: financialData.parsingNotes.some((note) => /tax/i.test(note)) ? 45 : 35,
    },
  };
}

export async function POST(req: NextRequest) {
  const body = await req.json() as AgentRequest;

  try {
    const fallback = fallbackTaxOutput(body.financialData);

    const response = await client.messages.create({
      model: 'claude-opus-4-5',
      max_tokens: 1800,
      messages: [{ role: 'user', content: TAX_AGENT_PROMPT(body.financialData, body.questionnaire, body.dealInfo) }],
    });

    const text = response.content[0].type === 'text' ? response.content[0].text : '{}';
    const parsed = JSON.parse(cleanAgentJson(text)) as {
      summary?: string;
      confidence?: number;
      notes?: string[];
      metrics?: Record<string, unknown>;
      flags?: Array<{ severity: 'info' | 'warning' | 'critical'; dimension: string; message: string; metric?: string | null }>;
    };

    const output: AgentOutput = {
      agentId: 'tax',
      summary: parsed.summary ?? fallback.summary,
      confidence: typeof parsed.confidence === 'number' ? parsed.confidence : fallback.confidence,
      notes: Array.isArray(parsed.notes) ? parsed.notes : fallback.notes,
      metrics: {
        revenueVariancePct: typeof parsed.metrics?.revenueVariancePct === 'number' ? parsed.metrics.revenueVariancePct : fallback.metrics.revenueVariancePct,
        netIncomeVariancePct: typeof parsed.metrics?.netIncomeVariancePct === 'number' ? parsed.metrics.netIncomeVariancePct : fallback.metrics.netIncomeVariancePct,
        ownerCompVariancePct: typeof parsed.metrics?.ownerCompVariancePct === 'number' ? parsed.metrics.ownerCompVariancePct : fallback.metrics.ownerCompVariancePct,
        normalizedSDE: typeof parsed.metrics?.normalizedSDE === 'number' ? parsed.metrics.normalizedSDE : fallback.metrics.normalizedSDE,
        deductionRiskScore: typeof parsed.metrics?.deductionRiskScore === 'number' ? parsed.metrics.deductionRiskScore : fallback.metrics.deductionRiskScore,
      },
      flags: Array.isArray(parsed.flags) && parsed.flags.length > 0
        ? parsed.flags.map((flag) => ({
          severity: flag.severity,
          dimension: flag.dimension,
          message: flag.message,
          metric: flag.metric ?? undefined,
          sourceAgent: 'tax',
        }))
        : fallback.flags,
    };

    return NextResponse.json({ success: true, output });
  } catch (error) {
    const output = fallbackTaxOutput(body.financialData);
    return NextResponse.json({ success: true, output });
  }
}
