# Agent Accuracy And Natural Context Reduction Plan

Date: 2026-04-26
Status: Read-only planning pass. No application code changed in this pass.
Purpose: Give a future `GPT-5.4` high-reasoning window a concrete implementation plan to fix the remaining data-quality issues and reduce prompt/output bloat without introducing hard caps, truncation, or arbitrary context limits.

## Mission

This plan has two goals that must be pursued together:

1. Fix the remaining source-alignment problems in the analysis pipeline.
2. Reduce prompt and agent-output size as much as possible by improving what data is selected and how it flows, not by bolting on artificial limits.

The operating rule for the follow-on pass is:

- Do not add explicit context caps, truncation thresholds, or prompt clipping as the primary solution.
- Reduce context naturally by removing duplication, passing only what each downstream stage truly needs, and cleaning up noisy or misleading intermediate structures.
- Preserve analytical quality. The system should become smaller because it is more precise, not because it is more aggressively cropped.

## Compressed Context

The current pipeline is mostly working, but a few issues remain:

- Explicit asking price exists in the source artifacts for `sample company4`, but the pipeline still falls back to `3.0x SDE` in lending.
- Tax-return fiscal year can still become `1981` because date-of-birth content is being mistaken for a reporting year.
- AR concentration semantics are inflated because grouped rows like `Other clients (18 accounts)` are treated like a single customer.
- Prompt bloat still exists, but the biggest problems are in context assembly and duplicated ingestion payloads, not in the specialist prompt templates themselves.

The prompt templates in `backend/app/agents/prompts.py` are already reasonably compact and downstream-aware. The next pass should treat deterministic extraction, section identity, and context assembly as the primary levers.

## Confirmed Root Causes

### 1. Asking price is present, but the pipeline does not use it reliably

Observed behavior:

- The source CIM contains explicit asking-price data for `sample company4`.
- In artifacts, that data is present in ingestion.
- Lending still often uses the deterministic fallback `3.0x SDE`.

Why this happens:

- `extract_financial_data()` only populates `loan_terms.asking_price` through `_extract_loan_terms(sde_section, ...)` in [backend/app/services/financial_data_extractor.py](C:/S/BizzBuy/backend/app/services/financial_data_extractor.py:42).
- `_extract_loan_terms()` only searches the provided section, not all relevant deal-term sections in [backend/app/services/financial_data_extractor.py](C:/S/BizzBuy/backend/app/services/financial_data_extractor.py:261).
- `run_lending_affordability()` trusts `PipelineInput.asking_price` and otherwise falls back to `round(sde * 3.0)` in [backend/app/agents/runners.py](C:/S/BizzBuy/backend/app/agents/runners.py:1661).
- `run_pipeline()` passes `pipeline_input.asking_price` into lending, but it does not hydrate that field from extracted document data in [backend/app/agents/orchestrator.py](C:/S/BizzBuy/backend/app/agents/orchestrator.py:821).

Conclusion:

- This is primarily a deterministic extraction and state-propagation issue, not a prompt issue.

### 2. DOCX table sections inherit the full narrative body

Observed behavior:

- Asking-price tables and other small DOCX tables can be misclassified because their section identity is polluted by unrelated memo prose.

Why this happens:

- In the DOCX path, each extracted table is stored with `raw_text=narrative` in [backend/app/services/intake_service.py](C:/S/BizzBuy/backend/app/services/intake_service.py:447).
- `infer_section_kind()` inspects `section_name`, `raw_text`, and row values together in [backend/app/services/section_kind.py](C:/S/BizzBuy/backend/app/services/section_kind.py:49).
- That means a tiny deal-terms table can inherit “balance sheet” or other unrelated keywords from the full memo body and be classified incorrectly.

Conclusion:

- This is both an accuracy problem and a context-bloat problem. Fixing it should help both.

### 3. Fiscal year inference still leaks DOB-like years

Observed behavior:

- Some tax-return sections still end up with `fiscal_year = 1981`.

Why this happens:

