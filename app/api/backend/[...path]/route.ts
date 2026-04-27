import { NextRequest, NextResponse } from 'next/server';
import { readAnalysisFlow } from '@/lib/server/analysis-flow';
import { proxyRateLimitAllowed, sameOriginRequest } from '@/lib/server/proxy-security';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const DEFAULT_BACKEND_URL = 'http://localhost:8000/api';
const DEFAULT_UPLOAD_REQUEST_LIMIT_BYTES = 100 * 1024 * 1024;
const DEFAULT_ANALYSIS_REQUEST_LIMIT_BYTES = 5 * 1024 * 1024;
const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
]);

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

type BackendRoute = {
  bucket: 'upload' | 'parse' | 'analysis' | 'sse';
  bodyLimitBytes: number;
};

function envInt(name: string, fallback: number): number {
  const value = Number.parseInt(process.env[name] ?? '', 10);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function uploadRequestLimitBytes(): number {
  return envInt('BIZBUY_MAX_UPLOAD_REQUEST_BYTES', DEFAULT_UPLOAD_REQUEST_LIMIT_BYTES);
}

function analysisRequestLimitBytes(): number {
  return envInt('BIZBUY_MAX_ANALYSIS_REQUEST_BYTES', DEFAULT_ANALYSIS_REQUEST_LIMIT_BYTES);
}

function backendRoute(method: string, segments: string[]): BackendRoute | null {
  const path = segments.join('/');
  if (method === 'POST') {
    if (path === 'documents/ingest') {
      return { bucket: 'upload', bodyLimitBytes: uploadRequestLimitBytes() };
    }
    if (path === 'parse-documents') {
      return { bucket: 'parse', bodyLimitBytes: uploadRequestLimitBytes() };
    }
    if (path === 'analyze' || path === 'analyses') {
      return { bucket: 'analysis', bodyLimitBytes: analysisRequestLimitBytes() };
    }
  }

  if (method === 'GET') {
    if (segments.length === 2 && segments[0] === 'analyses') {
      return { bucket: 'analysis', bodyLimitBytes: 0 };
    }
    if (segments.length === 3 && segments[0] === 'analyses' && segments[2] === 'events') {
      return { bucket: 'sse', bodyLimitBytes: 0 };
    }
  }

  return null;
}

function backendUrl(segments: string[], search: string): URL {
  const rawBase = process.env.BIZBUY_BACKEND_URL || DEFAULT_BACKEND_URL;
  const normalizedBase = rawBase.endsWith('/') ? rawBase : `${rawBase}/`;
  const encodedPath = segments.map((segment) => encodeURIComponent(segment)).join('/');
  const url = new URL(encodedPath, normalizedBase);
  url.search = search;
  return url;
}

function requestHeaders(req: NextRequest, flowId: string): Headers {
  const headers = new Headers();
  const contentType = req.headers.get('content-type');
  const accept = req.headers.get('accept');
  const token = process.env.BIZBUY_API_BEARER_TOKEN;

  if (contentType) headers.set('content-type', contentType);
  if (accept) headers.set('accept', accept);
  if (token) headers.set('authorization', `Bearer ${token}`);
  headers.set('x-bizbuy-flow-id', flowId);

  return headers;
}

function responseHeaders(upstreamHeaders: Headers): Headers {
  const headers = new Headers();
  upstreamHeaders.forEach((value, key) => {
    const lowerKey = key.toLowerCase();
    if (!HOP_BY_HOP_HEADERS.has(lowerKey)) {
      headers.set(key, value);
    }
  });
  headers.set('cache-control', upstreamHeaders.get('cache-control') || 'no-store');
  return headers;
}

async function readBodyWithLimit(req: NextRequest, limitBytes: number): Promise<Uint8Array | null> {
  const contentLength = req.headers.get('content-length');
  if (contentLength) {
    const parsed = Number.parseInt(contentLength, 10);
    if (Number.isFinite(parsed) && parsed > limitBytes) {
      return null;
    }
  }

  if (!req.body) {
    return new Uint8Array();
  }

  const reader = req.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = value instanceof Uint8Array ? value : new Uint8Array(value);
    total += chunk.byteLength;
    if (total > limitBytes) {
      await reader.cancel();
      return null;
    }
    chunks.push(chunk);
  }

  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

async function proxy(req: NextRequest, context: RouteContext): Promise<Response> {
  const { path = [] } = await context.params;
  const method = req.method.toUpperCase();
  const route = backendRoute(method, path);

  if (!route) {
    return NextResponse.json({ error: 'Backend route is not proxied.' }, { status: 404 });
  }

  if (method !== 'GET' && method !== 'HEAD' && !sameOriginRequest(req)) {
    return NextResponse.json({ error: 'Cross-origin backend requests are not allowed.' }, { status: 403 });
  }

  const flow = readAnalysisFlow(req);
  if (!flow) {
    return NextResponse.json({ error: 'Analysis flow authorization required.' }, { status: 401 });
  }

  if (!proxyRateLimitAllowed(req, route.bucket, flow.flowId)) {
    return NextResponse.json({ error: 'Rate limit exceeded.' }, { status: 429 });
  }

  let url: URL;
  try {
    url = backendUrl(path, req.nextUrl.search);
  } catch {
    return NextResponse.json({ error: 'Backend proxy is not configured.' }, { status: 500 });
  }

  const init: RequestInit & { duplex?: 'half' } = {
    method,
    headers: requestHeaders(req, flow.flowId),
    redirect: 'manual',
    cache: 'no-store',
    signal: req.signal,
  };

  if (method !== 'GET' && method !== 'HEAD') {
    const body = await readBodyWithLimit(req, route.bodyLimitBytes);
    if (body === null) {
      return NextResponse.json(
        {
          error: 'request_too_large',
          detail: 'Request body exceeds the configured byte limit.',
          limitBytes: route.bodyLimitBytes,
        },
        { status: 413 },
      );
    }
    const arrayBuffer = body.buffer.slice(body.byteOffset, body.byteOffset + body.byteLength) as ArrayBuffer;
    init.body = new Blob([arrayBuffer]);
  }

  try {
    const upstream = await fetch(url, init);
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders(upstream.headers),
    });
  } catch (error) {
    console.error('Backend proxy request failed:', error);
    return NextResponse.json({ error: 'Backend request failed.' }, { status: 502 });
  }
}

export async function GET(req: NextRequest, context: RouteContext): Promise<Response> {
  return proxy(req, context);
}

export async function POST(req: NextRequest, context: RouteContext): Promise<Response> {
  return proxy(req, context);
}
