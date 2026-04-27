# Security Deployment Pass Plan

Date: 2026-04-26
Status: Planning only. No application code changed in this pass.
Audience: GPT-5.4 agent running with high reasoning.
Purpose: Give a follow-on agent a concrete, repo-specific plan to assess whether this repository is safe to deploy in a Railway + Vercel style setup, and to produce a remediation plan under `docs/` if real vulnerabilities are found.

## Primary Goal

Perform a full security pass across the repo with production deployment in mind:

- frontend on Vercel (Next.js app at repo root)
- backend on Railway (FastAPI service under `backend/`)
- secrets injected through platform env vars
- public internet exposure for both app surfaces

The agent executing this plan should answer one question clearly:

Is the current repository safe enough to deploy publicly without avoidable secret exposure, abuse risk, insecure defaults, or obvious data-handling issues?

## Required Outputs

The executing agent must create the following docs as part of the audit:

1. `docs/SECURITY_AUDIT_REPORT.md`
2. `docs/SECURITY_REMEDIATION_PLAN.md` only if at least one confirmed vulnerability is found

Rules for those outputs:

- `SECURITY_AUDIT_REPORT.md` must separate:
  - confirmed vulnerabilities
  - likely hardening gaps
  - non-issues / false alarms that were investigated
- `SECURITY_REMEDIATION_PLAN.md` must be created if any confirmed vulnerability exists, even if the fix is small.
- The remediation plan must be actionable enough that another agent can implement it without redoing the full investigation.

## Scope

In scope:

- tracked code under the frontend root app
- tracked code under `backend/`
- deployment config and environment variable handling
- Dockerfiles and `docker-compose.yml`
- secret exposure risks
- auth / abuse-control gaps
- file upload, OCR artifact, and filesystem persistence behavior
- dependency and supply-chain exposure
- runtime logging, debug artifact, and data retention behavior

Out of scope for this pass:

- redesigning product architecture
- rewriting business logic just because it is imperfect
- fixing findings in the same pass unless the user explicitly asks for implementation

This is an audit-and-plan pass, not an implementation pass.

## Non-Negotiable Execution Rules

- Start read-only. Build evidence before suggesting fixes.
- Do not revert the user's current dirty worktree.
- Do not overwrite or "clean up" existing user changes while auditing.
- If you need to run any command that changes local tooling state, justify it in the audit report.
- Prefer proving or disproving a risk with code evidence over general security advice.
- Treat production deployment defaults as important. "It is okay in local dev" is not enough.

## Repo Snapshot To Anchor The Audit

These facts were confirmed on 2026-04-26 and should shape the audit:

- Frontend is a Next.js 14 app at repo root.
- Backend is a FastAPI app under `backend/`.
- Deployment-adjacent files exist:
  - `Dockerfile`
  - `backend/Dockerfile`
  - `docker-compose.yml`
  - `next.config.mjs`
- No checked-in `vercel.json` or `railway.json` was found during this planning pass.
- Root `Dockerfile` currently starts `next dev`.
- `backend/Dockerfile` currently starts `uvicorn ... --reload`.
- Backend exposes routes for:
  - document ingestion
  - document parsing
  - synchronous analysis
  - async analysis jobs
  - SSE event streaming
  - full pipeline execution
- Public envs already referenced in code include:
  - `NEXT_PUBLIC_BACKEND_URL`
  - `NEXT_PUBLIC_APP_URL`
- Backend secret/env handling references include:
  - `OPENROUTER_API_KEY`
  - `OPENROUTER_REFERRER`
  - `MISTRAL_API_KEY`
  - `FRONTEND_ORIGIN`
  - `BIZBUY_ARTIFACT_DIR`
  - `BIZBUY_UPLOAD_DIR`
  - pipeline debug flags
- The repo is already dirty from cleanup work. At minimum, `README.md`, `backend/README.md`, `backend/app/api/routes/ingest_documents.py`, several backend tests, and multiple deletions are already in progress. Do not disturb those changes.

## Highest-Priority Hotspots

The executing agent should inspect these areas early because they are the most likely to affect a real Railway/Vercel deployment:

