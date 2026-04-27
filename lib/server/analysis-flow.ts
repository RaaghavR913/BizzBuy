import { createHmac, randomBytes, timingSafeEqual } from 'node:crypto';
import type { NextRequest, NextResponse } from 'next/server';

export const ANALYSIS_FLOW_COOKIE = 'bizbuy_analysis_flow';

const DEFAULT_FLOW_TTL_SECONDS = 60 * 60;
const devFallbackSecret = randomBytes(32).toString('hex');

export interface AnalysisFlowClaims {
  flowId: string;
  expiresAt: number;
}

function envInt(name: string, fallback: number): number {
  const value = Number.parseInt(process.env[name] ?? '', 10);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

export function analysisFlowTtlSeconds(): number {
  return envInt('BIZBUY_FLOW_TOKEN_TTL_SECONDS', DEFAULT_FLOW_TTL_SECONDS);
}

function flowSecret(): string {
  return process.env.BIZBUY_FLOW_TOKEN_SECRET || process.env.BIZBUY_API_BEARER_TOKEN || devFallbackSecret;
}

function sign(payload: string): string {
  return createHmac('sha256', flowSecret()).update(payload).digest('base64url');
}

function safeCompare(a: string, b: string): boolean {
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  if (left.byteLength !== right.byteLength) return false;
  return timingSafeEqual(left, right);
}

export function createAnalysisFlowToken(nowMs = Date.now()): AnalysisFlowClaims & { token: string } {
  const flowId = randomBytes(16).toString('hex');
  const expiresAt = Math.floor(nowMs / 1000) + analysisFlowTtlSeconds();
  const payload = `${flowId}.${expiresAt}`;
  return {
    flowId,
    expiresAt,
    token: `${payload}.${sign(payload)}`,
  };
}

export function verifyAnalysisFlowToken(token: string | undefined | null, nowMs = Date.now()): AnalysisFlowClaims | null {
  if (!token) return null;
  const parts = token.split('.');
  if (parts.length !== 3) return null;

  const [flowId, expiresAtRaw, signature] = parts;
  if (!/^[a-f0-9]{32}$/.test(flowId)) return null;

  const expiresAt = Number.parseInt(expiresAtRaw, 10);
  if (!Number.isFinite(expiresAt) || expiresAt <= Math.floor(nowMs / 1000)) return null;

  const payload = `${flowId}.${expiresAt}`;
  if (!safeCompare(signature, sign(payload))) return null;

  return { flowId, expiresAt };
}

export function readAnalysisFlow(req: NextRequest): AnalysisFlowClaims | null {
  return verifyAnalysisFlowToken(req.cookies.get(ANALYSIS_FLOW_COOKIE)?.value);
}

export function setAnalysisFlowCookie(
  req: NextRequest,
  res: NextResponse,
  token: string,
  expiresAt: number,
): void {
  res.cookies.set({
    name: ANALYSIS_FLOW_COOKIE,
    value: token,
    httpOnly: true,
    sameSite: 'lax',
    secure: shouldUseSecureCookie(req),
    path: '/',
    expires: new Date(expiresAt * 1000),
  });
}

function parseBool(value: string | undefined): boolean | null {
  if (value === undefined) return null;
  const normalized = value.trim().toLowerCase();
  if (['1', 'true', 'yes', 'on'].includes(normalized)) return true;
  if (['0', 'false', 'no', 'off'].includes(normalized)) return false;
  return null;
}

function isLocalHostname(hostname: string): boolean {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]' || hostname === '::1';
}

function shouldUseSecureCookie(req: NextRequest): boolean {
  const configured = parseBool(process.env.BIZBUY_FLOW_COOKIE_SECURE);
  if (configured !== null) return configured;

  const forwardedProto = req.headers.get('x-forwarded-proto')?.split(',', 1)[0]?.trim().toLowerCase();
  if (forwardedProto === 'https') return true;
  if (req.nextUrl.protocol === 'https:') return true;

  if (isLocalHostname(req.nextUrl.hostname)) return false;
  return process.env.NODE_ENV === 'production';
}
