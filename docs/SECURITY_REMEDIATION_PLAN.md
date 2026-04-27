# Security Remediation Plan

Date: 2026-04-26
Source: `docs/SECURITY_AUDIT_REPORT.md`
Purpose: Implementation-ready follow-on plan for the confirmed vulnerabilities from the security deployment audit

## Executive Summary

Remediation is required before public Railway and Vercel deployment.

Severity-ordered confirmed findings:

1. `critical` - `POST /api/documents/ingest` allows path traversal and arbitrary file write through attacker-controlled filenames.
2. `critical` - `POST /api/analyses` and `POST /api/pipeline` allow path traversal and arbitrary artifact writes through attacker-controlled `analysis_id` values.
3. `high` - Public OCR and LLM endpoints have no authentication, rate limiting, quota controls, or SSE connection limits.
4. `high` - Sensitive uploads, OCR artifacts, ingestion artifacts, partial reports, and prompt bodies are persisted to disk by default.

Recommended release decision:

- Do not expose the backend publicly until Wave 1, Wave 2, and the production-default portions of Wave 3 are complete.
- Treat Wave 4 and Wave 5 as release hardening work that should land before broad public launch, even if a constrained internal deployment happens earlier.

## Fix Wave Plan

## Wave 1: Block Filesystem Traversal And Storage-Key Injection

Goal: eliminate the two critical arbitrary-write paths before any public deployment.

### Scope

- sanitize or replace client-provided upload filenames
- validate or eliminate caller-provided `analysis_id`
- enforce resolved-path containment centrally for all artifact writes

### Exact Files Likely To Change

- `backend/app/api/routes/ingest_documents.py`
- `backend/app/services/analysis_repository.py`
- `backend/app/services/analysis_jobs.py`
- `backend/app/agents/orchestrator.py`
- `backend/app/models/schemas.py`
- `backend/app/agents/schemas.py`
- likely a new shared path-safety helper under `backend/app/services/` or `backend/app/core/`
- tests:
  - `backend/tests/test_ingest_documents_route.py`
  - `backend/tests/test_parse_documents_route.py`
  - add new tests for analysis job path validation

### Implementation Plan

1. Stop writing uploads under the original client filename.
   - Generate a server-side storage filename such as `<uuid><normalized-extension>`.
   - Store the original filename only in response metadata and downstream document metadata.
   - Reject filenames containing path separators only for logging clarity, but do not rely on rejection alone.

2. Add a strict safe-path helper for upload writes.
   - Accept `(root_dir, relative_name)` and return a resolved path only if it stays under `root_dir`.
   - Normalize separators, reject absolute paths, reject empty names, reject `..`, and reject reserved traversal forms on both Windows and Linux.

3. Remove caller control over artifact directory names wherever possible.
   - Preferred: always generate server-side UUID analysis IDs.
   - If resumable caller-supplied IDs are required, validate them against a strict UUID format and nothing else.

4. Add containment checks inside the repository layer, not just at the API boundary.
   - Every `get_*_ref`, `save_*`, and `load_*` path should resolve under `BIZBUY_ARTIFACT_DIR`.
   - Fail closed with a 400-style validation error for invalid IDs rather than attempting path construction.

5. Review all places that reuse `analysis_id`.
   - `POST /api/analyses`
   - `POST /api/pipeline`
   - partial report save path
   - prompt debug save path
   - ingestion artifact save path

### Validation Steps

- Add tests that attempt:
  - upload filename `../../escape.txt`
  - upload filename with backslashes such as `..\\..\\escape.txt`
  - absolute upload filename such as `/tmp/escape.txt`
  - `analysisId` values with `../`, `..\\`, leading slash, trailing slash, and empty strings
- Confirm invalid inputs return a 400-class response and do not create files.
- Confirm valid uploads still work and downstream parsing receives the original filename as metadata.
- Confirm valid server-generated analysis IDs still create readable artifacts under the configured root.

