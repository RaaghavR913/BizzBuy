# GPT-5.5 Security Completion Plan

Date: 2026-04-27
Target agent: GPT-5.5, high reasoning
Purpose: Complete the remaining production security hardening after the latest repository-wide security pass.
Status: Completed on 2026-04-27. See `docs/SECURITY_COMPLETION_REPORT.md` for the implementation summary, verification results, and residual risks.

## Goal

Bring the repo to a safer public-deployment posture for a Next.js frontend plus FastAPI backend without undoing the recent security fixes.

The earlier critical path traversal bugs appear fixed. Do not rework them unless tests reveal a regression. Focus on the remaining risks:

- Public Next.js proxy can anonymously spend backend OCR/LLM budget.
- Upload and multipart request limits are not enforced early enough.
- OCR cache references are not bound to the uploaded file or user/session.
- Report URLs are capability links without owner/session binding.
- Tracked sample-company documents may contain sensitive fixture data.
- Docker and HTTP response security headers need deployment hardening.

## Operating Rules

- Start with `git status --short` and do not revert unrelated user changes.
- Do not print `.env.local` or any secret values.
- Prefer small, testable changes over sweeping rewrites.
- Keep backend access tokens server-only; never introduce `NEXT_PUBLIC_*` secrets.
- Preserve the frontend browser contract unless a security fix truly requires a UX change.
- Add or update tests for every behavior change that protects a security boundary.

## Current Evidence To Reconfirm

Run these before editing:

```powershell
git status --short
npm audit --omit=dev
python -m pip_audit .  # from backend/
npm run lint
python -m pytest -q tests/test_security_controls.py tests/test_security_path_safety.py  # from backend/
```

Also inspect these files first:

- `app/api/backend/[...path]/route.ts`
- `lib/api-client.ts`
- `context/AnalysisContext.tsx`
- `backend/app/api/routes/ingest_documents.py`
- `backend/app/api/routes/parse_documents.py`
- `backend/app/services/intake_service.py`
- `backend/app/api/routes/analyses.py`
- `backend/app/core/security.py`
- `backend/app/core/config.py`
- `docker-compose.production.yml`
- `Dockerfile`
- `backend/Dockerfile`
- `next.config.mjs`

## Phase 1: Protect The Public Next.js Proxy

Problem: `app/api/backend/[...path]/route.ts` correctly injects `BIZBUY_API_BEARER_TOKEN` server-side, but any public browser/client can call the proxy. That means anonymous users can still trigger OCR, parsing, analysis jobs, polling, and SSE through the frontend origin.

Implement one of these, in this preference order:

1. If the app already has or is about to have real auth, require an authenticated user/session for proxied expensive routes.
2. If full auth is out of scope, add a server-issued short-lived flow token for the analyze flow and require it on:
   - `POST /api/backend/documents/ingest`
   - `POST /api/backend/parse-documents`
   - `POST /api/backend/analyses`
   - `GET /api/backend/analyses/{id}`
   - `GET /api/backend/analyses/{id}/events`
3. Add a Next-layer rate limiter keyed by user/session when available, otherwise by trusted client IP.

Implementation notes:

- Do not rely only on FastAPI rate limits, because the backend may see the proxy identity rather than a true end user.
- Do not put backend bearer tokens in browser-visible state.
- Keep SSE usable with `EventSource`, which cannot set custom headers. Prefer a same-origin secure cookie or short-lived query token issued by the frontend, not the backend bearer token.

Tests or validation:

- Missing public-flow auth is rejected before proxying to FastAPI.
- Valid flow can still upload, parse, create a job, poll, and open SSE.
- Rate-limited callers get `429`.
- Verify no browser bundle contains `BIZBUY_API_BEARER_TOKEN`.

## Phase 2: Enforce Upload And Body Limits Early

Problem: backend routes validate file sizes after multipart parsing and whole-file reads. A large request can consume memory/disk before application checks run.

Tasks:

- Add a Next.js proxy request-size guard for allowed backend upload/analysis routes.
- Add backend ASGI middleware or deployment guidance to enforce maximum request body size before FastAPI parses multipart data.
- Keep per-file and total-request limits aligned across:
  - `components/upload/FileDropZone.tsx`
  - `backend/app/api/routes/ingest_documents.py`
  - `backend/app/api/routes/parse_documents.py`
  - `.env.example`
  - deployment docs
- Consider reducing public defaults from 50 MB per file and 100 MB per request unless product requirements demand them.
- Bound concurrent OCR classification inside `ingest_documents.py` so one request cannot spawn OCR work for every file at once without a cap.

Tests or validation:

- Oversized `Content-Length` gets `413` without calling OCR/parser code.
- Oversized streaming body still gets rejected.
- Too many files still gets `400`.
- Valid uploads still work.

## Phase 3: Bind OCR Cache References To Actual Uploads

Problem: `/parse-documents` accepts client-provided `fileHashes` and `ocrArtifactRefs`; `intake_service.py` uses them to read cached OCR artifacts. These refs are path-safe now, but they are not clearly bound to the file bytes being parsed.

