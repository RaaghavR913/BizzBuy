# BizBuy Architecture

A comprehensive guide to the BizBuy multi-agent AI pipeline for small business acquisition due diligence.

## 1. System Overview

BizBuy automates the due diligence process for acquiring small businesses. Instead of hiring 5–8 separate professionals (accountant, tax advisor, commercial attorney, market researcher, SBA lending specialist), BizBuy runs a pipeline of **10 specialized AI agents** that analyze uploaded business documents and produce a unified acquisition recommendation.

The system is designed for first-time business buyers using SBA 7(a) financing to acquire businesses in the $500K–$10M revenue range.

### The 10 Agents

| # | Agent | Model | Phase | Purpose |
|---|-------|-------|-------|---------|
| 1 | Document Ingestion | Haiku | 1 — Ingestion | Parse all uploaded documents into structured data |
| 2 | Financial Analysis | Sonnet | 2 — Parallel | Assess revenue, profitability, cash flow, balance sheet |
| 3 | Tax Compliance | Sonnet | 2 — Parallel | Cross-reference P&L against tax returns |
| 4 | AR & Collections | Haiku | 2 — Parallel | Evaluate accounts receivable quality and collectibility |
| 5 | Customer Concentration | Haiku | 2 — Parallel | Assess customer portfolio diversification |
| 6 | Operations & Transferability | Sonnet | 2 — Parallel | Evaluate owner dependence and operational risk |
| 7 | Lease & Contract | Sonnet | 2 — Parallel | Review lease terms, contracts, non-competes |
| 8 | Market & Macro | Sonnet | 2 — Parallel | Research industry trends and macro conditions (web search) |
| 9 | Lending & Affordability | Sonnet | 3 — Lending | SBA 7(a) bankability and deal structuring |
| 10 | Synthesis Report | Opus | 4 — Synthesis | Unified acquisition recommendation |

### The 4-Phase Execution Model

```
Phase 1: Ingestion ──────────> [Document Ingestion]
                                      │
Phase 2: Parallel Analysis ──> [Financial] [Tax] [AR] [Customer] [Ops] [Lease] [Market]
                                      │                                         │
Phase 3: Lending ────────────> [Lending & Affordability] ◄─── depends on Financial
                                      │
Phase 4: Synthesis ──────────> [Synthesis Report] ◄─── receives all 9 results
```

- **Phase 1** is sequential and blocking — if ingestion fails, the pipeline aborts
- **Phase 2** runs 7 agents in parallel via `Promise.allSettled()` — individual failures don't crash the pipeline
- **Phase 3** conditionally depends on Financial Analysis success (needs SDE figure)
- **Phase 4** always runs, even with partial data, and handles missing analyses gracefully

## 2. Data Flow

### Request → Response

```
POST /api/pipeline
  └─ PipelineInput { documents[], askingPrice?, businessType?, location? }
       └─ Phase 1: Documents → IngestionOutput (structured extraction)
            └─ Phase 2: IngestionOutput → 7 parallel agent results
                 └─ Phase 3: IngestionOutput + FinancialAnalysisOutput → LendingOutput
                      └─ Phase 4: All 9 AgentResults → SynthesisReportOutput
                           └─ PipelineState (full response with metadata)
```

### Compression at Boundaries

Each phase boundary compresses the data that flows to the next stage:

1. **Raw documents → IngestionOutput**: Unstructured PDFs/spreadsheets become structured JSON with typed fields, fiscal years, and confidence scores. The raw text is preserved in `rawText` as fallback.

2. **IngestionOutput → Per-agent user messages**: Each runner filters for relevant document types only (e.g., Financial Analysis only sees P&L, balance sheet, and cash flow documents). It then computes deterministic metrics in TypeScript and passes a compressed summary to the LLM.

3. **Agent outputs → Synthesis user message**: The synthesis runner extracts only the score, confidence, summary, and top 3 risks from each agent — not the full output. Red and green flags are pre-collected and sorted.

This compression principle keeps token usage low and ensures the LLM receives focused context rather than the entire document corpus at every stage.

## 3. File Organization

