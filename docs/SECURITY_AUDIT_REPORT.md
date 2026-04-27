# Security Audit Report

Date: 2026-04-26
Auditor: Codex GPT-5.4
Mode: Read-only security audit with documentation output only
Scope: Next.js frontend at repo root, FastAPI backend under `backend/`, deployment posture for a Vercel frontend plus Railway backend

## Executive Summary

Conclusion: `Not ready for public deployment without remediation`

I confirmed multiple real vulnerabilities that are material for a public Railway and Vercel style deployment:

1. A public upload route writes attacker-controlled filenames directly to disk, which allows path traversal and arbitrary file write outside the intended upload directory.
2. Public analysis routes accept attacker-controlled `analysis_id` values that are used directly as filesystem path components, which creates a second arbitrary file write path outside the artifact root.
3. Expensive OCR and LLM-backed routes are publicly callable with no authentication, no rate limiting, no quota controls, and no SSE connection controls.
4. Sensitive customer content is persisted to local disk by default, including raw uploads, OCR markdown, report artifacts, ingestion evidence, and prompt-debug bodies.

I did not find committed live secrets in the tracked env templates or the inspected code, and I did not find evidence that server-only secrets are intentionally exposed to the browser bundle. However, the confirmed filesystem and abuse-control findings are enough to block public deployment.

## Audit Baseline

### Dirty Worktree

The repository was already dirty at audit start. I did not revert or modify these user changes:

```text
 D .env.local.example
 M README.md
 M backend/README.md
 D backend/app/agents/claude_client.py
 M backend/app/agents/deterministic.py
 M backend/app/api/routes/ingest_documents.py
 M backend/app/services/financial_data_extractor.py
 M backend/app/services/section_data_normalizer.py
 M backend/app/services/section_kind.py
 D backend/bizbuy_backend.egg-info/PKG-INFO
 D backend/bizbuy_backend.egg-info/SOURCES.txt
 D backend/bizbuy_backend.egg-info/dependency_links.txt
 D backend/bizbuy_backend.egg-info/requires.txt
 D backend/bizbuy_backend.egg-info/top_level.txt
 M backend/tests/test_field_population_bugs.py
 M backend/tests/test_ingest_documents_route.py
 M backend/tests/test_ingestion_service.py
 M backend/tests/test_section_kind_ingestion.py
 D components/ui/CardNav.css
 D components/ui/CardNav.tsx
 D components/ui/loader.css
 D components/ui/loader.tsx
 D knip-output.txt
 D src/main.py
 ?? docs/AGENT_ACCURACY_AND_NATURAL_CONTEXT_REDUCTION_PLAN.md
 ?? docs/REPO_BLOAT_REMOVAL_PLAN.md
 ?? docs/SECURITY_DEPLOYMENT_PASS_PLAN.md
```

### Env File Handling

- Tracked env files from `git ls-files .env*`: `.env.example`, `.env.local.example`
- `.env.local` exists locally but is ignored by `.gitignore` via `.env*.local`
- I did not print or inspect `.env.local` secret values
- `HEAD:.env.local.example` still contains stale `ANTHROPIC_API_KEY` content, but the file is already deleted in the current dirty worktree

### Deployment Config Inventory

Confirmed deployment-adjacent files:

- `Dockerfile`
- `backend/Dockerfile`
- `docker-compose.yml`
- `next.config.mjs`
- `.dockerignore`

No checked-in `vercel.json`, `railway.json`, `railway.toml`, or similar platform-specific deployment config was found.

## Method And Evidence Sources

Primary evidence came from:

- `git status --short`
- `git ls-files .env*`
- `git check-ignore -v .env.local`
- repo-wide `rg` searches for env usage, auth, rate limiting, file writes, and prompt-debug behavior
- direct review of:
  - `backend/app/main.py`
  - `backend/app/core/config.py`
  - `backend/app/api/routes/*.py`
  - `backend/app/services/intake_service.py`
  - `backend/app/services/ingestion_service.py`
  - `backend/app/services/analysis_jobs.py`
  - `backend/app/services/analysis_repository.py`
  - `backend/app/agents/openrouter_client.py`
  - `backend/app/agents/mistral_ocr_client.py`
  - `backend/app/agents/orchestrator.py`
  - `app/api/generate-pdf/route.ts`
  - `app/layout.tsx`
  - `lib/api-client.ts`
  - `Dockerfile`
  - `backend/Dockerfile`
  - `docker-compose.yml`
  - `README.md`
  - `backend/README.md`

