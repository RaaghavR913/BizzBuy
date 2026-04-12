# BizBuy Runtime Overview

This document explains what happens when you start the frontend and backend containers, how the multi-agent pipeline runs, how the agents coordinate, and which files in the repo own each part of the system.

## 1. What starts when Docker starts

From [`docker-compose.yml`](/c:/S/BizzBuy/docker-compose.yml):

- `backend`
  - built from [`backend/Dockerfile`](/c:/S/BizzBuy/backend/Dockerfile)
  - runs FastAPI on `localhost:8000`
- `frontend`
  - built from [`Dockerfile`](/c:/S/BizzBuy/Dockerfile)
  - runs Next.js on `localhost:3000`

Environment wiring:

- frontend sends API requests to `http://localhost:8000/api`
- backend enables CORS so the frontend can call it

Backend app entrypoint:

- [`backend/app/main.py`](/c:/S/BizzBuy/backend/app/main.py)

API router:

- [`backend/app/api/router.py`](/c:/S/BizzBuy/backend/app/api/router.py)

Mounted routes:

- `/api/health`
- `/api/parse-documents`
- `/api/analyze`
- `/api/analyses`
- `/api/pipeline`

## 2. End-to-end runtime flow

The product now follows this path:

```text
User uploads documents in frontend
  ->
Frontend calls /api/parse-documents
  ->
Backend normalizes uploads and builds ingestion artifacts
  ->
Frontend stores analysisId + pipeline documents
  ->
User reviews extracted data and answers targeted clarifications
  ->
Frontend starts analysis job with /api/analyses
  ->
Backend runs pipeline:
  ingestion
  parallel specialist agents
  lending affordability
  deterministic scoring
  synthesis narrative
  report assembly
  ->
Frontend polls job status
  ->
Frontend renders summary report
  ->
Optional deep review uses the same report payload
```

## 3. Frontend flow

Main pages:

- [`app/analyze/upload/page.tsx`](/c:/S/BizzBuy/app/analyze/upload/page.tsx)
- [`app/analyze/review/page.tsx`](/c:/S/BizzBuy/app/analyze/review/page.tsx)
- [`app/analyze/questions/page.tsx`](/c:/S/BizzBuy/app/analyze/questions/page.tsx)
- [`app/analyze/report/page.tsx`](/c:/S/BizzBuy/app/analyze/report/page.tsx)

Shared state:

- [`context/AnalysisContext.tsx`](/c:/S/BizzBuy/context/AnalysisContext.tsx)

Frontend API bridge:

- [`lib/api-client.ts`](/c:/S/BizzBuy/lib/api-client.ts)

Upload UI:

- [`components/upload/FileDropZone.tsx`](/c:/S/BizzBuy/components/upload/FileDropZone.tsx)

Canonical frontend types:

- [`lib/types.ts`](/c:/S/BizzBuy/lib/types.ts)
- [`lib/constants.ts`](/c:/S/BizzBuy/lib/constants.ts)

What the frontend does:

1. collect files and document types
2. send uploads to `/api/parse-documents`
3. keep `analysisId`, `pipelineDocuments`, and clarifications in context
4. start an analysis job for document-backed runs
5. poll job progress
6. render report output

## 4. Parse-documents step

Route:

- [`backend/app/api/routes/parse_documents.py`](/c:/S/BizzBuy/backend/app/api/routes/parse_documents.py)

Service:

- [`backend/app/services/document_parser.py`](/c:/S/BizzBuy/backend/app/services/document_parser.py)

Supporting services:

- [`backend/app/services/intake_service.py`](/c:/S/BizzBuy/backend/app/services/intake_service.py)
- [`backend/app/services/ingestion_service.py`](/c:/S/BizzBuy/backend/app/services/ingestion_service.py)
- [`backend/app/services/analysis_repository.py`](/c:/S/BizzBuy/backend/app/services/analysis_repository.py)

Purpose:

- normalize uploaded files
- assign canonical document types
- produce structured sections and extracted data
- return `analysisId`
- return `pipelineDocuments`
- return compatibility `FinancialData`

The main ingestion schema lives in:

- [`backend/app/agents/schemas.py`](/c:/S/BizzBuy/backend/app/agents/schemas.py)

Key structures:

- `DocumentType`
- `DocumentInfo`
- `DocumentSection`
- `IngestionOutput`
- `IngestionMetadata`

