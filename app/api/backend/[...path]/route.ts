import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const DEFAULT_BACKEND_URL = 'http://localhost:8000/api';
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

function isAllowedBackendRoute(method: string, segments: string[]): boolean {
  if (method === 'POST') {
    return (
      segments.join('/') === 'documents/ingest' ||
      segments.join('/') === 'parse-documents' ||
      segments.join('/') === 'analyze' ||
      segments.join('/') === 'analyses'
    );
  }

  if (method === 'GET') {
    return (
      (segments.length === 2 && segments[0] === 'analyses') ||
      (segments.length === 3 && segments[0] === 'analyses' && segments[2] === 'events')
    );
  }

  return false;
}

function backendUrl(segments: string[], search: string): URL {
  const rawBase = process.env.BIZBUY_BACKEND_URL || DEFAULT_BACKEND_URL;
  const normalizedBase = rawBase.endsWith('/') ? rawBase : `${rawBase}/`;
  const encodedPath = segments.map((segment) => encodeURIComponent(segment)).join('/');
  const url = new URL(encodedPath, normalizedBase);
  url.search = search;
  return url;
}

function requestHeaders(req: NextRequest): Headers {
  const headers = new Headers();
  const contentType = req.headers.get('content-type');
  const accept = req.headers.get('accept');
  const token = process.env.BIZBUY_API_BEARER_TOKEN;

  if (contentType) headers.set('content-type', contentType);
  if (accept) headers.set('accept', accept);
  if (token) headers.set('authorization', `Bearer ${token}`);

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

async function proxy(req: NextRequest, context: RouteContext): Promise<Response> {
  const { path = [] } = await context.params;
  const method = req.method.toUpperCase();

  if (!isAllowedBackendRoute(method, path)) {
    return NextResponse.json({ error: 'Backend route is not proxied.' }, { status: 404 });
  }

  let url: URL;
  try {
    url = backendUrl(path, req.nextUrl.search);
  } catch {
    return NextResponse.json({ error: 'Backend proxy is not configured.' }, { status: 500 });
  }

  const init: RequestInit & { duplex?: 'half' } = {
    method,
    headers: requestHeaders(req),
    redirect: 'manual',
    cache: 'no-store',
    signal: req.signal,
  };

  if (method !== 'GET' && method !== 'HEAD') {
    init.body = req.body;
    init.duplex = 'half';
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