Dependency audit status:

- `npm audit` could not be run because `npm` is not installed in this environment
- `python -m pip_audit --version` failed because `pip_audit` is not installed
- Because of that, runtime dependency vulnerability status remains an explicit audit gap rather than a passed check

## Environment Variable Classification

| Variable | Classification | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | Secret | Server-side API credential for LLM calls |
| `MISTRAL_API_KEY` | Secret | Server-side API credential for OCR |
| `OPENROUTER_REFERRER` | Server-only non-secret | Header metadata, should not be client-exposed |
| `FRONTEND_ORIGIN` | Server-only non-secret | CORS allowlist input |
| `BIZBUY_ENV` | Server-only non-secret | Environment label |
| `REPORT_MODE` | Server-only non-secret | Backend mode control |
| `BIZBUY_PIPELINE_ENABLED` | Server-only non-secret | Feature flag |
| `BIZBUY_ANALYSIS_JOBS_ENABLED` | Server-only non-secret | Feature flag |
| `BIZBUY_PIPELINE_ALLOW_PARTIAL_FAILURES` | Server-only non-secret | Feature flag |
| `BIZBUY_PIPELINE_ENABLE_SYNTHESIS` | Server-only non-secret | Feature flag |
| `BIZBUY_PIPELINE_RETRY_ATTEMPTS` | Server-only non-secret | Runtime tuning |
| `BIZBUY_PIPELINE_STAGE_TIMEOUT_SECONDS` | Server-only non-secret | Runtime tuning |
| `BIZBUY_PIPELINE_PROMPT_DEBUG_ARTIFACTS_ENABLED` | Server-only non-secret but sensitive-impacting | Controls whether prompt-debug artifacts are written |
| `BIZBUY_PIPELINE_PROMPT_DEBUG_INCLUDE_BODIES` | Server-only non-secret but sensitive-impacting | Controls whether full prompt bodies are written |
| `BIZBUY_PIPELINE_PROMPT_DEBUG_STAGES` | Server-only non-secret | Stage allowlist |
| `BIZBUY_ARTIFACT_DIR` | Server-only non-secret | Filesystem storage root |
| `BIZBUY_UPLOAD_DIR` | Server-only non-secret | Filesystem upload root |
| `USE_MISTRAL_BATCH` | Server-only non-secret | OCR mode flag |
| `NEXT_PUBLIC_BACKEND_URL` | Safe public client var | Browser-visible backend base URL |
| `NEXT_PUBLIC_APP_URL` | Safe public client var | Browser-visible app URL used for metadata base |

Answers to the required env questions:

- Are any secrets tracked in git?
  - I found no committed live secret values in the tracked env templates or the inspected README files. `.env.local` exists locally but is ignored, and I did not inspect its contents.
- Can any secret or secret-derived value reach browser code?
  - I found no evidence that `OPENROUTER_API_KEY`, `MISTRAL_API_KEY`, or other server-only secrets are intentionally exposed to browser code. The browser-visible vars in inspected code are URL values only.
- Are deployment docs likely to cause unsafe env handling?
  - The docs are mostly local-dev oriented rather than Railway/Vercel specific. They do not instruct committing secrets, but they also do not provide a production-safe env matrix, and `docker-compose.yml` injects `.env.local` directly for local containers.

## Confirmed Vulnerabilities

### CV-1: Critical - Public upload route allows path traversal and arbitrary file write via attacker-controlled filename

- Severity: `critical`
- Affected files:
  - `backend/app/api/routes/ingest_documents.py:123-170`
- Affected surface:
  - `POST /api/documents/ingest`
- Evidence:
  - `original_name = upload.filename or f"upload_{file_id}"` at `backend/app/api/routes/ingest_documents.py:129`
  - `dest = run_dir / original_name` at `backend/app/api/routes/ingest_documents.py:168`
  - `dest.parent.mkdir(parents=True, exist_ok=True)` at `backend/app/api/routes/ingest_documents.py:169`
  - `dest.write_bytes(file_bytes)` at `backend/app/api/routes/ingest_documents.py:170`
