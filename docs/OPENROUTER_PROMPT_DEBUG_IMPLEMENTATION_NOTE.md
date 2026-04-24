# OpenRouter Prompt Debug Implementation Note

Instrumentation from `docs/OPENROUTER_PROMPT_DEBUG_EXECUTION_PLAN.md` is now wired through the pipeline.

## What Changed

- `call_agent(...)` now emits request lifecycle diagnostics:
  - `request_started_at`
  - `request_finished_at`
  - `provider_response_received`
  - `usage_received`
  - `tool_call_found`
  - `validation_passed`
- normalized specialist results now preserve `diagnostics`
- timeout/fallback stages now mark token accounting truthfully with:
  - `token_usage_known`
  - `token_usage_unknown_due_to_timeout`
- prompt debug artifacts can now include literal prompt bodies for selected stages

## New Env Flags

- `BIZBUY_PIPELINE_PROMPT_DEBUG_ARTIFACTS_ENABLED=true`
- `BIZBUY_PIPELINE_PROMPT_DEBUG_INCLUDE_BODIES=true`
- `BIZBUY_PIPELINE_PROMPT_DEBUG_STAGES=financial_analysis,synthesis_report`

If no stage allowlist is provided, prompt debug capture defaults to:

- `financial_analysis`
- `synthesis_report`

## Artifact Output

Prompt debug artifacts are written to:

- `backend/.artifacts/<analysis_id>/prompt_debug.json`

When body capture is enabled for a selected stage, the artifact now includes:

- `systemPrompt`
- `userMessage`
- `schemaChars`
- `promptChars`
- `promptSections`
- `contextTruncation`
- `responseChars`
- timeout / fallback flags
- provider-response / usage flags

## Status

The instrumentation and tests are in place. A fresh live debug run is still required to answer the prompt-size findings questions with real captured artifacts.
