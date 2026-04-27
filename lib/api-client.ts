import type {
  AnalysisJobSnapshot,
  AnyReportOutput,
  ClarificationAnswer,
  DealInfo,
  FinancialData,
  IngestResponse,
  PipelineDocumentPayload,
  QuestionnaireData,
  ReportOutput,
} from './types';

interface ParseDocumentsResponse {
  success: boolean;
  extractedData: FinancialData;
  analysisId?: string;
  pipelineDocuments: PipelineDocumentPayload[];
  error?: string;
}

interface AnalyzeResponse {
  success: boolean;
  report: AnyReportOutput;
  error?: string;
}

interface AnalysisRunContext {
  analysisId?: string | null;
  pipelineDocuments?: PipelineDocumentPayload[];
  clarifications?: ClarificationAnswer[];
}

const BACKEND_PROXY_BASE = '/api/backend';

function backendUrl(path: string): string {
  const base = BACKEND_PROXY_BASE.replace(/\/$/, '');
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${base}${normalizedPath}`;
}

export async function ingestDocuments(files: File[]): Promise<IngestResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));

  const res = await fetch(backendUrl('/documents/ingest'), {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(err.detail || err.error || 'Failed to classify documents');
  }
  return res.json();
}

export async function parseDocuments(
  files: File[],
  fileTypes: string[],
  fileHashes: Array<string | null | undefined> = [],
  ocrArtifactRefs: Array<string | null | undefined> = []
): Promise<ParseDocumentsResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  formData.append('fileTypes', JSON.stringify(fileTypes));
  if (fileHashes.length > 0) {
    formData.append('fileHashes', JSON.stringify(fileHashes));
  }
  if (ocrArtifactRefs.length > 0) {
    formData.append('ocrArtifactRefs', JSON.stringify(ocrArtifactRefs));
  }

  const res = await fetch(backendUrl('/parse-documents'), {
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
  financials: FinancialData,
  questionnaire: QuestionnaireData,
  dealInfo: DealInfo,
  _context?: AnalysisRunContext
): Promise<AnalyzeResponse> {
  // This function is only called for the deterministic (no-documents) path.
  // When documents are present the caller uses startAnalysisJob instead.
  const legacyRes = await fetch(backendUrl('/analyze'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ financials, questionnaire, dealInfo }),
  });
  if (!legacyRes.ok) {
    const err = await legacyRes.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(err.error || 'Failed to run analysis');
  }
  return legacyRes.json();
}

export async function startAnalysisJob(
  financials: FinancialData,
  questionnaire: QuestionnaireData,
  dealInfo: DealInfo,
  context?: AnalysisRunContext
): Promise<AnalysisJobSnapshot> {
  const res = await fetch(backendUrl('/analyses'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      financials,
      questionnaire,
      dealInfo,
      documents: context?.pipelineDocuments ?? [],
      analysisId: context?.analysisId,
      clarifications: context?.clarifications ?? [],
      reportDepth: 'summary',
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(err.error || err.detail || 'Failed to start analysis job');
  }

  return res.json();
}

/** Full URL for SSE; use with `EventSource` (same origin/CORS as other API calls). */
export function getAnalysisJobEventsUrl(analysisId: string): string {
  return backendUrl(`/analyses/${analysisId}/events`);
}

export async function getAnalysisJob(analysisId: string): Promise<AnalysisJobSnapshot> {
  const res = await fetch(backendUrl(`/analyses/${analysisId}`), {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(err.error || err.detail || 'Failed to load analysis job');
  }

  return res.json();
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
