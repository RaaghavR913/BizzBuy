# OpenRouter Prompt Debug Execution Plan

## Purpose

This plan is for a separate GPT-5.4 instance to execute.

The goal is to make the slow OpenRouter stages observable enough that we can answer, with evidence:

1. exactly what prompt payloads are being built
2. exactly what prompt payloads are being sent
3. whether timeouts are happening before the provider returns
4. whether token usage is missing because of timeouts or because of internal result handling bugs
5. whether `financial_analysis` and `synthesis_report` are still too large even after context reduction

This plan is intentionally focused on instrumentation and diagnosis, not on immediate architectural refactors.

## Why This Plan Exists

Recent runs show:

- runtime improved materially
- total token counts dropped materially
- `financial_analysis` and `synthesis_report` still timed out
- both stages then used deterministic fallbacks
- both fallback stages reported `total_tokens = 0`

That does **not** necessarily mean "no prompt was sent". It likely means:

- a prompt was built
- a request was started
- the request timed out locally
- the fallback path returned a synthetic `AgentResult`
- the synthetic result did not carry provider `usage`

We now need to capture the exact lifecycle so we stop guessing.

## Current Observability State

Already present:

- per-stage timeout budgets in `backend/app/agents/registry.py`
- stage timing / queued / started / completed timestamps in pipeline metadata
- prompt size summary fields such as:
  - `prompt_chars`
  - `prompt_sections`
  - `context_truncation`
  - `evidence_count`
- optional prompt debug artifact support in:
  - `backend/app/services/analysis_repository.py`
  - `backend/app/agents/orchestrator.py`

Important limitation:

- prompt debug artifacts are currently disabled by config unless enabled via env
- current prompt debug artifact serializer only stores summary metadata, not the literal prompts
- some stages appear to lose diagnostics after normalization

## Key Suspected Gaps

These are the highest-probability causes of confusing telemetry:

### 1. Diagnostics lost during normalization

In `backend/app/agents/runners.py`, helper functions that wrap agent results may be dropping `diagnostics`.

Likely suspect:

- `_copy_result(...)`

If that helper does not preserve `diagnostics`, then prompt metrics from `call_agent(...)` will be lost for normalized specialist outputs.

### 2. Prompt debug artifact is too shallow

Current debug artifact structure records prompt summaries, but not:

- `system_prompt`
- `user_message`
- tool schema size as a separate field per stage
- whether the request actually reached the provider
- whether a timeout occurred before provider `usage` was available

### 3. Token accounting is ambiguous for fallback stages

When a stage times out and fallback is used:

- local `token_usage` may remain zero
- but the provider may still have processed some of the request

This makes `total_tokens = 0` misleading.

## Deliverables

The executing agent should produce all of the following:

1. full prompt debug artifacts that show the exact prompts for chosen debug runs
2. corrected diagnostics propagation through normalized results
3. improved timeout/fallback telemetry
4. tests covering the new debug instrumentation
5. a short follow-up note or doc summarizing what the captured prompts reveal

## Scope

Focus only on the slow, high-value stages first:

- `financial_analysis`
- `synthesis_report`

Optionally include:

- `tax_compliance`

Do not try to instrument every stage deeply in the first pass unless the implementation is clean and cheap.

## Implementation Plan

## Phase 1: Preserve Diagnostics Through Result Normalization

### Goal

Ensure prompt diagnostics from `call_agent(...)` survive into pipeline stage metrics for every successful specialist.

### Tasks

1. inspect all helper functions in `backend/app/agents/runners.py` that wrap or copy `AgentResult`
2. ensure `diagnostics` is preserved when:
   - domain outputs are normalized
   - `AgentEnvelope` wrappers are created
   - fallback results are transformed

### Expected Code Touchpoints

- `backend/app/agents/runners.py`
- especially `_copy_result(...)`

### Acceptance Criteria

After the change:

- successful non-fallback specialists show non-null `prompt_chars`
- successful non-fallback specialists show `prompt_sections`
- stage metrics no longer randomly show null diagnostics unless no prompt existed

## Phase 2: Enable Full Prompt Debug Artifacts

### Goal

Persist the actual literal prompts used for selected stages in selected runs.

### Tasks