- `_year_columns()` in [backend/app/services/financial_data_extractor.py](C:/S/BizzBuy/backend/app/services/financial_data_extractor.py:390) accepts short year-looking cells too broadly.
- A value like `March 4, 1981` can be treated as a year-bearing header because the surrounding text remains short enough to pass the current heuristic.
- `infer_latest_fiscal_year()` in [backend/app/services/section_data_normalizer.py](C:/S/BizzBuy/backend/app/services/section_data_normalizer.py:83) relies on `_year_columns()` and contextual cues, but when the bad year is already inferred early, later normalization may preserve it.
- In ingestion, explicit or inferred `fiscal_year` is only replaced if missing in [backend/app/services/ingestion_service.py](C:/S/BizzBuy/backend/app/services/ingestion_service.py:172).

Conclusion:

- This is a deterministic year-detection problem. It should be fixed at inference time, not papered over in prompts.

### 4. Grouped AR buckets are being treated as a single customer

Observed behavior:

- `Other clients (18 accounts)` can become the “largest customer” in AR concentration metrics.

Why this happens:

- `_ar_aging_values()` preserves grouped entries in `customers` in [backend/app/services/section_data_normalizer.py](C:/S/BizzBuy/backend/app/services/section_data_normalizer.py:123).
- `compute_ar_metrics()` converts those rows straight into `customer_concentrations` in [backend/app/agents/deterministic.py](C:/S/BizzBuy/backend/app/agents/deterministic.py:330).

Conclusion:

- The math is working on the wrong semantic unit. This is a normalization/business-rules issue, not an LLM issue.

### 5. Prompt bloat is mainly caused by assembly choices, not template verbosity

Observed behavior:

- Some stages still receive much more information than they need.
- Some agent outputs are fuller than synthesis really needs.

Why this happens:

- The current context builders often include broad evidence packs with `max_items=None`, `max_total_snippet_chars=None`, and `max_fields=None` in [backend/app/agents/context_builders.py](C:/S/BizzBuy/backend/app/agents/context_builders.py:73).
- `run_lending_affordability()` serializes the full financial-analysis output plus precomputed lending figures and scenarios in [backend/app/agents/runners.py](C:/S/BizzBuy/backend/app/agents/runners.py:1667).
- Synthesis still carries broad `specialist_context`, including top findings and summaries for each agent in [backend/app/agents/context_builders.py](C:/S/BizzBuy/backend/app/agents/context_builders.py:205).

Conclusion:

- The next pass should reduce payload size by improving data shape and routing, not by adding caps.

## Design Principles For The Next Pass

The implementation window should follow these principles:

### Accuracy first

- Fix deterministic truth before reducing payloads.
- If a downstream stage is bloated because upstream data is messy or duplicated, fix the upstream structure first.

### Natural reduction only

- Do not solve prompt bloat by adding arbitrary truncation or low global limits.
- Instead:
  - remove duplicate narrative text
  - stop passing fields that are never consumed
  - pass compact summaries of deterministic truth instead of full raw envelopes
  - avoid sending the same fact in multiple formats

### Metric-first specialist contexts

- Specialists should receive:
  - the authoritative deterministic metrics they need
  - a small amount of source evidence sufficient for interpretation
  - explicit missing-data notes where coverage is incomplete
- They should not receive entire upstream outputs unless strictly required.

### Compact-by-structure outputs

- Do not rely only on wording like “be concise.”
- Make compactness structural by ensuring the schemas and handoff envelopes contain only what synthesis or scoring truly uses.

### Preserve debuggability

- Prompt-debug artifacts can remain rich.
- The live prompt path should still be slimmer than the debug path.
- Keep enough diagnostic breadcrumbs to explain why a value was chosen.

## Implementation Plan

### Workstream 1: Fix explicit asking-price extraction and propagation

Priority: Highest
Why first: It fixes a visible business outcome and removes a major downstream distortion in lending.

Target behavior:

- If uploaded documents contain an explicit asking price, that value should become the canonical deal asking price unless the user explicitly overrides it.
- `3.0x SDE` should remain only as a final fallback when no explicit asking price exists anywhere.

Implementation direction:

1. Add a deterministic asking-price extraction path that is not tied only to `sde_summary`.
2. Search all plausible deal-term sections for asking price:
   - DOCX/CIM tables
   - contract/deal-term style tables
   - extracted section data containing `asking_price`
3. Promote asking price into a pipeline-level canonical field before lending runs.
4. Change lending to prefer:
   - user-supplied `PipelineInput.asking_price`
   - extracted canonical asking price
   - otherwise no explicit asking price
   - only then `3.0x SDE` fallback
