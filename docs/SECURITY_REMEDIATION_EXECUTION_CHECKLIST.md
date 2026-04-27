# Security Remediation Execution Checklist

Date: 2026-04-26
Purpose: Hand-off checklist for the next implementation agent
Use with:

- `docs/SECURITY_AUDIT_REPORT.md`
- `docs/SECURITY_REMEDIATION_PLAN.md`

## What "Tool-Capable Environment" Means

The dependency-audit part was not completed in the audit pass because this environment could not run the required audit tools:

- `npm audit` failed because `npm` was not installed or not available on PATH
- `python -m pip_audit` failed because `pip_audit` was not installed

So the next agent needs an environment where these actually work, for example:

- Node.js and npm installed and usable
- Python package auditing available, such as `pip-audit`
- enough access to install missing audit tooling if needed

This does not mean the repo is broken there. It means the security audit could not truthfully clear dependency advisories from this specific shell environment.

## Working Rule For The Next Agent

- Implement fixes in waves
- Do not mix large unrelated refactors into the security pass
- Keep all path-safety fixes centralized and testable
- Prefer server-generated identifiers over caller-controlled storage keys
- Validate after each wave before moving on

## Preflight

1. Read:
   - `docs/SECURITY_AUDIT_REPORT.md`
   - `docs/SECURITY_REMEDIATION_PLAN.md`
   - this checklist
2. Run:
   - `git status --short`
3. Do not revert unrelated user changes.
4. Confirm current behavior in:
   - `backend/app/api/routes/ingest_documents.py`
   - `backend/app/services/analysis_repository.py`
   - `backend/app/services/analysis_jobs.py`
   - `backend/app/agents/orchestrator.py`
5. Add or update tests as each fix lands. Do not leave critical fixes untested.

## Wave 1: Fix The Two Critical Filesystem Write Bugs

### Goal

Block path traversal and arbitrary file writes from:

- attacker-controlled upload filenames
- attacker-controlled `analysis_id`

### Files To Inspect First

- `backend/app/api/routes/ingest_documents.py`
- `backend/app/services/analysis_repository.py`
- `backend/app/services/analysis_jobs.py`
- `backend/app/agents/orchestrator.py`
- `backend/app/models/schemas.py`
- `backend/app/agents/schemas.py`

### Implementation Tasks

1. Replace client-controlled upload storage names.
   - Do not write files using `upload.filename` directly.
   - Generate a server-side filename instead.
   - Preserve the original filename only as metadata.

2. Add a shared safe-path helper.
   - It should reject absolute paths.
   - It should reject traversal like `..` and mixed slash forms.
   - It should resolve the final path and verify it stays inside the intended root.

3. Lock down `analysis_id`.
   - Best option: ignore caller-provided storage IDs and generate UUIDs server-side.
   - If caller-provided IDs must stay, only allow strict UUID format.

4. Enforce path containment inside the repository layer.
   - Do not rely only on route-level validation.
   - Protect all artifact reads and writes.

5. Review all artifact save points.
   - ingestion artifacts
   - analysis jobs
   - analysis reports
   - prompt debug artifacts
   - partial reports

### Tests Required

- upload filename with `../../escape.txt`
- upload filename with `..\\..\\escape.txt`
- upload filename with absolute path form
- `analysis_id` with `../escape`
- `analysis_id` with `..\\escape`
- `analysis_id` with leading slash
- valid upload still succeeds
- valid analysis still writes under artifact root

### Wave 1 Exit Criteria

- No attacker-controlled path segment can escape upload or artifact roots.
- Invalid path-like IDs return a clean client error.
- Tests cover both Linux-style and Windows-style traversal attempts.

## Wave 2: Add Abuse Controls To Public Expensive Routes

### Goal

Stop anonymous users from cheaply burning OCR/LLM credits or tying up SSE/job resources.

### Files To Inspect First

- `backend/app/main.py`
- `backend/app/api/routes/ingest_documents.py`
- `backend/app/api/routes/parse_documents.py`
- `backend/app/api/routes/analyses.py`
- `backend/app/api/routes/pipeline.py`
- `backend/app/api/routes/analyze.py`
- `backend/app/services/analysis_jobs.py`
- `lib/api-client.ts`

### Implementation Tasks

1. Choose access model.
   - Preferred: authenticated users only.
   - Minimum fallback: signed short-lived tokens plus strict rate limits.

2. Protect these routes:
   - `POST /api/documents/ingest`
   - `POST /api/parse-documents`
   - `POST /api/analyses`
   - `GET /api/analyses/{analysis_id}`
   - `GET /api/analyses/{analysis_id}/events`
   - `POST /api/pipeline`

3. Add rate limiting.
   - per IP
   - per authenticated identity
   - separate limits for uploads, OCR, analysis creation, and SSE