- Why this is a vulnerability:
  - `upload.filename` is client-controlled multipart metadata.
  - The route joins that value directly onto `run_dir` without sanitizing path separators, `..` segments, or absolute paths.
  - Python `Path` joins do not neutralize traversal segments. A filename such as `../../somewhere/file.txt` or an absolute path can escape the intended upload root.
- Exploitability assessment:
  - High. This is a direct remote call on a public route and does not require authentication.
  - An attacker only needs to submit a crafted multipart filename.
- Deployment impact:
  - Arbitrary write outside `uploads/<run_id>/`
  - Possible overwrite or creation of files elsewhere on the writable filesystem
  - Tampering with application state, artifacts, or future processing inputs
- Recommended fix direction:
  - Never use the client-provided filename as a path segment
  - Generate storage filenames server-side
  - Preserve original filename only as metadata
  - Enforce resolved-path containment before every write

### CV-2: Critical - Public analysis routes allow path traversal and arbitrary artifact writes via attacker-controlled `analysis_id`

- Severity: `critical`
- Affected files:
  - `backend/app/models/schemas.py:517`
  - `backend/app/agents/schemas.py:885-892`
  - `backend/app/services/analysis_jobs.py:123-180`
  - `backend/app/services/analysis_jobs.py:221-271`
  - `backend/app/services/analysis_repository.py:60-163`
  - `backend/app/agents/orchestrator.py:884-898`
  - `backend/app/agents/orchestrator.py:998-1023`
- Affected surface:
  - `POST /api/analyses`
  - `POST /api/pipeline`
- Evidence:
  - `AnalysisJobRequest.analysis_id: str | None = None` at `backend/app/models/schemas.py:517`
  - `PipelineInput.analysis_id: Optional[str] = None` at `backend/app/agents/schemas.py:890`
  - `analysis_id = payload.analysis_id or str(uuid4())` at `backend/app/services/analysis_jobs.py:124` and `:230`
  - Repository paths are built with `self.root_dir / analysis_id / ...` at `backend/app/services/analysis_repository.py:60-93`
  - Writes occur via `write_text(...)` at `backend/app/services/analysis_repository.py:101-102`, `121-122`, `140-141`, and `162-163`
  - Partial reports and prompt-debug artifacts are also written using `pipeline_input.analysis_id` at `backend/app/agents/orchestrator.py:898` and `:1013-1023`
- Why this is a vulnerability:
  - The server accepts client-provided artifact keys and uses them directly as filesystem path segments.
  - There is no UUID validation, no path normalization check, and no containment check before writes.
  - A malicious caller can supply traversal strings such as `../../outside-root`.
- Exploitability assessment:
  - High. This is a direct remote JSON call and does not require authentication.
  - It is easier to exploit than blind report enumeration because the attacker controls the write key at job creation time.
- Deployment impact:
  - Arbitrary file write outside `BIZBUY_ARTIFACT_DIR`
  - Overwrite of job state, report files, and prompt-debug artifacts
  - Potential read exposure for similarly traversed `load_*` calls if matching filenames exist
- Recommended fix direction:
  - Stop accepting caller-supplied path keys for filesystem storage
  - Use server-generated UUIDs only, or strictly validate against a canonical UUID regex
  - Resolve and verify containment before every artifact read or write

### CV-3: High - Public OCR and LLM routes have no authentication, rate limiting, quota control, or SSE connection guardrails

- Severity: `high`
- Affected files:
  - `backend/app/api/routes/ingest_documents.py:361-388`
  - `backend/app/api/routes/parse_documents.py:52-91`
  - `backend/app/api/routes/analyses.py:20-98`
  - `backend/app/api/routes/pipeline.py:15-24`
  - `backend/app/api/routes/analyze.py:11-13`
  - `backend/app/services/analysis_jobs.py:137-180`
  - `backend/app/agents/openrouter_client.py:73-83`
  - `backend/app/agents/mistral_ocr_client.py:196-205`
- Affected surface:
  - `POST /api/documents/ingest`
  - `POST /api/parse-documents`
  - `POST /api/analyses`
  - `GET /api/analyses/{analysis_id}`
  - `GET /api/analyses/{analysis_id}/events`
  - `POST /api/pipeline`
  - `POST /api/analyze`
