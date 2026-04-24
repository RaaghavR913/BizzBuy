# OpenRouter Context Condensation Plan

## Goal

Reduce prompt tokens sent to the OpenRouter specialist and synthesis agents without breaking report quality, evidence traceability, or the current parallel specialist execution model.

This plan is based on the live sample run in:

- `backend/backend/.artifacts/9f8e78db-9b74-4f5c-9ba8-e65405b0cf03/analysis_report.json`
- `backend/backend/.artifacts/9f8e78db-9b74-4f5c-9ba8-e65405b0cf03/analysis_job.json`
- related OCR cache files in `backend/backend/.artifacts/ocr/`

## Important Finding: Specialists Are Already Parallel

The current pipeline already runs applicable specialist agents concurrently.

Evidence from code:

- `run_pipeline(...)` launches specialists with `asyncio.gather(...)` in `backend/app/agents/orchestrator.py`.
- each specialist stage is executed through `loop.run_in_executor(...)`, so blocking OpenRouter HTTP calls run on worker threads instead of blocking the event loop.
- the analysis job creates a dedicated thread pool with `max_workers=20` in `backend/app/services/analysis_jobs.py`.

Evidence from the sample run:

- total wall-clock runtime was about `330.35s`
- sum of specialist latencies was about `660.00s`

If specialists were actually serial, wall time would be at least the sum of specialist runtimes before synthesis. Since wall time is much lower, the calls are overlapping already.

## Why `analysis_job.json` Looks Serial

`analysis_job.json` only records:

- one current `progress.stage`
- one current `progress.message`
- one growing `completed_agents` list

It does not store:

- a per-agent `started_at`
- a per-agent `in_progress` flag
- a live list of currently running specialists

So the artifact naturally looks like:

1. specialists started
2. one completion arrives
3. another completion arrives
4. another completion arrives

That is a progress reporting limitation, not proof of serial execution.

## What "Internally Blocking" Means

Each individual agent call uses the synchronous OpenAI/OpenRouter client:

- `client.chat.completions.create(...)`

Within the worker thread handling that specialist, that call blocks until:

- the network request finishes
- the model returns
- the response is parsed and validated

This means:

- the worker thread is occupied during the request
- the event loop is not occupied
- other specialists can still run at the same time on other worker threads

In other words:

- per-call behavior: blocking
- per-stage orchestration: concurrent

## Current Prompt Cost Hotspots

From the sample run:

- `synthesis_report`: `43,384` tokens
- `tax_compliance`: `14,928` tokens
- `market_macro`: `6,082` tokens
- `lease_contract`: `4,740` tokens
- `ar_collections`: `3,852` tokens
- `customer_concentration`: `1,433` tokens
- `financial_analysis`: timed out at `240s`
- total successful token volume: `74,419`

The biggest savings are likely in:

1. `synthesis_report`
2. `financial_analysis`
3. `tax_compliance`
4. `market_macro`
5. raw text heavy specialist prompts generally

## Current Prompt Construction Pattern

Today most specialist prompts are built from a mix of:

- deterministic metrics as pretty-printed JSON
- raw extracted structured data from sections
- concatenated raw text from relevant documents
- repeated document inventory context

Main prompt-build helpers:

- `_raw_data_summary(...)`
- `_raw_text_summary(...)`
- direct `json.dumps(..., indent=2)` blocks in specialist runners

Main risk:

- the same underlying document content is repeated across several prompts in slightly different forms

## Design Principle For The Refactor

Send each agent only the minimum context it needs to make the next decision well.

That means shifting from:

- "dump all relevant raw rows/text"

to:

- "send compact metrics + a curated evidence pack + explicit missing-data notes"

## Proposed Target Architecture

Introduce a prompt-context builder layer between `IngestionOutput` and `call_agent(...)`.

New responsibilities:

1. build a compact, agent-specific context object
2. enforce token and character budgets
3. prefer normalized metrics and evidence snippets over full raw tables
4. degrade gracefully when context is incomplete
5. expose diagnostics for what was trimmed

Suggested module:

- `backend/app/agents/context_builders.py`

Suggested outputs per agent:

- `system_prompt`
- compact `user_message`
- metadata about truncation and included evidence

## Context Reduction Strategy

### 1. Replace Pretty JSON With Compact JSON

Current pattern:

- `json.dumps(..., indent=2, default=str)`

Planned change:

- use compact serialization for model-facing payloads
- reserve pretty printing for logs/debug only

Expected result:

- immediate low-risk token reduction across all agents

### 2. Stop Sending Full Row Dumps By Default

Current pattern:

