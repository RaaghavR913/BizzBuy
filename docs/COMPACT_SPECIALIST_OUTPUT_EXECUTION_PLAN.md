# Compact Specialist Output Execution Plan

## Purpose

This document is a handoff plan for another GPT-5.4 high-reasoning context window to execute.

The goal is to make every specialist agent produce output that is:

- concise
- compact
- number-dense
- evidence-grounded
- synthesis-ready
- high-signal
- non-redundant
- decision-oriented
- plain-language when needed
- still fully analytical

The intended downstream consumer is another agent:

- `synthesis_report`

That synthesis agent should be able to consume specialist outputs as compact context without losing analytical quality.

## Primary Objective

Adjust the specialist and synthesis prompt instructions so that agents still perform full analysis, but present their output in a tighter, more synthesis-friendly way.

The specialists must not become shallow. They should still:

- reason carefully
- inspect the provided metrics and evidence
- identify risks and opportunities
- explain confidence and missing inputs
- produce a complete schema-valid output

The change is about:

- how much they say
- how repetitive they are
- how many items they emit
- how dense and downstream-usable the wording is

The change is not about:

- removing analysis
- weakening evidence
- changing downstream contracts

## Non-Negotiable Constraints

These constraints must be honored exactly.

Do not change:

- normalization logic in `backend/app/agents/runners.py`
- deterministic scorecard derivation
- synthesis context building assumptions
- downstream report assembly assumptions
- schema shapes in `backend/app/agents/schemas.py`
- prompt context builders in `backend/app/agents/context_builders.py`
- the data model consumed by the rest of the pipeline

Do not change:

- what downstream code expects the agent outputs to look like
- field names
- nesting structure
- required schema contracts

This means:

- no schema redesign
- no adapter layer
- no normalization refactor
- no scorecard refactor
- no synthesis input refactor

The implementation surface should be intentionally narrow.

Preferred files to edit:

- `backend/app/agents/prompts.py`
- prompt-focused tests in `backend/tests/`

Avoid editing unless absolutely necessary:

- `backend/app/agents/runners.py`
- `backend/app/agents/context_builders.py`
- `backend/app/agents/schemas.py`
- `backend/app/services/scoring_engine.py`
- `backend/app/services/report_assembler.py`

## Why This Plan Exists

We previously compressed:

- prompt context sent into specialists
- prompt context sent into synthesis

But we have not yet systematically compressed:

- the specialist agents' own returned analyses

That means specialists may still produce output that is:

- verbose
- repetitive
- over-explanatory
- not optimized for another LLM to consume

The better architecture is:

```text
documents
-> specialist context
-> specialist returns compact, high-signal, synthesis-ready analysis
-> normalization
-> synthesis consumes those compact outputs
```

This plan moves us toward that architecture without changing downstream contracts.

## Key Design Principle

The agents should do full diligence and return the same schema, but the textual content inside the schema should be shaped to be:

- terse but not cryptic
- dense with numbers and evidence
- explicit about what matters most
- capped in list length
- capped in prose length
- easy for another agent to summarize

Think:

- "full analysis in compact form"

not:

- "reduced analysis"

## Execution Strategy

The next GPT-5.4 context window should primarily rewrite prompt instructions, not code flow.

The main work is to strengthen the prompt language so every agent understands that its output is:

- a specialist analysis
- later consumed by a synthesis agent
- expected to be compact and high-signal

### Important Prompt-Writing Requirement

Use as many adjectives as needed to shape the output behavior clearly.

Do not be shy about telling the model to be:

- crisp
- compact
- economical
- highly specific
- evidence-led
- number-heavy
- non-repetitive
- downstream-friendly
- synthesis-ready
- tightly written
- ranking-focused
- decision-useful
- confidence-calibrated
- plain-English but not fluffy

This is one of the few places where strong stylistic language is desirable.

## Implementation Scope

Update every relevant prompt in:

- `backend/app/agents/prompts.py`

Targets:

- `FINANCIAL_ANALYSIS_PROMPT`
- `TAX_COMPLIANCE_PROMPT`
- `AR_COLLECTIONS_PROMPT`
- `CUSTOMER_CONCENTRATION_PROMPT`
- `OPERATIONS_TRANSFERABILITY_PROMPT`
- `LEASE_CONTRACT_PROMPT`
- `MARKET_MACRO_PROMPT`
- `LENDING_AFFORDABILITY_PROMPT`
- `SYNTHESIS_REPORT_PROMPT`

## Prompt Shaping Pattern

Each specialist prompt should be updated to explicitly tell the model:

1. another synthesis agent will read this output later
2. the output must remain schema-valid
3. the output must preserve analytical quality
4. summaries must be short and high-signal
5. findings must be ranked and capped
6. evidence should be numeric and document-specific when possible
7. avoid repeating the same point across fields
8. missing data should be stated once, clearly

### Core Wording Pattern To Introduce

Every specialist prompt should contain a variant of this instruction:

```text
Your output will be consumed by a downstream synthesis agent. Perform a full specialist analysis, but present it in a compact, high-signal, evidence-grounded, non-redundant form. Prefer concrete numbers, specific comparisons, and ranked findings over long prose. Do not sacrifice analytical quality. Be concise because another agent will synthesize your output later.
```

### Core Output Style Pattern

Every specialist prompt should also contain a variant of:

```text
Write crisply, tightly, and economically. Keep summaries short, specific, and number-dense. Avoid filler, repetition, throat-clearing, and restating the same issue in multiple ways. Make each sentence earn its place.
```