4. Add concurrency and quota controls.
   - max active jobs
   - max active SSE streams
   - max upload bytes per window

5. Make rejections explicit.
   - use 401 or 403 for auth failures
   - use 429 for throttling
   - use 503 only for intentional service unavailability

### Tests Required

- unauthenticated expensive route request rejected
- throttled request returns 429
- SSE connection limit enforced
- normal authorized request still works

### Wave 2 Exit Criteria

- Expensive routes are not anonymously callable in production mode.
- Rate limits and concurrency limits are enforced and test-covered.

## Wave 3: Change Sensitive Data Defaults And Retention

### Goal

Make production stop storing sensitive prompt bodies and customer content by default.

### Files To Inspect First

- `backend/app/core/config.py`
- `backend/app/agents/openrouter_client.py`
- `backend/app/agents/orchestrator.py`
- `backend/app/services/analysis_repository.py`
- `backend/app/api/routes/ingest_documents.py`
- `backend/app/services/intake_service.py`

### Implementation Tasks

1. Make production defaults safe.
   - `BIZBUY_PIPELINE_PROMPT_DEBUG_ARTIFACTS_ENABLED=false` by default in production
   - `BIZBUY_PIPELINE_PROMPT_DEBUG_INCLUDE_BODIES=false` by default in production

2. Separate safe diagnostics from sensitive prompt content.
   - keep timings, token counts, and sizes
   - do not keep full prompt bodies unless explicitly enabled

3. Add retention policy and cleanup logic for:
   - uploads
   - OCR cache
   - analysis artifacts
   - prompt debug artifacts

4. Review persisted ingestion content.
   - keep only what is required
   - minimize raw customer text where possible

### Tests Required

- production config does not create prompt debug bodies by default
- debug artifact disabled means no `prompt_debug.json`
- cleanup only deletes inside allowed roots

### Wave 3 Exit Criteria

- Production defaults are opt-in for sensitive prompt/body persistence.
- Artifact retention behavior is explicit and testable.

## Wave 4: Production Deployment Hardening

### Goal

Remove dev-mode deployment behavior and make Railway/Vercel setup explicit.

### Files To Inspect First

- `Dockerfile`
- `backend/Dockerfile`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `README.md`
- `backend/README.md`

### Implementation Tasks

1. Replace dev runtime commands.
   - frontend image: no `next dev`
   - backend image: no `uvicorn --reload`

2. Make production CORS explicit.
   - require real frontend origin(s)
   - fail fast if production origin config is unsafe or missing

3. Decide policy for FastAPI docs.
   - disable `/docs`, `/redoc`, and OpenAPI in production unless intentionally public

4. Reduce sensitive startup logging.
   - avoid logging masked secret suffixes in production

5. Update deployment docs.
   - exact Vercel envs
   - exact Railway envs
   - safe prod defaults

### Tests / Validation

- backend image runs without `--reload`
- frontend production image runs without `next dev`
- production config enforces allowed origin setup
- docs exposure matches chosen production policy

### Wave 4 Exit Criteria

- Deployment defaults are production-safe without relying on manual operator memory.

## Wave 5: Dependency Audit And Closure

### Goal

Actually clear dependency advisories in a tool-capable environment.

### Environment Requirements

- `node -v`
- `npm -v`
- Python environment where `python -m pip_audit --version` works

### Commands To Run

1. Frontend/runtime audit:
   - `npm audit --omit=dev`
   - `npm audit`
2. Python/runtime audit:
   - `python -m pip_audit`

### If Tooling Is Missing

Do one of:

- install the missing audit tool if allowed
- use a container or CI job that already has it
- document exactly what could not be run

### Output Required

- list any high or critical runtime findings
- patch or pin affected packages
- rerun audits to confirm status

### Wave 5 Exit Criteria

- No unresolved high or critical runtime dependency advisories remain, or any exception is explicitly documented and accepted.

## Final Acceptance Checklist

The pass is complete only if all are true:

- upload path traversal is fixed
- `analysis_id` path traversal is fixed
- expensive public routes are protected
- SSE/job abuse controls exist
- sensitive debug/body persistence is off by default in production
- retention and cleanup behavior is explicit
- backend no longer runs with `--reload` in production image
- frontend no longer relies on `next dev` for production container deployment
- production CORS/docs behavior is explicit
- dependency audits have been run in a tool-capable environment

## Suggested Handoff Prompt For The Next Agent

Use `docs/SECURITY_AUDIT_REPORT.md`, `docs/SECURITY_REMEDIATION_PLAN.md`, and `docs/SECURITY_REMEDIATION_EXECUTION_CHECKLIST.md` as the source of truth.

Implement the security remediation in waves. Start with Wave 1 and do not skip tests. Preserve unrelated user changes. Do not re-audit from scratch unless the code has materially changed. After each wave, summarize what was fixed, what was validated, and what remains.