- `_raw_data_summary(...)` can include large `rows` arrays

Planned change:

- send normalized metrics first
- send only selected supporting rows
- include a small evidence list with the source section, fiscal year, and key extracted fields

Expected result:

- large reduction for `financial_analysis`, `tax_compliance`, and `ar_collections`

### 3. Introduce Agent-Specific Evidence Packs

For each specialist, create a small evidence pack such as:

- `financial_analysis`: 6-10 top financial evidence items
- `tax_compliance`: tax return coverage summary, discrepancy summary, 4-6 supporting snippets
- `customer_concentration`: top customers, concentration metrics, 3-5 contract/customer snippets
- `lease_contract`: lease term summary, assignment clues, 3-5 clause/snippet extracts
- `market_macro`: business profile + short extracted business context, not broad raw text dumps

Evidence item shape should stay close to `EvidenceReference`.

### 4. Add Hard Budgets Per Agent

Suggested first-pass budgets:

- `financial_analysis`: compact metrics + max 8 evidence items
- `tax_compliance`: compact metrics + max 8 evidence items
- `ar_collections`: compact metrics + max 6 evidence items
- `customer_concentration`: max 5 snippets
- `operations_transferability`: max 5 snippets
- `lease_contract`: max 6 snippets
- `market_macro`: max 4 snippets plus inferred profile
- `synthesis_report`: no raw document text; only scorecard + compact agent summaries

Budgets should be enforced before the OpenRouter call, not just by prompt slicing afterward.

### 5. Remove Raw Document Text From Synthesis

Synthesis should not need document-level raw text again.

Planned synthesis input:

- deterministic scorecard
- compact summaries from successful specialist outputs
- compact list of failed/skipped specialists
- selected red flags / green flags / top findings only

It should not receive:

- repeated broad document context
- repeated structured rows
- large duplicated narrative from previous agents

This is likely the single highest-leverage token cut.

### 6. Build Short Summaries For Text-Heavy Agents

For `customer`, `ops`, `lease`, and `market`:

- summarize raw text into small topical snippets before building `user_message`
- prefer top matching sections over full concatenation
- include explicit truncation metadata when text is clipped

### 7. Preserve Missing-Data Signaling

When trimming prompts, do not lose missing-data information.

Every compact context builder should include:

- missing document types
- confidence caveats
- notes about whether evidence is direct vs inferred

This is especially important because the system relies heavily on explicit incompleteness penalties.

## Proposed Implementation Phases

### Phase 1: Instrumentation

Add prompt diagnostics before changing behavior.

Deliverables:

- per-agent prompt size logging
- per-agent context component sizes
- optional artifact dump of the final `user_message`

Suggested artifact:

- `prompt_debug.json` under the analysis artifact directory

Purpose:

- measure exactly what each agent receives
- confirm where the largest prompt bloat comes from

### Phase 2: Shared Prompt Builder Utilities

Add reusable utilities for:

- compact JSON serialization
- evidence item selection
- text clipping with provenance
- token-safe context budgeting

Deliverables:

- shared builder functions
- tests for clipping and deterministic evidence selection

### Phase 3: Convert Specialist Agents One By One

Recommended order:

1. `financial_analysis`
2. `tax_compliance`
3. `market_macro`
4. `lease_contract`
5. `customer_concentration`
6. `ar_collections`
7. `operations_transferability`
8. `synthesis_report`

Reason:

- start with biggest probable token and timeout contributors

### Phase 4: Synthesis Compression

Refactor synthesis to consume only:

- scorecard
- compact per-agent summaries
- top findings
- failed/skipped metadata

No raw section dumps.

### Phase 5: Quality Review

Compare old vs new on:

- total tokens
- per-agent latency
- timeout rate
- scorecard/report regressions
- missing evidence regressions

## Concrete Refactor Ideas By Agent

### Financial Analysis

Current issue:

- may receive large structured dumps from `_raw_data_summary(...)`

Planned input:

- compact financial metrics object
- compact annual statement summary
- selected evidence rows only
- explicit missing-doc warnings

### Tax Compliance

Current issue:

- repeats financial detail plus tax coverage context

Planned input:

- tax coverage summary
- discrepancy summary
- top evidence snippets from tax returns and P&L
- explicit warning if returns are missing

### AR Collections

Planned input:

- aging metrics
- top overdue buckets/customers
- 3-6 evidence references

### Customer Concentration

Planned input:

- concentration metrics
- top customer table summary
- top contract renewal/transfer snippets

### Lease Contract

Planned input:

- structured lease summary
- key clause snippets
- explicit flags for assignment, term, and change-of-control language