5. Preserve provenance:
   - explicit user input
   - extracted from document
   - estimated fallback

Suggested file focus:

- [backend/app/services/financial_data_extractor.py](C:/S/BizzBuy/backend/app/services/financial_data_extractor.py)
- [backend/app/services/document_parser.py](C:/S/BizzBuy/backend/app/services/document_parser.py)
- [backend/app/agents/orchestrator.py](C:/S/BizzBuy/backend/app/agents/orchestrator.py)
- [backend/app/agents/runners.py](C:/S/BizzBuy/backend/app/agents/runners.py)

Validation expectations:

- `sample company4` should use `$1,300,000` rather than `3.0x SDE`.
- Existing fallback tests without listing/deal-term docs should still pass.

### Workstream 2: Stop DOCX narrative contamination and duplicate context

Priority: Highest
Why second: It improves both extraction accuracy and prompt compactness with one change.

Target behavior:

- DOCX tables should carry only their own local table context.
- Narrative memo prose should be stored once, separately.
- Section classification should be driven by the table content itself, not the full memo body.

Implementation direction:

1. In the DOCX ingestion path, stop assigning the full narrative body to every table section.
2. For each table section, use one of:
   - table-local text reconstructed from the table
   - no `raw_text` when row structure is sufficient
3. Create one narrative text section for the overall DOCX prose.
4. Re-run section-kind inference with table-local evidence instead of full-document contamination.
5. Confirm that asking-price tables and similar deal-term tables stop being mis-tagged as balance sheets.

Suggested file focus:

- [backend/app/services/intake_service.py](C:/S/BizzBuy/backend/app/services/intake_service.py)
- [backend/app/services/section_kind.py](C:/S/BizzBuy/backend/app/services/section_kind.py)
- [backend/app/services/ingestion_service.py](C:/S/BizzBuy/backend/app/services/ingestion_service.py)

Expected token impact:

- Lower prompt size for any agent consuming DOCX-derived sections.
- Less duplication in prompt-debug bodies too.

### Workstream 3: Harden fiscal-year inference

Priority: High
Why now: It is a clean deterministic bug and it pollutes many downstream artifacts.

Target behavior:

- Identity dates such as DOB must never become `fiscal_year`.
- Only reporting-context years should be accepted.
- If no valid year can be confidently inferred, leave it null rather than guessing.

Implementation direction:

1. Tighten `_year_columns()` to recognize only real reporting-year shapes:
   - `2024`
   - `FY2024`
   - `Fiscal Year 2024`
   - `Year Ended 2024`
   - `As of December 31, 2024`
2. Explicitly reject:
   - full DOB-like dates
   - taxpayer identity blocks
   - arbitrary standalone years in personal metadata
3. Audit whether any OCR section builder is pre-populating fiscal-year-like data that should instead remain unset.
4. Prefer contextual year extraction over bare year extraction when both are present.
5. Add a plausibility rule:
   - if a year comes only from identity-like text and no reporting cue exists, discard it

Suggested file focus:

- [backend/app/services/financial_data_extractor.py](C:/S/BizzBuy/backend/app/services/financial_data_extractor.py)
- [backend/app/services/section_data_normalizer.py](C:/S/BizzBuy/backend/app/services/section_data_normalizer.py)
- [backend/app/services/ocr_markdown_parser.py](C:/S/BizzBuy/backend/app/services/ocr_markdown_parser.py)
- [backend/app/services/ingestion_service.py](C:/S/BizzBuy/backend/app/services/ingestion_service.py)

Validation expectations:

- `1981` should disappear from tax-return fiscal-year fields in the sample artifacts.
- Legitimate tax-year values should still be inferred when actually present.

### Workstream 4: Fix grouped-customer AR semantics

Priority: High
Why now: It is a targeted fix with low blast radius and improves concentration truth.

Target behavior:

- Grouped rows like `Other clients (18 accounts)` should still contribute to totals and aging math.
- They should not be treated as a single real customer for top-customer concentration.

Implementation direction:

1. Keep grouped rows in AR totals.
2. Mark grouped buckets explicitly during normalization.
3. Exclude grouped buckets from `top_customer_percent` and similar single-customer ranking metrics.
4. Optionally preserve a separate metric for “aggregated small-account bucket percent” if useful.