1. add an env-gated option to persist full prompt bodies for debug runs
2. store, per selected stage:
   - `systemPrompt`
   - `userMessage`
   - `schemaChars`
   - `promptChars`
   - `promptSections`
   - `contextTruncation`
   - `responseChars`
   - `timedOut`
   - `fallbackUsed`
   - `model`
3. save this as `prompt_debug.json` under the analysis artifact directory

### Important Guardrail

Do not enable literal prompt persistence by default in production-like runs.

Recommended gating:

- existing flag: `BIZBUY_PIPELINE_PROMPT_DEBUG_ARTIFACTS_ENABLED`
- plus one of:
  - `BIZBUY_PIPELINE_PROMPT_DEBUG_INCLUDE_BODIES`
  - or stage allowlist config such as `BIZBUY_PIPELINE_PROMPT_DEBUG_STAGES`

### Suggested Artifact Shape

```json
{
  "analysisId": "...",
  "generatedAt": "...",
  "stages": {
    "financial_analysis": {
      "status": "success",
      "timedOut": true,
      "fallbackUsed": true,
      "model": "z-ai/glm-5.1",
      "promptChars": 4934,
      "schemaChars": 12345,
      "responseChars": 1721,
      "promptSections": {
        "metrics": 507,
        "evidence_pack": 4377
      },
      "contextTruncation": {...},
      "systemPrompt": "...",
      "userMessage": "..."
    }
  }
}
```

### Acceptance Criteria

When debug mode is enabled and a run completes:

- `prompt_debug.json` is written
- it contains the literal prompts for selected stages
- the file is small enough to be usable but detailed enough to diagnose prompt composition

## Phase 3: Record Whether The Provider Response Was Ever Received

### Goal

Distinguish these cases:

1. prompt built but request never sent
2. request sent but timed out before any provider response
3. provider response returned but usage missing
4. provider response returned with usage

### Tasks

In `backend/app/agents/openrouter_client.py`, add diagnostics fields such as:

- `request_started_at`
- `request_finished_at`
- `provider_response_received`
- `usage_received`
- `tool_call_found`
- `validation_passed`

These should be returned in `AgentResult.diagnostics`.

### Suggested Semantics

- `provider_response_received = true` only after `client.chat.completions.create(...)` returns a response object
- `usage_received = true` only when `response.usage` is present and parseable

### Acceptance Criteria

For fallback runs, we can tell whether:

- the local timeout happened before any response came back
- or the provider returned something but the app lost usage later

## Phase 4: Make Timeout/Fallback Token Reporting Honest

### Goal

Stop treating `0` tokens on a timed-out fallback stage as if it meant "no prompt happened".

### Tasks

Add explicit diagnostics or metadata fields such as:

- `token_usage_known`
- `token_usage_unknown_due_to_timeout`
- `provider_response_received`
- `provider_usage_received`

This can live in:

- `AgentResult.diagnostics`
- `PipelineStageMetric`
- or both

### Recommendation

Keep `total_tokens` numeric for compatibility, but pair it with a truthfulness flag.

Example:

- `total_tokens: 0`
- `token_usage_known: false`
- `token_usage_unknown_due_to_timeout: true`

### Acceptance Criteria

A future reviewer looking at `analysis_report.json` should not mistake fallback-stage `0` token counts for "no prompt was sent".

## Phase 5: Capture Full-Prompt Runs For The Slow Stages

### Goal

Get concrete evidence from real runs.

### Tasks

Run at least one full sample package with prompt debug enabled for:

- `financial_analysis`
- `synthesis_report`

If possible, also include:

- `tax_compliance`

Then inspect:

- literal prompt bodies
- prompt section sizes
- truncation metadata
- timeout behavior
- whether the schema itself is a large hidden contributor

### Questions To Answer From The Captured Artifacts

1. Is the `userMessage` still too large?
2. Is the output schema size surprisingly large?
3. Is `synthesis_report` still dominated by specialist context?
4. Is `financial_analysis` still carrying too much evidence text?
5. Are the prompt builders producing redundant fields?
6. Are we truncating intelligently or just clipping raw text everywhere?

## Phase 6: Write A Findings Summary

### Goal

Turn the debug run into a compact engineering conclusion.

### Deliverable

Either:

- a short new doc under `docs/`

or:

- an appended section in one of the existing OpenRouter plan docs

