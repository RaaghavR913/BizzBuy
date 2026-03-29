import { NextRequest, NextResponse } from 'next/server';
import { buildSharedContext } from '@/lib/merge-context';
import type { AgentId, AgentOutput, DealInfo, FinancialData, QuestionnaireData } from '@/lib/types';

interface MergeRequest {
  financialData: FinancialData;
  questionnaire: QuestionnaireData;
  dealInfo: DealInfo;
  agentOutputs: Partial<Record<AgentId, AgentOutput>>;
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as MergeRequest;
    const sharedContext = buildSharedContext(
      body.financialData,
      body.questionnaire,
      body.dealInfo,
      body.agentOutputs
    );

    return NextResponse.json({ success: true, sharedContext });
  } catch (error) {
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : 'Agent merge failed' },
      { status: 500 }
    );
  }
}