```
src/
├── types/
│   └── pipeline.ts              # Core types: PipelineInput, PipelineState, AgentResult<T>
├── agents/
│   ├── schemas/                  # Zod schemas + inferred TypeScript types
│   │   ├── ingestion.schema.ts
│   │   ├── financial-analysis.schema.ts
│   │   ├── tax-compliance.schema.ts
│   │   ├── ar-collections.schema.ts
│   │   ├── customer-concentration.schema.ts
│   │   ├── operations-transferability.schema.ts
│   │   ├── lease-contract.schema.ts
│   │   ├── market-macro.schema.ts
│   │   ├── lending-affordability.schema.ts
│   │   └── synthesis-report.schema.ts
│   ├── prompts/                  # Markdown prompt files (XML-tagged)
│   │   ├── document-ingestion.md
│   │   ├── financial-analysis.md
│   │   └── ... (one per agent)
│   ├── runners/                  # Agent runner functions
│   │   ├── document-ingestion.ts
│   │   ├── financial-analysis.ts
│   │   └── ... (one per agent)
│   ├── utils/
│   │   ├── openrouter-client.py  # Singleton OpenRouter client + call_agent()
│   │   ├── prompt-loader.ts      # Loads & caches markdown prompts with {{var}} interpolation
│   │   └── validation.ts         # Zod validation helpers + retry prompt builder
│   ├── registry.ts               # AGENT_REGISTRY — central config for all 10 agents
│   └── orchestrator.ts           # Pipeline execution: phases, cost tracking, error handling
└── app/
    └── api/
        └── pipeline/
            └── route.ts          # Next.js API route (POST + GET health check)
```

### Why Prompts, Schemas, and Runners Are Separated

- **Schemas** define the contract — what shape of data each agent must produce. They are imported by runners (for validation), by the registry (for tool definition), and by `pipeline.ts` (for type safety).
- **Prompts** contain the domain expertise — they change when the analysis logic evolves but the data shape stays the same. Stored as markdown files so domain experts can edit them without touching code.
- **Runners** contain the pipeline integration logic — how to extract data from ingestion output, compute deterministic metrics, build user messages, and call the LLM. They change when the data preparation logic evolves.

This separation means you can change the analysis criteria (prompt) without touching the data schema, or add a new output field (schema) without rewriting the prompt.

### How the Registry Ties Them Together

`AGENT_REGISTRY` is a single `Record<string, AgentConfig>` that maps agent names to their configuration:

```typescript
interface AgentConfig {
  name: string;           // Agent identifier
  promptFile: string;     // Which .md file to load
  schema: z.ZodType<any>; // Zod schema for output validation
  model: string;          // Which OpenRouter model to use (e.g. z-ai/glm-5.1)
  phase: PipelinePhase;   // Which execution phase
  dependsOn: string[];    // Upstream dependencies
  tools?: Tool[];         // Extra tools (web search for market-macro)
  maxTokens?: number;     // Max output tokens
}
```

Every runner reads its model and maxTokens from the registry rather than hardcoding them. This means model routing changes require editing only one file.

## 4. Agent Pattern

Every agent (except Market & Macro) follows this standard pattern:

### Step 1: Load Configuration
```typescript
const config = AGENT_REGISTRY['agent-name'];
const systemPrompt = loadAgentPrompt(config.promptFile);
```

### Step 2: Filter Relevant Documents
Each runner filters `IngestionOutput.documents` by document type to extract only the sections relevant to its analysis.

### Step 3: Compute Deterministic Metrics
Financial calculations happen in TypeScript — not delegated to the LLM. Examples:
- Financial Analysis: EBITDA, SDE, gross/net margins, growth rates, current ratio
- Tax Compliance: revenue discrepancies between P&L and tax returns
- AR Collections: DSO, aging bucket percentages, estimated write-offs
- Lending: monthly payment, DSCR, max supportable loan (amortization formula)

This ensures numerical accuracy and makes the results reproducible.

### Step 4: Build User Message
The runner constructs a user message containing:
- Pre-computed metrics (labeled "DO NOT RECALCULATE")
- Raw extracted data from relevant documents
- Warnings about missing data

### Step 5: Call the LLM via `call_agent<T>()`
```typescript
return call_agent<T>({
  model: config.model,
  systemPrompt,
  userMessage,
  schema: OutputSchema,
  maxTokens: config.maxTokens,
  temperature: 0,
});
```

### Step 6: Validate and Return
`call_agent` handles:
1. Converting the Pydantic schema to JSON Schema
2. Sending it as an OpenAI-compatible function/tool definition (forcing structured output)
3. Parsing the tool_calls response
4. Validating with Pydantic
5. On validation failure: sending errors back to the model for retry (max 2 retries)
6. Tracking token usage and latency
7. Returning a discriminated union: `AgentResult<T>` with status `'success'` or `'error'`

### Market & Macro Exception
This agent uses context from uploaded documents alongside structured output. It calls `call_agent` directly like all other agents — there is no web search integration in the current Python implementation.

## 5. Orchestration Logic

### Promise.allSettled for Graceful Degradation

Phase 2 uses `Promise.allSettled()` instead of `Promise.all()`:

```typescript
const phase2Results = await Promise.allSettled([
  runFinancialAnalysis(ingestionOutput),
  runTaxCompliance(ingestionOutput),
  // ... 5 more agents
]);
```