| Area | Why it matters |
|---|---|
| `backend/app/main.py` | CORS currently allows `allow_credentials=True` with wildcard methods/headers, and startup logs print masked secret state. Verify whether production-safe origin restriction and logging posture exist. |
| `backend/app/core/config.py` | Production defaults matter here. Prompt debug artifact flags currently default to enabled. Confirm whether prompt bodies or sensitive derived data can be persisted in prod by default. |
| `backend/app/api/routes/ingest_documents.py` | Handles uploads, writes files and OCR artifacts, and may be publicly callable without auth or rate limiting. |
| `backend/app/api/routes/parse_documents.py` | Public upload endpoint that should be checked for size validation, parser abuse, and artifact reference trust boundaries. |
| `backend/app/services/intake_service.py` | Reads DOCX/XLSX/CSV/JSON and resolves OCR artifact references. Validate zip parsing safety, path containment, and cache artifact trust. |
| `backend/app/services/analysis_repository.py` | Stores analysis artifacts and prompt-debug artifacts on disk. Confirm retention, path safety, and whether stored payloads can include sensitive customer content. |
| `backend/app/api/routes/analyses.py` | Exposes job creation, status lookup, and SSE event streams. Check for ID enumeration, data leakage, and abuse controls. |
| `backend/app/api/routes/pipeline.py` and `backend/app/api/routes/analyze.py` | Expensive compute endpoints appear unauthenticated. Determine whether this is intentional and whether abuse protections are missing. |
| `app/api/generate-pdf/route.ts` | Server-side PDF generation should be checked for input validation, payload size limits, and denial-of-service risk. |
| `app/layout.tsx` and `lib/api-client.ts` | Confirm that only intended values are public and that prod URLs/origins cannot be misconfigured into insecure behavior. |
| `.env.example`, `.env.local`, `README.md`, `backend/README.md` | Audit for stale or misleading deployment instructions that could cause insecure production setup. |

## Success Criteria

For this repo to be considered reasonably deployable to Railway + Vercel, the audit should be able to show all of the following or explicitly document why a gap remains:

- No real secrets are committed to git or exposed to the browser bundle.
- `NEXT_PUBLIC_*` variables contain only information that is safe to expose publicly.
- Production backend origins are explicitly restricted to the intended frontend origin(s).
- Dev-only behavior is not relied upon in production images or production commands.
- Sensitive prompt/debug artifacts are not persisted by default in production without deliberate opt-in.
- Upload, OCR cache, and analysis artifact paths cannot escape intended storage roots.
- Public expensive endpoints have an explicit abuse-control story.
- Logs do not reveal secret values, user document contents, or sensitive prompt bodies beyond accepted operational need.
- No unresolved high or critical dependency vulnerabilities remain in core runtime dependencies.
- The report distinguishes between true vulnerabilities and "nice-to-have" hardening suggestions.

## Execution Plan

### Phase 0: Safety Baseline

Goal: preserve user work and establish a clean audit baseline.

Tasks:

- Run `git status --short`.
- Record the dirty worktree in `SECURITY_AUDIT_REPORT.md` so later agents do not accidentally revert it.
- Confirm whether `.env.local` is tracked or ignored; do not print secret values into docs.
- Confirm whether any deployment-specific config files exist beyond the ones already identified.

Deliverable for this phase:

- A short "Audit Baseline" section in the report listing current dirty files and any local-only files that must not be copied into docs.

### Phase 1: Secrets And Environment Exposure

Goal: determine whether secrets can leak through git, client-side code, runtime logs, or docs.

Tasks:

- Inspect all tracked env templates and docs:
  - `.env.example`
  - `README.md`
  - `backend/README.md`
  - any deployment docs under `docs/`
- Inventory every env var used in code.
- Classify each env var as:
  - secret
  - server-only non-secret
  - safe public client var
- Verify that only safe public vars use the `NEXT_PUBLIC_` prefix.
- Search for accidental secret logging, masking, or interpolation into responses.
- Check whether startup logs in `backend/app/main.py` are acceptable for production.
- Check whether any docs encourage copying secret values into tracked files.

Evidence commands to prefer:

- `git ls-files .env*`
- `rg -n "NEXT_PUBLIC_|API_KEY|SECRET|TOKEN|PASSWORD|REFERRER|FRONTEND_ORIGIN|BIZBUY_" .`

Questions to answer in the report:

- Are any secrets tracked in git?
- Can any secret or secret-derived value reach browser code?
- Are deployment docs likely to cause unsafe env handling?

### Phase 2: Deployment Posture For Railway And Vercel

Goal: verify that the repo can be deployed in a production-safe way, not just run locally.

Tasks:

- Review `Dockerfile`, `backend/Dockerfile`, and `docker-compose.yml`.
- Flag any dev-only commands used as production defaults:
  - `next dev`
  - `uvicorn --reload`
- Check whether build/runtime separation is production-grade.
- Check whether `.vercel` is ignored and whether platform build output is kept out of git.
- Verify whether FastAPI docs/OpenAPI routes are intentionally public in production.
- Check whether required prod env vars are documented clearly enough for Railway/Vercel setup.
- Recommend a minimal production env matrix for:
  - Vercel frontend
  - Railway backend