### Market Macro

Current issue:

- currently gets broad raw document text

Planned input:

- business profile
- inferred location / business type / revenue band
- short business-context snippet pack
- no general raw document dump beyond a small cap

### Synthesis

Current issue:

- most expensive prompt in the sample run

Planned input:

- deterministic scorecard
- top 1-3 findings per successful specialist
- compact narrative summaries only
- failed/skipped specialist list

## Suggested Validation Tests

Add regression tests for:

- compact prompt builders preserving required facts
- deterministic evidence selection
- prompt clipping not dropping all support
- synthesis using compact summaries only
- token/size caps enforced

Suggested new tests:

- `test_financial_context_builder_compacts_rows`
- `test_tax_context_builder_limits_evidence_count`
- `test_market_context_builder_caps_raw_text`
- `test_synthesis_context_excludes_document_raw_text`
- `test_prompt_debug_artifact_written_when_enabled`

## Optional UX Improvement

If we want the job artifact to better reflect true concurrency, add per-agent live state to `analysis_job.json`.

Suggested fields:

- `running_agents`
- `stage_metrics[agent].started_at`
- `stage_metrics[agent].completed_at`
- `stage_metrics[agent].status`

This is not required for token reduction, but it would make the parallel behavior visible.

## Recommended Next Step

Start with instrumentation plus the synthesis and financial prompt builders first.

Highest-value sequence:

1. add prompt diagnostics
2. compact JSON serialization everywhere
3. replace `_raw_data_summary(...)` usage for financial and tax with compact evidence packs
4. remove raw document text from synthesis input
5. add explicit prompt budgets and regression tests

## Success Criteria

The refactor is successful if we can achieve most of the following:

- reduce total prompt tokens materially on the full sample package
- reduce `synthesis_report` token usage sharply
- reduce `financial_analysis` timeout frequency
- preserve report quality and evidence traceability
- keep the current parallel specialist execution behavior intact

## Handoff Setup

This section is for the next agent picking up the work after the first context-reduction pass has already been implemented.

Treat the earlier sections of this document as the design intent. Treat this section as the execution handoff.

## Assumed State When You Start

If context reduction has already been worked on in a separate context window, assume some or all of the following may now exist:

- a new prompt-context builder module or helper layer
- compact JSON serialization for model-facing payloads
- evidence-pack based prompt builders for one or more specialists
- prompt diagnostics or a debug artifact such as `prompt_debug.json`
- prompt budgets or truncation rules for one or more agents
- changes to specialist prompt assembly in `backend/app/agents/runners.py`
- new tests validating prompt clipping, evidence selection, or compact builders

Do not assume all of this landed cleanly or consistently. Your first task is to verify the implementation state and normalize it.

## First 30 Minutes: Verification Checklist

Before making follow-up changes, inspect these files first:

- `backend/app/agents/runners.py`
- `backend/app/agents/openrouter_client.py`
- `backend/app/agents/orchestrator.py`
- `backend/app/agents/schemas.py`
- `backend/app/services/report_assembler.py`
- any newly added file such as `backend/app/agents/context_builders.py`
- relevant tests under `backend/tests/`

Answer these questions immediately:

1. Which agents already use compact context builders?
2. Which agents still build prompts directly inline in `runners.py`?
3. Is synthesis still receiving broad context or has it been compacted?
4. Are prompt budgets enforced before the OpenRouter call?
5. Is there a prompt debug artifact or logging path in place?
6. Did the previous implementation add tests, and do they pass?
7. Are there any partial migrations where some agents use the new builder layer and others still use the old helper functions?

## What To Measure First

Before changing anything else, capture a fresh before/after view on the full sample package.

Use these artifacts as the baseline dataset:

- `backend/backend/.artifacts/9f8e78db-9b74-4f5c-9ba8-e65405b0cf03/analysis_report.json`
- `backend/backend/.artifacts/9f8e78db-9b74-4f5c-9ba8-e65405b0cf03/analysis_job.json`
- `backend/backend/.artifacts/9f8e78db-9b74-4f5c-9ba8-e65405b0cf03/ingestion_artifacts.json`
- OCR cache artifacts under `backend/backend/.artifacts/ocr/`

Record at minimum:

- total tokens
- per-stage tokens
- wall-clock runtime
- per-stage latency
- timeout count
- which agents are already compacted
- whether synthesis still dominates token usage

If a `prompt_debug.json` style artifact exists, use it. If it does not exist yet, add one before making further reductions.

## Immediate Follow-On Priorities After Context Reduction Lands

