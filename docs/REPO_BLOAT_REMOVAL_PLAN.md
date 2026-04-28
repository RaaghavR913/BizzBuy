# Repo Bloat Removal Plan

Date: 2026-04-26
Status: Read-only audit completed. No application code changed in this pass.
Purpose: Give another GPT-5.4 window a concrete, low-risk execution plan for removing dead code, generated clutter, stale docs, and avoidable duplication.

## Scope

This plan is for cleanup only.

- Prefer behavior-preserving deletions and simplifications first.
- Do not rewrite active product logic just because it is imperfect.
- Do not revert or overwrite the user's existing dirty worktree changes.
- Keep backend behavior green at every wave.

## Baseline Snapshot

### Current dirty files

These were already modified before this audit and should be treated as user-owned unless explicitly coordinated:

- `backend/app/agents/deterministic.py`
- `backend/app/api/routes/ingest_documents.py`
- `backend/app/services/financial_data_extractor.py`
- `backend/app/services/section_data_normalizer.py`
- `backend/app/services/section_kind.py`
- `backend/tests/test_field_population_bugs.py`
- `backend/tests/test_ingest_documents_route.py`
- `backend/tests/test_ingestion_service.py`
- `backend/tests/test_section_kind_ingestion.py`

### Validation baseline

- Backend tests are green: `cd backend && python -m pytest -q`
  - Result during audit: `177 passed, 6 warnings`
- Frontend build was not runnable in this environment because `npm` was not on `PATH`.
  - The follow-on cleanup pass must run frontend verification on a machine/container with Node/npm available.

### Important repo facts

- `backend/backend/.artifacts/` exists because the default artifact path is relative (`backend/.artifacts`) and resolves differently when the current working directory is `backend/`.
- `sample company1/` is not just demo data. It is referenced by backend tests.
- `sample company3 - LoneStar Plumbing/` is tracked, but no code or tests currently reference it.
- `uploads/` is local runtime clutter, not tracked.
- Existing docs are partially stale and should not be treated as canonical architecture truth.

## High-Confidence Cleanup Targets

These are the best first-wave targets because the evidence for removal is strong.

| Path | Confidence | Why it looks removable | Required verification before/after deletion |
|---|---|---|---|
| `src/main.py` | High | Tracked empty file. Actual backend entry point is `backend/app/main.py`. | `git ls-files src/main.py`; `rg -n "src/main.py|backend/app/main.py|app.main:app" .` |
| `components/ui/CardNav.tsx` | High | No import sites in app/components/lib/context. Only self/CSS references. | `rg -n "CardNav" app components lib context` |
| `components/ui/CardNav.css` | High | Only consumed by `CardNav.tsx`. | Delete with `CardNav.tsx` in same commit. |
| `components/ui/loader.tsx` | High | No import sites in app/components/lib/context. | `rg -n "\\bLoader\\b|components/ui/loader|loader.css" app components lib context` |
| `components/ui/loader.css` | High | Only consumed by `loader.tsx`. | Delete with `loader.tsx` in same commit. |
| `backend/app/agents/claude_client.py` | High | No imports from backend app/tests/scripts. Current runtime uses `openrouter_client.py`. `pyproject.toml` does not even declare `anthropic`. | `rg -n "claude_client|ANTHROPIC_API_KEY|anthropic" backend app docs README.md .env*` |
| `backend/bizbuy_backend.egg-info/*` | High | Generated packaging metadata tracked in git. Should never be versioned. | `git ls-files backend/bizbuy_backend.egg-info` |
| `knip-output.txt` | High | Stale static-analysis artifact. Mentions nonexistent files/dependencies and is not referenced anywhere. | `rg -n "knip-output|knip" .` |
| `.env.local.example` | High | Stale template still references `ANTHROPIC_API_KEY`; current repo standard is `.env.example`. | `rg -n "\\.env\\.local\\.example|ANTHROPIC_API_KEY" README.md docs .env.local.example` |