### Deployment And Config Changes

- None required for platform env vars, but existing deployed instances should not continue to accept old path keys.

### Migration / Rollback Concerns

- If any client currently depends on custom `analysisId` submission, that behavior will break and must be coordinated.
- Before deploy, inspect existing artifact directories for suspicious traversal-created files and clean them up.
- If rollback is required, do not re-enable caller-controlled path keys.

## Wave 2: Add Public Abuse Controls For OCR, LLM, Jobs, And SSE

Goal: make public routes expensive to abuse rather than cheap to exploit.

### Scope

- authentication or signed session gating
- rate limiting and quota enforcement
- concurrency limits for jobs and SSE streams
- explicit rejection of anonymous high-cost access

### Exact Files Likely To Change

- `backend/app/main.py`
- `backend/app/api/routes/ingest_documents.py`
- `backend/app/api/routes/parse_documents.py`
- `backend/app/api/routes/analyses.py`
- `backend/app/api/routes/pipeline.py`
- `backend/app/api/routes/analyze.py`
- `backend/app/services/analysis_jobs.py`
- possibly new middleware or dependency modules under `backend/app/core/` or `backend/app/api/`
- frontend callers in `lib/api-client.ts` if auth headers or signed tokens are introduced
- deployment docs:
  - `README.md`
  - `backend/README.md`

### Implementation Plan

1. Decide the minimum public access model.
   - Best option for public launch: authenticated users only.
   - Minimum acceptable fallback for limited beta: signed short-lived upload and analysis tokens plus strict rate limits.

2. Add a request identity layer.
   - Examples: session cookie, bearer token, signed JWT, or trusted proxy header if an auth gateway sits in front.
   - Reject unauthenticated calls to:
     - `POST /api/documents/ingest`
     - `POST /api/parse-documents`
     - `POST /api/analyses`
     - `POST /api/pipeline`
     - `GET /api/analyses/{analysis_id}`
     - `GET /api/analyses/{analysis_id}/events`

3. Add rate limiting.
   - Per IP and per authenticated principal
   - Separate budgets for:
     - upload attempts
     - OCR-triggering requests
     - analysis job creation
     - SSE connections

4. Add compute and storage quotas.
   - Max concurrent jobs per identity
   - Max uploads per hour
   - Max total upload bytes per window
   - Max active SSE streams per identity

5. Add defensive job gating in `analysis_jobs.py`.
   - Reject new work if concurrency thresholds are exceeded.
   - Emit clear 429 or 503 responses rather than letting the executor queue grow invisibly.

6. Add route-level audit logging for abuse signals.
   - principal
   - IP
   - route
   - file count
   - byte count
   - accepted vs rejected outcome

### Validation Steps

- Integration tests for unauthenticated requests returning 401 or 403.
- Integration tests for rate-limit exhaustion returning 429.
- SSE tests that enforce a max open connection count or max stream lifetime.
- Load-test a burst of uploads and confirm limits trigger before expensive OCR/LLM calls.
- Confirm authorized normal flows still work end to end from the frontend.

### Deployment And Config Changes

Railway backend:

- add auth secret or trusted JWT issuer config
- add rate-limit store config if using Redis or a managed store
- add environment variables for quotas and concurrency thresholds

Vercel frontend:

- if auth is introduced in-app, update frontend env and request flow accordingly
- if CAPTCHA or bot mitigation is added, add public site keys only on the frontend side

### Migration / Rollback Concerns

- Frontend and backend must roll out together if new auth headers or cookies are required.
- If using a distributed rate-limit store, degraded behavior during store outage should be defined up front.
- Avoid a rollback that re-opens anonymous OCR and analysis routes after customers have started using auth.

## Wave 3: Change Sensitive Data Handling Defaults And Add Retention Controls

Goal: ensure public production does not retain prompt bodies and customer document content by default.

### Scope

- prompt-debug defaults
- upload retention
- OCR cache retention
- analysis artifact retention
- separation of operational telemetry from customer content