- Evidence:
  - The route handlers take plain request payloads and do not use auth dependencies or request throttles
  - Repo-wide search for auth and rate-limit primitives did not find middleware or libraries enforcing them
  - `POST /api/analyses` immediately starts a job at `backend/app/api/routes/analyses.py:20-33`
  - SSE streams stay open with keepalives at `backend/app/api/routes/analyses.py:69-97`
  - OCR calls return cost-bearing results from Mistral at `backend/app/agents/mistral_ocr_client.py:196-205`
  - OpenRouter API calls are configured server-side in `backend/app/agents/openrouter_client.py:73-83`
- Why this is a vulnerability:
  - Anonymous callers can trigger paid OCR and LLM work repeatedly.
  - Anonymous callers can also hold long-lived SSE connections open.
  - There is no application-level mechanism to constrain per-IP, per-user, per-session, or per-analysis usage.
- Exploitability assessment:
  - High. No prior access is needed if the backend is public.
- Deployment impact:
  - Direct credit burn for `OPENROUTER_API_KEY` and `MISTRAL_API_KEY`
  - Thread pool and worker starvation
  - Disk growth from repeated uploads and artifacts
  - Service degradation for legitimate users
- Recommended fix direction:
  - Require authentication or signed pre-authorized sessions before expensive routes
  - Add rate limiting, concurrency caps, upload quotas, and SSE connection limits
  - Add explicit abuse telemetry and alerting

### CV-4: High - Sensitive customer data and prompt bodies are persisted to local disk by default

- Severity: `high`
- Affected files:
  - `backend/app/core/config.py:75-84`
  - `backend/app/agents/openrouter_client.py:100-129`
  - `backend/app/agents/orchestrator.py:457-461`
  - `backend/app/agents/orchestrator.py:884-898`
  - `backend/app/agents/orchestrator.py:998-1023`
  - `backend/app/services/analysis_repository.py:60-163`
  - `backend/app/services/analysis_repository.py:181-223`
  - `backend/app/agents/mistral_ocr_client.py:146-154`
  - `backend/app/agents/mistral_ocr_client.py:196-202`
  - `backend/app/api/routes/ingest_documents.py:115-119`
  - `backend/app/api/routes/ingest_documents.py:168-170`
  - `backend/app/services/intake_service.py:483-503`
- Affected surface:
  - OCR cache under `<BIZBUY_ARTIFACT_DIR>/ocr/`
  - analysis artifact directories under `<BIZBUY_ARTIFACT_DIR>/<analysis_id>/`
  - raw upload files under `uploads/<run_id>/`
- Evidence:
  - `pipeline_prompt_debug_artifacts_enabled` defaults to `True` at `backend/app/core/config.py:75-78`
  - `pipeline_prompt_debug_include_bodies` defaults to `True` at `backend/app/core/config.py:79-82`
  - Full prompt bodies are stored when capture is enabled at `backend/app/agents/openrouter_client.py:126-128`
  - Prompt-debug serialization includes `systemPrompt` and `userMessage` at `backend/app/agents/orchestrator.py:457-461`
  - Prompt-debug artifacts are saved at `backend/app/agents/orchestrator.py:998-1023`
  - Partial reports are saved to disk during execution at `backend/app/agents/orchestrator.py:884-898`
  - OCR output includes full page markdown and `full_markdown` at `backend/app/agents/mistral_ocr_client.py:146-154` and `:196-202`
  - OCR artifacts are written to disk at `backend/app/api/routes/ingest_documents.py:115-119`
  - Ingestion artifacts persist `ingestion_output` plus evidence snippets derived from `section.raw_text` at `backend/app/services/analysis_repository.py:181-223`
  - Raw upload files are written under `uploads/` at `backend/app/api/routes/ingest_documents.py:168-170`
- Why this is a vulnerability:
  - Sensitive business documents and prompt bodies are retained by default even when the app is intended for public production exposure.
  - The defaults are opt-out rather than opt-in.
  - The stored data includes customer document text, OCR markdown, report payloads, evidence snippets, clarifications, and prompt bodies.
