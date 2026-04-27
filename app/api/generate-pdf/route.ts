import { NextRequest, NextResponse } from 'next/server';
import { renderToBuffer } from '@react-pdf/renderer';
import { ReportPdfDocument } from '@/lib/report-pdf';
import { normalizeReportOutput } from '@/lib/report-normalization';
import type { AnyReportOutput, ReportOutput } from '@/lib/types';

export const runtime = 'nodejs';

const DEFAULT_MAX_BODY_BYTES = 2 * 1024 * 1024;

class PdfRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

function maxPdfBodyBytes(): number {
  const configured = Number(process.env.BIZBUY_PDF_MAX_BODY_BYTES);
  return Number.isFinite(configured) && configured > 0 ? configured : DEFAULT_MAX_BODY_BYTES;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function hasRecord(value: Record<string, unknown>, key: string): boolean {
  return isRecord(value[key]);
}

function isLegacyReport(value: unknown): value is ReportOutput {
  if (!isRecord(value)) return false;
  return (
    hasRecord(value, 'executiveSummary') &&
    hasRecord(value, 'financialSnapshot') &&
    hasRecord(value, 'debtServiceAnalysis') &&
    hasRecord(value, 'riskAssessment') &&
    hasRecord(value, 'transferabilityAnalysis') &&
    hasRecord(value, 'finalRecommendation') &&
    hasRecord(value, 'sbaLoanSizing') &&
    hasRecord(value, 'metadata')
  );
}

function isReportV2(value: unknown): value is AnyReportOutput {
  if (!isRecord(value)) return false;
  return hasRecord(value, 'modeAvailable') && hasRecord(value, 'summary') && hasRecord(value, 'scorecard') && hasRecord(value, 'metadata');
}

async function readAndValidateBody(req: NextRequest): Promise<ReportOutput> {
  const limit = maxPdfBodyBytes();
  const contentLength = Number(req.headers.get('content-length') || 0);
  if (Number.isFinite(contentLength) && contentLength > limit) {
    throw new PdfRequestError('Request body is too large.', 413);
  }

  const rawBody = await req.text();
  if (Buffer.byteLength(rawBody, 'utf8') > limit) {
    throw new PdfRequestError('Request body is too large.', 413);
  }

  let payload: unknown;
  try {
    payload = JSON.parse(rawBody);
  } catch {
    throw new PdfRequestError('Request body must be valid JSON.', 400);
  }

  if (!isRecord(payload) || !('report' in payload)) {
    throw new PdfRequestError('Request body must include a report object.', 400);
  }

  const report = payload.report;
  if (isLegacyReport(report)) {
    return report;
  }
  if (isReportV2(report)) {
    return normalizeReportOutput(report);
  }

  throw new PdfRequestError('Report payload is invalid.', 400);
}

export async function POST(req: NextRequest) {
  try {
    const report = await readAndValidateBody(req);
    const pdfBuffer = await renderToBuffer(ReportPdfDocument({ report }));

    return new NextResponse(pdfBuffer as unknown as BodyInit, {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'attachment; filename="bizbuy-acquisition-report.pdf"',
        'Cache-Control': 'no-store',
      },
    });
  } catch (error) {
    if (error instanceof PdfRequestError) {
      return NextResponse.json({ error: error.message }, { status: error.status });
    }
    console.error('PDF generation error:', error);
    return NextResponse.json(
      { error: 'Failed to generate report' },
      { status: 500 }
    );
  }
}
