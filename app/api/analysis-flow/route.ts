import { NextRequest, NextResponse } from 'next/server';
import {
  createAnalysisFlowToken,
  readAnalysisFlow,
  setAnalysisFlowCookie,
} from '@/lib/server/analysis-flow';
import { proxyRateLimitAllowed, sameOriginRequest } from '@/lib/server/proxy-security';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest): Promise<NextResponse> {
  if (!sameOriginRequest(req)) {
    return NextResponse.json({ error: 'Cross-origin flow requests are not allowed.' }, { status: 403 });
  }

  const existing = readAnalysisFlow(req);
  if (existing) {
    return NextResponse.json({ ok: true, expiresAt: existing.expiresAt });
  }

  if (!proxyRateLimitAllowed(req, 'flow')) {
    return NextResponse.json({ error: 'Rate limit exceeded.' }, { status: 429 });
  }

  const flow = createAnalysisFlowToken();
  const res = NextResponse.json({ ok: true, expiresAt: flow.expiresAt });
  setAnalysisFlowCookie(req, res, flow.token, flow.expiresAt);
  return res;
}