Tasks:

- Recompute SHA-256 for each uploaded file in `/parse-documents`.
- Only honor a provided `fileHash` if it equals the recomputed hash.
- Only honor `ocrArtifactRef` when it resolves to the same recomputed hash.
- Prefer passing trusted server-computed hashes to `normalize_upload_files`, not raw client values.
- Consider moving OCR artifact lookup behind a repository/helper that never accepts arbitrary paths; only `ocr:<sha256>` or SHA-256 digest should remain supported.

Tests:

- Mismatched file hash does not load the OCR cache.
- Mismatched `ocrArtifactRef` does not load another file's artifact.
- Valid hash/ref still reuses cached OCR.
- Traversal-like refs remain rejected.

## Phase 4: Bind Analysis Reports To A Principal Or Flow

Problem: report pages use `?aid=<uuid>` as a resumable/shareable capability link. UUID guessing is not practical, but leaked URLs expose sensitive reports.

Tasks:

- Decide whether reports are intentionally shareable. If yes, document that `aid` is a bearer capability and add an expiration option.
- If not intentionally shareable, bind analysis IDs to the authenticated user/session/flow token created in Phase 1.
- Store ownership metadata in the analysis artifact/job record.
- Require that owner/session on:
  - `GET /analyses/{analysis_id}`
  - `GET /analyses/{analysis_id}/events`
  - any future report download endpoint
- Avoid putting sensitive artifacts in URL parameters if a secure cookie/session can carry the binding.

Tests:

- Owner can read and stream their job.
- Different session/user cannot read or stream the job.
- Invalid UUID still returns a clean `400`.
- Missing job still returns `404`.

## Phase 5: Decide What To Do With Tracked Sample Documents

Problem: `git ls-files` currently shows tracked sample-company files under `sample company1/` and `sample company3 - LoneStar Plumbing/`. `.gitignore` ignores new sample-company paths, but existing tracked files remain tracked.

Tasks:

- Confirm whether these documents are fully synthetic and safe to keep.
- If not safe, remove them from the working tree and history with an approved history-rewrite plan.
- If safe, add a short `docs/SAMPLE_DATA_CLASSIFICATION.md` note stating that sample data is synthetic and approved for repo use.
- Ensure future test fixtures live under an explicitly named sanitized fixture directory.

Validation:

```powershell
git ls-files | rg "sample company|\\.docx$|\\.xlsx$|\\.xls$|\\.csv$"
```

## Phase 6: Production Deployment Hardening

Tasks:

- Restrict `docker-compose.production.yml` so the backend is not publicly published unless explicitly intended. Prefer internal service networking with only the frontend public.
- Add non-root users to both Docker images.
- Consider pinning Node/Python images by digest or at least using more specific patch tags.
- Add production security headers in `next.config.mjs`:
  - `Content-Security-Policy`
  - `Strict-Transport-Security` for HTTPS deployments
  - `X-Frame-Options` or CSP `frame-ancestors`
  - `Referrer-Policy`
  - `X-Content-Type-Options`
- Verify FastAPI production settings still fail fast for unsafe CORS, missing bearer token, and docs exposure.

Tests or validation:

- `next build` succeeds.
- Headers are visible on key pages and API responses.
- Production compose does not accidentally expose backend directly unless an env flag opts in.
- Backend `/docs`, `/redoc`, and `/openapi.json` remain disabled by default in production.

## Phase 7: Final Verification

Run the full focused verification suite:

```powershell
npm run lint
npm audit --omit=dev
npm run build
```

From `backend/`:

```powershell
python -m pip_audit .
python -m pytest -q
```

Add manual smoke checks:

- Start local dev stack and run the analyze flow with a small valid file.
- Confirm unauthenticated or tokenless proxy calls are blocked if Phase 1 implemented auth/flow tokens.
- Confirm one valid analysis can upload, parse, create a job, stream progress, and render a report.
- Confirm an oversized upload is rejected cleanly.
- Confirm a mismatched OCR ref cannot affect parsing.

## Expected Deliverables

At completion, update or create:

- Code changes for Phases 1-6 as needed.
- Tests covering new security behavior.
- README or deployment doc updates for any new env vars.
- A short implementation report under `docs/SECURITY_COMPLETION_REPORT.md` that lists:
  - changes made
  - security gaps closed
  - commands run and results
  - any residual risks or intentional tradeoffs

## Completion Criteria

The work is complete when:

- Public expensive routes have an end-user abuse-control story at the Next.js boundary.
- Large requests are rejected before they can force expensive parsing or OCR work.
- OCR cache reuse is bound to actual uploaded bytes.
- Analysis report reads are bound to a principal, flow token, or explicitly documented share-token model.
- Production deployment no longer exposes avoidable backend, root-container, or missing-header risk.
- Dependency, lint, build, and backend test checks pass or have documented, non-security blockers.
