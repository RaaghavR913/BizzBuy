import { NextRequest, NextResponse } from 'next/server';
import { renderToBuffer } from '@react-pdf/renderer';
import { ReportPdfDocument } from '@/lib/report-pdf';
import type { ReportOutput } from '@/lib/types';

export async function POST(req: NextRequest) {
  try {
    const { report } = await req.json() as { report: ReportOutput };
    const pdfBuffer = await renderToBuffer(ReportPdfDocument({ report }));

    return new NextResponse(pdfBuffer as unknown as BodyInit, {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'attachment; filename="bizbuy-acquisition-report.pdf"',
        'Cache-Control': 'no-store',
      },
    });
  } catch (error) {
    console.error('PDF generation error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to generate report' },
      { status: 500 }
    );
  }
}