## 5. Clarifications step

Frontend clarification logic:

- [`lib/clarification-service.ts`](/c:/S/BizzBuy/lib/clarification-service.ts)

Backend clarification service:

- [`backend/app/services/clarification_service.py`](/c:/S/BizzBuy/backend/app/services/clarification_service.py)

Clarifications are:

- targeted follow-up questions
- generated from missing or weak evidence
- stored as supplemental evidence
- weaker than documentary evidence by default

This replaces the old broad questionnaire as the primary analysis driver.

## 6. Analysis job runtime

Route:

- [`backend/app/api/routes/analyses.py`](/c:/S/BizzBuy/backend/app/api/routes/analyses.py)

Job service:

- [`backend/app/services/analysis_jobs.py`](/c:/S/BizzBuy/backend/app/services/analysis_jobs.py)

Artifact persistence:

- [`backend/app/services/analysis_repository.py`](/c:/S/BizzBuy/backend/app/services/analysis_repository.py)

What happens:

1. frontend posts analysis inputs to `/api/analyses`
2. backend creates a queued job record
3. backend runs the analysis in a background thread
4. frontend polls `/api/analyses/{analysisId}`
5. backend returns the final report when the job is completed

## 7. The multi-agent pipeline

Core orchestrator:

- [`backend/app/agents/orchestrator.py`](/c:/S/BizzBuy/backend/app/agents/orchestrator.py)

The pipeline sequence is:

```text
PipelineInput
  ->
run_document_ingestion
  ->
parallel specialist agents
  ->
lending affordability
  ->
deterministic scoring engine
  ->
synthesis narrative
  ->
report assembly
  ->
ReportOutputV2
```

Pipeline state model:

- [`backend/app/agents/schemas.py`](/c:/S/BizzBuy/backend/app/agents/schemas.py)

Important object:

- `PipelineState`

It stores:

- pipeline input
- ingestion result
- each specialist result
- deterministic scorecard
- synthesis result
- metadata, partial failures, token usage, and timings

## 8. How the agents coordinate

The agents do not freeform chat with each other.

They coordinate through structured state.

The pattern is:

```text
IngestionOutput
  ->
specialist runners
  ->
AgentEnvelope objects
  ->
deterministic scoring engine
  ->
DeterministicScorecard
  ->
synthesis report
  ->
report assembler
```

That means:

- the orchestrator controls execution order
- each agent reads shared evidence, not another agent's prose
- deterministic code merges the specialist outputs
- synthesis explains deterministic results instead of deciding them

## 9. Agent registry

Registry:

- [`backend/app/agents/registry.py`](/c:/S/BizzBuy/backend/app/agents/registry.py)

Registered agents:

- `document-ingestion`
- `financial-analysis`
- `tax-compliance`
- `ar-collections`
- `customer-concentration`
- `operations-transferability`
- `lease-contract`
- `market-macro`
- `lending-affordability`
- `synthesis-report`

Each registry entry defines:

- model
- prompt key
- schema class
- phase
- dependencies
- token budget

## 10. What each agent does

Agent runner implementations:

- [`backend/app/agents/runners.py`](/c:/S/BizzBuy/backend/app/agents/runners.py)

### Document ingestion

Function:

- `run_document_ingestion`

Purpose:

- convert document payloads into canonical `IngestionOutput`

### Financial analysis

Function:

- `run_financial_analysis`

Purpose:

- analyze revenue, margins, EBITDA, SDE, working capital, and financial risk

### Tax compliance

Function:

- `run_tax_compliance`

Purpose:

- compare reported revenue to tax support and identify compliance exposure

### AR collections

Function:

- `run_ar_collections`

Purpose:

- analyze receivables quality, DSO, aged AR, and collectibility risk

### Customer concentration

Function:

- `run_customer_concentration`

Purpose:

- measure customer dependency and concentration risk

### Operations transferability

Function:

- `run_ops_transferability`

Purpose:

- assess owner dependence, personnel transfer risk, and operational continuity

### Lease and contract

Function:

- `run_lease_contract`

Purpose:

- assess lease assignment risk and transferability of key agreements

### Market and macro

Function:

- `run_market_macro`

Purpose:

- assess industry and local market context

### Lending affordability

Function:

