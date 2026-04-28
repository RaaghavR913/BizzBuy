# BizBuy Codex Execution Prompts

Use these prompts one at a time.

Start each new Codex context from the latest committed branch state after the previous slice is reviewed and committed.

## Slice 0A: Contract backbone

```text
Implement only Slice 0A from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Scope:
- define the canonical document taxonomy
- define the shared agent envelope
- define NormalizedFinding, evidence reference, and normalized metrics structures
- define ReportOutputV2
- align Python and TypeScript contracts

Files likely involved:
- backend/app/agents/schemas.py
- backend/app/models/schemas.py
- lib/types.ts
- lib/constants.ts
- docs if needed

Constraints:
- do not change runtime behavior yet
- do not switch orchestration order yet
- do not modify the frontend flow yet
- avoid opportunistic refactors

Definition of done:
- one canonical contract exists for document types, agent outputs, and reports
- downstream slices can target these contracts without reinterpretation

Also:
- update tests if contract validation already exists in this area
- summarize assumptions briefly at the end
```

## Slice 0B: Orchestrator scoring hook

```text
Implement only Slice 0B from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 0A being already completed and committed

Scope:
- add backend/app/services/scoring_engine.py as a skeleton interface
- wire the orchestrator to call deterministic scoring after specialist agents
- keep existing scoring logic as fallback or placeholder where needed

Files likely involved:
- backend/app/agents/orchestrator.py
- backend/app/services/scoring_engine.py
- small supporting files only if required

Constraints:
- do not replace existing risk_engine.py behavior wholesale
- do not change the synthesis role yet
- do not change frontend behavior
- avoid broad refactors

Definition of done:
- pipeline execution has a stable place where deterministic scoring occurs after specialist analysis

Also:
- add or update focused tests for the new orchestration hook if practical
- summarize assumptions briefly at the end
```

## Slice 1A: Ingestion foundations

```text
Implement only Slice 1A from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 0B being already completed and committed

Scope:
- add canonical document metadata normalization
- improve preprocessing interfaces for PDFs, spreadsheets, and parsed sections
- shape ingestion output around the new contracts

Files likely involved:
- backend/app/services/intake_service.py
- backend/app/services/ingestion_service.py
- backend/app/services/document_parser.py
- related schemas/tests

Constraints:
- keep dependencies minimal unless clearly required
- do not introduce the job system yet
- prefer a thin vertical slice over full ingestion perfection
- preserve existing flows outside this scope

Definition of done:
- uploaded files can produce structured ingestion artifacts with explicit missing/failed tracking

Also:
- add or update focused tests around normalization and ingestion output shape
- summarize assumptions briefly at the end
```

## Slice 1B: Ingestion confidence and persistence stubs

```text
Implement only Slice 1B from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 1A being already completed and committed

Scope:
- track ingestion confidence
- persist enough ingestion artifacts for downstream scoring/report assembly
- add artifact storage abstraction stubs if needed

Files likely involved:
- ingestion services
- repository or storage abstraction files
- related tests

Constraints:
- keep persistence lightweight in dev
- avoid full production storage design in this slice
- do not add the job system yet

Definition of done:
- downstream slices can consume stable ingestion artifacts instead of transient parsing state

Also:
- add or update focused tests for stored ingestion artifacts where practical
- summarize assumptions briefly at the end
```

## Slice 2A: Normalized specialist outputs

```text
Implement only Slice 2A from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 1B being already completed and committed

Scope:
- update specialist schemas and runners to emit normalized findings
- add normalized metrics, missing inputs, and evidence references
- preserve domain-specific fields where already useful

Files likely involved:
- backend/app/agents/schemas.py
- backend/app/agents/runners.py
- related tests

Constraints:
- keep agent prompts as stable as possible
- do not redesign every domain schema unless required for normalization
- do not change scoring policy yet

Definition of done:
- deterministic code can consume specialist outputs without parsing prose

Also:
- add or update focused tests for runner output validation
- summarize assumptions briefly at the end
```