Once the initial context-reduction implementation is in place, use this order for cleanup and follow-up work.

### Priority 1: Normalize The Builder Layer

Goal:

- ensure there is one coherent way to build compact agent contexts

What to do:

- consolidate duplicate helper logic
- ensure all shared clipping/serialization/evidence-selection helpers live in one place
- remove temporary or one-off prompt builder code if a shared pattern now exists
- make sure old raw prompt paths are not silently still being used

Red flags:

- some agents use `context_builders.py` while others still use `_raw_data_summary(...)` directly
- compact JSON is used in some places and pretty JSON in others
- evidence selection logic is duplicated across agents

### Priority 2: Finish Synthesis Compression If It Is Incomplete

Goal:

- make sure synthesis only consumes compact specialist outputs, not broad document context

What to verify:

- no raw document text is sent into synthesis
- no large repeated structured data blobs are sent into synthesis
- the synthesis prompt is built from scorecard + compact specialist summaries + top findings only

This should be the first follow-up if the initial context reduction pass did not complete it.

### Priority 3: Remove Legacy Prompt Builders Gradually

Goal:

- reduce the chance of future regressions back to bloated prompts

Candidates to retire or downgrade:

- `_raw_data_summary(...)`
- `_raw_text_summary(...)`
- inline `json.dumps(..., indent=2)` prompt blocks

This should be done carefully. Some of these helpers may still be useful for debug artifacts or fallback flows, but they should not remain the default prompt path if compact builders now exist.

### Priority 4: Tighten Budgets With Real Data

Goal:

- move from approximate prompt budgets to measured ones

After the first pass lands:

- compare prompt sizes agent by agent
- find which agents still have large long-tail payloads
- reduce evidence counts or text caps where quality still holds

Recommended order:

1. `synthesis_report`
2. `financial_analysis`
3. `tax_compliance`
4. `market_macro`
5. remaining text-heavy agents

### Priority 5: Align Tests With The New Architecture

Goal:

- ensure the compact-context path is the protected default

Add or update tests so they verify:

- compact builders are used
- prompt budgets are enforced
- evidence packs stay deterministic
- synthesis excludes raw document text
- missing-data warnings survive context reduction

If old tests assume the old raw prompt shape, update them to assert behavior rather than exact prompt formatting.

## Files Most Likely To Need Follow-Up Edits

Expect the next round of cleanup to focus on:

- `backend/app/agents/runners.py`
- `backend/app/agents/openrouter_client.py`
- `backend/app/agents/orchestrator.py`
- `backend/app/services/report_assembler.py`
- `backend/app/agents/schemas.py`
- any new builder module such as `backend/app/agents/context_builders.py`
- tests in `backend/tests/`

## Recommended Handoff Questions To Answer In Your First Commit Or Note

When you pick this up, leave behind explicit answers to these questions so the next handoff is easier:

1. Which agents now use compact context builders?
2. Which agents are still on legacy prompt assembly?
3. What is the current largest prompt by token volume?
4. Is synthesis now free of raw document text?
5. Did total tokens go down on the full sample package?
6. Did runtime improve, stay flat, or regress?
7. Which cleanup work remains before runtime tuning can start?

## Definition Of "Context Reduction Complete Enough To Hand Off"

The context-reduction effort is ready to hand off into runtime optimization when all of the following are true:

- at least the highest-cost agents have moved to compact context assembly
- synthesis no longer consumes broad raw document context
- prompt diagnostics exist or prompt sizes can be measured reliably
- legacy raw prompt helpers are no longer the default path for the most expensive agents
- tests cover the compact-path behavior well enough to refactor safely afterward

At that point, the next agent should switch primary focus from "reduce tokens safely" to:

- reducing wall-clock runtime
- shortening stage budgets
- introducing stronger fail-soft behavior
- improving job/progress visibility

That next-stage work is documented in:

- `docs/OPENROUTER_RUNTIME_REDUCTION_PLAN.md`

## Suggested Next-Agent Workflow

Use this sequence after the initial context reduction pass:

1. verify what actually landed
2. measure prompt sizes and remaining hotspots
3. finish synthesis compression if incomplete
4. normalize remaining builder-layer inconsistencies
5. update tests to lock in the compact path
6. hand off into runtime reduction work

## Final Note For The Next Agent

Do not assume lower token count automatically means a successful refactor.

The compacted prompts still need to preserve:

- evidence traceability
- explicit missing-data signaling
- deterministic scorecard compatibility
- usable synthesis inputs

The best result is not simply the smallest prompt. It is the smallest prompt that still preserves stable downstream scoring and report quality.
