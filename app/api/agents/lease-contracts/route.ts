import { NextRequest, NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';
import { cleanAgentJson, LEASE_CONTRACTS_AGENT_PROMPT } from '@/lib/agent-prompts';
import type { AgentOutput, DealInfo, FinancialData, QuestionnaireData } from '@/lib/types';

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

interface AgentRequest {
  financialData: FinancialData;
  questionnaire: QuestionnaireData;
  dealInfo: DealInfo;
}

function fallbackLeaseOutput(questionnaire: QuestionnaireData): AgentOutput {
  const contractType = questionnaire.customerConcentration.contractType;
  const averageTenure = questionnaire.customerConcentration.averageCustomerTenure;
  const transferabilityRiskScore =
    contractType === 'mostly_contracted' ? 35 :
      contractType === 'mixed' ? 55 : contractType === 'mostly_handshake' ? 75 : 60;

  const flags: AgentOutput['flags'] = [];
  if (contractType === 'mostly_handshake') {
    flags.push({
      severity: 'warning',
      dimension: 'Lease & Contracts',
      sourceAgent: 'leaseContracts',
      metric: 'contractType',
      message: 'Formal transferable customer contracts appear limited, which weakens transition certainty.',
    });
  }

  return {
    agentId: 'leaseContracts',
    summary: 'Lease and contract analysis used fallback questionnaire signals because no dedicated lease documents are captured in the current workflow.',
    confidence: 0.35,
    notes: [
      'Dedicated lease uploads are not yet preserved separately from core financial documents.',
      'Transfer clause, rent escalation, and remaining lease term should be confirmed during diligence.',
    ],
    flags,
    metrics: {
      leaseTermMonthsRemaining: averageTenure === '3_plus_years' ? 36 : averageTenure === '1_to_3_years' ? 18 : null,
      rentEscalationPct: null,
      transferApprovalRequired: null,
      transferabilityRiskScore,
    },
  };
}

export async function POST(req: NextRequest) {
  const body = await req.json() as AgentRequest;

  try {
    const fallback = fallbackLeaseOutput(body.questionnaire);
    const response = await client.messages.create({
      model: 'claude-opus-4-5',
      max_tokens: 1800,
      messages: [{ role: 'user', content: LEASE_CONTRACTS_AGENT_PROMPT(body.financialData, body.questionnaire, body.dealInfo) }],
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
      agentId: 'leaseContracts',
      summary: parsed.summary ?? fallback.summary,
      confidence: typeof parsed.confidence === 'number' ? parsed.confidence : fallback.confidence,
      notes: Array.isArray(parsed.notes) ? parsed.notes : fallback.notes,
      metrics: {
        leaseTermMonthsRemaining: typeof parsed.metrics?.leaseTermMonthsRemaining === 'number' ? parsed.metrics.leaseTermMonthsRemaining : fallback.metrics.leaseTermMonthsRemaining,
        rentEscalationPct: typeof parsed.metrics?.rentEscalationPct === 'number' ? parsed.metrics.rentEscalationPct : fallback.metrics.rentEscalationPct,
        transferApprovalRequired: typeof parsed.metrics?.transferApprovalRequired === 'boolean' ? parsed.metrics.transferApprovalRequired : fallback.metrics.transferApprovalRequired,
        transferabilityRiskScore: typeof parsed.metrics?.transferabilityRiskScore === 'number' ? parsed.metrics.transferabilityRiskScore : fallback.metrics.transferabilityRiskScore,
      },
      flags: Array.isArray(parsed.flags) && parsed.flags.length > 0
        ? parsed.flags.map((flag) => ({
          severity: flag.severity,
          dimension: flag.dimension,
          message: flag.message,
          metric: flag.metric ?? undefined,
          sourceAgent: 'leaseContracts',
        }))
        : fallback.flags,
    };

    return NextResponse.json({ success: true, output });
  } catch (error) {
    return NextResponse.json({ success: true, output: fallbackLeaseOutput(body.questionnaire) });
  }
}
