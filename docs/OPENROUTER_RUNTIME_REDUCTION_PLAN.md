# OpenRouter Runtime Reduction Plan

## Purpose

This document focuses on reducing the end-to-end wall-clock runtime of the document-first analysis pipeline.

It is intentionally separate from prompt-condensation strategy, though the two are closely related.

This plan explicitly excludes model-routing changes. In other words, it assumes we keep the current per-agent model selection as-is for now and seek runtime wins through:

- smaller and more targeted contexts
- better stage budgeting
- reduced critical-path dependence on slow agents
- deterministic fallback behavior
- improved observability

Primary related document:

- `docs/OPENROUTER_CONTEXT_CONDENSATION_PLAN.md`

## Current Status

The first slice of the related prompt-condensation work has already landed in code.

Implemented groundwork:

- new prompt builder module: `backend/app/agents/context_builders.py`
- specialist runners now use compact builder-generated `user_message` payloads for:
  - `financial_analysis`
  - `tax_compliance`
  - `ar_collections`
  - `customer_concentration`
  - `operations_transferability`
  - `lease_contract`
  - `market_macro`
  - `synthesis_report`
- synthesis now receives compact specialist briefs and a reduced scorecard slice rather than the older larger JSON assembly path
- targeted runner tests now assert that:
  - financial prompts do not include raw row dumps by default
  - market prompts cap document text
  - synthesis prompts exclude oversized raw specialist context and trim validated metrics

Relevant files:

- `backend/app/agents/context_builders.py`
- `backend/app/agents/runners.py`
- `backend/tests/test_runner_normalization.py`

Not yet implemented from this runtime plan:

- prompt diagnostics / prompt debug artifacts
- stage-specific timeout budgets
- timeout-aware fallback envelopes
- richer per-agent lifecycle telemetry
- improved `analysis_job.json` live concurrency reporting
- lending critical-path reduction

Implication for the next context window:

- do not redo prompt compaction first
- build on the new context-builder layer and move next into observability, timeout policy, and fallback behavior

## Summary

The pipeline already runs specialist agents in parallel. The user-visible runtime is therefore dominated by the critical path:

1. ingestion
2. the slowest applicable specialist
3. synthesis

For the sample run in:

- `backend/backend/.artifacts/9f8e78db-9b74-4f5c-9ba8-e65405b0cf03/analysis_report.json`
- `backend/backend/.artifacts/9f8e78db-9b74-4f5c-9ba8-e65405b0cf03/analysis_job.json`

the rough shape was:

- ingestion: ~`0.01s`
- specialists: blocked by `financial_analysis` timing out at `240s`
- synthesis: ~`90s`
- total wall-clock: ~`330s`

That means the biggest runtime wins come from:

1. making `financial_analysis` return much faster
2. making `synthesis_report` return much faster
3. removing or shrinking dependent critical-path steps such as `lending_affordability`

Improving already-fast parallel specialists is still useful, but it produces much smaller wall-clock gains than reducing the slowest stage and the post-specialist synthesis stage.

## Current Execution Model

## Specialist calls are already parallel

The current implementation already runs applicable specialists concurrently.

Relevant code:

- `backend/app/services/analysis_jobs.py`
- `backend/app/agents/orchestrator.py`
- `backend/app/agents/openrouter_client.py`

Execution pattern:

1. `start_analysis_job(...)` creates a dedicated thread pool for the pipeline.
2. `run_pipeline(...)` starts ingestion.
3. `run_pipeline(...)` launches applicable specialists with `asyncio.gather(...)`.
4. each specialist call runs inside `run_in_executor(...)`.
5. each worker thread performs a blocking OpenRouter request.

Important nuance:

- individual agent calls are blocking within their worker thread
- the pipeline as a whole is concurrent because those blocking calls occur on different executor threads

## Why the job artifact looks serial

`analysis_job.json` stores one current pipeline progress state and a cumulative `completed_agents` list.

It does not currently store:

- live per-agent running state
- per-agent start timestamps
- per-agent completion timestamps in the job record itself
- a list of currently active specialist threads

As a result, the artifact visually reads like agents are running one after another, even though they are not.

This distinction matters because runtime optimization should focus on critical-path latency, not on "enabling parallelism" that already exists.

## Critical Path Analysis

## Sample-run evidence

From the sample run:

- wall-clock runtime: ~`330.35s`
- sum of specialist latencies: ~`660.00s`

This proves overlap already exists. If specialists were serial, wall-clock runtime would be at least the sum of specialist runtimes before synthesis began.

## Practical critical path

In the current pipeline, the user waits for:

```text
ingestion
  -> all applicable specialists to finish
     -> especially the slowest specialist
  -> lending (if applicable and financial succeeds)
  -> deterministic scorecard
  -> synthesis
```