## Slice 2B: Coverage pass across remaining agents

```text
Implement only Slice 2B from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 2A being already completed and committed

Scope:
- bring any remaining specialist agents onto the shared envelope
- normalize naming inconsistencies across agent outputs
- fill obvious gaps in evidence or missing-input declarations

Files likely involved:
- backend/app/agents/schemas.py
- backend/app/agents/runners.py
- related tests

Constraints:
- no scoring policy changes in this slice
- keep changes narrow and consistency-focused

Definition of done:
- all active specialist agents follow the shared downstream contract

Also:
- add or update coverage tests for any remaining active agents
- summarize assumptions briefly at the end
```

## Slice 3A: Deterministic scoring MVP

```text
Implement only Slice 3A from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 2B being already completed and committed

Scope:
- implement normalized metrics/findings ingestion in backend/app/services/scoring_engine.py
- compute initial scorecards, completeness, confidence, and recommendation
- add conservative conflict handling

Files likely involved:
- backend/app/services/scoring_engine.py
- backend/app/agents/deterministic.py
- backend/app/services/risk_engine.py only for reuse if helpful
- related tests

Constraints:
- reuse existing deterministic math where practical
- avoid mixing recommendation policy back into synthesis
- keep questionnaire-based scoring path available for comparison
- avoid broad refactors

Definition of done:
- pipeline outputs can produce a deterministic scorecard and recommendation

Also:
- add or update focused scoring tests
- summarize assumptions briefly at the end
```

## Slice 3B: Scoring calibration and regression coverage

```text
Implement only Slice 3B from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 3A being already completed and committed

Scope:
- expand tests for scoring rules, overrides, conflicts, and missing-data penalties
- compare selected fixture outputs against expected behavior

Files likely involved:
- backend/tests/test_scoring_engine.py
- backend/tests/test_risk_engine.py
- fixture-based tests as needed

Constraints:
- focus on stability, not new product features
- keep production code changes minimal unless a test exposes a real issue

Definition of done:
- scorer behavior is test-backed enough to support report and frontend work

Also:
- summarize any scoring assumptions or fixture gaps briefly at the end
```

## Slice 4A: Synthesis as narrative only

```text
Implement only Slice 4A from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 3B being already completed and committed

Scope:
- change synthesis inputs to consume deterministic scorecard outputs
- remove synthesis authority over recommendation or final score
- generate narrative sections only

Files likely involved:
- backend/app/agents/orchestrator.py
- backend/app/agents/schemas.py
- backend/app/agents/prompts.py
- related tests

Constraints:
- preserve useful narrative output
- do not let synthesis mutate deterministic decisions
- do not change frontend behavior yet

Definition of done:
- synthesis explains the result but does not decide it

Also:
- add or update focused tests for synthesis input/output contracts
- summarize assumptions briefly at the end
```

## Slice 5A: Canonical summary report assembly

```text
Implement only Slice 5A from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 4A being already completed and committed

Scope:
- add backend/app/services/report_assembler.py
- transform ingestion, agent outputs, scoring outputs, and synthesis into summary-ready ReportOutputV2

Files likely involved:
- backend/app/services/report_assembler.py
- backend/app/agents/orchestrator.py
- related schemas/tests

Constraints:
- summary mode first
- no frontend cutover yet
- keep report contract aligned with existing TypeScript definitions from Slice 0A

Definition of done:
- the pipeline can return a frontend-ready summary report payload

Also:
- add or update focused contract tests for the summary report payload
- summarize assumptions briefly at the end
```

## Slice 5B: Deep review assembly

```text
Implement only Slice 5B from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 5A being already completed and committed

Scope:
- add deep review sections, evidence index, audit trail, and missing-data detail

Files likely involved:
- backend/app/services/report_assembler.py
- related schemas/tests

Constraints:
- use the same evidence base and scorecard as summary mode
- do not build a second scoring path
- keep summary mode stable

Definition of done:
- backend can return summary and deep review variants from the same run

Also:
- add or update focused tests for deep review payload shape
- summarize assumptions briefly at the end
```