## Medium-Confidence Cleanup Targets

These are likely worth doing, but they need a small refactor or stakeholder decision.

| Area | Why it matters | Risk |
|---|---|---|
| Frontend `sharedContext` state and related types | The state exists in `context/AnalysisContext.tsx`, but app code only resets it to `null`; no read path remains. This likely leaves dead types in `lib/types.ts`. | Low to medium. Requires coordinated TS cleanup and build verification. |
| `sample company1/` fixture location | The files are real test fixtures but live at repo root with a product/demo naming scheme. They should move under backend fixtures. | Medium. Tests and docs need path updates. |
| `sample company3 - LoneStar Plumbing/` | Tracked sample data with no runtime/test references. Likely pure bloat, but confirm it is not still wanted for manual demos. | Medium. Stakeholder intent check recommended. |
| Root planning docs and stale docs in `docs/` | Many are historical planning artifacts, not runtime documentation. Several are outdated enough to mislead future work. | Medium. Better to archive than hard-delete on first pass. |
| Schema duplication across backend and frontend | `backend/app/agents/schemas.py`, `backend/app/models/schemas.py`, and `lib/types.ts` contain overlapping contracts. | High if done aggressively. Treat as a later wave, not part of the first safe cleanup commit. |
| Artifact path normalization | Current relative defaults create duplicate generated trees like `backend/backend/.artifacts`. | Medium. Small code change, but it touches runtime/config behavior. |

## Execution Order

Use this order. It keeps risk low and makes it easy to stop after any green checkpoint.

### Wave 0: Safety Setup

Goal: protect the existing dirty worktree and establish a repeatable validation loop.

Tasks:

- Create a cleanup branch.
- Re-run `git status --short` and make sure the same user-owned dirty files are still present.
- Do not touch the nine dirty backend files listed in the baseline unless a later cleanup step absolutely requires it.
- Save the current baseline:
  - `cd backend && python -m pytest -q`
  - `git status --short`

Expected result:

- Backend still green.
- Cleanup work isolated from user-owned changes.

### Wave 1: Remove Generated / Trivially Dead Files

Goal: take the easiest wins first.

Delete:

- `src/main.py`
- `backend/bizbuy_backend.egg-info/PKG-INFO`
- `backend/bizbuy_backend.egg-info/SOURCES.txt`
- `backend/bizbuy_backend.egg-info/dependency_links.txt`
- `backend/bizbuy_backend.egg-info/requires.txt`
- `backend/bizbuy_backend.egg-info/top_level.txt`
- `knip-output.txt`

Also clean local-only clutter, but do not commit that cleanup unless the repo intentionally wants it documented:

- `backend/__pycache__/` and nested `__pycache__/`
- `backend/.pytest_cache/`
- `backend/.artifacts/`
- `backend/backend/.artifacts/`
- `uploads/`

Verification:

- `git diff --name-status`
- `cd backend && python -m pytest -q`
- `rg -n "src/main.py|bizbuy_backend\\.egg-info|knip-output" .`

Notes:

- Deleting ignored local runtime directories is optional for the commit but recommended for repo hygiene.
- The follow-on window should not use destructive git commands. Delete only the specific paths it intends to remove.

### Wave 2: Remove Confirmed Unused Frontend UI Files

Goal: remove dead UI primitives and then prune any dependency that becomes unused.

Delete:

- `components/ui/CardNav.tsx`
- `components/ui/CardNav.css`
- `components/ui/loader.tsx`
- `components/ui/loader.css`

Then inspect `package.json`:

- `gsap` appears to be used only by `CardNav.tsx`. If no other file uses it after deletion, remove `gsap` from `package.json` and refresh the lockfile.

Verification:

- `rg -n "CardNav|loader\\.css|components/ui/loader|gsap" app components lib context package.json`
- `npm run build`
- `npm run lint`

