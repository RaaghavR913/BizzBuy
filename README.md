# BizBuy — AI Acquisition Diligence Co-Pilot

> "Carfax for buying a business" — AI-powered diligence that tells non-expert buyers whether a small business is truly affordable, transferable, and worth acquiring.

## Getting Started

### Prerequisites
- Node.js 18+
- Anthropic API Key (Claude)

### Installation

```bash
# Install dependencies
npm install

# Copy and fill in your API key
cp .env.local.example .env.local
# Edit .env.local and add your ANTHROPIC_API_KEY

# Run in development
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Features

- **Document Upload & AI Parsing** — Upload P&L, balance sheets, and loan term sheets. Claude extracts structured financial data.
- **Editable Data Review** — Confirm or correct extracted values before analysis.
- **6-Dimension Risk Questionnaire** — Owner dependence, customer concentration, revenue quality, employee risk, supplier risk, and financial risk.
- **Deterministic Financial Engine** — DSCR, SDE, gross margin, scenarios, and break-even calculated in TypeScript (not AI).
- **AI-Generated Report** — 9-section acquisition analysis report with plain-language explanations.
- **Interactive Risk Radar Chart** — Visual overview of all 6 risk dimensions.
- **Due Diligence Checklist** — Interactive checklist with priority levels.
- **Demo Mode** — Pre-loaded HVAC business data for demonstrations.

## Tech Stack

- **Frontend**: Next.js 14 (App Router) + TypeScript
- **UI**: Tailwind CSS + shadcn/ui + Recharts
- **AI**: Anthropic Claude API (claude-opus-4-5)
- **State**: React Context + useReducer

## Architecture

```
app/
├── page.tsx                    # Landing page
├── analyze/
│   ├── upload/page.tsx         # Step 1: Document upload
│   ├── review/page.tsx         # Step 2: Data review & confirmation  
│   ├── questions/page.tsx      # Step 3: Risk questionnaire (6 sections)
│   └── report/page.tsx         # Step 4: Full analysis report
└── api/
    ├── parse-documents/        # Claude-powered document extraction
    ├── analyze/                # Deterministic calculations + AI narrative
    └── generate-pdf/           # HTML report generation

lib/
├── calculations.ts             # Deterministic financial math (DSCR, SDE, etc.)
├── risk-scoring.ts             # Weighted risk scoring algorithm
├── types.ts                    # TypeScript interfaces
├── prompts.ts                  # Claude API prompt templates
└── constants.ts                # Risk weights, thresholds, labels
```

## Usage

1. **Upload** — Drag and drop your P&L, balance sheet, and loan term sheet (or use Demo Mode)
2. **Review** — Confirm the AI-extracted data (or enter manually)
3. **Questions** — Answer 6 sections of operational risk questions
4. **Report** — Get your full acquisition analysis with scores, seller questions, and recommendation

## Disclaimer

This tool is for informational purposes only. It does not constitute financial, legal, or investment advice. Consult qualified professionals before making any acquisition decision.
