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

const DEFAULT_BACKEND_URL = 'http://localhost:8000/api';

function backendUrl(path: string): string {
  const base = (process.env.NEXT_PUBLIC_BACKEND_URL || DEFAULT_BACKEND_URL).replace(/\/$/, '');
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${base}${normalizedPath}`;
}

export async function parseDocuments(
  files: File[],
  fileTypes: string[]
): Promise<ParseDocumentsResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  formData.append('fileTypes', JSON.stringify(fileTypes));

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
  dealInfo: DealInfo
): Promise<AnalyzeResponse> {
  const res = await fetch(backendUrl('/analyze'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ financials, questionnaire, dealInfo }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(err.error || 'Failed to run analysis');
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