For the sample run, that effectively became:

```text
ingestion
  -> financial_analysis timeout at 240s
  -> synthesis at 90s
  -> done
```

This is the core reason runtime feels slow even though multiple specialists overlap.

## Runtime Reduction Goals

The pipeline should aim for the following user-facing improvements:

1. make most document-first runs complete within a clearly lower latency budget
2. avoid waiting the full global timeout for a single weak stage
3. ensure a slow or overloaded specialist does not hold the entire pipeline hostage
4. preserve report quality and structured evidence
5. preserve existing partial-failure behavior where useful

Suggested operational targets:

- `financial_analysis`: complete or fail-soft within `60-90s`
- `synthesis_report`: complete within `20-45s`
- most remaining specialists: complete within `15-60s`
- full end-to-end document-first run: ideally under `120-180s` on normal packages

These are target ranges, not hard guarantees.

## Strategy Overview

Runtime should be reduced through six coordinated workstreams:

1. reduce the amount of context processed by the slowest stages
2. add better stage-specific timeout budgets
3. shorten or remove avoidable critical-path dependencies
4. add deterministic or partial fallbacks for expensive LLM-dependent stages
5. improve observability so future slowdowns are diagnosable
6. improve UX reporting so parallelism is visible and runtime expectations feel credible

## Workstream 1: Reduce Context Processed By Slowest Stages

This is the highest-leverage workstream because LLM runtime is heavily correlated with prompt complexity, schema complexity, and output length.

The main runtime offenders in the sample run were:

- `financial_analysis`
- `synthesis_report`
- `tax_compliance`

These should be optimized first.

### 1.1 Financial analysis prompt simplification

Current pattern:

- large deterministic metrics payload
- raw extracted financial section dumps
- potentially large row arrays from structured sections
- complex structured output schema

Observed issue:

- `financial_analysis` reached the full `240s` timeout in the sample run

Planned changes:

- replace raw row dumps with compact evidence packs
- send only the metrics required for decision-making
- cap the number of supporting evidence items
- avoid sending duplicate representations of the same statement data
- consider splitting must-have fields from nice-to-have descriptive fields

Expected runtime impact:

- likely the single biggest improvement in total wall-clock time

### 1.2 Synthesis prompt compression

Current pattern:

- receives deterministic scorecard
- receives specialist-derived narrative context
- currently very high token consumption in the sample

Observed issue:

- `synthesis_report` used `43,384` tokens and took about `90s`

Planned changes:

- synthesis should consume only a compact set of specialist summaries
- do not re-send raw document text
- do not send broad repeated structured detail
- cap top findings per agent
- send only the high-value scorecard slices needed for narrative explanation

Expected runtime impact:

- high
- likely the second-largest wall-clock improvement after financial analysis

### 1.3 Tax compliance compression

Current pattern:

- combines tax metrics with raw extracted data
- can include a lot of detail if financial packages are large

Planned changes:

- send tax coverage summary
- send discrepancy summary
- send selected evidence only
- preserve explicit warnings for missing returns

Expected runtime impact:

- moderate
- especially valuable when tax returns are large or noisy

## Workstream 2: Add Stage-Specific Timeout Budgets

The current pipeline uses one broad stage timeout value:

- `BIZBUY_PIPELINE_STAGE_TIMEOUT_SECONDS`
- default: `240s`

This creates a bad failure mode:

- a slow specialist can consume the full timeout budget even when it is unlikely to recover

### 2.1 Why stage-specific timeouts matter

Different agents have different roles and different acceptable failure costs.

Examples:

- `financial_analysis` is important, but waiting a full `240s` is often too expensive
- `customer_concentration` should not need nearly as much time
- `market_macro` should not have the same timeout as a complex financial parser
- `synthesis_report` is important, but the pipeline should not be stalled indefinitely by narrative assembly

### 2.2 Proposed timeout policy

Replace the single global stage timeout with per-stage defaults.

Suggested first-pass budgets:

- `financial_analysis`: `60-90s`
- `tax_compliance`: `60-90s`
- `ar_collections`: `30-45s`
- `customer_concentration`: `30-45s`
- `operations_transferability`: `30-45s`
- `lease_contract`: `30-60s`
- `market_macro`: `30-60s`
- `lending_affordability`: `30-45s`
- `synthesis_report`: `30-60s`

Implementation direction:

- introduce a config map or registry-level timeout field
- preserve the global timeout as a fallback default

Suggested code touchpoints:

- `backend/app/agents/registry.py`
- `backend/app/agents/orchestrator.py`
- `backend/app/core/config.py`

### 2.3 Fail-soft after timeout

When a stage times out:

- record timeout metadata
- keep partial-failure behavior
- continue to score and synthesize when safe
- favor structured fallback content over waiting longer