### Exact Files Likely To Change

- `backend/app/core/config.py`
- `backend/app/agents/openrouter_client.py`
- `backend/app/agents/orchestrator.py`
- `backend/app/api/routes/ingest_documents.py`
- `backend/app/services/analysis_repository.py`
- `backend/app/services/intake_service.py`
- likely new cleanup or retention helpers under `backend/app/services/`
- tests:
  - `backend/tests/test_orchestrator_scoring_hook.py`
  - `backend/tests/test_ingest_documents_route.py`
  - new tests for cleanup and retention

### Implementation Plan

1. Make prompt-debug artifact creation opt-in in production.
   - Set production default for `BIZBUY_PIPELINE_PROMPT_DEBUG_ARTIFACTS_ENABLED` to `false`.
   - Set production default for `BIZBUY_PIPELINE_PROMPT_DEBUG_INCLUDE_BODIES` to `false`.
   - Consider environment-aware defaults based on `BIZBUY_ENV`.

2. Split debug metadata from sensitive prompt bodies.
   - Keep safe metrics such as token counts, stage timings, and prompt sizes.
   - Do not store `systemPrompt` or `userMessage` unless an explicit secure debug mode is enabled.

3. Add retention policies.
   - uploads: short TTL or delete immediately after parsing if not needed
   - OCR artifacts: bounded TTL and size budget
   - analysis reports: explicit retention rule
   - prompt-debug artifacts: shortest TTL of all, or disabled entirely in prod

4. Add deletion workflows.
   - synchronous deletion after successful downstream use where safe
   - scheduled cleanup job for stale directories
   - startup or periodic janitor with careful root containment checks

5. Revisit what is stored inside ingestion artifacts.
   - keep document inventory and normalized evidence if required
   - avoid persisting full raw text unless there is a strong product requirement
   - if raw evidence must remain, limit it intentionally and document retention

6. Decide whether OCR cache reuse is worth the privacy cost.
   - If yes, keep it under a bounded private storage policy.
   - If no, disable cache persistence in production and accept re-OCR cost for smaller risk.

### Validation Steps

- Production-config tests proving debug flags default to off.
- Verify no `prompt_debug.json` is created unless explicitly enabled.
- Verify prompt-debug output omits prompt bodies when bodies are disabled.
- Verify uploads and OCR artifacts are deleted or expire according to policy.
- Verify cleanup jobs do not delete outside the intended roots.

### Deployment And Config Changes

Railway backend:

- `BIZBUY_ENV=production`
- `BIZBUY_PIPELINE_PROMPT_DEBUG_ARTIFACTS_ENABLED=false`
- `BIZBUY_PIPELINE_PROMPT_DEBUG_INCLUDE_BODIES=false`
- configure private writable directories for artifacts and uploads
- add retention TTL env vars if implemented

Vercel frontend:

- none beyond ensuring the frontend does not depend on prompt-debug artifacts

### Migration / Rollback Concerns

- Existing artifact directories may already contain sensitive content and should be purged before public launch.
- If support workflows rely on prompt-debug artifacts, define a temporary secure break-glass process rather than keeping bodies enabled by default.

## Wave 4: Production Deployment Hardening

Goal: eliminate dev-mode runtime assumptions and make deployment behavior explicit for Railway and Vercel.

### Scope

- production image commands
- CORS origin correctness
- docs/OpenAPI exposure
- clearer production env guidance

### Exact Files Likely To Change

- `backend/Dockerfile`
- `Dockerfile`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `README.md`
- `backend/README.md`
- optionally add:
  - `vercel.json`
  - Railway deployment config if the team wants it

### Implementation Plan

1. Replace dev-only runtime commands.
   - backend: remove `--reload`
   - frontend container, if kept: build with `next build` and run `next start`

2. Fix backend image completeness.
   - Ensure the Railway image actually copies the full application code rather than depending on bind mounts.

