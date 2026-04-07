import { NextRequest, NextResponse } from 'next/server';
import { runPipeline } from '@/src/agents/orchestrator';
import type { PipelineInput } from '@/src/types/pipeline';

export const maxDuration = 300;
export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    if (!body.documents || !Array.isArray(body.documents) || body.documents.length === 0) {
      return NextResponse.json(
        { error: 'Invalid input: documents array is required and must not be empty' },
        { status: 400 }
      );
    }

    for (const doc of body.documents) {
      if (!doc.id || !doc.filename || !doc.mimeType || !doc.content) {
        return NextResponse.json(
          { error: 'Invalid input: each document must have id, filename, mimeType, and content fields' },
          { status: 400 }
        );
      }
    }

    if (body.askingPrice !== undefined && (typeof body.askingPrice !== 'number' || body.askingPrice <= 0)) {
      return NextResponse.json(
        { error: 'Invalid input: askingPrice must be a positive number' },
        { status: 400 }
      );
    }

    const input: PipelineInput = {
      documents: body.documents,
      askingPrice: body.askingPrice,
      businessType: body.businessType,
      location: body.location,
    };

    console.log(
      `[API] Pipeline started — ${input.documents.length} documents, askingPrice: ${input.askingPrice ?? 'not provided'}`
    );

    const state = await runPipeline(input);

    return NextResponse.json(state, { status: 200 });
  } catch (error) {
    console.error('[API] Unexpected pipeline error:', error);
    return NextResponse.json(
      {
        error: 'Internal server error during pipeline execution',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json({
    status: 'ok',
    service: 'bizbuy-pipeline',
    timestamp: new Date().toISOString(),
    agents: 10,
    phases: 4,
  });
}