This turns runtime from:

- "wait forever and maybe get one more answer"

into:

- "stop waiting, preserve what we know, finish the report"

## Workstream 3: Shorten Critical-Path Dependencies

Not all stages are equally important to the critical path.

The critical-path dependency graph should be made as shallow as possible.

### 3.1 Re-examine lending as a critical-path LLM stage

Current behavior:

- `lending_affordability` depends on `financial_analysis`
- if financial fails, lending is skipped
- if financial succeeds, lending becomes another post-specialist stage

Observation:

- much of lending is already deterministic:
  - SDE-based valuation assumptions
  - SBA loan math
  - DSCR calculations
  - scenario analysis

Plan:

- move as much lending output generation as possible into deterministic code
- reserve LLM behavior, if still needed later, for small explanatory wording only

This reduces:

- critical-path length
- risk of another slow LLM stage after specialists

### 3.2 Avoid redundant dependence on the full financial domain output

If lending only needs a small subset of financial facts, it should depend on a compact normalized financial summary rather than the entire domain-shaped output.

That allows:

- smaller downstream prompts
- simpler fallback paths
- possible partial lending completion even if the financial narrative agent fails

## Workstream 4: Add Deterministic And Partial Fallbacks

The repo already includes a deterministic fallback when all applicable LLM agents fail. That idea should be extended more aggressively to runtime-sensitive stages.

### 4.1 Financial fallback

If financial narrative generation exceeds its shorter timeout:

- preserve extracted financial metrics
- preserve scorecard-compatible values
- emit a compact fallback envelope with:
  - summary
  - key normalized metrics
  - missing-data notes
  - low-confidence narrative

This is preferable to:

- timing out completely and contributing nothing

### 4.2 Synthesis fallback

If synthesis exceeds its timeout:

- assemble a deterministic summary directly from:
  - scorecard
  - top findings
  - missing inputs
  - completed specialist summaries

The current code already has some deterministic summary behavior; this should be strengthened and made explicit as a first-class fallback path.

### 4.3 Specialist mini-fallbacks

For some specialists, deterministic or semi-deterministic fallback is possible:

- `ar_collections`
- `customer_concentration`
- `lease_contract`

These do not have to be fully equivalent to the LLM outputs. They only need to:

- preserve essential metrics
- preserve top risks
- preserve evidence anchoring
- unblock scoring and synthesis

## Workstream 5: Improve Observability

Runtime optimization is much harder without deeper artifacts and metrics.

### 5.1 Per-agent lifecycle telemetry

Add lifecycle fields for each stage:

- queued time
- started time
- completed time
- timed_out boolean
- prompt size
- output size
- evidence count
- context truncation metadata

Suggested storage:

- `analysis_report.metadata.auditMetadata.stageMetrics`
- optional debug artifact per run

### 5.2 Prompt diagnostics

For each agent call, capture:

- serialized prompt length
- character count
- component breakdown
  - metrics payload size
  - raw text size
  - evidence size
  - schema size if measurable

This should be done before major refactors so improvements can be measured cleanly.

### 5.3 Critical-path reporting

Add explicit critical-path analysis to runtime debug output:

- slowest specialist stage
- time from specialist completion to synthesis completion
- wall-clock vs summed stage latency

This will help future agents avoid mistaken conclusions about serial execution.

## Workstream 6: Improve Progress Reporting

This does not change actual runtime, but it changes how runtime is perceived and debugged.

### 6.1 Show live parallelism in job artifacts

Add richer job progress fields, for example:

- `running_agents`
- `completed_agents`
- `queued_agents`
- per-agent status map
- per-agent start timestamps

Today the user sees one completion at a time and naturally assumes serial behavior.

### 6.2 Show stage transitions more honestly

Suggested UI/progress states:

- `specialists_started`
- `n_of_m_specialists_completed`
- `synthesis_started`
- `fallback_mode_active`

This makes it clear that multiple specialists are in-flight together.

## Recommended Implementation Sequence

The work should be sequenced to maximize impact quickly and keep regression risk manageable.

## Phase 1: Instrumentation and runtime observability

Goal:

- make the runtime behavior measurable before changing logic

Deliverables:

- prompt diagnostics
- per-stage lifecycle timestamps
- optional prompt debug artifact
- explicit wall-clock vs summed-latency reporting

Code touchpoints:

- `backend/app/agents/openrouter_client.py`
- `backend/app/agents/orchestrator.py`
- `backend/app/services/analysis_jobs.py`
- `backend/app/services/analysis_repository.py`

## Phase 2: Financial analysis runtime reduction

Goal:

- attack the current critical-path bottleneck first

Deliverables:

- compact financial context builder
- shorter financial timeout budget
- financial fallback envelope on timeout

Success metric:

- `financial_analysis` no longer commonly consumes the full timeout