3. Add explicit production CORS behavior.
   - Require `FRONTEND_ORIGIN` in production
   - reject boot with unsafe or missing production origin config

4. Decide whether API docs should be public.
   - If not, disable `/docs`, `/redoc`, and `/openapi.json` in production
   - If they must stay public, document that choice explicitly and gate it through config

5. Tighten startup logging.
   - Remove masked secret-value logging in production
   - Keep only non-sensitive config posture logs

6. Document the Railway plus Vercel deployment matrix clearly.
   - frontend envs
   - backend envs
   - required domains
   - artifact retention expectations

### Validation Steps

- Build the backend image without bind mounts and confirm it starts successfully.
- Confirm production backend process does not use `--reload`.
- Confirm frontend container, if used, runs `next start` after a production build.
- Confirm production boot fails fast if `FRONTEND_ORIGIN` is missing or unsafe.
- Confirm `/docs` and `/openapi.json` behave according to the chosen production policy.

### Deployment And Config Changes

Railway backend:

- set `FRONTEND_ORIGIN` to exact Vercel production origin(s)
- decide whether docs are enabled
- choose private volume or ephemeral storage deliberately, not implicitly

Vercel frontend:

- set `NEXT_PUBLIC_BACKEND_URL`
- set `NEXT_PUBLIC_APP_URL`

### Migration / Rollback Concerns

- Disabling docs in production may affect existing internal workflows.
- Tightened CORS can break the frontend if the Vercel domain list is incomplete.

## Wave 5: Dependency And Documentation Closure

Goal: close the remaining audit gaps and prevent unsafe drift.

### Scope

- current dependency advisory scan
- CI enforcement
- doc cleanup for secure deployment

### Exact Files Likely To Change

- `package.json`
- `package-lock.json`
- `backend/pyproject.toml`
- CI workflow files if present
- `README.md`
- `backend/README.md`
- possibly new security runbooks under `docs/`

### Implementation Plan

1. Run a real dependency advisory pass in a tool-capable environment.
   - `npm audit --omit=dev`
   - `npm audit`
   - Python dependency audit using `pip-audit` or equivalent

2. Patch or pin any confirmed high or critical runtime issues.

3. Add CI checks.
   - Node dependency audit
   - Python dependency audit
   - basic static checks for dangerous defaults if practical

4. Update docs so future deploys follow the secure path by default.
   - clear production env matrix
   - auth and rate-limit expectations
   - retention expectations
   - no suggestion that `.env.local` or dev compose settings map directly to production

### Validation Steps

- CI passes with no unresolved high or critical runtime advisories.
- Deployment docs are reviewed against an actual Railway and Vercel setup flow.

### Deployment And Config Changes

- none beyond dependency updates and any new CI secrets required for scans

### Migration / Rollback Concerns

- Dependency updates can change runtime behavior; stage them after the critical path and abuse-control fixes.

## Cross-Wave Validation Checklist

A release candidate should not be considered public-deployable until all of the following are true:

- upload filenames cannot escape the intended storage root
- artifact IDs cannot escape the intended artifact root
- public expensive routes require authorization or equivalent signed access
- rate limits and quotas are enforced
- prompt-debug artifacts are off by default in production
- prompt bodies are not stored by default in production
- uploads, OCR cache, and analysis artifacts have explicit retention behavior
- Railway backend does not run `--reload`
- production CORS origins are explicit and correct
- dependency advisory scans pass in CI for runtime packages

## Recommended Implementation Order

1. Wave 1
2. Wave 2
3. Wave 3 production-default changes
4. Wave 4
5. Wave 5

Reasoning:

- Wave 1 removes direct filesystem compromise paths.
- Wave 2 closes the easiest public abuse path against paid services.
- Wave 3 reduces the damage radius of normal usage and any later compromise.
- Wave 4 makes the deployment posture production-safe.
- Wave 5 closes the remaining supply-chain and documentation gaps.
