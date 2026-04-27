# Railway Production Hardening Plan

Date: 2026-04-27
Audience: GPT-5.5 extra-high reasoning agent
Purpose: Complete the remaining security and deployment work for a Railway production deployment.

## Target Architecture

Deploy on Railway as two services:

1. `bizzbuy-web`: public Next.js frontend.
2. `bizzbuy-api`: FastAPI backend, private/internal if possible.

The browser must not call the protected backend directly with a bearer token. The frontend should act as a small server-side proxy/BFF for backend calls. Keep `BIZBUY_API_BEARER_TOKEN` only in Railway server-side environment variables, never in `NEXT_PUBLIC_*`.

## Phase 1: Railway Deployment Topology

Goal: make the deployment shape explicit before changing code.

Tasks:

- Create or document two Railway services:
  - `bizzbuy-web` for the Next.js app.
  - `bizzbuy-api` for the FastAPI backend.
- Configure the frontend service to reach the backend service over Railway internal networking where possible.
- Keep backend production auth enabled:
  - `BIZBUY_ENV=production`
  - `BIZBUY_REQUIRE_EXPENSIVE_ROUTE_AUTH=true`
  - `BIZBUY_API_BEARER_TOKEN=<strong-secret>`
- Do not expose `BIZBUY_API_BEARER_TOKEN` to browser code.

Acceptance criteria:

- Browser calls only same-origin frontend API routes.
- Backend bearer token exists only in server-side Railway env vars.
- Backend direct public access is either disabled or requires auth.

## Phase 2: Add Next.js Backend Proxy

Goal: let browser code call same-origin Next.js routes while Next.js attaches backend auth server-side.

Create server-side proxy routes under `app/api/backend/...` or an equivalent naming scheme.

Proxy these backend routes:

- `POST /documents/ingest`
- `POST /parse-documents`
- `POST /analyze`
- `POST /analyses`
- `GET /analyses/:id`
- `GET /analyses/:id/events`

Tasks:

- Update `lib/api-client.ts` so browser code calls same-origin Next.js routes instead of `NEXT_PUBLIC_BACKEND_URL`.
- Attach `Authorization: Bearer ${BIZBUY_API_BEARER_TOKEN}` only inside server-side route handlers.
- Preserve multipart upload behavior.
- Preserve JSON request and response shapes.
- Carefully handle SSE streaming for analysis events.
- Remove any need for browser-visible backend auth.

Acceptance criteria:

- No browser bundle contains `BIZBUY_API_BEARER_TOKEN`.
- Upload, parse, analysis job creation, job polling, SSE progress, and report loading still work.
- Backend production auth can stay enabled without breaking the frontend.

## Phase 3: Railway Environment Matrix

Goal: document the exact Railway env vars so production setup is repeatable.

Frontend Railway service:

```env
BIZBUY_BACKEND_URL=http://<backend-internal-host>:8000/api
BIZBUY_API_BEARER_TOKEN=<same-secret-as-backend>
NEXT_PUBLIC_APP_URL=https://<frontend-domain>
```

Backend Railway service:

```env
BIZBUY_ENV=production
FRONTEND_ORIGIN=https://<frontend-domain>
BIZBUY_API_BEARER_TOKEN=<strong-secret>
OPENROUTER_API_KEY=<secret>
MISTRAL_API_KEY=<secret>
OPENROUTER_REFERRER=https://<frontend-domain>
BIZBUY_API_DOCS_ENABLED=false
BIZBUY_PIPELINE_PROMPT_DEBUG_ARTIFACTS_ENABLED=false
BIZBUY_PIPELINE_PROMPT_DEBUG_INCLUDE_BODIES=false
BIZBUY_DELETE_UPLOADS_AFTER_INGEST=true
```

Tasks:

- Update `README.md` and `backend/README.md` with Railway-specific deployment instructions.
- Remove or clearly mark any local-only Docker Compose guidance.
- Document that `BIZBUY_API_BEARER_TOKEN` is server-only and must not use a `NEXT_PUBLIC_` prefix.

Acceptance criteria:

- Docs explain how to deploy the two Railway services.
- Docs do not suggest exposing backend bearer tokens publicly.

## Phase 4: Docker Context And Sensitive Files

Goal: prevent local artifacts, uploads, and customer/sample data from being sent to remote builders.

Update root `.dockerignore` to exclude at least:

```text
uploads
backend/.artifacts
backend/backend/.artifacts
backend/.test-artifacts
backend/backend/.test-artifacts
sample company*
.env*
.vercel
```