## Slice 6A: Frontend report contract adoption

```text
Implement only Slice 6A from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 5A being already completed and committed

Scope:
- update frontend types and report rendering to the new summary contract
- keep the old runtime path available during transition

Files likely involved:
- lib/types.ts
- components/report/*
- app/analyze/report/page.tsx

Constraints:
- do not switch uploads/questions flow yet
- favor compatibility shims over broad UI rewrites
- preserve current user flow outside report rendering

Definition of done:
- the frontend can render the new summary report shape

Also:
- add or update focused frontend tests if present in this area
- summarize assumptions briefly at the end
```

## Slice 6B: Pipeline-first frontend cutover

```text
Implement only Slice 6B from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 6A being already completed and committed
- Slice 5A being already completed and committed

Scope:
- switch lib/api-client.ts and analysis context to pipeline-backed analysis
- keep old endpoints only for fallback or comparison

Files likely involved:
- lib/api-client.ts
- context/AnalysisContext.tsx
- related analyze pages

Constraints:
- do not introduce clarifications redesign in the same slice
- preserve basic report usability throughout the cutover
- avoid broad UI refactors

Definition of done:
- the default frontend analysis path uses the pipeline-backed summary report

Also:
- add or update focused integration or flow tests if practical
- summarize assumptions briefly at the end
```

## Slice 7A: Clarifications conversion

```text
Implement only Slice 7A from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 6B being already completed and committed

Scope:
- convert the questionnaire concept into targeted clarifications
- store clarification answers as supplemental evidence

Files likely involved:
- app/analyze/questions/page.tsx
- clarification service files
- related frontend state

Constraints:
- keep clarifications narrower than the current questionnaire
- do not let user assertions become stronger than documentary evidence by default
- preserve the overall analysis flow

Definition of done:
- the app asks targeted follow-ups instead of relying on a broad manual questionnaire

Also:
- add or update focused tests for clarification generation or storage where practical
- summarize assumptions briefly at the end
```

## Slice 7B: Deep review UI

```text
Implement only Slice 7B from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 5B being already completed and committed
- Slice 6B being already completed and committed

Scope:
- render deep review sections, evidence drilldowns, and conflicts in the frontend

Files likely involved:
- app/analyze/report/page.tsx
- components/report/*
- related frontend types

Constraints:
- do not rebuild summary mode
- keep deep review optional
- preserve summary mode stability

Definition of done:
- users can inspect the analyst-grade report without changing the scoring path

Also:
- add or update focused frontend rendering tests if present
- summarize assumptions briefly at the end
```

## Slice 8A: Analysis jobs and progress

```text
Implement only Slice 8A from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 6B being already completed and committed

Scope:
- add job-based analysis endpoints or equivalent orchestration
- add progress polling or events
- persist analysis status and artifacts

Files likely involved:
- backend/app/api/routes/analyses.py
- backend/app/services/analysis_jobs.py
- backend/app/services/analysis_repository.py
- lib/api-client.ts
- context/AnalysisContext.tsx

Constraints:
- keep local development workflow simple
- avoid bundling full observability and retry logic into this slice
- preserve current pipeline behavior while adding job support

Definition of done:
- long-running analyses survive refreshes and expose progress

Also:
- add or update focused tests for job lifecycle and progress state
- summarize assumptions briefly at the end
```

## Slice 8B: Reliability and observability

```text
Implement only Slice 8B from MULTI_AGENT_PRIMARY_RUNTIME_PLAN.md.

Builds on:
- Slice 8A being already completed and committed

Scope:
- add retries, timeouts, partial-failure handling, cost and latency instrumentation, and rollout flags

Files likely involved:
- orchestration and job service files
- observability or config files
- related tests

Constraints:
- do not change core report contracts unless required for audit metadata
- keep changes targeted to reliability and rollout safety

Definition of done:
- the pipeline is supportable, measurable, and safer to roll out

Also:
- add or update focused tests for partial-failure behavior where practical
- summarize assumptions briefly at the end
```