### The Summary Should Answer

1. Why are `financial_analysis` and `synthesis_report` still timing out?
2. Is the main culprit:
   - prompt size
   - schema size
   - model latency
   - response verbosity
   - fallback/result wiring
3. Which exact prompt sections are still too large?
4. What should be changed next?

## Recommended Code Changes

The executing agent should expect to touch some or all of these files:

- `backend/app/agents/openrouter_client.py`
- `backend/app/agents/runners.py`
- `backend/app/agents/orchestrator.py`
- `backend/app/agents/context_builders.py`
- `backend/app/agents/schemas.py`
- `backend/app/services/analysis_repository.py`
- `backend/app/core/config.py`
- tests in `backend/tests/`

## Suggested Tests

Add or update tests for:

1. diagnostics survive normalization
2. prompt debug artifact is written when enabled
3. prompt debug artifact includes literal prompt bodies when the body flag is enabled
4. timed-out fallback stages mark token usage as unknown rather than silently implying zero work
5. provider-response flags are correctly populated for success and timeout paths

Suggested test names:

- `test_copy_result_preserves_diagnostics`
- `test_prompt_debug_artifact_writes_full_prompt_bodies_when_enabled`
- `test_timeout_fallback_marks_token_usage_unknown`
- `test_openrouter_client_sets_provider_response_flags_on_success`
- `test_openrouter_client_timeout_path_preserves_prompt_diagnostics`

## Operational Notes

### Keep full-prompt capture opt-in

Literal prompt bodies may be large and may contain sensitive or proprietary document excerpts.

The plan should therefore:

- keep summary diagnostics always available
- keep literal prompt body capture opt-in and temporary

### Start with only the slow stages

Full prompt capture for every stage will create noise quickly.

Start with:

- `financial_analysis`
- `synthesis_report`

That is enough to answer most current questions.

## Recommendations On Helping These Agents Complete

These recommendations are guidance for the human owner and the follow-up agents, based on current evidence.

### Recommendation 1: Add the debug instrumentation first

Do this before making large additional changes.

Why:

- right now the runs are faster but still ambiguous
- without literal prompt capture and better timeout accounting, it is too easy to optimize blindly

### Recommendation 2: Keep the shorter timeouts for now

Do **not** immediately raise the timeouts just to make the agents "finish".

Why:

- the shorter timeouts exposed the current problem clearly
- raising them would hide the problem and make wall-clock regress again

### Recommendation 3: Fix the financial fallback → lending interface

This is a concrete bug or integration mismatch.

The financial fallback appears to be successful enough for reporting, but not shaped well enough for lending to consume.

That should be fixed regardless of model choice.

### Recommendation 4: Do not change models yet as the first move

Current recommendation:

- debug first
- inspect literal prompts
- verify whether prompt shape or schema size is still the primary cause

Why:

- `financial_analysis` prompt size is now around `4934` chars in the sample, which is not obviously huge by itself
- `synthesis_report` prompt is still larger at around `18179` chars, but we need the full prompt and schema picture before concluding model latency is the dominant issue
- changing models now would mix two variables:
  - prompt-shape changes
  - model-behavior changes

### Recommendation 5: Be open to changing models for those two agents later

After debugging, it may make sense to route:

- `financial_analysis`
- `synthesis_report`

to different models than the rest.

But treat that as a second-phase experiment, not the first debugging step.

Decision rule:

- if full-prompt capture shows these stages are now reasonably compact, yet they still time out often, then model latency/behavior becomes a stronger suspect
- if full-prompt capture shows they are still bloated or schema-heavy, fix that first

## Success Criteria

This debugging effort is successful when we can answer all of the following with direct evidence from artifacts:

1. What exact prompts were sent for `financial_analysis` and `synthesis_report`?
2. Did the provider ever return a response before timeout?
3. Are token counts truly unknown, or are they being lost internally?
4. Which prompt sections still dominate size?
5. Is the next best move:
   - more prompt compression
   - schema simplification
   - fallback/interface fixes
   - or model changes

## Suggested Final Handoff Note

When the executing agent is done, they should leave a short summary covering:

- what was instrumented
- where prompt debug artifacts are now written
- what the captured prompts showed
- whether `financial_analysis` and `synthesis_report` should remain on the current model
- what the next concrete code change should be
