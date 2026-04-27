import type { NextRequest } from 'next/server';

type RateBucket = 'flow' | 'upload' | 'parse' | 'analysis' | 'sse';

interface RateWindow {
  resetAt: number;
  count: number;
}

const rateWindows = new Map<string, RateWindow>();

const DEFAULT_LIMITS: Record<RateBucket, number> = {
  flow: 20,
  upload: 20,
  parse: 30,
  analysis: 30,
  sse: 60,
};

function envInt(name: string, fallback: number): number {
  const value = Number.parseInt(process.env[name] ?? '', 10);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function bucketLimit(bucket: RateBucket): number {
  const envName = `BIZBUY_PROXY_${bucket.toUpperCase()}_RATE_LIMIT`;
  return envInt(envName, DEFAULT_LIMITS[bucket]);
}

function rateWindowSeconds(): number {
  return envInt('BIZBUY_PROXY_RATE_LIMIT_WINDOW_SECONDS', 60);
}

function csv(value: string | undefined): string[] {
  if (!value) return [];
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function originFromUrl(value: string | undefined): string | null {
  if (!value) return null;
  try {
    return new URL(value).origin;
  } catch {
    return null;
  }
}

function forwardedOrigin(req: NextRequest): string | null {
  const forwardedHost = req.headers.get('x-forwarded-host')?.split(',', 1)[0]?.trim();
  const forwardedProto = req.headers.get('x-forwarded-proto')?.split(',', 1)[0]?.trim();
  if (!forwardedHost) return null;
  return `${forwardedProto || req.nextUrl.protocol.replace(':', '')}://${forwardedHost}`;
}

function hostHeaderOrigin(req: NextRequest): string | null {
  const host = req.headers.get('host');
  if (!host) return null;
  return `${req.nextUrl.protocol}//${host}`;
}

function isLoopback(hostname: string): boolean {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]' || hostname === '::1';
}

function loopbackEquivalent(left: string, right: string): boolean {
  try {
    const leftUrl = new URL(left);
    const rightUrl = new URL(right);
    return (
      isLoopback(leftUrl.hostname) &&
      isLoopback(rightUrl.hostname) &&
      leftUrl.port === rightUrl.port &&
      leftUrl.protocol === rightUrl.protocol
    );
  } catch {
    return false;
  }
}

function allowedOrigins(req: NextRequest): Set<string> {
  return new Set(
    [
      req.nextUrl.origin,
      forwardedOrigin(req),
      hostHeaderOrigin(req),
      originFromUrl(process.env.NEXT_PUBLIC_APP_URL),
      ...csv(process.env.BIZBUY_ALLOWED_FLOW_ORIGINS).map(originFromUrl),
    ].filter((origin): origin is string => Boolean(origin)),
  );
}

export function clientIp(req: NextRequest): string {
  const forwardedFor = req.headers.get('x-forwarded-for')?.split(',', 1)[0]?.trim();
  return (
    forwardedFor ||
    req.headers.get('x-real-ip') ||
    req.headers.get('cf-connecting-ip') ||
    'unknown'
  );
}

function checkCounter(key: string, limit: number): boolean {
  if (limit <= 0) return true;
  const now = Date.now();
  const resetAt = now + rateWindowSeconds() * 1000;
  const current = rateWindows.get(key);
  const window = current && current.resetAt > now ? current : { resetAt, count: 0 };
  if (window.count + 1 > limit) {
    rateWindows.set(key, window);
    return false;
  }
  window.count += 1;
  rateWindows.set(key, window);
  return true;
}

export function proxyRateLimitAllowed(req: NextRequest, bucket: RateBucket, flowId?: string): boolean {
  const limit = bucketLimit(bucket);
  const ipAllowed = checkCounter(`${bucket}:ip:${clientIp(req)}`, limit);
  const flowAllowed = flowId ? checkCounter(`${bucket}:flow:${flowId}`, limit) : true;
  return ipAllowed && flowAllowed;
}

export function sameOriginRequest(req: NextRequest): boolean {
  const origin = req.headers.get('origin');
  if (!origin) return true;
  const allowed = allowedOrigins(req);
  if (allowed.has(origin)) return true;
  return Array.from(allowed).some((candidate) => loopbackEquivalent(origin, candidate));
}