- Exploitability assessment:
  - High impact with normal application use, even without a separate attacker foothold.
  - Any filesystem compromise, overly broad backup policy, shared volume access, or internal log/artifact mishandling would expose customer content.
- Deployment impact:
  - Unnecessary retention of sensitive customer/business data
  - Larger blast radius if Railway volumes, snapshots, support tooling, or other host access paths are compromised
  - Violates the stated deployment goal that sensitive debug artifacts should not persist by default in production
- Recommended fix direction:
  - Default prompt-debug artifact creation to off in production
  - Default prompt-body capture to off in production
  - Separate transient operational artifacts from customer-content-bearing artifacts
  - Add explicit retention TTLs and deletion workflows for uploads, OCR cache, and analysis artifacts

## Likely Hardening Gaps

These are real concerns, but I am intentionally keeping them separate from the confirmed vulnerabilities above.

### HG-1: Backend production image still runs the public service with `uvicorn --reload`

- Evidence:
  - `backend/Dockerfile:12` runs `uvicorn app.main:app ... --reload`
- Why it matters:
  - Railway-style deployment should not use dev reloaders in production
  - This is an insecure production default and an operational risk

### HG-2: Root Dockerfile runs `next dev`

- Evidence:
  - `Dockerfile:11` runs `next dev`
- Why it matters:
  - Vercel itself would normally do a production build instead of using this image, but the checked-in Dockerfile is not production-ready for any container deployment

### HG-3: FastAPI docs and OpenAPI remain public by default

- Evidence:
  - `backend/app/main.py:16-20` instantiates `FastAPI(...)` without disabling `docs_url`, `redoc_url`, or `openapi_url`
  - `backend/README.md:20` explicitly points users to `/docs`
- Why it matters:
  - This is not a direct exploit, but it exposes the full public schema and route list unless explicitly disabled in production

### HG-4: CORS is only safe if `FRONTEND_ORIGIN` is set correctly in production

- Evidence:
  - `backend/app/core/config.py:60-62` defaults to localhost-only origins
  - `backend/app/main.py:22-28` enables credentialed CORS with wildcard methods and headers
- Why it matters:
  - A naive deploy may either break the frontend or tempt operators to use overly broad origins
  - Production needs an explicit Railway/Vercel origin matrix

### HG-5: `/api/generate-pdf` has no repo-level request size or schema guardrails

- Evidence:
  - `app/api/generate-pdf/route.ts:8-9` accepts arbitrary JSON and renders it directly to a PDF buffer
- Why it matters:
  - I cannot prove a practical exploit without platform limits, but the route does not enforce an application-level body limit or shape validation
  - On Vercel this could become a resource-abuse or memory-pressure issue

### HG-6: `parse-documents` can 500 on malformed JSON form fields

- Evidence:
  - `backend/app/api/routes/parse_documents.py:68`, `:73`, and `:78` call `json.loads(...)` without local error handling
- Why it matters:
  - Malformed `fileTypes`, `fileHashes`, or `ocrArtifactRefs` appear likely to become 500-class errors instead of clean 400 responses

### HG-7: Startup logs reveal masked key suffixes and runtime posture

- Evidence:
  - `backend/app/main.py:52-60` logs environment, masked key tails, and pipeline behavior on startup
- Why it matters:
  - This is not the highest risk item, but production logging usually should not emit even partial secret fingerprints unless there is a strong operational need

### HG-8: Dependency advisory status remains unresolved in this environment

- Evidence:
  - `npm audit` unavailable because `npm` is not installed here
  - `pip_audit` unavailable because the module is not installed here
- Why it matters:
  - I cannot currently clear the repo against current high or critical dependency advisories

## Non-Issues And False Alarms Investigated

### NI-1: No tracked live secrets were found in the inspected env templates and docs

- Evidence:
  - `git ls-files .env*` returned `.env.example` and `.env.local.example`
  - `.env.example` contains blank placeholders rather than live keys
  - `.env.local` is ignored

### NI-2: Browser-visible env usage appears limited to public URL values

- Evidence:
  - `lib/api-client.ts:33-38` uses `NEXT_PUBLIC_BACKEND_URL`
  - `app/layout.tsx:14-16` uses `NEXT_PUBLIC_APP_URL`
- Assessment:
  - These are public URL values, not secrets