Update `backend/.dockerignore` to exclude at least:

```text
.artifacts
backend/.artifacts
uploads
backend/uploads
.test-artifacts
backend/.test-artifacts
```

Tasks:

- Confirm whether tracked `sample company*` files are synthetic.
- If any tracked sample files contain real customer data, stop and ask for a decision on removal and history purge.
- Ensure local generated artifacts are not copied into build contexts.

Acceptance criteria:

- Railway build contexts do not receive local artifacts, uploads, or non-synthetic sample data.
- Any real sample/customer data is removed before production deployment.

## Phase 5: Opaque OCR Artifact References

Goal: stop exposing server filesystem paths in API responses.

Current concern:

- `ocrArtifactRef` can contain a server filesystem path.

Implementation direction:

- Return an opaque ref such as `ocr:<sha256>` or just the validated file hash.
- Resolve opaque refs inside the backend only.
- Keep existing path-based parsing support only if needed for backward compatibility.
- Do not return filesystem paths to clients.

Acceptance criteria:

- API responses do not expose server paths.
- Cached OCR reuse still works.
- Path traversal tests remain green.

## Phase 6: Upload, Parser, And PDF Abuse Hardening

Goal: reduce denial-of-service risk from large or complex inputs.

Tasks:

- Add a max file count per upload request.
- Add stricter per-request byte caps.
- Add early multipart/body size controls where practical.
- Add XLSX/DOCX zip entry-count caps.
- Add XLSX/DOCX decompressed-size caps.
- Add app-level body size and schema validation for `app/api/generate-pdf/route.ts`.
- Ensure error responses do not leak stack traces or internal paths.

Acceptance criteria:

- Tests cover too many files.
- Tests cover oversized upload requests.
- Tests cover oversized or suspicious zip payloads.
- Tests cover invalid PDF-generation payloads.

## Phase 7: Production Rate Limits

Goal: make abuse controls match Railway's deployment model.

Current limitation:

- Backend rate limits and SSE counters are in-memory.
- `_client_ip()` currently trusts `x-forwarded-for`.

Tasks:

- For a single-instance beta, document that in-memory rate limits are a temporary defense.
- For safer production, use Redis-backed limits or a trusted gateway.
- Decide whether Railway service topology provides a trusted proxy boundary.
- Do not trust arbitrary `x-forwarded-for` unless the request came through an explicitly trusted proxy path.
- Keep backend limits as defense in depth even if an external gateway is used.

Acceptance criteria:

- Rate-limit behavior is explicit in docs.
- Trusted client IP handling is documented or fixed.
- SSE/job abuse controls remain tested.

## Phase 8: Dependency Closure

Goal: clear known dependency advisories before launch.

Run:

```bash
npm audit --omit=dev
npm audit
python -m pip_audit .
python -m pytest -q
npm run lint
npm run build
```

Tasks:

- Address all high or critical runtime advisories.
- Investigate the moderate Next/PostCSS advisory and upgrade safely if a fix is available.
- Document any accepted moderate advisory with reason and mitigation.

Acceptance criteria:

- No unresolved high or critical runtime advisories remain.
- Tests and production build pass.
- Any remaining moderate advisory is explicitly documented.

## Phase 9: Railway Staging Verification

Goal: prove the production flow works in a Railway-like environment.

Test on Railway staging:

- Upload sample documents.
- Parse documents.
- Start an analysis.
- Receive SSE progress updates.
- View completed report.
- Generate PDF.
- Confirm backend direct public access is blocked or requires auth.
- Confirm `/docs`, `/redoc`, and `/openapi.json` are disabled in production.
- Confirm no prompt-debug bodies are created.
- Confirm uploads are deleted after ingest if configured.

Acceptance criteria:

- Full user flow works through the frontend service.
- Backend expensive routes are not anonymously callable.
- Production-sensitive debug and docs endpoints are off.

## Definition Of Done

This work is complete only when all of the following are true:

- Browser never talks directly to protected backend routes with a public token.
- Backend expensive routes require auth in production.
- Railway deployment docs are accurate.
- Docker contexts exclude sensitive and generated data.
- No server filesystem paths leak in API responses.
- Upload, parser, and PDF abuse limits exist.
- Rate-limit limitations are either fixed or clearly documented for the Railway topology.
- Dependency audits show no unresolved high or critical runtime advisories.
- Backend tests, frontend lint, and frontend build pass.