## Phase 3: Synthesis runtime reduction

Goal:

- shorten the second major critical-path stage

Deliverables:

- compact synthesis context builder
- deterministic synthesis fallback
- smaller synthesis timeout budget

Success metric:

- synthesis time materially reduced on large document packages

## Phase 4: Lending critical-path reduction

Goal:

- reduce dependency depth after specialists

Deliverables:

- move lending math to deterministic path
- optionally keep only lightweight narrative generation if still needed

Success metric:

- lending no longer meaningfully extends the critical path

## Phase 5: Remaining specialist tuning

Goal:

- reduce tail latency and improve resilience

Deliverables:

- stage budgets for customer, AR, lease, ops, market
- evidence-pack based prompt inputs
- deterministic/partial fallback where practical

## Phase 6: UX and artifact reporting improvements

Goal:

- make runtime behavior legible

Deliverables:

- richer `analysis_job.json`
- UI-ready running/completed specialist status fields

## Concrete Engineering Tasks

### Task group A: Add per-stage timeout configuration

Possible implementation options:

1. extend `AgentConfig` with a timeout field
2. create a separate timeout map in orchestrator
3. use env-configured overrides with registry defaults

Recommended:

- put default timeout on `AgentConfig`
- allow env override later if needed

### Task group B: Add prompt/runtime diagnostics

Implement:

- `prompt_chars`
- `prompt_sections`
- `response_chars`
- `started_at`
- `completed_at`
- `timed_out`

for each stage metric or debug artifact

### Task group C: Build compact context builders

Introduce a dedicated context layer, for example:

- `backend/app/agents/context_builders.py`

Responsibilities:

- compact JSON serialization
- evidence selection
- caps and truncation
- stage-specific input assembly

### Task group D: Add fallback builders

Introduce fallback helpers, for example:

- `build_financial_fallback_envelope(...)`
- `build_synthesis_fallback(...)`
- optional specialist fallback helpers

### Task group E: Enrich job progress shape

Extend progress persistence so that job artifacts and SSE snapshots can expose:

- running agent set
- completed agent set
- stage-level lifecycle state

## Validation Plan

Each phase should be validated against real artifact-heavy packages, not just unit tests.

## Validation datasets

Use at minimum:

- the current complete sample package at `9f8e78db-9b74-4f5c-9ba8-e65405b0cf03`
- at least one smaller package
- at least one OCR-heavy package

## Validation metrics

Track:

- total wall-clock runtime
- per-stage latency
- timeout frequency
- total prompt tokens
- per-agent prompt tokens if measurable
- final scorecard stability
- report completeness
- fallback activation rate

## Validation questions

1. Did total runtime go down?
2. Did the slowest specialist get substantially faster?
3. Did synthesis get substantially faster?
4. Did report quality regress?
5. Did missing-data behavior remain intact?
6. Did fallback outputs remain useful and safe?

## Suggested Tests

Add tests for:

- per-agent timeout policy selection
- financial fallback activation after timeout
- synthesis fallback activation after timeout
- prompt diagnostics artifact generation
- progress snapshots showing multiple running agents

Suggested test names:

- `test_stage_specific_timeout_applied_to_financial_analysis`
- `test_financial_analysis_timeout_uses_fallback_envelope`
- `test_synthesis_timeout_uses_deterministic_summary`
- `test_progress_snapshot_tracks_running_agents`
- `test_prompt_debug_artifact_includes_component_sizes`

## Risks And Tradeoffs

### Risk 1: Faster may become shallower

Aggressive compression can cause:

- lower-quality reasoning
- missed evidence
- weaker summaries

Mitigation:

- add fallback-safe evidence packs
- validate against full sample runs
- compress in phases rather than all at once

### Risk 2: Shorter timeouts may increase partial results

This is often acceptable, but it can reduce narrative richness.

Mitigation:

- make fallbacks structured and informative
- keep deterministic scorecard robust

### Risk 3: Added observability can create artifact bloat

Mitigation:

- gate detailed prompt debug artifacts behind a flag
- keep audit metadata concise by default

## Definition Of Success

This runtime effort is successful if, after rollout:

- the pipeline no longer commonly waits the full timeout for `financial_analysis`
- synthesis no longer dominates post-specialist runtime
- large document-first packages finish materially faster
- reports remain coherent and evidence-grounded
- progress artifacts better reflect true concurrent execution

## Recommended Immediate Next Step

If another agent is picking this up, the best first implementation slice is:

1. add instrumentation and per-stage lifecycle data
2. add stage-specific timeout configuration
3. refactor `financial_analysis` to use compact context + fallback
4. refactor `synthesis_report` to use compact context + fallback

This sequence gives the best chance of reducing wall-clock runtime quickly while preserving the current pipeline architecture.