Questions to answer:

- If deployed today, would the app run in dev mode or production mode?
- Are there insecure defaults that would survive a naive Railway/Vercel deployment?
- Is the public origin model documented correctly?

### Phase 3: Dependency And Supply-Chain Pass

Goal: identify known dependency vulnerabilities and risky supply-chain posture.

Tasks:

- Review root `package.json` and `package-lock.json`.
- Review `backend/pyproject.toml`.
- Run dependency audits if tooling is available without destabilizing the workspace.
- Prioritize runtime dependencies over dev-only dependencies.
- Note packages handling:
  - network calls
  - file parsing
  - PDF generation
  - OCR / AI provider access

Preferred checks:

- `npm audit --omit=dev`
- `npm audit`
- Python dependency audit only if safe tooling is available in this environment

If Python dependency tooling is not readily available:

- Document the gap explicitly instead of pretending the audit was complete.

Questions to answer:

- Are there known high/critical issues in runtime dependencies?
- Are any risky packages unmaintained or obviously unnecessary for production?

### Phase 4: Backend Attack Surface Review

Goal: inspect every backend route as if it were publicly reachable on Railway.

Tasks:

- Inventory all backend routes from `backend/app/api/router.py`.
- For each route, document:
  - auth requirements
  - whether it is publicly callable
  - data sensitivity
  - compute cost / abuse potential
  - request size / payload controls
  - response leakage risk
- Pay special attention to:
  - `POST /api/documents/ingest`
  - `POST /api/parse-documents`
  - `POST /api/analyze`
  - `POST /api/analyses`
  - `GET /api/analyses/{analysis_id}`
  - `GET /api/analyses/{analysis_id}/events`
  - `POST /api/pipeline`
- Confirm whether route IDs are guessable or whether analysis/job data could be enumerated.
- Review CORS configuration in `backend/app/main.py`.
- Determine whether lack of auth is a deliberate product decision or an unaddressed exposure.

Questions to answer:

- Which routes are currently unauthenticated?
- Which routes could be abused for cost amplification or data exfiltration?
- Is CORS configured tightly enough for production?

### Phase 5: Upload, Archive, And Filesystem Safety

Goal: verify that user-supplied files and artifact references cannot be used to break containment or cause unsafe storage behavior.

Tasks:

- Review upload validation in:
  - `backend/app/api/routes/ingest_documents.py`
  - `backend/app/api/routes/parse_documents.py`
- Review file parsing logic in:
  - `backend/app/services/intake_service.py`
  - any helper used for OCR cache reuse
- Specifically investigate:
  - path traversal
  - archive traversal
  - zip bomb / decompression amplification
  - oversized request behavior
  - MIME vs extension trust
  - retention of uploaded source files
  - artifact directory containment
  - whether artifact refs can point outside the intended root
- Review `backend/app/services/analysis_repository.py` for any path-trust issues or cross-job leakage.

Important repo-specific question:

- Prompt debug and OCR artifacts appear to be stored on disk. Confirm exactly what sensitive information can land in:
  - `backend/.artifacts/`
  - `backend/backend/.artifacts/`
  - `uploads/`

Questions to answer:

- Can a malicious caller make the app read or write outside approved directories?
- Can uploaded content be used to force excessive memory/CPU/disk work?
- Does prod need retention limits or cleanup jobs before safe deployment?

### Phase 6: Frontend And Next.js Surface Review

Goal: verify that the Vercel-hosted app does not create avoidable client or server-route exposure.

Tasks:

- Inspect browser-accessible API callers in `lib/api-client.ts`.
- Inspect server-side route handlers under `app/api/`.
- Review `app/api/generate-pdf/route.ts` for:
  - input validation
  - request size limits
  - denial-of-service risk
  - error leakage
- Review `app/layout.tsx` for URL/env handling.
- Search for dangerous HTML rendering, direct `dangerouslySetInnerHTML`, or untrusted URL usage.
- Confirm there are no accidental server-only imports crossing into client code.

Evidence commands to prefer:

- `rg -n "dangerouslySetInnerHTML|new URL\\(|process\\.env|fetch\\(|innerHTML|eval\\(" app components lib`

Questions to answer:

- Does any server route accept unbounded or weakly validated input?
- Is any client-visible configuration overly permissive or misleading?

### Phase 7: LLM, OCR, And Sensitive Data Handling

Goal: assess whether model-provider integrations and debug tooling create privacy or prompt leakage risks.

Tasks:

