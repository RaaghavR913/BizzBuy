# BizBuy Multi-Agent Primary Runtime Plan

## 1. Purpose

This document is the implementation plan for turning BizBuy into a product where the Claude-driven multi-agent pipeline is the app's primary runtime path, while deterministic code remains the authority for:

- final risk scoring
- affordability math
- conservative conflict resolution
- recommendation policy
- auditability

The goal is not "replace deterministic logic with agents."

The goal is:

1. Use agents to analyze the uploaded documents in specialist lanes.
2. Convert those agent outputs into structured, evidence-backed findings.
3. Feed those findings into a deterministic score and recommendation engine.
4. Render a buyer-friendly report by default.
5. Render a deeper technical review when the user asks for it.

This plan is written against the repository as it exists today.

---

## 2. Executive Summary

### 2.1 Current reality

Today the app has two overlapping architectures:

- The frontend wizard in `app/analyze/*` currently talks to the deterministic FastAPI backend through:
  - `POST /api/parse-documents`
  - `POST /api/analyze`
- The more advanced agent pipeline exists in `backend/app/agents/*` and is exposed through:
  - `POST /api/pipeline`

But that pipeline is not the main product path yet.

### 2.2 What must change

The app needs to move from:

```text
frontend wizard -> deterministic backend -> report
```

to:

```text
frontend wizard
  -> document ingestion
  -> multi-agent specialist analysis
  -> deterministic scoring and recommendation engine
  -> summary report or deep review report
```

### 2.3 Core architectural decision

The winning architecture is:

- Claude agents own extraction, domain interpretation, and evidence surfacing.
- Deterministic code owns score calculation, affordability math, and recommendation policy.
- The synthesis agent writes explanations, not authoritative scores.

### 2.4 Recommended delivery strategy

Do this in phases:

1. Standardize agent outputs so the deterministic scorer can trust them.
2. Make the pipeline return a canonical report object, not just raw pipeline state.
3. Switch the frontend from `/analyze` to a pipeline-backed report flow.
4. Replace the static questionnaire with targeted clarifications driven by document gaps.
5. Add summary mode and deep review mode.
6. Add persistence, observability, and rollout controls.

---

## 3. Current Repository Assessment

## 3.1 What is active today

### Frontend

- `app/analyze/upload/page.tsx`
- `app/analyze/review/page.tsx`
- `app/analyze/questions/page.tsx`
- `app/analyze/report/page.tsx`
- `context/AnalysisContext.tsx`
- `lib/api-client.ts`
- `lib/types.ts`
- `components/report/*`

### Backend deterministic path

- `backend/app/api/routes/parse_documents.py`
- `backend/app/api/routes/analyze.py`
- `backend/app/services/document_parser.py`
- `backend/app/services/analysis_service.py`
- `backend/app/services/risk_engine.py`
- `backend/app/services/report_writer.py`
- `backend/app/models/schemas.py`

### Backend agent path

- `backend/app/api/routes/pipeline.py`
- `backend/app/agents/orchestrator.py`
- `backend/app/agents/runners.py`
- `backend/app/agents/deterministic.py`
- `backend/app/agents/schemas.py`
- `backend/app/agents/claude_client.py`
- `backend/app/agents/prompts.py`
- `backend/app/agents/registry.py`

## 3.2 The biggest current gaps

### Gap 1: The app still uses the deterministic endpoint as the primary runtime

The frontend currently calls `parse-documents` and `analyze`, not `pipeline`.

### Gap 2: The pipeline returns `PipelineState`, not the final report contract the frontend needs

The UI expects the shape defined in `lib/types.ts` under `ReportOutput`.

The agent pipeline returns a technical orchestration object:

- per-agent `AgentResult`
- token usage
- metadata
- synthesis result

That is useful for orchestration, but it is not the app's canonical runtime response yet.

### Gap 3: Deterministic scoring is not yet built on top of the agent outputs

The current deterministic scoring engine (`backend/app/services/risk_engine.py`) scores mostly from the user questionnaire plus a small amount of financial data.

The future model needs scoring to be driven primarily by:

- ingestion output
- specialist agent metrics
- specialist agent flags/findings
- cross-agent conflicts
- document completeness

### Gap 4: Document ingestion is still scaffolded on the deterministic path

`backend/app/services/document_parser.py` currently returns placeholder notes and low completeness, not true extraction.

### Gap 5: Frontend document types do not match backend agent document types

Current frontend document types in `lib/constants.ts` are:

- `income_statement`
- `balance_sheet`
- `cash_flow`
- `loan_terms`
- `tax_return`

The pipeline expects a richer canonical taxonomy in `backend/app/agents/schemas.py`, including:

- `profit_and_loss`
- `cash_flow_statement`
- `tax_return_1120s`
- `tax_return_1040`
- `tax_return_schedule_c`
- `ar_aging_report`
- `customer_list`
- `contract`
- `lease_agreement`
- `employee_roster`
- `insurance_policy`
- `equipment_list`
- `other`

These need to be reconciled.

### Gap 6: Agent outputs are not normalized enough for deterministic downstream use

Today the agent schemas are detailed but inconsistent in how they expose findings:

- `risks`
- `compliance_flags`
- `collectibility_flags`
- `contract_risks`
- `threats`

That forces special-case handling in deterministic code.

We need one normalized findings envelope across all agents.

### Gap 7: The synthesis agent currently owns too much conceptual authority

The current synthesis agent schema includes recommendation and risk score concepts.

That should change.

The deterministic engine should own:

- overall risk score
- recommendation
- deal-breaker overrides
- affordability policy

The synthesis agent should explain those results, not author them.

### Gap 8: The current frontend "questions" step is built around manual risk input

That flow made sense when documents were not the primary evidence source.