Suggested file focus:

- [backend/app/services/section_data_normalizer.py](C:/S/BizzBuy/backend/app/services/section_data_normalizer.py)
- [backend/app/agents/deterministic.py](C:/S/BizzBuy/backend/app/agents/deterministic.py)

Validation expectations:

- `top_customer_ar_pct` should reflect Apex-like named customers, not the aggregated “other clients” bucket.

### Workstream 5: Reduce specialist prompt size naturally

Priority: High
Why here: After the deterministic fixes, prompt reduction can be done more safely and cleanly.

Important constraint:

- Do not reintroduce generic truncation or artificial caps as the main mechanism.

Target behavior:

- Each specialist should receive the minimum sufficient context for correct interpretation.
- Prompt size should shrink because fewer redundant or irrelevant fields are passed.

Implementation direction by stage:

#### Financial analysis

- Keep deterministic financial metrics as the primary payload.
- Pass only the most relevant supporting sections instead of broad repeated section packs.
- Avoid sending duplicate forms of the same fact:
  - raw text plus normalized fields plus repeated snippets for the same table

#### Tax compliance

- Pass reconciled year/revenue comparisons and tax coverage first.
- Include only tax-return-specific evidence and the corresponding P&L support.
- Avoid identity-heavy snippets unless they are genuinely relevant to an issue.

#### AR collections

- Pass normalized AR totals, aging buckets, DSO, and named-customer concentration.
- Avoid sending full raw AR table bodies when the structured normalized fields already capture the relevant math.

#### Customer concentration

- Prefer structured customer metrics plus a few contract signals.
- Do not duplicate AR customer evidence here unless it adds unique value.

#### Lease and operations

- Preserve raw text where narrative clauses matter.
- Still remove duplicate whole-document memo text that is unrelated to the specific lease or ops question.

#### Market

- Build a smaller business profile plus only the narrowest snippets needed to infer industry, geography, and business model.
- Eliminate broad document packs that restate the same business overview repeatedly.

#### Lending

- This is the biggest prompt-reduction target.
- Replace full serialized financial-analysis output with a compact deterministic lending handoff:
  - explicit asking price provenance
  - adjusted SDE
  - EBITDA
  - working capital
  - a few highest-severity financial risks
  - base case
  - scenario bounds
- Use compact JSON rather than pretty-printed JSON.
- Do not send entire upstream domain objects when only a few values are consumed.

Suggested file focus:

- [backend/app/agents/context_builders.py](C:/S/BizzBuy/backend/app/agents/context_builders.py)
- [backend/app/agents/runners.py](C:/S/BizzBuy/backend/app/agents/runners.py)

Success criterion:

- Prompt size drops materially without adding caps or omitting required analysis signal.

### Workstream 6: Reduce specialist output naturally

Priority: Medium to High
Why later: The current prompt instructions already help, but structural reduction may still be worthwhile after input cleanup.

Target behavior:

- Specialist outputs should contain only what scoring and synthesis actually need.
- They are internal handoff payloads, not final buyer-facing prose.

Implementation direction:

1. Audit what synthesis truly consumes from each specialist envelope:
   - summary
   - overall_score
   - confidence
   - normalized_metrics
   - top findings
   - missing inputs
2. Audit what scoring consumes:
   - validated metrics
   - findings
   - certain fallback raw values from lending
3. Reduce output verbosity structurally:
   - shorter summaries
   - fewer overlapping findings
   - avoid duplicated recommendation language across multiple fields
4. If needed, consider slimming internal schemas in a later pass, but only after verifying no downstream dependency breaks.

Suggested file focus:

- [backend/app/agents/prompts.py](C:/S/BizzBuy/backend/app/agents/prompts.py)
- [backend/app/agents/runners.py](C:/S/BizzBuy/backend/app/agents/runners.py)
- [backend/app/agents/context_builders.py](C:/S/BizzBuy/backend/app/agents/context_builders.py)
- [backend/app/services/scoring_engine.py](C:/S/BizzBuy/backend/app/services/scoring_engine.py)

Important note:

- Prompt wording changes should be the last lever, not the first.
- If prompt edits are made, they should tighten field discipline rather than just say “be shorter.”