- `run_lending_affordability`

Purpose:

- evaluate DSCR, SBA eligibility, price reasonableness, and buyer cash needs

### Synthesis report

Function:

- `run_synthesis_report`

Purpose:

- write the plain-language narrative after scoring is already determined

## 11. Where Claude is called

Claude client:

- [`backend/app/agents/claude_client.py`](/c:/S/BizzBuy/backend/app/agents/claude_client.py)

What it does:

- sends prompt + tool schema to Anthropic
- forces structured tool output
- validates the result with Pydantic
- retries if the response is invalid
- returns an `AgentResult`

So each specialist runner follows this shape:

```text
deterministic precompute
  ->
prompt construction
  ->
Claude structured call
  ->
schema validation
  ->
normalization into AgentEnvelope
```

## 12. Deterministic layer

Deterministic helper logic:

- [`backend/app/agents/deterministic.py`](/c:/S/BizzBuy/backend/app/agents/deterministic.py)

This file owns:

- metric extraction helpers
- business context inference
- SBA math
- precomputed metrics used to guide prompts

Final scoring authority:

- [`backend/app/services/scoring_engine.py`](/c:/S/BizzBuy/backend/app/services/scoring_engine.py)

This file owns:

- metric merging
- conservative conflict resolution
- completeness/confidence scoring
- technical scorecards
- buyer-facing dimensions
- overall risk score
- final recommendation

Important principle:

- agents analyze
- deterministic code decides

## 13. Canonical contracts

Primary backend contract file:

- [`backend/app/agents/schemas.py`](/c:/S/BizzBuy/backend/app/agents/schemas.py)

Primary frontend/backend report contract file:

- [`backend/app/models/schemas.py`](/c:/S/BizzBuy/backend/app/models/schemas.py)
- [`lib/types.ts`](/c:/S/BizzBuy/lib/types.ts)

Important shared structures:

- `NormalizedMetric`
- `NormalizedFinding`
- `MissingInput`
- `EvidenceReference`
- `AgentEnvelope`
- `DeterministicScorecard`
- `ReportOutputV2`

These are the main contract boundaries between:

- ingestion
- specialist agent outputs
- deterministic scoring
- report assembly
- frontend rendering

## 14. Report assembly

Assembler:

- [`backend/app/services/report_assembler.py`](/c:/S/BizzBuy/backend/app/services/report_assembler.py)

Input:

- ingestion output
- specialist results
- deterministic scorecard
- synthesis result
- clarification evidence
- pipeline metadata

Output:

- `ReportOutputV2`

That includes:

- summary report data
- deterministic scorecard
- optional deep review
- metadata and audit information

## 15. Frontend report rendering

Report page:

- [`app/analyze/report/page.tsx`](/c:/S/BizzBuy/app/analyze/report/page.tsx)

Deep review component:

- [`components/report/DeepReview.tsx`](/c:/S/BizzBuy/components/report/DeepReview.tsx)

Normalization bridge:

- [`lib/report-normalization.ts`](/c:/S/BizzBuy/lib/report-normalization.ts)

Why the normalization file exists:

- older UI components still expect the legacy `ReportOutput`
- backend now returns `ReportOutputV2`
- the bridge converts the new contract into the old rendering shape where needed

## 16. Architecture diagram

```text
Docker Compose
  |
  +-- Frontend container (Next.js, :3000)
  |     |
  |     +-- upload page
  |     +-- review page
  |     +-- clarifications page
  |     +-- report page
  |     +-- AnalysisContext
  |     +-- api-client
  |
  +-- Backend container (FastAPI, :8000)
        |
        +-- /api/parse-documents
        |     -> intake_service
        |     -> ingestion_service
        |     -> document_parser
        |     -> analysis_repository
        |
        +-- /api/analyses
        |     -> analysis_jobs
        |
        +-- orchestrator.run_pipeline
              |
              +-- ingestion
              +-- parallel specialists
              +-- lending
              +-- deterministic scoring
              +-- synthesis
              +-- report assembly
```

## 17. Data flow diagram