If Node is still unavailable:

- Defer the dependency removal commit until the build can be run.

### Wave 3: Remove Confirmed Unused Backend Legacy Client

Goal: remove the abandoned Anthropic client path and the stale env/docs references around it.

Delete:

- `backend/app/agents/claude_client.py`

Update references:

- Remove stale `ANTHROPIC_API_KEY` mentions from:
  - `.env.local.example`
  - stale docs that are being kept rather than archived
  - any README section still claiming Anthropic is active

Verification:

- `rg -n "claude_client|ANTHROPIC_API_KEY|anthropic" backend README.md docs .env*`
- `cd backend && python -m pytest -q`

Important note:

- `backend/app/agents/openrouter_client.py` is the active structured-output client.
- Do not add `anthropic` to `pyproject.toml`; removal is the right direction here.

### Wave 4: Simplify Dead Frontend State and Legacy Types

Goal: remove state shape that no longer participates in runtime behavior.

Likely dead path:

- `sharedContext` in `context/AnalysisContext.tsx`
- `SharedContext`, `AgentId`, `AgentOutput`, and any types only retained to support that dead state path in `lib/types.ts`

Evidence from audit:

- `QuestionsPage` calls `setSharedContext(null)` before analysis.
- No page/component reads `state.sharedContext`.
- `SharedContext` appears to be legacy from the old multi-agent frontend merge path.

Concrete changes:

- Remove `sharedContext` from `AnalysisState`
- Remove `SET_SHARED_CONTEXT` from the reducer
- Remove `setSharedContext` from context value and provider
- Remove the `setSharedContext(null)` call in `app/analyze/questions/page.tsx`
- Remove now-unused TS interfaces/types from `lib/types.ts`

Verification:

- `rg -n "sharedContext|setSharedContext|SharedContext|AgentId|AgentOutput" app components context lib`
- `npm run build`
- `npm run lint`

Do not do this in the same commit as Wave 2 unless the frontend build is available. Keep the diff reviewable.

### Wave 5: Rationalize Test Fixtures and Sample Data

Goal: separate real test fixtures from demo/sample clutter.

#### Part A: Move `sample company1/` into backend fixtures

Reason:

- It is actively used by `backend/tests/test_parse_documents_route.py`.
- Keeping it at repo root makes it look like demo content instead of test data.

Recommended target:

- `backend/tests/fixtures/peakair/`

Files to move:

- `sample company1/Hidden Red flags.txt`
- `sample company1/PeakAir_CustomerList_PPE.xlsx`
- `sample company1/PeakAir_EmployeeContracts.docx`
- `sample company1/PeakAir_Financials.xlsx`
- `sample company1/PeakAir_LeaseAgreement.docx`
- `sample company1/PeakAir_TaxReturns.docx`

Required code/docs updates:

- `backend/tests/test_parse_documents_route.py`
- Any docs that point to the old root path

Verification:

- `cd backend && python -m pytest -q tests/test_parse_documents_route.py`
- `cd backend && python -m pytest -q`

#### Part B: Decide what to do with `sample company3 - LoneStar Plumbing/`

Audit finding:

- Tracked in git.
- No code or tests currently reference it.

Decision options:

1. Preferred cleanup option: remove it from git entirely if nobody needs it.
2. Safer first pass: move it to `docs/archive/sample-data/` or a clearly labeled non-runtime sample directory.

Before removal:

- Confirm with the user whether LoneStar still matters for demos or future test cases.

#### Part C: Leave `sample company4/` alone unless explicitly asked

Reason:

- It is present locally but not tracked.
- The backend Alpine smoke test is synthetic and does not rely on these files.

### Wave 6: Normalize Runtime Artifact and Upload Paths

Goal: stop generating duplicate local directories and make runtime storage predictable.

Current problem:

