# BizBuy Backend Plan

## 1. Why The Backend Should Be Deterministic

BizBuy is not a generic chatbot product. It is a diligence and risk product that influences whether someone may spend anywhere from roughly `$100K` to `$5M` on a business acquisition. That means the backend should optimize for:

- repeatability
- traceability
- conservative assumptions
- explicit thresholds
- auditable outputs

The core rule for this system is:

`LLMs may extract and explain, but they should not own the final score.`

That means:

- document extraction can use an LLM because source documents are messy
- risk scoring should be deterministic application code
- financial calculations must be deterministic application code
- conflict resolution should be deterministic and conservative
- final report narrative can be template-based first, then optionally LLM-assisted later

This gives us a system where the same inputs produce the same score every time, which is exactly what we want for BizBuy.

## 2. Product-Level Decision

We should not use an LLM agent as the authority that decides acquisition risk.

We should use:

1. `LLM for ingestion`
2. `Deterministic engine for scoring and calculations`
3. `LLM or templates for narrative output`

This is the safest and most defensible architecture for an MVP and also the best base for a more advanced version later.

## 3. Backend Goals

The backend needs to do five things well:

1. Accept structured financial data and questionnaire answers from the frontend.
2. Parse uploaded files into normalized schemas.
3. Compute acquisition metrics deterministically.
4. Score risk deterministically.
5. Return a structured analysis report that the frontend can render directly.

## 4. Recommended Backend Stack

### Primary Stack

- `Python 3.11+`
- `FastAPI`
- `Pydantic`
- `Uvicorn`
- `python-multipart`

### Optional Integrations

- `Anthropic SDK` for document extraction later
- `httpx` if we want service-to-service calls or async integrations
- `pytest` for unit tests

### Why Python

Python is a good fit here because:

- it is strong for data modeling and rule engines
- it gives us room for future document-processing and analytics work
- it is easy to test deterministic calculations
- it leaves space for future ML, OCR, or benchmarking modules

## 5. High-Level Architecture

```text
Next.js Frontend
    |
    |  HTTP JSON / multipart
    v
Python FastAPI Backend
    |
    +--> Document Parsing Layer
    |       - file intake
    |       - normalization
    |       - optional LLM extraction
    |
    +--> Deterministic Calculation Engine
    |       - SDE
    |       - EBITDA
    |       - DSCR
    |       - working capital
    |       - valuation multiple
    |       - break-even revenue
    |       - scenarios
    |
    +--> Deterministic Risk Engine
    |       - owner dependence scoring
    |       - concentration scoring
    |       - revenue quality scoring
    |       - employee/operations scoring
    |       - supplier scoring
    |       - financial/add-back scoring
    |       - transferability scoring
    |       - recommendation logic
    |
    +--> Report Composer
            - executive summary
            - risk explanations
            - seller questions
            - diligence checklist
            - opportunities
```

## 6. Core Principle: Separate Facts From Judgment

The backend should always distinguish between:

- `facts`
- `derived metrics`
- `risk judgments`
- `narrative text`

### Facts

Facts are raw or normalized values:

- revenue
- COGS
- net income
- owner salary
- add-backs
- loan amount
- interest rate
- top customer concentration
- SOP existence

### Derived Metrics

Derived metrics are deterministic outputs:

- gross margin
- SDE
- EBITDA
- DSCR
- working capital
- valuation multiple
- break-even monthly revenue
- scenario projections

### Risk Judgments

Risk judgments are still deterministic, but they use rules:

- if `DSCR < 1.25`, flag debt-service risk
- if top customer revenue > `50%`, raise concentration risk
- if owner generates > `80%` of sales, raise owner-dependence risk
- if add-backs exceed `30%` of EBITDA, raise financial-quality risk

### Narrative Text

Narrative text should be produced only after the score is already decided.

That means the narrative engine explains the score. It does not invent the score.

## 7. Recommended Backend Modules

```text
backend/
  app/
    api/
      routes/
        health.py
        parse_documents.py
        analyze.py
    core/
      config.py
    models/
      schemas.py
    services/
      calculations.py
      risk_engine.py
      analysis_service.py
      document_parser.py
      report_writer.py
    main.py
  tests/
```

### Module Responsibilities

`config.py`
- environment variables
- CORS configuration
- future API keys

`schemas.py`
- request models
- response models
- internal normalized data models

`calculations.py`
- all deterministic formulas
- no prompt logic
- no network calls

`risk_engine.py`
- all scoring rules
- dimension thresholds
- weighting model
- deal-breaker logic

`analysis_service.py`
- orchestration layer
- combines metrics + scores + report assembly

`document_parser.py`
- upload intake
- normalization
- future LLM extraction adapter

`report_writer.py`
- deterministic report text templates
- future optional LLM summarization hook

## 8. API Surface

### `GET /api/health`

Purpose:
- simple readiness check

Returns:
- service name
- environment
- deterministic mode

### `POST /api/parse-documents`

Purpose:
- receive uploaded files
- normalize file metadata
- eventually extract structured financial values

Input:
- multipart files
- `fileTypes` JSON array aligned to each uploaded file

Output:
- normalized `FinancialData`
- parsing notes
- completeness score