If documents and specialist agents become primary, then this step should become:

- targeted clarifications
- missing-data follow-up
- optional buyer context

not the main scoring input.

### Gap 9: The current app likely has stale frontend code around phase-2 progress

`app/analyze/questions/page.tsx` references `PHASE2_AGENT_LABELS` and `phase2Progress`, but those definitions were not found in the file search. This suggests stale or partial migration work around the old architecture.

### Gap 10: The pipeline is still exposed as a technical endpoint, not a product endpoint

`POST /api/pipeline` is useful for backend development, but the product needs analysis-oriented endpoints and a frontend contract that:

- accepts uploads and configuration
- reports progress
- returns a canonical report
- optionally returns deep review artifacts

---

## 4. Product End State

At the end of this migration, the product should behave like this:

1. The user uploads a diligence package.
2. The system classifies and ingests all documents.
3. Claude-driven specialist agents analyze the document corpus in parallel, by specialty.
4. Deterministic code merges the evidence and computes:
   - internal specialist scorecards
   - buyer-facing summary dimensions
   - overall risk score
   - affordability score
   - recommendation
   - completeness/confidence indicators
5. The frontend renders one of two report modes:
   - Summary report
   - Deep review report
6. The user can inspect:
   - the final conclusion
   - why the conclusion happened
   - which documents and evidence support each major finding
   - what is missing or low-confidence

The user should be able to trust that:

- the narrative may be LLM-authored
- the decision policy is code-authored

---

## 5. Design Principles

## 5.1 Agents analyze; code decides

Agents are excellent at:

- reading messy documents
- extracting structured facts
- identifying domain-specific issues
- writing plain-language summaries

Agents are not the final authority on:

- numeric truth
- weighting policy
- override logic
- risk thresholds
- recommendation policy

## 5.2 Evidence must be structured

The deterministic engine should never have to parse natural language summaries to understand what happened.

Every agent output should include:

- standardized findings
- normalized metrics
- confidence
- evidence references
- missing data markers

## 5.3 Conservative conflict resolution

Whenever multiple agents or documents disagree:

- choose the more conservative value for scoring
- preserve the disagreement in the report
- raise a conflict flag

## 5.4 Summary and deep review are views over the same evidence base

Do not build two separate pipelines.

Build one pipeline that produces:

- a shared evidence model
- a deterministic scorecard
- summary-ready narratives
- optional deep-review sections

## 5.5 The frontend should become thinner

Business logic should continue moving out of the Next.js client and into the backend.

The frontend should own:

- upload UX
- progress UI
- report rendering
- report mode toggles

The backend should own:

- document ingestion
- agent orchestration
- scoring
- recommendation
- audit trail generation

## 5.6 Missing data is itself a risk signal

If the user does not provide tax returns, AR aging, contracts, or other critical materials:

- do not silently skip the issue
- do not infer safety
- do not lower the risk score because the evidence is absent

Instead:

- add uncertainty penalties
- expose completeness separately
- tell the user what is missing

---

## 6. Target End-to-End Runtime

## 6.1 Recommended user flow

### Step 1: Upload and classify documents

The user uploads all available documents and chooses document types from a canonical taxonomy.

### Step 2: Review document inventory

The system shows:

- what was uploaded
- what was recognized
- what is missing
- what optional high-value docs are recommended

### Step 3: Clarifications (not broad questionnaire)

The system asks only targeted follow-up questions where the documents cannot answer high-impact diligence questions.

Examples:

- Does the owner personally manage the top 5 customer relationships?
- Are there any pending lawsuits not reflected in the uploaded package?
- Are supplier relationships assignable to a buyer?
- Is there a management layer beneath the owner?

These clarifications become supplemental evidence, not the primary basis of scoring.

### Step 4: Run analysis

The backend runs:

1. ingestion
2. parallel specialist agents
3. deterministic scorecard engine
4. narrative synthesis
5. report assembly

### Step 5: Report

The user sees:

- Summary mode by default
- Deep review mode if selected or expanded

## 6.2 Runtime flow diagram

```text
User Uploads Diligence Package
  ->
Document Intake Service
  ->
Ingestion Agent + Parsers
  ->
Canonical Ingestion Output
  ->
Parallel Specialist Agents
  ->
Normalized Findings + Metrics + Evidence
  ->
Deterministic Score Engine
  ->
Recommendation Policy + Report Builder
  ->
Synthesis Narrative
  ->
Summary Report + Deep Review Report
```

## 6.3 Recommended backend execution model

For the final product architecture, this should be an analysis job model, not a single synchronous request that blocks the browser for the entire runtime.

Recommended long-term shape:

- `POST /api/analyses`
- `GET /api/analyses/{analysis_id}`
- `GET /api/analyses/{analysis_id}/events`
- `GET /api/analyses/{analysis_id}/report`
- `GET /api/analyses/{analysis_id}/report?mode=deep`

However, for migration simplicity, there is a staged path:

- Phase A: keep a synchronous pipeline endpoint while backend contracts stabilize
- Phase B: add job-based orchestration and progress streaming

---

## 7. Target Backend Architecture

## 7.1 Core services

Add or reshape the backend into the following conceptual modules:

### Intake and storage

- file upload handling
- document metadata normalization
- temporary file/object storage
- analysis job metadata storage

### Ingestion service

- document classification validation
- raw text extraction
- spreadsheet parsing
- image/PDF preprocessing
- ingestion agent prompt building
- canonical `IngestionOutput`

### Specialist analysis service

- parallel agent orchestration
- per-agent prompt routing
- common output validation
- retries
- partial-failure handling

### Deterministic scoring service

- normalized findings merger
- conflict resolution
- metric normalization
- scorecards
- recommendation policy
- completeness/confidence policy