- `FileSystemAnalysisArtifactRepository` defaults to `Path("backend/.artifacts")`
- `backend/app/api/routes/ingest_documents.py` defaults OCR artifacts to `backend/.artifacts/ocr`
- `backend/app/services/intake_service.py` also defaults OCR artifacts under `backend/.artifacts`
- When commands run from `c:\\S\\BizzBuy\\backend`, that resolves to `backend/backend/.artifacts`

Files to inspect/change together:

- `backend/app/services/analysis_repository.py`
- `backend/app/api/routes/ingest_documents.py`
- `backend/app/services/intake_service.py`
- `.env.example`
- `README.md`
- `backend/README.md`

Recommended direction:

- Pick one canonical artifact root.
- Make defaults resolve relative to the backend project root, not the caller's current working directory.
- Keep env override support with `BIZBUY_ARTIFACT_DIR`.
- Do the same review for `BIZBUY_UPLOAD_DIR`.

Verification:

- `cd backend && python -m pytest -q tests/test_parse_documents_route.py tests/test_analysis_jobs.py`
- `cd backend && python -m pytest -q`
- Manually confirm a local run no longer writes to `backend/backend/.artifacts`

### Wave 7: Consolidate or Archive Stale Docs

Goal: reduce repo noise and stop stale docs from misleading future work.

#### Docs that are currently misleading or outdated

- `README.md`
- `backend/README.md`
- `docs/CODEBASE_AUDIT.md`
- `docs/DevModeConfig.md`

Specific stale signals found during audit:

- `README.md` still points setup at `.env.local.example` instead of `.env.example`
- `README.md` describes older architecture paths and old dependency assumptions
- `backend/README.md` says `/parse-documents` returns placeholders, which is no longer true
- `docs/CODEBASE_AUDIT.md` claims the backend does not reference `uploads/`, but current `ingest_documents.py` does
- `docs/CODEBASE_AUDIT.md` still treats Anthropic as active

#### Root planning docs that likely belong in an archive

- `ARCHITECTURE.md`
- `BizzBuyBarebonesPRD.md`
- `BizzbuyPlan.txt`
- `backend-plan.md`
- `backend-math.txt`
- `monte-carlo-implementation.md`
- `MULTI_AGENT_CODEX_EXECUTION_PROMPTS.md`
- `MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md`
- `RUNTIME_OVERVIEW.md`
- `architecture flow.md`
- `architecture-flow.png`

Recommended action:

- Do not mass-delete these in the first cleanup commit.
- Move them under `docs/archive/` in a single follow-up docs-only commit.
- Keep only the smallest set of current operator docs at repo root.

Verification:

- `rg -n "architecture flow|MULTI_AGENT|backend-plan|backend-math|BizzbuyPlan|RUNTIME_OVERVIEW" README.md docs .`
- Open the updated `README.md` and make sure setup instructions match the current repo.

### Wave 8: Optional High-Risk Contract Deduplication

Goal: reduce long-term bloat from maintaining the same shapes in three places.

Current overlap:

- `backend/app/agents/schemas.py`
- `backend/app/models/schemas.py`
- `lib/types.ts`

Examples of duplicated domains:

- report output contracts
- normalized findings/evidence
- deterministic scorecard structures
- analysis job payload shapes

Recommended constraint:

- Do not start here.
- Only attempt this after all deletion-based cleanup is merged and the repo is green.

Safer direction:

1. Decide which backend schema module is canonical for HTTP responses.
2. Minimize duplication between `agents/schemas.py` and `models/schemas.py`.
3. Later, generate or semi-generate frontend TS types from the backend contract.

Risk:

- Easy to cause silent contract drift or frontend breakage if done too fast.

## File-by-File Checklist

Use this as a punch list for the implementation window.

### Delete in first pass