- Review `backend/app/agents/openrouter_client.py`.
- Review `backend/app/agents/mistral_ocr_client.py`.
- Review prompt-debug storage behavior in `backend/app/agents/orchestrator.py` and `backend/app/core/config.py`.
- Determine whether:
  - raw user document text
  - OCR markdown
  - prompts
  - model responses
  - evidence snippets
  are persisted locally by default.
- Determine whether prod defaults should disable:
  - `BIZBUY_PIPELINE_PROMPT_DEBUG_ARTIFACTS_ENABLED`
  - `BIZBUY_PIPELINE_PROMPT_DEBUG_INCLUDE_BODIES`
- Check whether external provider headers or metadata leak deployment information unnecessarily.

Questions to answer:

- Is sensitive customer/business data stored longer than intended?
- Could prompt/debug artifacts become a production data leak?
- Are provider integrations using the minimum necessary exposed metadata?

### Phase 8: Abuse Resistance And Operational Controls

Goal: decide whether a public deployment can be abused even if no classic code injection bug exists.

Tasks:

- Determine whether the app currently has any of:
  - authentication
  - authorization
  - rate limiting
  - request throttling
  - upload quotas
  - SSE connection limits
  - per-job retention limits
- If these are absent, determine whether that is acceptable for the intended deployment model.
- Evaluate whether public expensive endpoints can trigger runaway OCR / LLM cost.
- Review health and status endpoints for excessive detail.

Questions to answer:

- Could an anonymous user burn LLM/OCR credits or disk space cheaply?
- Could an attacker keep long-lived SSE connections open indefinitely?
- Does the system need minimum abuse controls before public deployment?

### Phase 9: Findings, Severity, And Follow-On Planning

Goal: produce a report that clearly tells the next agent what is dangerous, what is optional, and what to fix first.

For each finding, capture:

- title
- severity: critical / high / medium / low
- affected files
- affected route or runtime surface
- evidence
- exploitability assessment
- deployment impact
- recommended fix direction

Severity guidance:

- `critical`: direct secret exposure, arbitrary file read/write, obvious remote compromise path, or severe sensitive-data leak
- `high`: public abuse path with serious financial/data impact, major auth exposure, or production-default insecure behavior likely to cause harm
- `medium`: meaningful hardening gap with plausible impact but not trivial exploitation
- `low`: small leak, weak default, or defense-in-depth gap

Then decide:

- If no confirmed vulnerabilities exist:
  - create only `docs/SECURITY_AUDIT_REPORT.md`
  - include a "Hardening Backlog" section for non-vulnerability improvements
- If any confirmed vulnerability exists:
  - also create `docs/SECURITY_REMEDIATION_PLAN.md`

## Required Structure For The Remediation Plan

If `docs/SECURITY_REMEDIATION_PLAN.md` is required, it must include:

- an executive summary ordered by severity
- a fix wave plan
- exact files likely to change
- validation steps for each fix wave
- deployment/config changes required in Railway and/or Vercel
- any migration or rollback concerns

Recommended fix-wave order:

1. Secret exposure and production-default logging/debug issues
2. Public-route auth, abuse control, and CORS issues
3. Filesystem, upload, and artifact containment issues
4. Dependency vulnerabilities
5. Documentation and deployment hardening cleanup

## Suggested Report Conclusion Format

End `SECURITY_AUDIT_REPORT.md` with one of these explicit conclusions:

- `Ready for constrained production deployment`
- `Not ready for public deployment without remediation`
- `Blocked on unresolved audit gaps`

Do not end with vague wording.

## Concrete Repo-Specific Checks The Agent Must Not Skip

- Verify whether FastAPI docs at `/docs` and OpenAPI JSON are intentionally public in production.
- Verify whether `allow_credentials=True` combined with current CORS handling is production-safe.
- Verify whether prompt debug artifacts can include prompt bodies or sensitive document excerpts by default.
- Verify whether `analysis_id`-based reads and SSE streams can leak one user's data to another.
- Verify whether artifact references accepted by ingestion/parsing stay strictly inside the OCR artifact root.
- Verify whether uploads and analysis artifacts accumulate without cleanup.
- Verify whether current Dockerfiles would accidentally run dev servers in production.
- Verify whether the public frontend can directly trigger expensive backend work without any abuse throttling.

## Final Instruction To The Executing Agent

Be skeptical, concrete, and repo-specific.

If you suspect a vulnerability but cannot prove it from the current code, say so clearly and downgrade it to a risk or audit gap rather than overstating it.

If you do confirm vulnerabilities, create `docs/SECURITY_REMEDIATION_PLAN.md` before ending the pass.