### Narrative/report service

- summary report assembly
- deep review assembly
- synthesis agent prompt building
- PDF-ready report payload

### Observability and audit

- per-agent latency
- token usage
- cost estimation
- missing documents
- overrides and conflicts
- scorer inputs/outputs

## 7.2 Proposed file/module additions

Recommended backend additions:

```text
backend/app/
  api/routes/
    analyses.py                 # New product-facing analysis endpoints
  services/
    analysis_jobs.py            # Job orchestration / status transitions
    intake_service.py           # Upload intake and document persistence
    ingestion_service.py        # Preprocessing + ingestion agent adapter
    scoring_engine.py           # New deterministic score engine over agent outputs
    report_assembler.py         # New report assembly layer
    clarification_service.py    # Missing-data questions / follow-up prompts
    analysis_repository.py      # File-backed or DB-backed artifact storage abstraction
  agents/
    schemas.py                  # Expanded with normalized finding envelope
    runners.py                  # Updated to emit standardized metrics/findings
    orchestrator.py             # Updated to run end-to-end product pipeline
```

Keep existing deterministic math in:

- `backend/app/services/calculations.py`
- `backend/app/agents/deterministic.py`

but consolidate duplicated policy into shared scoring utilities over time.

---

## 8. Canonical Data Model Changes

The single most important technical change in this migration is introducing a canonical evidence and scoring model that sits between agent outputs and the final report.

## 8.1 New canonical concepts

### AnalysisJob

Represents one end-to-end diligence run.

Recommended fields:

```json
{
  "analysisId": "uuid",
  "status": "queued|running|completed|failed|partial",
  "requestedDepth": "summary|deep",
  "createdAt": "iso",
  "updatedAt": "iso",
  "progress": {
    "phase": "intake|ingestion|parallel_analysis|scoring|reporting|done",
    "percent": 0,
    "message": "text"
  }
}
```

### AnalysisDocument

Represents one uploaded file after normalization.

Recommended fields:

```json
{
  "documentId": "uuid",
  "analysisId": "uuid",
  "fileName": "P_and_L_2024.pdf",
  "declaredType": "profit_and_loss",
  "canonicalType": "profit_and_loss",
  "mimeType": "application/pdf",
  "sizeBytes": 12345,
  "status": "uploaded|parsed|failed",
  "storagePath": "artifact path",
  "notes": []
}
```

### EvidenceRef

Every meaningful finding should cite evidence.

Recommended fields:

```json
{
  "documentId": "uuid",
  "fileName": "P_and_L_2024.pdf",
  "sectionId": "uuid",
  "page": 3,
  "snippet": "Net income: $120,000",
  "extractedFields": {
    "net_income": 120000
  },
  "confidence": 0.91
}
```

### NormalizedFinding

This is the key standardization layer.

All specialist agents should emit findings through one common envelope, even if they also keep domain-specific structures.

Recommended fields:

```json
{
  "findingId": "financial-001",
  "sourceAgent": "financial_analysis",
  "category": "earnings_quality",
  "severity": "low|medium|high|critical",
  "title": "Add-backs appear aggressive",
  "description": "Seller add-backs exceed 30% of stated EBITDA.",
  "deterministicTags": [
    "financial_risk",
    "add_backs",
    "sde_adjustment"
  ],
  "metricImpact": {
    "validated_sde_delta": -25000
  },
  "evidence": [
    {
      "documentId": "uuid",
      "sectionId": "uuid",
      "page": 2,
      "snippet": "Officer compensation..."
    }
  ],
  "confidence": 0.84,
  "missingData": false
}
```

### AgentEnvelope

Each agent output should contain:

- agent-specific rich output
- normalized metrics
- normalized findings
- missing-data summary

Recommended pattern:

```json
{
  "agentName": "financial_analysis",
  "status": "success",
  "summary": "text",
  "confidence": 0.88,
  "overallScore": 7,
  "normalizedMetrics": {},
  "findings": [],
  "missingInputs": [],
  "rawDomainOutput": {}
}
```

### DeterministicScorecard

Represents scored results after agent outputs are merged.

Recommended fields:

```json
{
  "overallRiskScore": 63,
  "overallRecommendation": "proceed_with_caution",
  "buyerFacingDimensions": [],
  "technicalScorecards": [],
  "dealBreakers": [],
  "conflicts": [],
  "completenessScore": 0.78,
  "confidenceScore": 0.73,
  "validatedMetrics": {}
}
```

### ReportOutputV2

The report contract should evolve to support both modes:

```json
{
  "modeAvailable": {
    "summary": true,
    "deep": true
  },
  "summary": {},
  "scorecard": {},
  "deepReview": {
    "agentReviews": [],
    "evidenceIndex": [],
    "auditTrail": [],
    "missingData": []
  },
  "metadata": {}
}
```

---

## 9. Agent Contract Redesign

## 9.1 Why this matters

Right now the specialist agent schemas are rich but inconsistent. That is fine for isolated analysis, but not fine for a deterministic merger layer that needs stable inputs.

The fix is not to throw away the current agent schemas.

The fix is to wrap them in a shared envelope that every runner must populate.

## 9.2 Required common fields for all specialist agents

Each specialist agent should produce:

- `summary`
- `confidence`
- `overall_score`
- `normalized_metrics`
- `findings`
- `missing_inputs`
- `evidence`

## 9.3 What `normalized_metrics` should look like

Examples by agent:

### Financial analysis

- `revenue_latest`
- `revenue_growth_yoy`
- `gross_margin`
- `ebitda`
- `ebitda_margin`
- `sde_reported`
- `sde_validated_candidate`
- `working_capital`
- `cash_flow_net_income_divergence`

### Tax compliance