- `src/main.py`
- `components/ui/CardNav.tsx`
- `components/ui/CardNav.css`
- `components/ui/loader.tsx`
- `components/ui/loader.css`
- `backend/app/agents/claude_client.py`
- `backend/bizbuy_backend.egg-info/PKG-INFO`
- `backend/bizbuy_backend.egg-info/SOURCES.txt`
- `backend/bizbuy_backend.egg-info/dependency_links.txt`
- `backend/bizbuy_backend.egg-info/requires.txt`
- `backend/bizbuy_backend.egg-info/top_level.txt`
- `knip-output.txt`

### Rewrite or remove after neighboring cleanup

- `.env.local.example`
- `README.md`
- `backend/README.md`

### Move rather than delete

- `sample company1/*` -> `backend/tests/fixtures/peakair/*`
- root planning docs -> `docs/archive/...`

### Decide with user before removing

- `sample company3 - LoneStar Plumbing/*`

## Validation Matrix

Run these after each wave, not only at the end.

### Backend

Primary:

- `cd backend && python -m pytest -q`

Focused:

- `cd backend && python -m pytest -q tests/test_parse_documents_route.py`
- `cd backend && python -m pytest -q tests/test_analysis_jobs.py`
- `cd backend && python -m pytest -q tests/test_ingest_documents_route.py`

### Frontend

Primary:

- `npm run build`
- `npm run lint`

Helpful grep checks:

- `rg -n "CardNav|loader\\.css|claude_client|sharedContext|ANTHROPIC_API_KEY" .`

## Suggested Commit Breakdown

Keep commits small and reversible.

1. `cleanup: remove generated metadata and empty orphan files`
2. `cleanup: drop unused frontend ui components`
3. `cleanup: remove legacy anthropic client path`
4. `cleanup: remove dead sharedContext frontend state`
5. `test: move PeakAir sample data into backend fixtures`
6. `cleanup: normalize artifact path defaults`
7. `docs: archive stale planning docs and refresh setup docs`

## Compressed Context for the Next GPT-5.4 Window

If you need a minimal handoff block, use this:

```text
Repo cleanup plan only; no code changes were made in the audit pass.
Backend baseline is green: 177 tests passed via `cd backend && python -m pytest -q`.
Frontend build was not run because npm was unavailable in this environment.
Do not revert current dirty files in backend/app/agents/deterministic.py, backend/app/api/routes/ingest_documents.py, backend/app/services/financial_data_extractor.py, backend/app/services/section_data_normalizer.py, backend/app/services/section_kind.py, backend/tests/test_field_population_bugs.py, backend/tests/test_ingest_documents_route.py, backend/tests/test_ingestion_service.py, backend/tests/test_section_kind_ingestion.py.
Confirmed high-confidence deletions: src/main.py, components/ui/CardNav.tsx, components/ui/CardNav.css, components/ui/loader.tsx, components/ui/loader.css, backend/app/agents/claude_client.py, backend/bizbuy_backend.egg-info/*, knip-output.txt.
Do not delete sample company1 yet; backend/tests/test_parse_documents_route.py depends on it. Move it under backend/tests/fixtures/peakair and update tests/docs.
sample company3 - LoneStar Plumbing is tracked but currently unreferenced by code/tests; confirm with user before removal.
Artifact path defaults are inconsistent and create backend/backend/.artifacts when cwd=backend. Review backend/app/services/analysis_repository.py, backend/app/api/routes/ingest_documents.py, and backend/app/services/intake_service.py together.
README.md, backend/README.md, docs/CODEBASE_AUDIT.md, and .env.local.example are stale. Prefer docs/archive for historical planning docs rather than deleting them blindly.
Likely dead frontend state: sharedContext in context/AnalysisContext.tsx and related SharedContext/AgentId/AgentOutput types in lib/types.ts.
```

## Final Recommendation

Start with Waves 1 through 3 only. They are the cleanest, least controversial wins and should substantially reduce visible bloat without touching active product behavior.

After that, do Wave 5 before Wave 7 so the docs refresh can point at the new fixture locations and the cleaned artifact conventions.