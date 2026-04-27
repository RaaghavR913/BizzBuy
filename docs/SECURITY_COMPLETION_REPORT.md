# Security Completion Report

Date: 2026-04-27

## Changes Made

- Added a Next.js analysis-flow gate: `/api/analysis-flow` now issues an HttpOnly same-origin cookie, and `/api/backend/*` requires a valid flow before proxying expensive upload, parse, analysis, poll, and SSE routes.
- Added in-memory Next proxy rate limits keyed by client IP and flow ID, plus proxy request-body limits before forwarding to FastAPI.
- Added FastAPI ASGI request-body limiting before multipart parsing for upload/parse routes and JSON analysis routes.
- Added configurable per-file upload limits and bounded concurrent OCR classification work.
- Changed `/parse-documents` to recompute SHA-256 hashes from uploaded bytes, pass only server-computed hashes to parsing, and honor OCR artifact refs only when they match the recomputed hash.
- Removed filesystem-path OCR artifact refs; only `ocr:<sha256>` and raw SHA-256 digest refs are accepted.
- Added analysis job owner-flow metadata and enforced it on job status and SSE reads when jobs are created through the Next flow.
- Hardened production deployment config: backend is no longer publicly published in production compose, frontend/backend containers run as non-root users, and Next security headers are configured.
- Added env documentation for flow-token, proxy rate limit, upload/body limit, and OCR concurrency settings.
- Adjusted the flow cookie `Secure` flag so local `next start` over HTTP can still classify uploads, while HTTPS and non-local production hosts keep secure cookies by default.
- Made the flow-origin check aware of forwarded hosts, configured app URLs, local loopback aliases, and `BIZBUY_ALLOWED_FLOW_ORIGINS`.
- Stopped transient upload errors and loading state from being restored during client hydration.
- Added `docs/SAMPLE_DATA_CLASSIFICATION.md` documenting tracked sample-company files as synthetic approved fixtures.

## Security Gaps Closed

- Anonymous browsers can no longer call the public Next backend proxy without first receiving a server-issued flow cookie.
- Oversized request bodies are rejected at the Next boundary and by backend ASGI middleware before route code performs OCR or parsing work.
- OCR cache reuse is now bound to the bytes actually uploaded in the parse request.
- Report/job reads through the proxied flow are bound to the flow that created the analysis job.
- Production compose no longer exposes the backend port directly by default.
- Browser security headers are present on Next pages and API routes.

## Verification

- `git status --short`: reviewed before editing.
- `npm audit --omit=dev`: passed, 0 vulnerabilities.
- `python -m pip_audit .` from `backend/`: passed, no known vulnerabilities.
- `npm run lint`: passed with 2 pre-existing warnings in `components/ui/CardNav.tsx` and `lib/calculations.ts`.
- `python -m pytest -q tests/test_security_controls.py tests/test_security_path_safety.py`: passed before edits, 23 passed.
- `python -m pytest -q tests/test_security_controls.py tests/test_security_path_safety.py tests/test_parse_documents_route.py`: passed after edits, 33 passed.
- `npm run build`: passed after fixing a TypeScript body type issue.
- `python -m pytest -q` from `backend/`: passed, 206 passed.
- `rg -n "BIZBUY_API_BEARER_TOKEN" .next/static`: no browser-bundle matches.
- Local `next start` header smoke on `/analyze/upload`: confirmed CSP, HSTS, Referrer-Policy, X-Content-Type-Options, and X-Frame-Options headers.
- Local `next start` HTTP upload smoke on `127.0.0.1`: confirmed the flow cookie is sent without `Secure` locally and `/api/backend/documents/ingest` returns `200`.
- Local `next start` forwarded-HTTPS cookie smoke: confirmed `x-forwarded-proto: https` receives a `Secure` flow cookie.

## Residual Risks

- The flow cookie is an abuse-control/session binding layer, not full user authentication. Real accounts should replace or wrap it before multi-user production use.
- Next proxy rate limits are in-memory. Multi-instance deployments should move rate windows to Redis or a platform rate-limiting layer.
- Backend rate limits are also in-memory and should be centralized for horizontally scaled FastAPI deployments.
- Full live OCR/LLM analyze-flow smoke was not run because it requires external API keys and paid provider calls.
- Existing lint warnings remain unrelated to this pass.