- `max_revenue_discrepancy_pct`
- `missing_tax_years_count`
- `tax_returns_present`
- `potential_tax_exposure`

### AR and collections

- `dso`
- `top_customer_ar_pct`
- `write_off_risk_pct`
- `over_90_ar_pct`

### Customer concentration

- `top_customer_revenue_pct`
- `top5_revenue_pct`
- `hhi`
- `single_customer_dependency`

### Operations and transferability

- `owner_dependence_score`
- `delegated_management`
- `headcount`
- `key_person_risk_count`
- `transferable_license_count`

### Lease and contract

- `remaining_lease_months`
- `assignment_clause_risk`
- `monthly_rent`
- `key_contracts_non_transferable_count`

### Market and macro

- `industry_trend`
- `competitor_density`
- `demand_outlook_score`
- `threat_count_high_or_critical`

### Lending and affordability

- `asking_price`
- `adjusted_sde`
- `sde_multiple`
- `dscr`
- `dscr_meets_minimum`
- `cash_needed_total`
- `eligible_for_sba`

## 9.4 Finding categories and tags

Standard categories should be limited and stable.

Recommended categories:

- `earnings_quality`
- `cash_flow`
- `working_capital`
- `tax_compliance`
- `receivables`
- `customer_concentration`
- `contract_durability`
- `owner_dependence`
- `operational_transferability`
- `lease_transferability`
- `market_conditions`
- `lending`
- `legal_compliance`
- `missing_data`
- `conflict`

Recommended deterministic tags:

- `deal_breaker_candidate`
- `sde_adjustment`
- `valuation_pressure`
- `bankability_pressure`
- `transferability_pressure`
- `completeness_penalty`

## 9.5 Agent-by-agent role in final scoring

| Agent | Primary role | Secondary role | Feeds which scorecards |
|---|---|---|---|
| Document Ingestion | Extract and normalize evidence | Surface missing docs and low-confidence extraction | Completeness, confidence, evidence base |
| Financial Analysis | Core earnings and margin analysis | Revenue trend and working capital | Financial health, revenue quality, affordability |
| Tax Compliance | Reconcile seller books to tax reality | Flag earnings credibility issues | Compliance, earnings quality |
| AR and Collections | Validate receivables quality | Expose hidden working-capital weakness | Working capital, financial health |
| Customer Concentration | Measure dependency and contract durability | Support owner dependence conclusions | Revenue durability, transferability |
| Operations and Transferability | Evaluate key-person and owner risk | Validate operational continuity | Transferability, operating risk |
| Lease and Contract | Evaluate assignability and lease sufficiency | Support legal/compliance risk | Transferability, legal/compliance |
| Market and Macro | Evaluate external environment | Pressure-test growth assumptions | Revenue durability, market risk |
| Lending and Affordability | Convert validated earnings into bankability | Pressure-test purchase price | Affordability, final overrides |
| Synthesis Narrative | Explain the result | Organize deep review story | Narrative only |

---

## 10. Deterministic Scoring Design

## 10.1 The most important rule

The deterministic scorer should not use free-text summaries as scoring input.

It should score from:

- normalized metrics
- standardized findings
- evidence completeness
- deterministic overrides

The agent `overall_score` can be preserved, but it should be advisory only.

## 10.2 Recommended scoring structure

Use two layers:

### Layer 1: Technical scorecards

These are the specialist scorecards aligned to the agent lanes:

1. Financial health
2. Tax and earnings credibility
3. Working capital and receivables quality
4. Customer concentration and revenue durability
5. Operations and owner dependence
6. Lease, contract, and legal transferability
7. Market and macro conditions
8. Lending and affordability

Each should score from `0-100`, where higher means more risk.

### Layer 2: Buyer-facing dimensions

Roll those technical scorecards up into a smaller, more intuitive set for the report.

Recommended buyer-facing dimensions:

1. Financial health
2. Revenue durability
3. Owner and operational dependence
4. Transferability and legal friction
5. Affordability and bankability
6. Compliance and reporting quality

This gives the user a clean dashboard while preserving deeper internals.

## 10.3 Scoring inputs

Each technical scorecard should be computed from:

- metric thresholds
- standardized finding severities
- missing-data penalties
- cross-agent conflict penalties
- hard overrides

## 10.4 Recommended severity points

Use severity points as one part of the score:

| Severity | Risk points |
|---|---:|
| low | 5 |
| medium | 12 |
| high | 22 |
| critical | 35 |

These should not be the only input. They are a normalized way to translate findings into score pressure.

## 10.5 Metric rule examples

### Financial health

Example deterministic rules:

- Revenue decline > 10% YoY: `+18`
- Gross margin below configured floor: `+15`
- EBITDA margin below configured floor: `+15`
- Negative working capital: `+12`
- Cash flow vs net income divergence > 20%: `+12`
- Add-backs > 30% of earnings: `+18`

### Tax and earnings credibility

- Revenue discrepancy > 5%: `+10`
- Revenue discrepancy > 10%: `+20`
- Missing tax returns for latest year: `+18`
- Potential tax exposure above threshold: `+10` to `+25`

### AR and working capital

- Over-90 AR > 10%: `+10`
- Over-90 AR > 20%: `+18`
- DSO materially above benchmark: `+10`
- Estimated write-off > 5% of AR: `+10`

### Customer concentration

- Top customer > 20%: `+8`
- Top customer > 30%: `+18`
- Top 5 > 60%: `+10`
- Top 5 > 80%: `+18`
- Mostly non-contracted revenue: `+12`

### Operations and transferability

- No delegated management: `+14`
- Key-person dependency high: `+14`
- Low SOP/process maturity: `+12`
- Required licenses non-transferable: `+18`

### Lease and legal transferability