### Core Finding Pattern

For agents that emit findings or risks:

```text
Return only the most decision-relevant findings. Rank them by severity and materiality. Prefer fewer, stronger findings over many overlapping findings. Each finding should be concrete, evidence-based, and as concise as possible while still being clear.
```

### Core Confidence Pattern

```text
If data is incomplete, say so plainly and briefly. Lower confidence rather than compensating with extra prose.
```

## Per-Agent Intent

The next context window should adapt the exact wording by agent, but the intent below should be preserved.

### Financial Analysis

Keep full financial reasoning, but force output to be:

- compact
- numerically explicit
- buyer-facing
- evidence-cited
- concise in `summary`

Ask for:

- top financial risks, not every possible observation
- direct references to margins, SDE, EBITDA, working capital, cash conversion, or missing years
- limited repetition between `summary` and `risks`

### Tax Compliance

Keep full reconciliation logic, but make output:

- discrepancy-first
- filing-risk-first
- short and specific

Ask for:

- only the most material discrepancies and compliance issues
- brief, concrete summaries
- concise exposure statements

### AR / Collections

Keep full AR analysis, but make output:

- sharply ranked
- aging-driven
- concise

Ask for:

- the most material collectibility issues only
- limited overlap between summary and flags
- numbers first, prose second

### Customer Concentration

Keep full concentration reasoning, but make output:

- compact
- contract-aware
- dependency-focused

Ask for:

- only the biggest concentration and durability issues
- compact discussion of missing customer data
- strong ranking of top risks

### Operations / Transferability

Keep full transferability reasoning, but make output:

- dependency-focused
- handoff-focused
- compact

Ask for:

- only the most material transferability blockers
- concise handling of owner dependence and key-person risk

### Lease / Contract

Keep full lease review, but make output:

- clause-focused
- transferability-focused
- concise

Ask for:

- top lease transfer risks only
- no repeated explanation of the same assignment issue in multiple places

### Market / Macro

Keep full market reasoning, but make output:

- decision-relevant
- not essay-like
- selective

Ask for:

- top threats and top opportunities only
- concise market summary
- explicit uncertainty if based on limited context

### Lending / Affordability

Keep full lending reasoning, but make output:

- ratio-driven
- structure-driven
- compact

Ask for:

- DSCR, cash need, price multiple, and bankability implications first
- minimal narrative drift

### Synthesis Report

Even though synthesis is the consumer, it should also be tightened.

Ask it to be:

- decisive
- compact
- high-signal
- non-redundant

The synthesis prompt should explicitly say:

- specialist outputs are already compact specialist analyses
- do not re-expand them into verbose prose
- summarize only what matters most for the buyer

## What Must Not Happen

The next context window must avoid these mistakes:

- making prompts so terse that output quality degrades
- reducing analytical coverage in order to sound concise
- removing nuance that the scorecard or synthesis depends on
- changing schema contracts to force smaller outputs
- changing normalization code to accommodate new output shapes
- making specialists return fewer required fields

This work is about:

- wording discipline
- ranking discipline
- brevity discipline

It is not about:

- contract redesign

## Recommended Editing Approach

1. Read `backend/app/agents/prompts.py` fully.
2. Identify every prompt's current:
   - role
   - task
   - output instructions
3. Add an explicit "downstream synthesis consumer" framing to each specialist prompt.
4. Add explicit style constraints for:
   - compactness
   - number density
   - non-redundancy
   - ranked findings
   - limited prose
5. Keep agent-specific analytical criteria intact.
6. Update synthesis prompt to assume compact specialist outputs and avoid re-inflating them.
7. Add or update tests that assert the prompt strings include the new downstream-consumer and compactness guidance.

## Testing Requirements

The next context window should add prompt-focused tests that verify the prompt content includes the new instruction patterns.

Suggested test targets:

- prompt text now mentions downstream synthesis consumption for specialists
- prompt text now mentions compact / concise / non-redundant / number-dense output
- prompt text now asks for ranked, decision-relevant findings
- synthesis prompt now says not to re-expand compact specialist outputs

Possible test locations:

- `backend/tests/test_runner_normalization.py`
- a new prompt-focused test file if cleaner

Do not create brittle tests around exact full prompt text unless necessary.
Prefer assertions on required phrases or required instruction themes.

## Acceptance Criteria

This task is complete only when all of the following are true:

1. All specialist prompts instruct the model that its output will be used by a downstream synthesis agent.
2. All specialist prompts explicitly request compact, evidence-grounded, number-dense, non-redundant output.
3. All specialist prompts preserve full analytical intent.
4. The synthesis prompt explicitly assumes compact specialist outputs and avoids re-expanding them.
5. No schema files are changed.
6. No normalization logic is changed.
7. No scorecard logic is changed.
8. No synthesis context builder assumptions are changed.
9. Tests pass.

## Suggested Final Note For The Next Context Window

When the next GPT-5.4 context window finishes, it should report:

- which prompt blocks were updated
- what output-shaping language was added
- which tests were added or changed
- confirmation that schemas, normalization, scorecard logic, and synthesis context assumptions were not changed

## Relevant Files

- `backend/app/agents/prompts.py`
- `backend/app/agents/schemas.py`
- `backend/app/agents/runners.py`
- `backend/app/agents/context_builders.py`
- `backend/tests/test_runner_normalization.py`

## Final Reminder

The specialist agents should still do a full analysis.

The goal is not:

- "say less because less is cheaper"

The goal is:

- "say the same analytical truth in a tighter, cleaner, more synthesis-friendly form"

