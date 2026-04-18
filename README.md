# BizzBuy — AI Acquisition Diligence Co-Pilot



> There is no simple tool that helps non-expert buyers determine whether a small business is truly affordable, transferable, and worth acquiring. BizzBuy is the **"Carfax for buying a business"** — an AI-powered diligence engine that analyzes financials, operational risk, and lending viability, then delivers a plain-language buyer report.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Application Flow](#application-flow)
- [Phase 2 Parallel Agent System](#phase-2-parallel-agent-system)
- [Report Output Sections](#report-output-sections)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Disclaimer](#disclaimer)

---

## Overview

BizzBuy walks a buyer through a 4-step wizard:

1. **Upload** financial documents (or use Demo Mode)
2. **Review** and confirm the AI-extracted data
3. **Answer** 6 sections of risk questions (triggering 7 parallel AI agents)
4. **Receive** a full acquisition analysis report with a downloadable PDF

The engine combines deterministic financial math with multiple focused Claude AI calls — keeping costs low while producing deep, specific diligence output.

---

## Features

| Feature | Details |
|---|---|
| Document ingestion | Upload P&L, balance sheet, cash flow, loan terms, or tax returns as PDF/image/CSV — Claude extracts structured data |
| Editable review | Confirm or correct all AI-extracted values before analysis begins |
| 6-dimension risk questionnaire | Owner dependence, customer concentration, revenue quality, employee risk, supplier risk, financial/add-back risk |
| Phase 2 parallel agents | 7 specialized agents run simultaneously (financial, tax, AR/collections, customer, operations, lease & contracts, market & macro) |
| Shared context merge | Agent outputs are merged, flags deduplicated, and SDE validated before synthesis |
| SDE conflict detection | If tax-normalized SDE and financial SDE diverge by more than 15%, the conservative figure is used and a critical flag is raised |
| Lending & affordability | DSCR, break-even, 4 revenue scenarios, SBA max loan sizing (5× SDE, 10-year), bankability score |
| Full AI synthesis | Claude generates plain-language executive summary, seller questions, diligence checklist, upside opportunities, and a final recommendation |
| Risk radar chart | Visual overview of all 6 risk dimensions |
| Transferability analysis | Scored view of how easily the business can change hands |
| Downloadable PDF | Full report exported via `@react-pdf/renderer` |
| Demo mode | Pre-loaded HVAC business (Sunny's HVAC Services) for demonstrations |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 14 (App Router), TypeScript 5 |
| AI | OpenRouter (`z-ai/glm-5.1`) via `openai` Python SDK — all 9 LLM agents; Mistral OCR (`mistral-ocr-2512`) for document extraction |
| UI | Tailwind CSS 3, shadcn/ui components, Lucide React icons |
| Charts | Recharts |
| PDF | `@react-pdf/renderer` |
| State | React Context + `useReducer` |
| CSV parsing | PapaParse |
| Validation | Zod |

---

## Application Flow

```
Landing Page
    │
    ▼
Step 1 — Upload (/analyze/upload)
    Files + doc types → POST /api/parse-documents
    → FinancialData (structured payload)
    │
    ▼
Step 2 — Review (/analyze/review)
    User confirms/corrects extracted figures
    Adds deal info (asking price, business type, etc.)
    │
    ▼
Step 3 — Questions (/analyze/questions)
    6-section risk questionnaire
    → runPhase2Agents() — 7 parallel API calls
    → POST /api/agents/merge → SharedContext
    → POST /api/analyze → ReportOutput
    │
    ▼
Step 4 — Report (/analyze/report)
    Full plain-language analysis report
    → POST /api/generate-pdf → bizbuy-acquisition-report.pdf
```

---

## Phase 2 Parallel Agent System

When "Generate Report" is clicked, all 7 agents are called simultaneously via `Promise.all` in `lib/api-client.ts`. Each agent receives the same `{ financialData, questionnaire, dealInfo }` payload and returns an `AgentOutput` with `metrics`, `flags`, `confidence`, `summary`, and `notes`.

| Agent | Endpoint | Type | What it produces |
|---|---|---|---|
| **Financial** | `/api/agents/financial` | Deterministic | SDE, margins, DSCR, valuation multiple, working capital, cash flow metrics |
| **Tax** | `/api/agents/tax` | Claude + fallback | Tax-normalized SDE (`normalizedSDE`), revenue/income variance vs statements, deduction risk score |
| **AR & Collections** | `/api/agents/ar-collections` | Deterministic | Implied DSO, AR-to-revenue %, bad-debt risk score |
| **Customer** | `/api/agents/customer` | Deterministic | Approximate HHI, churn risk score, contract strength score |
| **Operations** | `/api/agents/operations` | Deterministic | Process maturity, management depth, supplier dependency, critical staff ratio, composite ops risk |
| **Lease & Contracts** | `/api/agents/lease-contracts` | Claude + fallback | Transferability risk, remaining lease term, rent escalation, transfer approval requirement |
| **Market & Macro** | `/api/agents/market-macro` | Claude + heuristics | Industry valuation range (low/high multiple), macro risk score, industry outlook score |

### Shared Context Merge (`lib/merge-context.ts`)

After all 7 agents complete, `/api/agents/merge` calls `buildSharedContext`:

- **Deduplicates** flags across all agents by `sourceAgent:dimension:message`
- **Sorts** flags — critical → warning → info, then by dimension
- **SDE conflict detection** — if tax `normalizedSDE` and financial `sde` diverge by more than 15%, the conservative (lower) figure is used as `validatedSDE` and a critical flag is added
- The merged `SharedContext` is then passed to `/api/analyze`

### SBA Loan Sizing & Bankability (`app/api/analyze/route.ts`)

| Calculation | Formula |
|---|---|
| Max supported loan | `validatedSDE × 5` |
| Estimated rate | WSJ Prime (8.5%) + SBA spread (2.75%) = **11.25%** |
| Payment model | 10-year amortization |
| Bankability base score | 55 |
| Adjustments | +25 / +15 / +5 for DSCR tiers; −20 if DSCR < 1; −15 if SDE conflict; −8 per critical flag; −3 per warning |
| Labels | Weak / Borderline / Bankable / Strong |

---

## Report Output Sections

Each `ReportOutput` contains the following sections, all rendered on-screen and exported to PDF:

| # | Section | Contents |
|---|---|---|
| 1 | Executive Summary | Plain-language verdict, risk and transferability scores |
| 2 | Financial Snapshot | Revenue, COGS, gross margin, SDE, EBITDA, working capital, valuation multiple |
| 3 | Debt Service & Affordability | DSCR, monthly/annual debt service, break-even, 4 revenue scenarios, SBA max loan, bankability score |
| 4 | Risk Assessment | 6-dimension scores (1–10), radar chart, deal breakers, Phase 2 agent flags |
| 5 | Transferability Analysis | Score, key factors, improvement suggestions |
| 6 | Questions for the Seller | 8–15 targeted questions grouped by risk category |
| 7 | Due Diligence Checklist | 10–20 prioritized items (critical / important / nice to have) |
| 8 | Upside Opportunities | 3–5 value-creation ideas with estimated impact and difficulty |
| 9 | Final Recommendation | Proceed / Proceed with Caution / Walk Away + strengths, risks, next steps |

---

## Architecture

See [`architecture flow.md`](./architecture%20flow.md) for the full phase diagram with visual flowchart.

```
app/
├── page.tsx                         # Landing page
├── layout.tsx                       # Root layout — AnalysisProvider, Header, Footer
├── analyze/
│   ├── layout.tsx                   # Wizard shell — StepIndicator
│   ├── upload/page.tsx              # Step 1: document upload
│   ├── review/page.tsx              # Step 2: data review & deal info
│   ├── questions/page.tsx           # Step 3: questionnaire + Phase 2 agents
│   └── report/page.tsx              # Step 4: full analysis report
└── api/
    ├── parse-documents/route.ts     # Claude document extraction
    ├── agents/
    │   ├── financial/route.ts       # Deterministic financial agent
    │   ├── tax/route.ts             # Tax normalization agent (Claude)
    │   ├── ar-collections/route.ts  # AR/collections agent
    │   ├── customer/route.ts        # Customer concentration agent
    │   ├── operations/route.ts      # Operations agent
    │   ├── lease-contracts/route.ts # Lease & contracts agent (Claude)
    │   ├── market-macro/route.ts    # Market & macro agent (Claude)
    │   └── merge/route.ts           # Merge → SharedContext
    ├── analyze/route.ts             # Lending + Claude synthesis → ReportOutput
    └── generate-pdf/route.ts        # PDF export via @react-pdf/renderer

lib/
├── types.ts                         # All TypeScript interfaces
├── api-client.ts                    # Browser fetch helpers + runPhase2Agents
├── calculations.ts                  # DSCR, SDE, scenarios, break-even (deterministic)
├── risk-scoring.ts                  # 6-dimension weighted risk scoring
├── merge-context.ts                 # SDE validation + flag merge
├── prompts.ts                       # Claude prompt templates (parsing + report)
├── agent-prompts.ts                 # Claude prompts for tax, lease, market agents
├── report-pdf.tsx                   # @react-pdf document layout
├── constants.ts                     # Risk thresholds, business types, disclaimers
├── demo-data.ts                     # Pre-loaded HVAC demo data
└── format.ts                        # UI formatting helpers

context/
└── AnalysisContext.tsx              # Global wizard state (step, data, report, loading)

components/
├── layout/                          # Header, Footer, StepIndicator
├── upload/                          # FileDropZone
├── report/                          # ExecutiveSummary, FinancialSnapshot,
│                                    # DebtServiceAnalysis, RiskAssessment,
│                                    # TransferabilityAnalysis, SellerQuestions,
│                                    # DiligenceChecklist, UpsideOpportunities,
│                                    # FinalRecommendation, ReportHeader, ScoreBadge
└── ui/                              # shadcn/ui primitives (button, card, slider, etc.)
```

---

## Getting Started

### Prerequisites

- Node.js 18+
- An [OpenRouter API key](https://openrouter.ai/) for all LLM agents
- A [Mistral API key](https://console.mistral.ai/) for OCR document extraction

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/Team7Hackers/BizzBuy.git
cd BizzBuy

# 2. Install dependencies
npm install

# 3. Set up environment variables
cp .env.local.example .env.local
# Open .env.local and add your key (see below)

# 4. Start the development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build for production

```bash
npm run build
npm start
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | Your OpenRouter API key (routes all 9 LLM agents to `z-ai/glm-5.1`) |
| `MISTRAL_API_KEY` | Yes | Your Mistral API key (OCR document extraction) |
| `NEXT_PUBLIC_BACKEND_URL` | No | FastAPI backend URL seen from the browser (default: `http://localhost:8000/api`) |
| `OPENROUTER_REFERRER` | No | HTTP-Referer header sent to OpenRouter (default: `https://bizbuy.local`) |

Create `.env.local` at the project root (never commit this file — it is in `.gitignore`):

```env
OPENROUTER_API_KEY=sk-or-v1-...
MISTRAL_API_KEY=...
```

A template is provided at `.env.local.example`.

---

## Project Structure — Key Data Types

### `FinancialData` (output of Phase 1)
Structured payload from uploaded documents: `incomeStatement`, `balanceSheet`, `loanTerms`, `cashFlow`, `parsingNotes`, `dataCompleteness`.

### `SharedContext` (output of Phase 2 merge)
Carries all Phase 2 agent outputs, merged flags, `validatedSDE`, `sdeConflict`, and the original financial/questionnaire/deal data.

### `ReportOutput` (output of Phase 3 synthesis)
All 9 report sections plus `agentFlags`, `sbaLoanSizing`, and `metadata`.

---

## Disclaimer

This tool is for informational purposes only. It does not constitute financial, legal, or investment advice. Financial calculations are deterministic and based solely on the data provided. AI-generated narrative sections reflect patterns in the provided data and should be independently verified. Consult qualified professionals — accountant, attorney, business broker — before making any acquisition decision.