- Remaining lease term below SBA-friendly threshold: `+18`
- Assignment approval required with weak language: `+12`
- Material non-transferable contracts: `+16`
- No lease provided when location is business-critical: `+18`

### Market and macro

- Industry trend declining: `+12`
- High competitor density: `+8`
- Multiple high/critical threats: `+10` to `+20`

### Lending and affordability

- DSCR < 1.25: `+20`
- DSCR < 1.00: `+35`
- SDE multiple above supported range: `+10` to `+20`
- Cash needed at close materially exceeds buyer assumptions: `+10`
- Not SBA-eligible: `+20`

## 10.6 Missing-data penalties

For each technical scorecard, missing critical inputs should add risk.

Examples:

- No tax returns: add tax credibility penalty
- No AR aging: add working-capital uncertainty penalty
- No customer list: add revenue durability uncertainty penalty
- No lease: add transferability uncertainty penalty

Recommended model:

- critical missing input: `+15`
- important missing input: `+8`
- minor missing input: `+3`

Also compute a separate completeness score so the user can tell whether the result is low-confidence because of missing materials.

## 10.7 Cross-agent conflict penalties

Examples:

- Financial agent SDE candidate and tax agent earnings view differ materially
- Customer agent says contract durability is strong but lease/contracts agent flags assignment friction
- Financial growth looks strong but market agent says the market trend is structurally declining

Recommended model:

- material conflict: `+8`
- major conflict affecting earnings or bankability: `+15`

Each conflict should also be logged in the report audit trail.

## 10.8 Recommendation policy

The deterministic scorer should output the final recommendation.

Recommended policy:

### `walk_away`

Trigger if any of the following are true:

- DSCR < 1.00
- multiple critical deal-breaker findings
- severe earnings credibility issues
- non-transferable lease/contracts make the business non-viable
- unresolved legal/tax exposure above defined threshold

### `proceed_with_caution`

Trigger if:

- DSCR between 1.00 and 1.25
- overall risk score in caution band
- one or more major unresolved issues remain
- completeness is too low for a clean buy conclusion

### `proceed`

Trigger only if:

- affordability passes
- no critical deal-breakers
- completeness above threshold
- transferability acceptable
- earnings credibility acceptable

## 10.9 Confidence vs risk

Do not reduce risk because confidence is low.

Low confidence should do two things:

1. lower the confidence score
2. increase uncertainty penalties where important evidence is missing

That keeps the product conservative.

---

## 11. Report Design: Summary vs Deep Review

## 11.1 Summary mode

This is the default buyer-facing report.

It should answer:

- Is this deal risky?
- Can it support debt?
- Will it transfer cleanly?
- What are the top issues?
- What should I ask next?

Recommended sections:

1. Executive summary
2. Overall risk and recommendation
3. Financial and affordability snapshot
4. Top risk drivers
5. Transferability highlights
6. Missing documents / open diligence items
7. Recommended next steps

## 11.2 Deep review mode

This is the technical, evidence-heavy report.

It should include:

1. Document inventory and completeness
2. Deterministic scorecard methodology summary
3. Technical scorecards by specialist lane
4. Agent-by-agent review sections
5. Evidence snippets and source references
6. Conflicts and conservative overrides
7. Missing-data impact
8. Deep diligence questions
9. Full audit trail of how recommendation was reached

## 11.3 Important product decision

Deep review mode should not require a second core analysis pipeline.

Recommended behavior:

- Always persist structured agent outputs and deterministic score artifacts
- In summary mode, render only a subset
- In deep mode, render the expanded sections

Optional optimization:

- The deep narrative can be expanded on demand using a second synthesis pass, but the underlying analysis should already exist

## 11.4 Recommended report contract

Keep the current frontend report object concept, but expand it.

Recommended top-level sections:

```text
report
  summary
  recommendation
  scorecard
  affordability
  transferability
  findings
  nextSteps
  deepReview
  metadata
```

## 11.5 Deep review section layout

Recommended per-agent deep review section:

```json
{
  "agentName": "tax_compliance",
  "headline": "Tax returns do not fully reconcile with seller P&L.",
  "summary": "text",
  "technicalScore": 71,
  "confidence": 0.82,
  "keyMetrics": {},
  "findings": [],
  "evidence": [],
  "missingInputs": [],
  "scoringImpact": {
    "buyerFacingDimensions": [
      "financial_health",
      "compliance_and_reporting_quality"
    ],
    "riskContribution": 14
  }
}
```

---

## 12. API and Contract Strategy

## 12.1 Short-term migration-safe API

For the first migration stage, it is acceptable to evolve the existing pipeline route into a product-capable route if that accelerates delivery.

Possible short-term pattern:

- `POST /api/pipeline`
  - request: files + config
  - response: full report payload

This is acceptable only while:

- job runtime is manageable
- no persistence is required
- progress UI can stay simple

## 12.2 Recommended target API

Preferred product-facing endpoints:

### Create analysis

`POST /api/analyses`

Request:

- files
- document type declarations
- optional buyer/deal metadata
- requested report depth

Response:

- `analysisId`
- initial status

### Get status

`GET /api/analyses/{analysisId}`

Response:

- status
- progress
- per-phase state
- high-level failures if any

### Stream progress

`GET /api/analyses/{analysisId}/events`

Use SSE if feasible. Polling is acceptable for the first cut.

### Get report

`GET /api/analyses/{analysisId}/report?mode=summary`
`GET /api/analyses/{analysisId}/report?mode=deep`

### Rerun with different depth

Optional:

`POST /api/analyses/{analysisId}/expand`

This would support generating a deeper narrative from existing artifacts.

## 12.3 Frontend request model additions

Add analysis configuration:

```json
{
  "analysisDepth": "summary|deep",
  "dealInfo": {
    "askingPrice": 750000,
    "businessType": "hvac",
    "location": "Austin, TX"
  }
}
```