### Workstream 7: Slim synthesis context naturally

Priority: Medium
Why not first: Synthesis depends on upstream shape. It should be cleaned after specialist inputs/outputs are cleaned.

Target behavior:

- Synthesis should consume a compact cross-agent handoff, not broad restatements of each specialist payload.

Implementation direction:

1. Keep deterministic scorecard as the primary truth source.
2. For each agent, pass only:
   - score
   - confidence
   - summary
   - highest-value findings
   - missing inputs
3. Remove repeated descriptions that restate the same issue already present in scorecard conflicts or deal breakers.
4. Ensure synthesis does not receive the same risk in multiple near-identical forms.

Suggested file focus:

- [backend/app/agents/context_builders.py](C:/S/BizzBuy/backend/app/agents/context_builders.py)
- [backend/app/agents/runners.py](C:/S/BizzBuy/backend/app/agents/runners.py)

## Explicit Non-Goals

The next pass should not do the following unless a specific blocker is discovered:

- Do not add blanket prompt truncation.
- Do not add global max-snippet or max-field caps just to force smaller prompts.
- Do not rewrite the entire prompt system.
- Do not perform a large schema redesign in the same pass as the deterministic fixes.
- Do not weaken evidence fidelity just to reduce tokens.

## Recommended Execution Order

Use this order so each wave improves correctness before chasing additional compactness:

### Wave 1: Deterministic truth fixes

- explicit asking-price extraction and propagation
- DOCX narrative/table separation
- fiscal-year hardening
- grouped AR semantics

### Wave 2: Natural prompt reduction

- remove duplicate narrative propagation
- convert large handoffs to compact deterministic snapshots
- eliminate redundant section pack duplication

### Wave 3: Natural specialist-output reduction

- tighten internal handoff shape
- remove repeated low-value prose
- preserve only what scoring and synthesis actually consume

### Wave 4: Synthesis cleanup

- shrink cross-agent context
- remove duplicate risk restatement
- keep final buyer-facing synthesis quality intact

## Validation Plan

The follow-on implementation window should validate after each wave.

### Core regression checks

- `sample company4` asking price resolves to `$1,300,000`
- lending no longer reports “explicit asking price was not provided” for that sample
- tax-return fiscal year does not become `1981`
- AR top-customer concentration excludes aggregate “other clients” buckets
- existing no-listing fallback behavior still works where appropriate

### Prompt-size checks

- Compare `prompt_debug.json` before and after changes
- Confirm that live prompts are smaller because they are cleaner, not because they were newly capped
- Inspect especially:
  - `financial_analysis`
  - `tax_compliance`
  - `lending_affordability`
  - `synthesis_report`

### Behavior checks

- Pipeline still completes successfully on the sample artifact set
- Recommendation quality does not degrade
- Missing-data signaling remains explicit and accurate

### Test targets

At minimum, update or add tests around:

- `backend/tests/test_field_population_bugs.py`
- `backend/tests/test_ingestion_service.py`
- `backend/tests/test_ingest_documents_route.py`
- `backend/tests/test_section_kind_ingestion.py`
- `backend/tests/test_runner_normalization.py`
- `backend/tests/test_prompts.py`
- any lending/orchestrator tests that currently assume fallback-only asking price behavior

## Acceptance Criteria

The pass should be considered successful only if all of the following are true:

- Explicit asking price from source documents is used when available.
- `1981`-style DOB leakage is eliminated from fiscal-year inference.
- Grouped AR rows no longer distort top-customer concentration metrics.
- Specialist prompts are materially smaller through cleaner data flow, without introducing explicit hard limits or truncation as the main solution.
- Specialist outputs are compact and high-signal enough for synthesis without losing required scoring data.
- Synthesis input is slimmer and less repetitive than before.

## Handoff Note For The Next GPT-5.4 Window

Treat this as an implementation brief, not a brainstorming prompt.

Recommended posture:

- inspect the current code paths first
- make deterministic fixes before prompt changes
- reduce prompt size by cleaning data flow
- avoid introducing new generic cap-based truncation
- validate against `sample company4` and the relevant backend tests after each wave

If tradeoffs appear, favor:

1. source-truth correctness
2. natural de-duplication
3. smaller handoff payloads
4. prompt wording changes last