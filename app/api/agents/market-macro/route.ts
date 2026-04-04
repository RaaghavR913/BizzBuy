import { NextRequest, NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';
import { BUSINESS_TYPES, RISK_THRESHOLDS } from '@/lib/constants';
import { cleanAgentJson, MARKET_MACRO_AGENT_PROMPT } from '@/lib/agent-prompts';
import type { AgentOutput, DealInfo, FinancialData, QuestionnaireData } from '@/lib/types';

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

interface AgentRequest {
  financialData: FinancialData;
  questionnaire: QuestionnaireData;
  dealInfo: DealInfo;
}

function getBenchmarkContext(dealInfo: DealInfo): string {
  const businessLabel = BUSINESS_TYPES.find((item) => item.value === dealInfo.businessType)?.label ?? dealInfo.businessType;

  return [
    `Business type: ${businessLabel}`,
    `Typical small-business valuation market threshold in current app logic: ${RISK_THRESHOLDS.valuationMultiple.market}x SDE.`,
    `Premium threshold in current app logic: ${RISK_THRESHOLDS.valuationMultiple.premium}x SDE.`,
    'Industries with higher transferability, recurring revenue, or durable contracts can support upper-range pricing.',
    'Industries with labor concentration, project-based revenue, or owner dependence should skew toward lower multiples and higher macro caution.',
  ].join('\n');
}

function fallbackMarketOutput(dealInfo: DealInfo): AgentOutput {
  const isServiceBusiness = ['home_services', 'professional_services', 'auto_services', 'healthcare'].includes(dealInfo.businessType);
  return {
    agentId: 'marketMacro',
    summary: 'Market and macro analysis used benchmark heuristics because the focused AI review could not be completed.',
    confidence: 0.45,
    notes: ['Live web-based macro research is not yet integrated into the runtime, so the market view is benchmark-driven rather than real-time.'],
    flags: [
      {
        severity: 'info',
        dimension: 'Market',
        sourceAgent: 'marketMacro',
        metric: 'typicalHighMultiple',
        message: 'Market valuation guidance is based on internal benchmark heuristics rather than live comparable sales data.',
      },
    ],
    metrics: {
      typicalLowMultiple: isServiceBusiness ? 2.5 : 2,
      typicalHighMultiple: isServiceBusiness ? 4 : 3.5,
      macroRiskScore: isServiceBusiness ? 45 : 55,
      industryOutlookScore: isServiceBusiness ? 65 : 55,
    },
  };
}

export async function POST(req: NextRequest) {
  const body = await req.json() as AgentRequest;

  try {
    const fallback = fallbackMarketOutput(body.dealInfo);
    const response = await client.messages.create({
      model: 'claude-opus-4-5',
      max_tokens: 1800,
      messages: [{
        role: 'user',
        content: MARKET_MACRO_AGENT_PROMPT(
          body.financialData,
          body.questionnaire,
          body.dealInfo,
          getBenchmarkContext(body.dealInfo)
        ),
      }],
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
      agentId: 'marketMacro',
      summary: parsed.summary ?? fallback.summary,
      confidence: typeof parsed.confidence === 'number' ? parsed.confidence : fallback.confidence,
      notes: Array.isArray(parsed.notes) ? parsed.notes : fallback.notes,
      metrics: {
        typicalLowMultiple: typeof parsed.metrics?.typicalLowMultiple === 'number' ? parsed.metrics.typicalLowMultiple : fallback.metrics.typicalLowMultiple,
        typicalHighMultiple: typeof parsed.metrics?.typicalHighMultiple === 'number' ? parsed.metrics.typicalHighMultiple : fallback.metrics.typicalHighMultiple,
        macroRiskScore: typeof parsed.metrics?.macroRiskScore === 'number' ? parsed.metrics.macroRiskScore : fallback.metrics.macroRiskScore,
        industryOutlookScore: typeof parsed.metrics?.industryOutlookScore === 'number' ? parsed.metrics.industryOutlookScore : fallback.metrics.industryOutlookScore,
      },
      flags: Array.isArray(parsed.flags) && parsed.flags.length > 0
        ? parsed.flags.map((flag) => ({
          severity: flag.severity,
          dimension: flag.dimension,
          message: flag.message,
          metric: flag.metric ?? undefined,
          sourceAgent: 'marketMacro',
        }))
        : fallback.flags,
    };

    return NextResponse.json({ success: true, output });
  } catch (_error) {
    return NextResponse.json({ success: true, output: fallbackMarketOutput(body.dealInfo) });
  }
}