Optional later additions:

- buyer cash available
- target hold period
- experience level
- financing assumptions

---

## 13. Frontend Migration Plan

## 13.1 Frontend goals

The frontend should transition from "manual questionnaire drives the score" to "documents drive the score, clarifications fill the gaps."

## 13.2 Step-by-step frontend changes

### Upload page

Current file:

- `app/analyze/upload/page.tsx`

Needed changes:

- switch to canonical backend document taxonomy
- allow more document types
- capture requested analysis depth
- optionally capture basic deal metadata earlier

### Review page

Current file:

- `app/analyze/review/page.tsx`

Recommended future role:

- review document classifications
- show extracted high-level metadata
- allow corrections to deal metadata
- avoid forcing manual financial entry as the primary path

Manual financial correction can remain as a fallback or override flow.

### Questions page -> Clarifications page

Current file:

- `app/analyze/questions/page.tsx`

Recommended future role:

- rename conceptually to "Clarifications"
- show only targeted follow-up questions generated from missing data and unresolved high-impact areas
- allow user-supplied facts to be tagged as supplemental, not primary documentary evidence

### Report page

Current file:

- `app/analyze/report/page.tsx`

Needed changes:

- support summary mode and deep review mode
- render technical scorecards
- render agent drilldowns
- render evidence snippets and missing-data warnings
- render audit trail/conflicts

## 13.3 Frontend state changes

Current state in `context/AnalysisContext.tsx` is centered around:

- financialData
- questionnaire
- dealInfo
- report

Recommended future state:

- analysisId
- upload manifest
- clarifications
- analysis status/progress
- report summary
- report deep review availability

Questionnaire state should become a much smaller `clarifications` structure.

## 13.4 Frontend types

`lib/types.ts` should be updated to reflect the backend's new canonical report contract.

Current mismatch to fix:

- current types are shaped around the deterministic report
- pipeline types live separately in Python only

We need one report contract the frontend actually renders.

## 13.5 PDF export

`app/api/generate-pdf/route.ts` and `lib/report-pdf.tsx` should be updated only after the new report contract stabilizes.

Do not make PDF the first migration step.

---

## 14. Backend Migration Plan

## 14.1 Phase 0: Lock the architecture and data contracts

Goal:

- stop drifting between the old deterministic path and the new agent path

Deliverables:

- canonical document taxonomy
- canonical report contract
- standardized agent envelope
- scoring engine interface

Files most likely touched:

- `backend/app/agents/schemas.py`
- `backend/app/models/schemas.py`
- `lib/types.ts`
- `lib/constants.ts`
- docs

Definition of done:

- all teams can point to one canonical runtime contract
- all new implementation work targets that contract

## 14.2 Phase 1: Make ingestion real

Goal:

- replace stub parsing with real document preprocessing and ingestion

Tasks:

1. Build `intake_service.py` for multipart uploads.
2. Add canonical document metadata normalization.
3. Add raw text extraction:
   - PDF
   - image OCR path
   - CSV/XLSX parsing
4. Refactor the ingestion agent to consume real extracted sections.
5. Persist ingestion artifacts.

Recommended dependencies to evaluate:

- `pymupdf` or `pdfplumber`
- `openpyxl`
- `pandas`
- OCR library if needed, or a Claude vision fallback path

Definition of done:

- uploaded files become usable `IngestionOutput`
- missing/failed documents are explicitly tracked
- ingestion confidence is meaningful

## 14.3 Phase 2: Normalize specialist agent outputs

Goal:

- make every specialist agent emit deterministic-ready structured findings

Tasks:

1. Add the `NormalizedFinding` concept to `backend/app/agents/schemas.py`.
2. Add `normalized_metrics` and `missing_inputs` to each specialist output.
3. Update each runner in `backend/app/agents/runners.py`.
4. Ensure evidence references are included.
5. Preserve existing domain-specific fields where useful.

Definition of done:

- scoring code can process agent results without reading free text
- all specialist agents follow a shared envelope

## 14.4 Phase 3: Build deterministic score engine over agent results

Goal:

- compute the final risk score from specialist outputs, not from the old questionnaire

Recommended new module:

- `backend/app/services/scoring_engine.py`

Responsibilities:

- collect normalized metrics/findings
- resolve conflicts conservatively
- compute technical scorecards
- roll up buyer-facing dimensions
- compute completeness and confidence
- compute recommendation

Definition of done:

- overall score is derived from pipeline outputs
- recommendation is deterministic
- deep review can explain the scoring path

## 14.5 Phase 4: Reposition the synthesis agent as a narrative layer

Goal:

- make synthesis explain deterministic results instead of deciding them

Tasks:

1. Change the synthesis prompt and schema so it consumes:
   - deterministic scorecard
   - validated metrics
   - normalized findings
   - conflicts
   - missing data
2. Remove synthesis authority over the final recommendation.
3. Have synthesis generate:
   - executive summary
   - per-section narrative
   - seller questions
   - diligence priorities
   - optional deep review prose

Definition of done:

- synthesis cannot override the deterministic score
- narrative aligns with the scored outcome

## 14.6 Phase 5: Assemble the canonical report contract

Goal:

- return a frontend-ready report from the pipeline

Recommended new module:

- `backend/app/services/report_assembler.py`

Responsibilities:

- transform ingestion + agent outputs + scorecard + synthesis into one report payload
- provide summary and deep review variants
- preserve evidence and audit artifacts

Definition of done:

- frontend no longer needs to understand raw `PipelineState`
- one canonical report object exists

## 14.7 Phase 6: Switch the frontend to pipeline-first

Goal:

- make the agent pipeline the app's primary runtime path