### `POST /api/analyze`

Purpose:
- accept confirmed financials and questionnaire answers
- compute all deterministic outputs
- return a full report payload

Input:
- `financials`
- `questionnaire`
- `dealInfo`

Output:
- executive summary
- financial snapshot
- debt service analysis
- risk assessment
- transferability analysis
- diligence questions
- checklist
- upside opportunities
- final recommendation

## 9. Deterministic Scoring Strategy

### Risk Dimensions

We should keep the six PRD dimensions:

1. `Owner Dependence`
2. `Customer Concentration`
3. `Revenue Quality`
4. `Employee & Operational Risk`
5. `Supplier & Vendor Risk`
6. `Financial & Add-Back Risk`

### Base Scoring Shape

Each dimension should score from `1` to `10`.

Then the weighted overall score should be:

```text
overallScore =
  ownerDependence * 0.25 +
  customerConcentration * 0.20 +
  revenueQuality * 0.20 +
  employeeOperational * 0.15 +
  supplierRisk * 0.10 +
  financialRisk * 0.10

overallRisk100 = round(overallScore * 10)
```

### Unknown Answers

Unknowns should not be ignored.

If a user answers `I don't know`, the score should increase conservatively because uncertainty itself is a risk in acquisition diligence.

### Deal Breakers

A deal-breaker flag should trigger when:

- any dimension scores `9` or `10`
- DSCR is below `1.00`
- major pending liabilities are present
- validated earnings are materially disputed

## 10. Conservative Evidence Rules

When two pieces of evidence conflict, the backend should choose the more conservative interpretation.

Examples:

- if seller SDE is `$310K` but validated normalized SDE is `$240K`, use `$240K`
- if revenue appears as `$1.2M` in one source and `$1.0M` in another, flag the discrepancy and prefer the lower defensible figure until reconciled
- if add-backs look weak or undocumented, do not count them fully

This conservative rule set is a product feature, not a bug.

## 11. Multi-Agent Vision, Without Letting Agents Own The Score

Your multi-agent idea still makes sense, but the agents should act like specialized evidence collectors, not judges.

### Good Agent Responsibilities

- `Document Ingestion Agent`
- `Financial Validation Agent`
- `Tax Reconciliation Agent`
- `AR / Collections Agent`
- `Customer Concentration Agent`
- `Operations / Transferability Agent`
- `Lease / Contract Agent`
- `Market / Macro Agent`

### What Agents Should Return

Each agent should return structured evidence like:

```json
{
  "agentId": "financial",
  "flags": [
    {
      "severity": "warning",
      "dimension": "Financial & Add-Back Risk",
      "message": "Seller add-backs exceed 30% of EBITDA"
    }
  ],
  "metrics": {
    "validatedSDE": 240000
  },
  "confidence": 0.82,
  "notes": [
    "Owner vehicle expenses were counted as add-backs but not fully documented."
  ]
}
```

### What The Deterministic Merger Does

The backend merger should:

- merge all flags
- choose conservative metric values
- calculate the final validated SDE
- calculate the final weighted risk score
- expose every adjustment in an audit trail

## 12. Recommended Phased Build Order

### Phase 1

Build the deterministic core:

- financial models
- calculation engine
- risk engine
- analyze endpoint
- template-based report output

This phase does not require LLMs.

### Phase 2

Add document parsing:

- upload endpoint
- file normalization
- optional Anthropic extraction
- manual review flow

### Phase 3

Add specialized evidence workers:

- financial
- tax
- AR
- customer
- operations
- lease
- market

### Phase 4

Add persistence and auditability:

- database
- report history
- evidence trail
- score versioning

## 13. Deterministic Recommendation Policy

The recommendation should also be rule-based.

Example policy:

- `Walk Away`
  - DSCR < `1.00`
  - or multiple critical deal breakers
  - or extreme owner dependence plus weak transferability

- `Proceed With Caution`
  - DSCR between `1.00` and `1.25`
  - or overall score above moderate risk
  - or one major unresolved issue

- `Proceed`
  - no critical flags
  - DSCR >= `1.25`
  - acceptable transferability
  - no material earnings dispute

## 14. Frontend/Backend Contract

The frontend should eventually stop doing important analysis work itself.

Instead:

- frontend collects documents and answers
- frontend sends normalized JSON to backend
- backend computes everything important
- frontend renders the returned report

That keeps business logic in one place and makes the product easier to test.

## 15. What We Are Setting Up Now

For the initial Python backend scaffold, we should implement:

1. FastAPI service with CORS for the Next.js app
2. Typed Pydantic models that mirror the frontend data shape
3. Deterministic financial calculation module
4. Deterministic risk engine
5. Deterministic analysis endpoint
6. Starter document parsing endpoint
7. Clear run instructions and testable file layout

## 16. Final Recommendation

Yes, BizBuy should absolutely use AI, but not as the entity that decides the risk score.

The winning architecture is:

- `AI for ingestion`
- `code for math`
- `code for risk scoring`
- `code for recommendation policy`
- `AI or templates for explanation`

That gives you a product that feels intelligent without becoming unstable, untestable, or hard to trust.
