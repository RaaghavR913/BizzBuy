import type {
  AgentId,
  AgentOutput,
  DealInfo,
  FinancialData,
  QuestionnaireData,
  ReportOutput,
  SharedContext,
} from './types';

export type { AgentId, AgentOutput, FinancialData, QuestionnaireData, DealInfo, ReportOutput, SharedContext };

export interface ParseDocumentsResponse {
  success: boolean;
  extractedData: FinancialData;
  error?: string;
}

export interface AnalyzeResponse {
  success: boolean;
  report: ReportOutput;
  error?: string;
}

export interface AgentRouteResponse {
  success: boolean;
  output: AgentOutput;
  error?: string;
}

export interface MergeResponse {
  success: boolean;
  sharedContext: SharedContext;
  error?: string;
}

export type Phase2AgentName =
  | 'financial'
  | 'tax'
  | 'arCollections'
  | 'customer'
  | 'operations'
  | 'leaseContracts'
  | 'marketMacro';

export interface Phase2ProgressEvent {
  agent: Phase2AgentName;
  status: 'running' | 'completed' | 'failed';
}

const PHASE2_AGENTS: Array<{ agent: Phase2AgentName; endpoint: string }> = [
  { agent: 'financial', endpoint: '/api/agents/financial' },
  { agent: 'tax', endpoint: '/api/agents/tax' },
  { agent: 'arCollections', endpoint: '/api/agents/ar-collections' },
  { agent: 'customer', endpoint: '/api/agents/customer' },
  { agent: 'operations', endpoint: '/api/agents/operations' },
  { agent: 'leaseContracts', endpoint: '/api/agents/lease-contracts' },
  { agent: 'marketMacro', endpoint: '/api/agents/market-macro' },
];

export async function parseDocuments(
  files: File[],
  fileTypes: string[]
): Promise<ParseDocumentsResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  formData.append('fileTypes', JSON.stringify(fileTypes));

  const res = await fetch('/api/parse-documents', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(err.error || 'Failed to parse documents');
  }
  return res.json();
}

export async function analyzeData(
  sharedContext: SharedContext
): Promise<AnalyzeResponse> {
  const res = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sharedContext }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(err.error || 'Failed to run analysis');
  }
  return res.json();
}

export async function runPhase2Agents(
  financialData: FinancialData,
  questionnaire: QuestionnaireData,
  dealInfo: DealInfo,
  onProgress?: (event: Phase2ProgressEvent) => void
): Promise<SharedContext> {
  const payload = { financialData, questionnaire, dealInfo };

  PHASE2_AGENTS.forEach(({ agent }) => onProgress?.({ agent, status: 'running' }));

  const results = await Promise.all(
    PHASE2_AGENTS.map(async ({ agent, endpoint }) => {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const body = await res.json().catch(() => ({ error: 'Request failed' }));
      if (!res.ok || !body.success) {
        onProgress?.({ agent, status: 'failed' });
        throw new Error(body.error || `Failed to run ${agent} agent`);
      }

      onProgress?.({ agent, status: 'completed' });
      return { agent, output: body.output as AgentOutput };
    })
  );

  const agentOutputs = results.reduce<Partial<Record<AgentId, AgentOutput>>>((acc, result) => {
    acc[result.agent] = result.output;
    return acc;
  }, {});

  const mergeRes = await fetch('/api/agents/merge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, agentOutputs }),
  });

  const mergeBody = await mergeRes.json().catch(() => ({ error: 'Merge failed' }));
  if (!mergeRes.ok || !mergeBody.success) {
    throw new Error(mergeBody.error || 'Failed to merge Phase 2 agent outputs');
  }

  return mergeBody.sharedContext as SharedContext;
}

export async function generatePDF(report: ReportOutput): Promise<void> {
  const res = await fetch('/api/generate-pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ report }),
  });
  if (!res.ok) throw new Error('Failed to generate report');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'bizbuy-acquisition-report.pdf';
  a.click();
  URL.revokeObjectURL(url);
}