Tasks:

1. Replace `analyzeData()` in `lib/api-client.ts` with a pipeline-backed call.
2. Update the analysis context around analysis jobs and progress.
3. Replace the broad questionnaire flow with targeted clarifications.
4. Update the report page to render the new contract.

Definition of done:

- the product flow does not rely on `POST /api/analyze`
- the pipeline is the default user path

## 14.8 Phase 7: Add summary mode and deep review mode

Goal:

- support a default buyer report and an analyst-grade report

Tasks:

1. Add `analysisDepth` to the UI and backend request model.
2. Add summary rendering sections.
3. Add deep review rendering sections.
4. Add expand-on-demand if desired.

Definition of done:

- users can choose the level of detail they want
- the backend can deliver both modes from the same evidence base

## 14.9 Phase 8: Add persistence, progress, and reliability

Goal:

- make the pipeline robust enough for production use

Tasks:

1. Add persistent analysis/job storage abstraction.
2. Add file-backed artifacts for dev, DB/object-store backing for production.
3. Add progress events or polling endpoints.
4. Add retries, timeouts, and partial-failure behavior.
5. Add cost and latency instrumentation.

Definition of done:

- long-running analyses are trackable
- users can refresh and still recover their report
- support/debugging is possible

---

## 15. Clarifications Strategy

## 15.1 Why the old questionnaire should change

The current questionnaire is broad and manual. It assumes the system needs the user to provide most of the risk context up front.

That is no longer the right model if the product is document-first.

## 15.2 New role of user input

User input should now be:

- gap-filling
- conflict-resolving
- deal-context augmenting

Examples:

- owner relationship dependence
- pending liabilities not yet documented
- whether contracts are actually assignable despite unclear wording
- whether a missing document truly does not exist

## 15.3 Recommended implementation

After ingestion completes, build a clarification request set from:

- missing critical documents
- low-confidence extraction fields
- unresolved scorecard-critical questions

Examples of generated clarifications:

- "No customer list was found. Does any one customer account for more than 20% of revenue?"
- "No employee roster or SOP materials were found. Is there a manager who can run the business without the owner?"
- "Lease assignment language is unclear. Has the landlord historically allowed assignment?"

These answers should be stored separately and tagged:

- `source = user_asserted`
- `confidence = moderate`

They should affect scoring, but less strongly than documentary evidence.

---

## 16. Implementation Details by File Area

## 16.1 Backend files likely to change substantially

### `backend/app/agents/schemas.py`

Add:

- normalized finding model
- evidence references
- normalized metrics fields
- agent envelope consistency
- optional report-depth support in synthesis output

### `backend/app/agents/runners.py`

Refactor:

- runner inputs
- document filtering
- evidence extraction
- normalized findings population
- missing input declaration

### `backend/app/agents/orchestrator.py`

Refactor:

- run deterministic scoring after specialist agents
- call synthesis after scoring, not before recommendation policy
- return report assembly output, not only raw pipeline state

### `backend/app/agents/deterministic.py`

Keep and expand:

- domain calculations
- deterministic preprocessing
- cross-agent synthesis helpers

Move policy-specific scoring logic into the new scoring engine to avoid scattering it.

### `backend/app/services/risk_engine.py`

This file will likely either:

- become legacy, or
- be reshaped into a new scorer over pipeline outputs

Recommendation:

- preserve current questionnaire-based logic temporarily
- build `scoring_engine.py`
- then retire or slim down `risk_engine.py`

### `backend/app/services/analysis_service.py`

This should stop being the primary orchestrator for the app's main analysis path.

Its current deterministic-only role can be retained as:

- fallback path
- regression baseline
- test oracle for certain calculations

### `backend/app/api/routes/analyze.py`

Likely legacy after migration.

Recommended final state:

- keep temporarily for backward compatibility and test comparison
- deprecate after frontend cutover

### `backend/app/api/routes/pipeline.py`

Can be evolved into:

- a lower-level backend-only route

But product-facing work should likely move into a new `analyses.py` route.

## 16.2 Frontend files likely to change substantially

### `lib/constants.ts`

Replace simplified document taxonomy with canonical backend taxonomy.

### `components/upload/FileDropZone.tsx`

Update for expanded document types and possibly required/optional guidance.

### `lib/api-client.ts`

Refactor around:

- analysis job creation
- progress polling/streaming
- report retrieval
- deep report expansion

### `context/AnalysisContext.tsx`

Refactor away from questionnaire-centric state toward analysis-job state.

### `app/analyze/questions/page.tsx`

Convert into dynamic clarifications UI.

### `app/analyze/report/page.tsx`

Support:

- summary mode
- deep review mode
- evidence drilldowns
- audit/conflicts

### `components/report/*`

Update the report component suite to handle:

- new scorecards
- technical sections
- evidence-backed findings
- completeness/confidence indicators

---

## 17. Testing Strategy

## 17.1 Unit tests

Add or expand unit tests for:

- document normalization
- ingestion preprocessing
- normalized finding generation
- scoring rules
- conflict resolution
- recommendation overrides
- report assembly

Important test files to expand:

- `backend/tests/test_agent_deterministic.py`
- `backend/tests/test_risk_engine.py`

Recommended new test files:

- `backend/tests/test_scoring_engine.py`
- `backend/tests/test_report_assembler.py`
- `backend/tests/test_ingestion_service.py`
- `backend/tests/test_pipeline_to_report.py`

## 17.2 Contract tests

Create contract tests to ensure:

- Python report output matches TypeScript `lib/types.ts`
- agent envelopes validate consistently
- summary and deep modes remain backward-compatible where intended

## 17.3 Golden fixture tests

Use the sample diligence packages already in the repo as golden fixtures:

- `sample company1`
- `sample company3 - LoneStar Plumbing`

