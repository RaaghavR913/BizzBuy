import { loadAgentPrompt } from '../utils/prompt-loader';
import { callAgent } from '../utils/claude-client';
import {
  IngestionOutputSchema,
  type IngestionOutput,
} from '../schemas/ingestion.schema';
import type { PipelineInput, AgentResult, UploadedDocument } from '@/src/types/pipeline';
import { AGENT_REGISTRY } from '../registry';

export async function runDocumentIngestion(
  input: PipelineInput
): Promise<AgentResult<IngestionOutput>> {
  const config = AGENT_REGISTRY['document-ingestion'];
  const systemPrompt = loadAgentPrompt('document-ingestion');

  if (input.documents.length === 0) {
    return {
      status: 'success',
      data: {
        documents: [],
        metadata: {
          totalDocuments: 0,
          successfullyParsed: 0,
          failedDocuments: [],
          warnings: ['No documents were provided for ingestion.'],
        },
      },
      tokenUsage: { input: 0, output: 0 },
      latencyMs: 0,
    };
  }

  const userMessage = buildIngestionUserMessage(input);

  return callAgent<IngestionOutput>({
    model: config.model,
    systemPrompt,
    userMessage,
    schema: IngestionOutputSchema,
    maxTokens: config.maxTokens ?? 8192,
  });
}

function buildIngestionUserMessage(input: PipelineInput): string {
  const parts: string[] = [];

  parts.push('# Document Ingestion Request');
  parts.push('');

  if (input.businessType || input.location) {
    parts.push('## Business Context');
    if (input.businessType) {
      parts.push(`- **Business type:** ${input.businessType}`);
    }
    if (input.location) {
      parts.push(`- **Location:** ${input.location}`);
    }
    parts.push('');
  }

  parts.push(`## Uploaded Documents (${input.documents.length} total)`);
  parts.push('');

  for (const doc of input.documents) {
    parts.push(formatDocumentEntry(doc));
    parts.push('');
  }

  parts.push('---');
  parts.push(
    'Parse every document above. For each one, identify its type, extract all structured data, and return the result via the structured_output tool. Every document must appear in your output.'
  );

  return parts.join('\n');
}

const PDF_MIME_TYPES = new Set([
  'application/pdf',
]);

const SPREADSHEET_MIME_TYPES = new Set([
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.ms-excel',
  'text/csv',
  'application/csv',
]);

function formatDocumentEntry(doc: UploadedDocument): string {
  const lines: string[] = [];
  const sizeKB = Math.round(doc.sizeBytes / 1024);

  lines.push(`### Document: ${doc.filename}`);
  lines.push(`- **ID:** ${doc.id}`);
  lines.push(`- **MIME type:** ${doc.mimeType}`);
  lines.push(`- **Size:** ${sizeKB} KB`);

  if (PDF_MIME_TYPES.has(doc.mimeType)) {
    lines.push('');
    lines.push(`<document id="${doc.id}" filename="${doc.filename}">`);
    lines.push(doc.content);
    lines.push('</document>');
  } else if (SPREADSHEET_MIME_TYPES.has(doc.mimeType)) {
    // TODO: Pre-convert Excel/CSV files to plain text or structured CSV
    // before passing to the model. For now, include the base64 content
    // and rely on the model's ability to handle it. A preprocessing step
    // (e.g., using a library like xlsx or papaparse) should convert each
    // sheet/tab to a labeled text table before this function is called.
    lines.push('');
    lines.push(`<document id="${doc.id}" filename="${doc.filename}">`);
    lines.push(doc.content);
    lines.push('</document>');
  } else {
    lines.push('');
    lines.push(`<document id="${doc.id}" filename="${doc.filename}">`);
    lines.push(doc.content);
    lines.push('</document>');
  }

  return lines.join('\n');
}