### NI-3: OCR artifact reference traversal appears to be contained

- Evidence:
  - `_safe_ocr_artifact_path(...)` in `backend/app/services/intake_service.py:557-570` resolves the candidate path, constrains it under `<BIZBUY_ARTIFACT_DIR>/ocr`, and requires a `.json` suffix
- Assessment:
  - I did not confirm a path traversal bug on the `ocrArtifactRefs` read path

### NI-4: `dangerouslySetInnerHTML` usage appears to be static CSS only

- Evidence:
  - `components/ui/shiny-text.tsx:14-19` injects a hard-coded `@keyframes` block rather than user input
- Assessment:
  - I did not find a user-controlled HTML injection issue there

### NI-5: Analysis IDs are not sequential when the server generates them

- Evidence:
  - `uuid4()` is used at `backend/app/services/analysis_jobs.py:124` and `:230`
- Assessment:
  - The real issue is not sequential enumeration; it is that the server also accepts caller-supplied IDs without validation

## Route Surface Summary

### Unauthenticated or effectively public routes observed

- `GET /api/health`
- `POST /api/documents/ingest`
- `POST /api/parse-documents`
- `POST /api/analyze`
- `POST /api/analyses`
- `GET /api/analyses/{analysis_id}`
- `GET /api/analyses/{analysis_id}/events`
- `POST /api/pipeline`
- `GET /` on the backend root
- FastAPI docs and OpenAPI endpoints unless separately disabled in deployment

### Public expensive routes with the clearest abuse risk

- `POST /api/documents/ingest`
  - Can trigger OCR work and raw upload persistence
- `POST /api/analyses`
  - Can trigger full pipeline execution and report/artifact persistence
- `POST /api/pipeline`
  - Can trigger full pipeline execution directly
- `GET /api/analyses/{analysis_id}/events`
  - Can hold open SSE connections

## Deployment Posture Assessment

### If deployed today, would the app run in dev mode or production mode?

- Frontend on Vercel:
  - Likely platform production build if deployed directly to Vercel
  - The checked-in root Dockerfile is still dev-mode only and would run `next dev` if used in a container deployment
- Backend on Railway:
  - The checked-in backend Dockerfile would run `uvicorn --reload`, which is a development-style runtime

### Are there insecure defaults that would survive a naive Railway/Vercel deployment?

Yes:

- prompt-debug artifacts enabled by default
- prompt bodies included by default
- public expensive routes with no abuse controls
- public docs/OpenAPI by default
- dev-style backend runtime via `--reload`

### Is the public origin model documented correctly?

Not well enough for production:

- current defaults are localhost-centric
- no checked-in Railway/Vercel origin matrix exists
- no platform-specific deployment config exists

## Minimal Production Env Matrix Recommendation

### Vercel frontend

- `NEXT_PUBLIC_BACKEND_URL=https://<railway-backend-domain>/api`
- `NEXT_PUBLIC_APP_URL=https://<public-frontend-domain>`

### Railway backend

- `BIZBUY_ENV=production`
- `FRONTEND_ORIGIN=https://<public-frontend-domain>[,https://<secondary-domain>]`
- `OPENROUTER_API_KEY=<secret>`
- `MISTRAL_API_KEY=<secret>`
- `OPENROUTER_REFERRER=https://<public-frontend-domain>`
- `BIZBUY_PIPELINE_PROMPT_DEBUG_ARTIFACTS_ENABLED=false`
- `BIZBUY_PIPELINE_PROMPT_DEBUG_INCLUDE_BODIES=false`
- `BIZBUY_ARTIFACT_DIR=<private-writable-dir>`
- `BIZBUY_UPLOAD_DIR=<private-writable-dir>`

Additional production controls likely needed before public launch:

- auth secret or signed-session config
- rate-limit backend or external gateway config
- optional Redis or durable store for quotas, sessions, or job state

## Final Assessment

The repo is not currently safe enough to deploy publicly on Railway plus Vercel without avoidable secret exposure, abuse risk, insecure defaults, and data-handling issues.

The two critical filesystem traversal bugs alone are blocking issues. The lack of auth and abuse controls, plus the default persistence of sensitive artifacts, compounds the risk materially.

Conclusion: `Not ready for public deployment without remediation`