Recommended golden test behavior:

- freeze expected scorecards and top findings for known packages
- assert no accidental scoring drift

## 17.4 End-to-end tests

At minimum, cover:

1. upload docs
2. run pipeline
3. show progress
4. render summary report
5. render deep review
6. download PDF

## 17.5 Failure-path tests

Test these scenarios explicitly:

- missing tax returns
- missing customer list
- malformed document upload
- one specialist agent fails
- synthesis agent fails
- low-confidence ingestion
- cross-agent earnings conflict

The pipeline should still return a useful report or a clearly partial report.

---

## 18. Observability, Cost, and Performance

## 18.1 What to measure

Track at minimum:

- total analysis runtime
- per-agent latency
- per-agent token usage
- per-agent estimated cost
- number of missing critical documents
- number of conflicts raised
- completeness score
- confidence score

## 18.2 Product metrics to expose

Useful UI-level metadata:

- analysis completeness
- number of uploaded docs used
- number of high/critical findings
- whether recommendation was affected by missing data

## 18.3 Cost controls

To keep the product practical:

- keep Haiku on lower-reasoning lanes
- keep Sonnet on specialist judgment lanes
- keep Opus or equivalent only for synthesis if truly needed
- compress context aggressively at each phase boundary
- support deep review as an explicit higher-cost mode

## 18.4 Performance considerations

Important performance realities:

- deep review will produce larger payloads
- multi-agent analyses may exceed comfortable synchronous request times
- PDF generation should remain separate from pipeline execution

This is why a job model is strongly recommended.

---

## 19. Rollout Strategy

## 19.1 Do not hard-cut the old path immediately

Keep the deterministic-only `/api/analyze` path long enough to:

- compare results
- regression-test affordability math
- validate report rendering

## 19.2 Recommended rollout phases

### Rollout 1: Internal dual-run

For the same uploaded package:

- run the old deterministic path
- run the new agent-primary path
- compare outputs internally

This is not to force them to match exactly.

It is to detect:

- impossible score swings
- broken report contracts
- missing sections
- bad recommendation overrides

### Rollout 2: Hidden pipeline UI

Let developers and internal testers use the pipeline-primary path behind a feature flag.

### Rollout 3: Default summary mode on pipeline

Switch standard users to the pipeline-primary summary report.

Keep deep review behind a flag until:

- payload size
- rendering
- synthesis quality
- evidence display

all look stable.

### Rollout 4: Enable deep review broadly

After summary mode is stable and supported.

## 19.3 Recommended feature flags

Examples:

- `USE_PIPELINE_PRIMARY_RUNTIME`
- `ENABLE_DYNAMIC_CLARIFICATIONS`
- `ENABLE_DEEP_REVIEW`
- `ENABLE_ANALYSIS_JOBS`
- `ENABLE_ON_DEMAND_DEEP_EXPANSION`

---

## 20. Risks and How to Manage Them

## 20.1 Risk: the scorer becomes too dependent on agent free text

Mitigation:

- require normalized findings and metrics
- never score directly from summary prose

## 20.2 Risk: pipeline complexity grows too fast

Mitigation:

- introduce one canonical report contract early
- centralize scoring
- centralize storage abstractions

## 20.3 Risk: deep review becomes a second product

Mitigation:

- treat deep review as another rendering of the same evidence base
- avoid building a separate scoring pipeline for it

## 20.4 Risk: users lose trust when evidence is thin

Mitigation:

- expose completeness/confidence clearly
- surface missing critical docs prominently
- use conservative uncertainty penalties

## 20.5 Risk: front-end and back-end schemas drift again

Mitigation:

- make schema updates part of the same migration PRs
- add contract tests
- treat report contract as a versioned interface

---

## 21. Suggested First Implementation Sequence

If this were executed as a real migration program, the highest-leverage order would be:

1. Normalize the document taxonomy across frontend and backend.
2. Standardize specialist agent outputs with common findings/metrics/evidence fields.
3. Build the deterministic scoring engine over agent outputs.
4. Make synthesis narrative consume deterministic outputs instead of setting the result.
5. Build the canonical report assembler.
6. Update the frontend report renderer to consume the new report.
7. Convert the old questionnaire step into targeted clarifications.
8. Add analysis jobs, persistence, and progress streaming.
9. Add deep review rendering and optional on-demand expansion.

This sequence avoids getting trapped in UI work before the backend contracts are trustworthy.

---

## 22. Definition of Done

This migration is complete when all of the following are true:

1. The frontend's primary runtime path uses the Claude-driven pipeline, not the old deterministic `/api/analyze` path.
2. Uploaded documents are the primary basis for analysis.
3. Specialist agents emit standardized findings, metrics, and evidence references.
4. The deterministic scoring engine computes the final risk score and recommendation from pipeline outputs.
5. Missing documents and low-confidence areas are explicitly represented in scoring and reporting.
6. The synthesis agent explains deterministic results instead of deciding them.
7. The frontend can render both a summary report and a deep review report from the same evidence base.
8. Progress, errors, and partial failures are visible and recoverable.
9. Tests cover scoring, report assembly, and at least one end-to-end sample diligence package.

---

## 23. Recommended Immediate Next Steps

The first concrete implementation PR should not try to do everything.

Recommended first PR scope:

1. Define the canonical document taxonomy.
2. Define the standardized agent envelope.
3. Define `ReportOutputV2` and align `lib/types.ts` with it.
4. Add a new `scoring_engine.py` skeleton that accepts pipeline outputs.
5. Wire the orchestrator so deterministic scoring runs after specialist agents, even if the frontend is not switched yet.

That creates the structural backbone for every later phase.

The second PR should then focus on making the pipeline emit a frontend-ready summary report.