```text
Uploaded Files
  ->
Intake + normalization
  ->
IngestionOutput
  - documents
  - sections
  - extracted data
  - raw text
  - confidence
  - missing inputs
  ->
Specialist runners
  ->
AgentEnvelope outputs
  - normalized metrics
  - findings
  - evidence
  - missing inputs
  ->
Deterministic scoring engine
  ->
DeterministicScorecard
  - overall risk
  - recommendation
  - technical scorecards
  - buyer-facing dimensions
  - conflicts
  - completeness/confidence
  ->
Synthesis narrative
  ->
Report assembler
  ->
ReportOutputV2
  ->
Frontend summary + deep review
```

## 18. Repo map by responsibility

### Frontend flow

- [`app/analyze/*`](/c:/S/BizzBuy/app/analyze)

### Frontend shared state

- [`context/AnalysisContext.tsx`](/c:/S/BizzBuy/context/AnalysisContext.tsx)

### Frontend API bridge

- [`lib/api-client.ts`](/c:/S/BizzBuy/lib/api-client.ts)

### Frontend types and compatibility

- [`lib/types.ts`](/c:/S/BizzBuy/lib/types.ts)
- [`lib/constants.ts`](/c:/S/BizzBuy/lib/constants.ts)
- [`lib/report-normalization.ts`](/c:/S/BizzBuy/lib/report-normalization.ts)

### Upload UI

- [`components/upload/FileDropZone.tsx`](/c:/S/BizzBuy/components/upload/FileDropZone.tsx)

### Report UI

- [`components/report/*`](/c:/S/BizzBuy/components/report)

### Backend routes

- [`backend/app/api/routes/*`](/c:/S/BizzBuy/backend/app/api/routes)

### Ingestion and persistence

- [`backend/app/services/intake_service.py`](/c:/S/BizzBuy/backend/app/services/intake_service.py)
- [`backend/app/services/ingestion_service.py`](/c:/S/BizzBuy/backend/app/services/ingestion_service.py)
- [`backend/app/services/document_parser.py`](/c:/S/BizzBuy/backend/app/services/document_parser.py)
- [`backend/app/services/analysis_repository.py`](/c:/S/BizzBuy/backend/app/services/analysis_repository.py)

### Analysis job runtime

- [`backend/app/services/analysis_jobs.py`](/c:/S/BizzBuy/backend/app/services/analysis_jobs.py)

### Agent system

- [`backend/app/agents/registry.py`](/c:/S/BizzBuy/backend/app/agents/registry.py)
- [`backend/app/agents/prompts.py`](/c:/S/BizzBuy/backend/app/agents/prompts.py)
- [`backend/app/agents/claude_client.py`](/c:/S/BizzBuy/backend/app/agents/claude_client.py)
- [`backend/app/agents/runners.py`](/c:/S/BizzBuy/backend/app/agents/runners.py)
- [`backend/app/agents/orchestrator.py`](/c:/S/BizzBuy/backend/app/agents/orchestrator.py)
- [`backend/app/agents/schemas.py`](/c:/S/BizzBuy/backend/app/agents/schemas.py)
- [`backend/app/agents/deterministic.py`](/c:/S/BizzBuy/backend/app/agents/deterministic.py)

### Deterministic scoring and report assembly

- [`backend/app/services/scoring_engine.py`](/c:/S/BizzBuy/backend/app/services/scoring_engine.py)
- [`backend/app/services/report_assembler.py`](/c:/S/BizzBuy/backend/app/services/report_assembler.py)

### Clarifications

- [`backend/app/services/clarification_service.py`](/c:/S/BizzBuy/backend/app/services/clarification_service.py)
- [`lib/clarification-service.ts`](/c:/S/BizzBuy/lib/clarification-service.ts)

### Legacy deterministic path

- [`backend/app/services/analysis_service.py`](/c:/S/BizzBuy/backend/app/services/analysis_service.py)
- [`backend/app/services/risk_engine.py`](/c:/S/BizzBuy/backend/app/services/risk_engine.py)

## 19. Mental model

The cleanest way to think about the system is:

- frontend collects inputs and renders outputs
- ingestion converts files into usable evidence
- specialist agents interpret evidence by domain
- deterministic code computes the final decision
- synthesis writes the explanation
- report assembly packages everything for the UI

If you ask, "where is the final truth?", the answer is:

- source evidence starts in ingestion
- specialist interpretation lives in `AgentEnvelope`
- final decision truth lives in `DeterministicScorecard`
- user-facing narrative lives in synthesis
- user-facing payload shape lives in `ReportOutputV2`