If any agent throws an unhandled exception, `Promise.allSettled` catches it as a `rejected` result. The `settledToAgentResult()` helper converts both outcomes:
- `fulfilled` → returns the `AgentResult<T>` directly
- `rejected` → wraps the error in a structured `AgentError`

This means a timeout in Market & Macro doesn't crash Tax Compliance.

### Phase Chaining

Each phase populates fields on a mutable `PipelineState` object:
1. Phase 1 sets `state.ingestion` — if it's an error, all other fields get abort errors and the pipeline returns early
2. Phase 2 sets 7 agent result fields
3. Phase 3 checks `state.financialAnalysis.status === 'success'` before running — if Financial Analysis failed, Lending gets a descriptive error explaining why
4. Phase 4 passes all 9 `AgentResult` objects (successes and errors) to the Synthesis runner, which adapts its analysis based on data completeness

### Error Propagation

Errors never crash the pipeline. They flow forward as typed `AgentResult<T>` with `status: 'error'`:
- The orchestrator logs each failure but continues
- The Synthesis agent receives error states and notes them in `dataCompleteness.failedAnalyses`
- The API always returns HTTP 200 with the full `PipelineState`, even if some agents failed
- Only truly unexpected errors (unhandled exceptions in the orchestrator itself) return HTTP 500

## 6. Model Routing

| Model | Agents | Rationale |
| Model | Agents | Rationale |
|-------|--------|-----------|
| **GLM-5.1** (`z-ai/glm-5.1` via OpenRouter) | All 9 LLM agents — Financial, Tax, AR, Customer, Ops, Lease, Market, Lending, Synthesis | Single unified model routed through OpenRouter. GLM-5.1 supports a 202K token context window and is capable of long-horizon structured reasoning. Model routing per-agent can be restored by updating `AGENT_REGISTRY` model strings without touching runner code. |
| **Mistral OCR** (`mistral-ocr-2512`) | Document Ingestion | Specialized OCR model for PDF/table extraction. Unchanged. |

## 7. Cost Control

The architecture targets **~$0.10–$0.50 per full analysis** at GLM-5.1 pricing through several mechanisms:

### Model Routing
All 9 LLM agents share a single model (`z-ai/glm-5.1`) at $0.95/M input and $3.15/M output via OpenRouter. Switching individual agents to a cheaper model only requires changing the `model` string in `registry.py`.

### Context Compression
Each agent receives only the documents relevant to its analysis, not the full corpus. The Synthesis agent receives compressed summaries (score + confidence + 3 risks per agent), not the full outputs.

### Deterministic Pre-computation
Financial ratios, DSO, DSCR, amortization schedules — all computed in Python. The LLM only interprets results, reducing output token needs and eliminating hallucinated arithmetic.

### Cost Tracking
The orchestrator computes per-model cost using actual token counts:

| Model | Input ($/1M tokens) | Output ($/1M tokens) |
|-------|---------------------|----------------------|
| GLM-5.1 (z-ai/glm-5.1) | $0.95 | $3.15 |
| Mistral OCR | $0.002/page | — |

Actual cost is calculated per-agent using `(input_tokens / 1M) × rate + (output_tokens / 1M) × rate` and summed across all successful agents, keyed by the model each agent used via the registry.

### Prompt Caching
Prompts are loaded once and cached in-memory by `prompts.py`. OpenRouter supports prompt caching on compatible models, which can further reduce repeated-analysis costs when system prompts are identical across invocations.

## 8. Key Architectural Decisions

### Principle 1: Separate What Changes Independently

- **Prompts** (domain expertise) change when analysis criteria evolve
- **Schemas** (data contracts) change when output fields are added/removed
- **Runners** (integration logic) change when data preparation logic evolves
- **Registry** (configuration) changes when model routing is adjusted

Each can be modified without touching the others. A domain expert can refine the tax compliance prompt without risking a regression in the lending calculations.

### Principle 2: Compress at Every Boundary

Raw data is compressed at each stage transition:
- Documents → structured sections (ingestion)
- All sections → relevant sections only (per-runner filtering)
- Full agent outputs → score + summary + top risks (synthesis)

This keeps per-agent token consumption proportional to that agent's scope, not the total document corpus size.

### Principle 3: Fail Gracefully, Not Catastrophically

The pipeline is designed so that partial results are always better than no results:
- `Promise.allSettled()` isolates agent failures in Phase 2
- Conditional dependencies (Phase 3) handle upstream failures with descriptive error messages
- The Synthesis agent adjusts its recommendation based on data completeness
- The API returns HTTP 200 with the full state even on partial failure
- Every `AgentResult<T>` is a discriminated union — code must explicitly check `status` before accessing `.data`

This means a buyer always gets something useful, even if the tax return analysis times out or the market research agent can't reach the web.
