# BizBuy — Product Requirements Document (MVP / Hackathon Build)

**Version:** 1.0
**Last Updated:** March 28, 2026
**Target:** Hackathon Demo / $30K Funding Pitch
**One-Line Summary:** An AI-powered acquisition diligence co-pilot that tells non-expert buyers whether a small business is truly affordable, transferable, and worth acquiring.

---

## 1. Problem Statement

Small business acquisition buyers face a diligence gap: they can access financial statements, asking prices, and loan terms, but they cannot easily determine whether the business is financially viable, operationally transferable, and worth the risk. Existing information is fragmented and requires expertise in accounting, lending, and operational diligence. There is no simple tool that helps non-expert buyers determine whether a small business is truly affordable, transferable, and worth acquiring based on both its financials and hidden operational risks.

**Core Insight:** Not every profitable business is an acquirable business. The product sells confidence and helps buyers avoid purchasing a business with hidden fragility.

**Positioning:** "Carfax for buying a business" — or — "TurboTax for buying a business, focused on risk, diligence, and transferability."

---

## 2. Target User

**Primary Persona:** First-time or non-expert small business buyer (individual acquirer, search fund operator, or aspiring entrepreneur) evaluating a business listed on BizBuySell, Flippa, or through a business broker. They understand basic business concepts but do not have deep accounting, lending, or M&A diligence experience. They are spending $100K–$5M on an acquisition and cannot afford to hire a full diligence team for every deal they evaluate.

**Secondary Persona:** Business brokers or SBA lenders who want a fast preliminary risk screen before deeper engagement.

---

## 3. Core Value Proposition

The buyer uploads financial documents and answers a structured set of operational risk questions. BizBuy outputs a plain-language acquisition decision report that covers:

1. **Affordability** — Can the buyer actually service the debt and still take home income?
2. **Transferability** — Will the business survive a change in ownership?
3. **Risk** — What hidden fragility exists in the financials and operations?
4. **Action Plan** — What questions to ask the seller, what to verify, and what deal terms to negotiate.

---

## 4. MVP Feature Scope

### 4.1 Feature: Document Upload & Parsing

**Description:** The buyer uploads financial documents (PDF, CSV, or images). The system extracts structured financial data using AI and presents it back for confirmation before analysis.

**Accepted Document Types (MVP):**
- Income Statement / Profit & Loss (P&L)
- Balance Sheet
- Cash Flow Statement (optional but ideal)
- Loan Term Sheet / Offer Letter from lender
- Tax Returns (Schedule C or business returns) — stretch goal

**Functional Requirements:**
- FR-1.1: Accept PDF, PNG, JPG, and CSV file uploads (max 20MB per file, max 6 files per session).
- FR-1.2: Use AI (Claude API with document/vision input) to extract structured financial data from each uploaded document.
- FR-1.3: Parse extracted data into a standardized JSON schema (see Section 8 — Data Models).
- FR-1.4: Display extracted data back to the user in editable fields so they can confirm or correct values before analysis proceeds.
- FR-1.5: Support manual entry as a fallback — if parsing fails or the user has no documents, they can type in key figures directly.
- FR-1.6: Store uploaded files temporarily in the session (no long-term storage for MVP). Files are deleted after 24 hours or session end.

**UX Flow:**
1. User lands on upload screen.
2. User drags/drops or selects files.
3. System shows a progress indicator ("Analyzing your documents...").
4. System displays extracted data in a structured review form.
5. User confirms, edits, or fills in missing fields.
6. User clicks "Continue to Risk Assessment."

---

### 4.2 Feature: Operational Risk Questionnaire

**Description:** After financial data is captured, the buyer answers a structured questionnaire about the business's operational characteristics. These questions target the risks that financials alone cannot reveal.

**Functional Requirements:**
- FR-2.1: Present a multi-step questionnaire (wizard-style, one section at a time).
- FR-2.2: The questionnaire covers the following risk dimensions (each dimension is a section):

**Section 1 — Owner Dependence**
- What percentage of sales does the current owner personally generate or close?
- How involved is the owner in day-to-day operations (full-time, part-time, minimal)?
- Does the owner hold key customer relationships that are not documented or shared with staff?
- If the owner disappeared for 90 days, would the business continue to operate and generate revenue?

**Section 2 — Customer Concentration**
- What percentage of total revenue comes from the top 1 customer?
- What percentage of total revenue comes from the top 5 customers?
- Are customer relationships contractual or handshake-based?
- What is the average customer tenure (less than 1 year, 1–3 years, 3+ years)?

**Section 3 — Revenue Quality**
- What percentage of revenue is recurring (subscriptions, contracts, retainers)?
- What percentage is project-based or one-time?
- Has revenue grown, stayed flat, or declined over the past 3 years?
- Are there any known upcoming customer losses or contract expirations?

**Section 4 — Employee & Operational Risk**
- How many total employees does the business have?
- How many employees are considered mission-critical (business breaks if they leave)?
- Are there documented standard operating procedures (SOPs)?
- Is there a management layer between the owner and frontline staff?

**Section 5 — Supplier & Vendor Risk**
- Is there a single supplier that accounts for more than 30% of COGS or operations?
- Are supplier agreements documented and transferable?
- Are there any exclusive or hard-to-replace vendor relationships?

**Section 6 — Financials & Add-Backs**
- Has the seller presented any add-backs to adjusted EBITDA (owner salary, one-time expenses, personal expenses run through the business)?
- Do the add-backs exceed 30% of stated EBITDA?
- Are there any pending lawsuits, tax liabilities, or environmental issues?

- FR-2.3: Each question should use the appropriate input type (single select, multi-select, slider, numeric input, or short text).
- FR-2.4: Allow "I don't know" as a valid answer for every question. Unknown answers increase the risk score for that dimension.
- FR-2.5: Persist answers in session state so the user can navigate back and forth between sections without losing data.

---

### 4.3 Feature: AI Analysis Engine

**Description:** The core intelligence layer. Takes the structured financial data + questionnaire answers and produces a comprehensive acquisition analysis. This is implemented as a multi-step AI pipeline using Claude API calls.

**Functional Requirements:**

**Step 1 — Financial Viability Analysis**
- FR-3.1: Calculate or derive the following from extracted financials:
  - Gross Revenue (trailing 12 months or most recent annual)
  - Cost of Goods Sold (COGS)
  - Gross Margin (%)
  - Operating Expenses (OpEx)
  - Seller's Discretionary Earnings (SDE)
  - EBITDA (with and without add-backs)
  - Net Income
  - Working Capital (Current Assets – Current Liabilities)
  - Debt-to-Equity Ratio (if balance sheet provided)

- FR-3.2: If a loan term sheet is provided, calculate:
  - Total Loan Amount
  - Interest Rate (annual)
  - Loan Term (months)
  - Monthly Debt Service Payment
  - Annual Debt Service
  - Debt Service Coverage Ratio (DSCR) = SDE / Annual Debt Service
  - Minimum Annual Revenue required to cover debt service + estimated operating costs
  - Estimated Loan Payoff Timeline under current performance
  - Estimated Loan Payoff Timeline under 10% growth scenario
  - Estimated Loan Payoff Timeline under 10% decline scenario
  - Break-Even Monthly Revenue

- FR-3.3: Flag financial red flags:
  - DSCR below 1.25 (critical warning)
  - Negative working capital
  - Revenue declining year-over-year
  - EBITDA margin below industry norms (if known)
  - Add-backs exceeding 30% of EBITDA
  - Asking price exceeds 4x SDE (high multiple warning)

**Step 2 — Operational Risk Scoring**
- FR-3.4: Score each of the 6 risk dimensions from the questionnaire on a 1–10 scale (1 = low risk, 10 = critical risk).
- FR-3.5: Calculate a weighted composite Acquisition Risk Score (1–100 scale).
  - Owner Dependence: 25% weight
  - Customer Concentration: 20% weight
  - Revenue Quality: 20% weight
  - Employee & Operational Risk: 15% weight
  - Supplier Risk: 10% weight
  - Financial & Add-Back Risk: 10% weight

- FR-3.6: Calculate a Transferability Score (1–100 scale, higher = more transferable) based on inverse of owner dependence, process maturity, customer contract quality, and employee stability.

- FR-3.7: Identify Deal Breakers — any single dimension scoring 9 or 10 triggers a "Potential Deal Breaker" flag with an explanation.

**Step 3 — Report Generation**
- FR-3.8: Use Claude API to generate a plain-language acquisition report that synthesizes all of the above into the following sections (see Section 6 — Report Output Format).

---

### 4.4 Feature: Report Output & Display

**Description:** The final deliverable. A structured, plain-language report displayed in-app and downloadable as PDF.

**Functional Requirements:**
- FR-4.1: Display the report in a clean, scrollable, in-app view with section navigation.
- FR-4.2: Provide a "Download PDF" button that generates a styled PDF of the full report.
- FR-4.3: Provide a "Copy Link" feature that generates a shareable read-only link to the report (stretch goal — for MVP, PDF download is sufficient).
- FR-4.4: The report must render properly on desktop and mobile screens.

---

### 4.5 Feature: Deal Comparison (Stretch Goal)

**Description:** Allow a buyer to save multiple analyses and compare them side by side.

- FR-5.1: Save completed analyses to user profile (requires auth).
- FR-5.2: Display a comparison table of key metrics across saved deals.
- FR-5.3: Rank deals by composite risk score and affordability.

**Note:** This is a stretch goal. Do not build unless core features are complete and stable.

---

## 5. Non-Functional Requirements

- NFR-1: The full analysis pipeline (upload → parse → questionnaire → report) should complete in under 90 seconds for a standard set of 3 documents.
- NFR-2: The application must work on Chrome, Safari, and Firefox (latest versions).
- NFR-3: The application must be responsive and usable on screens 375px wide and above.
- NFR-4: All uploaded documents must be processed securely. No financial data is stored permanently in the MVP. Session data is cleared after 24 hours.
- NFR-5: AI-generated financial calculations must be verified by a deterministic calculation layer (do not rely solely on LLM math). The AI extracts values; the application code computes ratios and derived metrics.
- NFR-6: The app should handle graceful errors — if document parsing fails, guide the user to manual entry. If the AI analysis times out, allow retry.

---

## 6. Report Output Format

The generated report must contain the following sections in this order:

### Section 1: Executive Summary
- 3–5 sentence overview of the deal.
- Overall Acquisition Risk Score (1–100) with a color-coded badge (Green: 1–35, Yellow: 36–65, Red: 66–100).
- Transferability Score (1–100) with a color-coded badge.
- One-line verdict: "This deal appears [strong / moderate / risky / highly risky] based on the information provided."

### Section 2: Financial Snapshot
- Table of key financial metrics (Revenue, COGS, Gross Margin, OpEx, SDE, EBITDA, Net Income, Working Capital).
- Asking Price and implied valuation multiple (Price / SDE).
- Comparison to common industry multiples if applicable.

### Section 3: Debt Service & Affordability
- Loan terms summary (amount, rate, term).
- Monthly and annual debt service payment.
- DSCR and what it means in plain language.
- Minimum revenue required to service debt.
- Scenario table: payoff timeline at current performance, +10% growth, and -10% decline.
- Plain-language affordability verdict.

### Section 4: Risk Assessment
- Each of the 6 risk dimensions with:
  - Score (1–10) and a visual indicator.
  - 2–3 sentence explanation of the score.
  - Key risk factors identified.
- Any Deal Breakers called out prominently.

### Section 5: Transferability Analysis
- Transferability Score with explanation.
- Key factors affecting transferability (owner role, process maturity, customer contracts, team stability).
- What would need to change for the business to be more transferable.

### Section 6: Questions to Ask the Seller
- AI-generated list of 8–15 targeted questions based on the specific risks identified in this deal.
- Questions are grouped by risk dimension.

### Section 7: Diligence Checklist
- A customized checklist of items to verify during due diligence, based on the business type and identified risks.
- Each item has a priority level (Critical, Important, Nice-to-Have).

### Section 8: Upside & Opportunities
- AI-generated observations on potential operational improvements, revenue additions, or cost reductions that could improve the deal.
- Estimated impact where possible (e.g., "Adding a recurring revenue component could increase valuation by 1–2x SDE").

### Section 9: Final Recommendation
- Plain-language recommendation: Proceed, Proceed with Caution, or Walk Away.
- Summary of the top 3 strengths and top 3 risks.
- Suggested next steps.

---

## 7. Technical Architecture

### 7.1 Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | Next.js 14+ (App Router) with TypeScript | Fast to build, SSR for performance, strong ecosystem |
| UI Library | Tailwind CSS + shadcn/ui | Professional look with minimal custom CSS, rapid development |
| State Management | React Context + useReducer (or Zustand if needed) | Lightweight, sufficient for wizard-style flow |
| Backend API | Next.js API Routes (Route Handlers) | Co-located with frontend, no separate server needed for MVP |
| AI Layer | Anthropic Claude API (claude-sonnet-4-20250514) | Best-in-class document understanding, long context, structured output |
| Document Parsing | Claude API with vision/document input for PDFs and images; Papaparse for CSVs | Claude handles unstructured financial docs well |
| PDF Generation | @react-pdf/renderer or Puppeteer (headless Chrome) | For downloadable report output |
| File Storage | Vercel Blob or local /tmp (MVP) | Temporary storage for uploaded files during session |
| Database | None for MVP (session-based) or Supabase if auth is needed | Keep it simple; add persistence post-MVP |
| Hosting | Vercel | One-click deploy, edge functions, free tier |
| Authentication | None for MVP. Clerk or NextAuth if adding saved reports. | Defer until stretch goals |

### 7.2 System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                   │
│                                                             │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌───────┐│
│  │  Upload   │→│  Review &    │→│  Risk       │→│ Report ││
│  │  Screen   │  │  Confirm     │  │  Questions  │  │ View  ││
│  └──────────┘  └──────────────┘  └────────────┘  └───────┘│
│       │              ↕                  │            │      │
└───────┼──────────────┼──────────────────┼────────────┼──────┘
        │              │                  │            │
        ▼              ▼                  ▼            ▼
┌─────────────────────────────────────────────────────────────┐
│                    API LAYER (Next.js Route Handlers)        │
│                                                             │
│  POST /api/parse-documents                                  │
│    → Sends files to Claude API with document/vision input   │
│    → Returns structured financial JSON                      │
│                                                             │
│  POST /api/analyze                                          │
│    → Receives: confirmed financials + questionnaire answers │
│    → Step 1: Deterministic financial calculations           │
│    → Step 2: Claude API call for risk scoring + narrative   │
│    → Step 3: Claude API call for report generation          │
│    → Returns: complete report JSON                          │
│                                                             │
│  POST /api/generate-pdf                                     │
│    → Receives: report JSON                                  │
│    → Returns: PDF file buffer                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
        │                    │
        ▼                    ▼
┌──────────────┐    ┌──────────────┐
│ Claude API   │    │  Calculation │
│ (Anthropic)  │    │  Engine      │
│              │    │  (Pure JS)   │
│ - Doc Parse  │    │              │
│ - Risk Score │    │ - DSCR       │
│ - Report Gen │    │ - Margins    │
│              │    │ - Debt Svc   │
│              │    │ - Scenarios  │
└──────────────┘    └──────────────┘
```

### 7.3 Architecture Decision: Why Not AWS Serverless for the MVP

A full AWS serverless architecture was proposed during planning and is documented here as the production target state. The proposed stack includes Route53 for DNS, CloudFront for CDN, four Lambda functions (API handler, document parsing, risk scoring/LLM orchestration, checklist/report generation), three S3 buckets (static frontend, uploaded documents, generated reports), DynamoDB for users/analyses/scores/job status, SQS for async analysis job queuing, and SNS for email/notification fanout.

**This architecture is the correct long-term production target but the wrong choice for the hackathon MVP.** The reasoning is as follows:

**Infrastructure overhead kills velocity.** Configuring Route53, CloudFront with S3 origins, four independent Lambda functions with IAM roles, three S3 buckets with CORS policies, DynamoDB table schemas, SQS queue/DLQ setup, and SNS topics represents two to three days of pure infrastructure work before a single line of product code is written. In a hackathon, that time is fatal.

**Microservices add debugging surface area.** Four separate Lambda functions mean four separate deployment packages, four sets of CloudWatch logs, and inter-service communication patterns (via SQS or direct invocation) that introduce failure modes unrelated to the product logic. A bug in IAM permissions between the document parsing Lambda and the S3 upload bucket can stall the entire build for hours.

**Async job queues are unnecessary at MVP scale.** SQS is valuable when analysis takes minutes and you need to decouple request from response. The BizBuy analysis pipeline — document parsing plus deterministic calculations plus one or two Claude API calls — completes in 30 to 90 seconds. A synchronous API route with streaming handles this cleanly.

**DynamoDB is unnecessary without user accounts.** The MVP has no authentication, no saved analyses, and no multi-user data model. All state lives in the client session and is passed to API routes as request payloads. Adding a database at this stage adds schema management and data access patterns that serve no demo purpose.

**The MVP stack (Next.js on Vercel) maps one-to-one functionally:**

| AWS Component | MVP Equivalent | Migration Path |
|--------------|----------------|----------------|
| Route53 + CloudFront | Vercel (automatic DNS, CDN, SSL) | Point Route53 to Vercel, or migrate to CloudFront when needed |
| 4 Lambda Functions | 3 Next.js API Route Handlers | Extract to Lambda when scaling requires independent compute |
| S3 (static frontend) | Vercel static hosting (automatic) | Deploy to S3 + CloudFront when leaving Vercel |
| S3 (uploaded docs) | Vercel Blob (temp storage) | Migrate to S3 with lifecycle policies for production |
| S3 (generated reports) | In-memory PDF generation, served directly | Migrate to S3 for persistent report storage |
| DynamoDB | None (session state) → Supabase when needed | Migrate to DynamoDB or keep Postgres via Supabase |
| SQS | Synchronous API with streaming | Add SQS when analysis pipeline exceeds 2 minutes |
| SNS | None (no notifications in MVP) | Add SNS when email reports or alerts are built |

**Post-Hackathon Migration Plan:** If the $30K funding is secured, the migration from Vercel to the full AWS stack is straightforward because the logical separation already exists. The three API routes become three or four Lambda functions. Vercel Blob becomes S3. Session state moves to DynamoDB. The frontend deploys to S3 + CloudFront. SQS is added when the analysis pipeline grows beyond synchronous tolerance. This migration can be executed in one to two weeks without rewriting business logic.

**For the pitch deck:** Include the AWS architecture diagram as the "Production Architecture" slide. It demonstrates that you have thought beyond the demo and have a clear scaling path. Judges want to see that the team can think at both the prototype and production levels.

---

### 7.4 API Route Specifications

#### POST /api/parse-documents

**Request:** `multipart/form-data`
- `files`: Array of uploaded files (PDF, PNG, JPG, CSV)
- `fileTypes`: Array of document type labels (e.g., ["income_statement", "balance_sheet", "loan_terms"])

**Processing:**
1. For each file, determine format (PDF/image → use Claude vision; CSV → use Papaparse).
2. Send to Claude API with a structured extraction prompt (see Section 9 — Prompt Templates).
3. Parse Claude's response into the standardized financial data schema.
4. Return structured data for user review.

**Response:** `200 OK`
```json
{
  "success": true,
  "extractedData": {
    "incomeStatement": {
      "revenue": 850000,
      "cogs": 340000,
      "grossProfit": 510000,
      "operatingExpenses": 280000,
      "netIncome": 230000,
      "periods": ["2023", "2024"],
      "revenueByYear": { "2023": 800000, "2024": 850000 },
      "confidence": 0.92
    },
    "balanceSheet": {
      "currentAssets": 120000,
      "currentLiabilities": 85000,
      "totalAssets": 450000,
      "totalLiabilities": 200000,
      "equity": 250000,
      "confidence": 0.88
    },
    "loanTerms": {
      "loanAmount": 600000,
      "interestRate": 0.085,
      "termMonths": 120,
      "monthlyPayment": 7432,
      "downPayment": 150000,
      "askingPrice": 750000,
      "confidence": 0.95
    },
    "cashFlow": null,
    "parsingNotes": [
      "Cash flow statement was not provided. Analysis will use income statement and balance sheet to estimate.",
      "Balance sheet appears to be from Q3 2024, not year-end. Values may not reflect full-year position."
    ]
  }
}
```

#### POST /api/analyze

**Request:** `application/json`
```json
{
  "financials": { /* confirmed/edited extractedData from parse step */ },
  "questionnaire": {
    "ownerDependence": {
      "ownerSalesPercentage": 70,
      "ownerInvolvement": "full-time",
      "ownerHoldsRelationships": true,
      "survives90DayAbsence": "unlikely"
    },
    "customerConcentration": {
      "topCustomerRevenuePercent": 35,
      "top5CustomersRevenuePercent": 72,
      "contractType": "mostly_handshake",
      "averageCustomerTenure": "1_to_3_years"
    },
    "revenueQuality": {
      "recurringRevenuePercent": 20,
      "projectBasedPercent": 80,
      "revenueTrend": "flat",
      "knownUpcomingLosses": false
    },
    "employeeRisk": {
      "totalEmployees": 8,
      "missionCriticalEmployees": 2,
      "hasSOPs": false,
      "hasManagementLayer": false
    },
    "supplierRisk": {
      "singleSupplierOver30Pct": false,
      "supplierAgreementsDocumented": true,
      "exclusiveVendorRelationships": false
    },
    "financialRisk": {
      "hasAddBacks": true,
      "addBacksExceed30Pct": false,
      "pendingLiabilities": false
    }
  },
  "dealInfo": {
    "askingPrice": 750000,
    "businessType": "home_services",
    "yearsInOperation": 12,
    "reasonForSale": "retirement"
  }
}
```

**Processing:**
1. Run deterministic financial calculations (DSCR, margins, scenarios, break-even).
2. Run risk scoring algorithm (weighted composite score from questionnaire + financial flags).
3. Send all computed data + raw inputs to Claude API for narrative report generation.
4. Assemble final report JSON.

**Response:** `200 OK`
```json
{
  "success": true,
  "report": {
    "executiveSummary": { "text": "...", "riskScore": 62, "transferabilityScore": 38, "verdict": "risky" },
    "financialSnapshot": { /* structured metrics */ },
    "debtServiceAnalysis": { /* DSCR, scenarios, affordability verdict */ },
    "riskAssessment": { /* 6 dimension scores + explanations */ },
    "transferabilityAnalysis": { /* score + narrative */ },
    "questionsForSeller": [ /* array of questions grouped by category */ ],
    "diligenceChecklist": [ /* array of checklist items with priority */ ],
    "upsideOpportunities": [ /* array of opportunity objects */ ],
    "finalRecommendation": { "action": "proceed_with_caution", "strengths": [], "risks": [], "nextSteps": [] }
  }
}
```

#### POST /api/generate-pdf

**Request:** `application/json` — the full report object.
**Response:** `application/pdf` — binary PDF file.

---

## 8. Data Models

### 8.1 FinancialData (TypeScript Interface)

```typescript
interface IncomeStatement {
  revenue: number;
  cogs: number;
  grossProfit: number;
  operatingExpenses: number;
  depreciationAmortization?: number;
  interestExpense?: number;
  netIncome: number;
  ownerSalary?: number;
  addBacks?: AddBack[];
  sde?: number; // Seller's Discretionary Earnings
  ebitda?: number;
  periods: string[]; // e.g., ["2022", "2023", "2024"]
  revenueByYear?: Record<string, number>;
  netIncomeByYear?: Record<string, number>;
}

interface AddBack {
  description: string;
  amount: number;
  category: 'owner_salary' | 'one_time_expense' | 'personal_expense' | 'non_cash' | 'other';
}

interface BalanceSheet {
  currentAssets: number;
  cashAndEquivalents?: number;
  accountsReceivable?: number;
  inventory?: number;
  currentLiabilities: number;
  accountsPayable?: number;
  totalAssets: number;
  totalLiabilities: number;
  equity: number;
}

interface LoanTerms {
  loanAmount: number;
  interestRate: number; // decimal (e.g., 0.085 for 8.5%)
  termMonths: number;
  monthlyPayment?: number; // calculated if not provided
  downPayment?: number;
  askingPrice: number;
  loanType?: 'sba_7a' | 'sba_504' | 'conventional' | 'seller_financing' | 'other';
  collateralRequired?: boolean;
}

interface CashFlowStatement {
  operatingCashFlow: number;
  investingCashFlow?: number;
  financingCashFlow?: number;
  netCashFlow: number;
  capitalExpenditures?: number;
  freeCashFlow?: number;
}

interface FinancialData {
  incomeStatement: IncomeStatement | null;
  balanceSheet: BalanceSheet | null;
  loanTerms: LoanTerms | null;
  cashFlow: CashFlowStatement | null;
  parsingNotes: string[];
  dataCompleteness: number; // 0–1 score
}
```

### 8.2 QuestionnaireData (TypeScript Interface)

```typescript
interface QuestionnaireData {
  ownerDependence: {
    ownerSalesPercentage: number | null; // 0–100
    ownerInvolvement: 'full_time' | 'part_time' | 'minimal' | 'unknown';
    ownerHoldsRelationships: boolean | null;
    survives90DayAbsence: 'yes' | 'likely' | 'unlikely' | 'no' | 'unknown';
  };
  customerConcentration: {
    topCustomerRevenuePercent: number | null;
    top5CustomersRevenuePercent: number | null;
    contractType: 'mostly_contracted' | 'mixed' | 'mostly_handshake' | 'unknown';
    averageCustomerTenure: 'less_than_1_year' | '1_to_3_years' | '3_plus_years' | 'unknown';
  };
  revenueQuality: {
    recurringRevenuePercent: number | null;
    projectBasedPercent: number | null;
    revenueTrend: 'growing' | 'flat' | 'declining' | 'unknown';
    knownUpcomingLosses: boolean | null;
  };
  employeeRisk: {
    totalEmployees: number | null;
    missionCriticalEmployees: number | null;
    hasSOPs: boolean | null;
    hasManagementLayer: boolean | null;
  };
  supplierRisk: {
    singleSupplierOver30Pct: boolean | null;
    supplierAgreementsDocumented: boolean | null;
    exclusiveVendorRelationships: boolean | null;
  };
  financialRisk: {
    hasAddBacks: boolean | null;
    addBacksExceed30Pct: boolean | null;
    pendingLiabilities: boolean | null;
  };
}

interface DealInfo {
  askingPrice: number;
  businessType: string;
  yearsInOperation: number | null;
  reasonForSale: string | null;
  location?: string;
  industry?: string;
}
```

### 8.3 ReportOutput (TypeScript Interface)

```typescript
interface RiskDimensionScore {
  dimension: string;
  score: number; // 1–10
  label: 'Low' | 'Moderate' | 'High' | 'Critical';
  explanation: string;
  keyFactors: string[];
  isDealBreaker: boolean;
}

interface ScenarioAnalysis {
  label: string;
  annualRevenue: number;
  annualDebtService: number;
  remainingCashFlow: number;
  dscr: number;
  payoffMonths: number;
  annualOwnerIncome: number;
}

interface ReportOutput {
  executiveSummary: {
    text: string;
    riskScore: number; // 1–100
    riskLabel: 'Low' | 'Moderate' | 'High' | 'Very High';
    transferabilityScore: number; // 1–100
    transferabilityLabel: 'High' | 'Moderate' | 'Low' | 'Very Low';
    verdict: string;
  };
  financialSnapshot: {
    metrics: Record<string, { value: number; formatted: string; note?: string }>;
    valuationMultiple: number;
    multipleAssessment: string;
  };
  debtServiceAnalysis: {
    loanSummary: Record<string, string>;
    monthlyDebtService: number;
    annualDebtService: number;
    dscr: number;
    dscrAssessment: string;
    minimumRevenueRequired: number;
    breakEvenMonthlyRevenue: number;
    scenarios: ScenarioAnalysis[];
    affordabilityVerdict: string;
  };
  riskAssessment: {
    overallScore: number;
    dimensions: RiskDimensionScore[];
    dealBreakers: string[];
  };
  transferabilityAnalysis: {
    score: number;
    explanation: string;
    keyFactors: { factor: string; impact: 'positive' | 'negative' | 'neutral'; detail: string }[];
    improvementSuggestions: string[];
  };
  questionsForSeller: {
    category: string;
    questions: string[];
  }[];
  diligenceChecklist: {
    item: string;
    category: string;
    priority: 'critical' | 'important' | 'nice_to_have';
    reason: string;
  }[];
  upsideOpportunities: {
    opportunity: string;
    estimatedImpact: string;
    difficulty: 'easy' | 'moderate' | 'hard';
    detail: string;
  }[];
  finalRecommendation: {
    action: 'proceed' | 'proceed_with_caution' | 'walk_away';
    strengths: string[];
    risks: string[];
    nextSteps: string[];
    summaryStatement: string;
  };
  metadata: {
    generatedAt: string;
    analysisVersion: string;
    dataCompleteness: number;
    disclaimers: string[];
  };
}
```

---

## 9. Prompt Engineering Templates

### 9.1 Document Extraction Prompt

```
You are a financial document parser for a business acquisition analysis tool.

You will be given a financial document (income statement, balance sheet, cash flow statement, or loan term sheet). Your job is to extract all relevant financial data into a structured JSON format.

RULES:
1. Extract exact dollar amounts. Do not round.
2. If a value is not present in the document, set it to null. Do NOT infer or estimate missing values.
3. Identify the time period(s) covered by the document.
4. If the document contains multiple years of data, extract all years.
5. Note any items that appear unusual or require clarification in the "parsingNotes" array.
6. Return ONLY valid JSON. No markdown, no explanation text.

DOCUMENT TYPE: {{documentType}}

Return JSON in this exact schema:
{{schemaForDocumentType}}

IMPORTANT: If you cannot confidently extract a value, set it to null and add a note in parsingNotes explaining what was unclear. Accuracy is more important than completeness.
```

### 9.2 Risk Scoring & Analysis Prompt

```
You are a business acquisition risk analyst. You are helping a non-expert buyer evaluate whether a small business is worth acquiring.

You will receive:
1. Structured financial data (already extracted and confirmed by the buyer).
2. Pre-computed financial metrics (DSCR, margins, scenarios — these are calculated deterministically, DO NOT recalculate them).
3. Questionnaire answers about the business's operational characteristics.
4. Deal information (asking price, business type, years in operation).

YOUR TASK:
Score each of the following risk dimensions on a 1–10 scale (1 = very low risk, 10 = critical risk). For each dimension, provide:
- A numeric score (1–10)
- A 2–3 sentence explanation written for a non-expert
- A list of 1–3 key risk factors identified
- Whether this dimension constitutes a potential deal breaker (true/false — only true if score >= 9)

RISK DIMENSIONS:
1. Owner Dependence (weight: 25%)
2. Customer Concentration (weight: 20%)
3. Revenue Quality (weight: 20%)
4. Employee & Operational Risk (weight: 15%)
5. Supplier Risk (weight: 10%)
6. Financial & Add-Back Risk (weight: 10%)

SCORING GUIDANCE:
- Owner Dependence: Score 8+ if owner generates >50% of sales AND holds key relationships AND business would not survive 90-day absence.
- Customer Concentration: Score 8+ if top customer is >30% of revenue OR top 5 are >70% AND relationships are handshake-based.
- Revenue Quality: Score 8+ if <20% recurring revenue AND revenue is declining AND there are known upcoming losses.
- Employee Risk: Score 8+ if >25% of employees are mission-critical AND no SOPs AND no management layer.
- Supplier Risk: Score 8+ if single supplier >30% of COGS AND agreements are not documented or transferable.
- Financial Risk: Score 8+ if add-backs exceed 30% of EBITDA AND there are pending liabilities.

Also calculate:
- Overall Acquisition Risk Score (1–100): Weighted average of dimension scores, scaled to 100.
- Transferability Score (1–100): Based on inverse of owner dependence, process maturity, customer contract quality, and team stability.

ALSO GENERATE:
- 8–15 targeted questions the buyer should ask the seller, grouped by risk category.
- A customized diligence checklist with priority levels (Critical, Important, Nice-to-Have).
- 3–5 upside opportunities (operational improvements, revenue additions, cost reductions).
- A final recommendation: Proceed, Proceed with Caution, or Walk Away.

Return your analysis as structured JSON matching this schema:
{{reportOutputSchema}}

IMPORTANT:
- Write all explanatory text for a non-expert audience. Avoid jargon. If you must use a financial term, define it in parentheses.
- Be specific. Reference actual numbers from the data. Do not use generic language.
- Be honest about uncertainty. If the data is incomplete, say so and explain how it affects the assessment.
- The buyer's financial future depends on this analysis. Be thorough and accurate.
```

### 9.3 Executive Summary Prompt (Optional — can be part of 9.2 or a separate call)

```
You are writing the executive summary for a business acquisition analysis report.

Given the following analysis results, write a 3–5 sentence executive summary that a non-expert buyer can read and immediately understand whether this deal is worth pursuing.

Risk Score: {{riskScore}}/100 ({{riskLabel}})
Transferability Score: {{transferabilityScore}}/100 ({{transferabilityLabel}})
DSCR: {{dscr}}
Key Deal Breakers: {{dealBreakers}}
Recommendation: {{recommendation}}

The summary should:
1. State the overall assessment clearly in the first sentence.
2. Highlight the 1–2 most important risk factors.
3. Note any significant strengths.
4. End with a clear, actionable statement.

Write in plain language. No bullet points. No jargon.
```

---

## 10. Calculation Engine (Deterministic — Not AI)

These calculations MUST be implemented in application code, not delegated to the LLM. This ensures accuracy and reproducibility.

```typescript
// calculations.ts

export function calculateMonthlyPayment(principal: number, annualRate: number, termMonths: number): number {
  const monthlyRate = annualRate / 12;
  if (monthlyRate === 0) return principal / termMonths;
  return principal * (monthlyRate * Math.pow(1 + monthlyRate, termMonths)) /
    (Math.pow(1 + monthlyRate, termMonths) - 1);
}

export function calculateDSCR(annualCashFlow: number, annualDebtService: number): number {
  if (annualDebtService === 0) return Infinity;
  return annualCashFlow / annualDebtService;
}

export function calculateWorkingCapital(currentAssets: number, currentLiabilities: number): number {
  return currentAssets - currentLiabilities;
}

export function calculateGrossMargin(revenue: number, cogs: number): number {
  if (revenue === 0) return 0;
  return ((revenue - cogs) / revenue) * 100;
}

export function calculateEBITDA(
  netIncome: number,
  interestExpense: number = 0,
  taxes: number = 0,
  depreciation: number = 0,
  amortization: number = 0
): number {
  return netIncome + interestExpense + taxes + depreciation + amortization;
}

export function calculateSDE(
  netIncome: number,
  ownerSalary: number = 0,
  addBacks: number = 0,
  depreciation: number = 0,
  interestExpense: number = 0
): number {
  return netIncome + ownerSalary + addBacks + depreciation + interestExpense;
}

export function calculateValuationMultiple(askingPrice: number, sde: number): number {
  if (sde === 0) return Infinity;
  return askingPrice / sde;
}

export function calculateMinimumRevenue(
  annualDebtService: number,
  operatingExpenses: number,
  desiredOwnerIncome: number = 0
): number {
  return annualDebtService + operatingExpenses + desiredOwnerIncome;
}

export function calculateBreakEvenMonthlyRevenue(
  monthlyDebtService: number,
  monthlyOperatingExpenses: number
): number {
  return monthlyDebtService + monthlyOperatingExpenses;
}

export function generateScenarios(
  baseRevenue: number,
  annualDebtService: number,
  operatingExpenses: number,
  termMonths: number
): ScenarioAnalysis[] {
  const growthRates = [
    { label: 'Current Performance (0% growth)', rate: 0 },
    { label: 'Moderate Growth (+10%)', rate: 0.10 },
    { label: 'Decline (-10%)', rate: -0.10 },
    { label: 'Strong Growth (+20%)', rate: 0.20 },
  ];

  return growthRates.map(({ label, rate }) => {
    const projectedRevenue = baseRevenue * (1 + rate);
    const remainingCashFlow = projectedRevenue - operatingExpenses - annualDebtService;
    const dscr = calculateDSCR(projectedRevenue - operatingExpenses, annualDebtService);
    return {
      label,
      annualRevenue: Math.round(projectedRevenue),
      annualDebtService: Math.round(annualDebtService),
      remainingCashFlow: Math.round(remainingCashFlow),
      dscr: Math.round(dscr * 100) / 100,
      payoffMonths: termMonths, // simplified for MVP
      annualOwnerIncome: Math.round(Math.max(0, remainingCashFlow)),
    };
  });
}
```

---

## 11. Page-by-Page UI Specification

### Page 1: Landing / Home (`/`)
- Hero section with headline: "Know Before You Buy" or "See the Real Risk Before You Sign"
- Subheadline: "Upload your financials. Answer a few questions. Get a plain-language acquisition report in minutes."
- Single primary CTA button: "Analyze a Business" → navigates to `/analyze`
- 3 value prop cards below the fold:
  1. "Affordability Analysis" — Can you actually service the debt?
  2. "Risk Scoring" — What's hiding in the numbers?
  3. "Transferability Check" — Will the business survive without the owner?
- Social proof section (for hackathon: can be placeholder or "Built for the ___ Hackathon")

### Page 2: Upload & Parse (`/analyze/upload`)
- Step indicator showing: Upload → Review → Questions → Report (step 1 active)
- File drop zone (drag-and-drop + click to browse)
- Supported format badges: PDF, PNG, JPG, CSV
- Document type selector for each uploaded file (dropdown: Income Statement, Balance Sheet, Cash Flow Statement, Loan Term Sheet)
- Upload button triggers `/api/parse-documents`
- Loading state with animated progress and message: "Reading your financials..."
- "Skip — I'll enter data manually" link at bottom

### Page 3: Review Extracted Data (`/analyze/review`)
- Step indicator (step 2 active)
- Tabbed or accordion layout with one section per document type
- Each section shows extracted values in editable form fields
- Confidence indicator per section (e.g., "92% confident in extraction — please verify")
- Parsing notes displayed as informational alerts
- "Add Missing Data" section for any values not extracted
- "Continue to Risk Assessment" button (disabled until at least income statement data is present)

### Page 4: Risk Questionnaire (`/analyze/questions`)
- Step indicator (step 3 active)
- Multi-step wizard (one risk dimension per step, 6 steps total)
- Section header with dimension name and brief explanation of why it matters
- Questions rendered with appropriate input types:
  - Sliders for percentages (0–100)
  - Radio buttons for categorical choices
  - Toggle switches for yes/no
  - "I don't know" option on every question
- Progress bar within the questionnaire
- Back/Next navigation
- "Generate Report" button on the final step

### Page 5: Report View (`/analyze/report`)
- Step indicator (step 4 active — complete)
- Sticky top bar with:
  - Overall Risk Score badge (color-coded)
  - Transferability Score badge (color-coded)
  - Verdict badge (Proceed / Caution / Walk Away)
  - "Download PDF" button
  - "Start New Analysis" button
- Scrollable report body with all 9 sections from Section 6
- Section navigation sidebar (desktop) or jump links (mobile)
- Risk dimension scores displayed as horizontal bar charts or gauges
- Scenario analysis displayed as a comparison table
- Questions for Seller section with copy-to-clipboard per question
- Diligence Checklist rendered as interactive checkboxes (for user tracking, client-side only)
- Upside Opportunities as cards with difficulty and impact indicators

---

## 12. File & Folder Structure

```
bizbuy/
├── app/
│   ├── layout.tsx                    # Root layout with global styles
│   ├── page.tsx                      # Landing page
│   ├── analyze/
│   │   ├── layout.tsx                # Shared layout for analyze flow (step indicator)
│   │   ├── upload/
│   │   │   └── page.tsx              # File upload page
│   │   ├── review/
│   │   │   └── page.tsx              # Data review and confirmation
│   │   ├── questions/
│   │   │   └── page.tsx              # Risk questionnaire wizard
│   │   └── report/
│   │       └── page.tsx              # Report display page
│   └── api/
│       ├── parse-documents/
│       │   └── route.ts              # Document parsing endpoint
│       ├── analyze/
│       │   └── route.ts              # Analysis + report generation endpoint
│       └── generate-pdf/
│           └── route.ts              # PDF generation endpoint
├── components/
│   ├── ui/                           # shadcn/ui components
│   ├── layout/
│   │   ├── Header.tsx
│   │   ├── Footer.tsx
│   │   └── StepIndicator.tsx
│   ├── upload/
│   │   ├── FileDropZone.tsx
│   │   ├── FileCard.tsx
│   │   └── DocumentTypeSelector.tsx
│   ├── review/
│   │   ├── FinancialDataForm.tsx
│   │   ├── IncomeStatementFields.tsx
│   │   ├── BalanceSheetFields.tsx
│   │   ├── LoanTermsFields.tsx
│   │   └── ConfidenceIndicator.tsx
│   ├── questionnaire/
│   │   ├── QuestionnaireWizard.tsx
│   │   ├── QuestionSection.tsx
│   │   ├── SliderQuestion.tsx
│   │   ├── RadioQuestion.tsx
│   │   └── ToggleQuestion.tsx
│   └── report/
│       ├── ReportHeader.tsx
│       ├── ExecutiveSummary.tsx
│       ├── FinancialSnapshot.tsx
│       ├── DebtServiceAnalysis.tsx
│       ├── RiskAssessment.tsx
│       ├── RiskDimensionCard.tsx
│       ├── TransferabilityAnalysis.tsx
│       ├── SellerQuestions.tsx
│       ├── DiligenceChecklist.tsx
│       ├── UpsideOpportunities.tsx
│       ├── FinalRecommendation.tsx
│       ├── ScenarioTable.tsx
│       └── ScoreBadge.tsx
├── lib/
│   ├── calculations.ts               # Deterministic financial calculations
│   ├── risk-scoring.ts               # Risk score computation logic
│   ├── prompts.ts                     # AI prompt templates
│   ├── schemas.ts                     # Zod validation schemas
│   ├── types.ts                       # TypeScript interfaces
│   ├── api-client.ts                  # Frontend API call helpers
│   ├── format.ts                      # Number/currency formatting utilities
│   └── constants.ts                   # Risk weights, thresholds, labels
├── context/
│   └── AnalysisContext.tsx             # Global state for the analysis flow
├── public/
│   ├── logo.svg
│   └── og-image.png
├── .env.local                          # ANTHROPIC_API_KEY
├── package.json
├── tailwind.config.ts
├── tsconfig.json
└── next.config.js
```

---

## 13. MVP Improvement Suggestions for Hackathon Judges

These are enhancements that would strengthen the demo and differentiate BizBuy in a competitive hackathon setting:

### 13.1 Demo Mode with Pre-Loaded Data
Build a "Try Demo" button on the landing page that pre-loads a realistic but fictional business (e.g., "Sunny's HVAC Services — $850K revenue, SBA loan, owner-dependent") and walks judges through the full flow without needing to upload real documents. This is critical for a live demo where upload latency and parsing uncertainty could derail the presentation.

### 13.2 Real-Time Streaming Report Generation
Use Claude's streaming API to progressively render the report as it generates. Judges see the executive summary appear first, then risk scores populate, then the detailed analysis fills in. This creates a "wow" moment and demonstrates the AI working in real time rather than showing a loading spinner for 30 seconds.

### 13.3 Interactive Risk Radar Chart
Add a radar/spider chart visualization for the 6 risk dimensions. This gives an instant visual snapshot of where the business is strong and weak. Use a charting library like Recharts (already available in the React artifact environment). This is visually compelling for a pitch.

### 13.4 "What-If" Scenario Slider
After the report generates, add an interactive section where the user can adjust assumptions (revenue growth rate, operating cost reduction, additional down payment) and see the debt service analysis and payoff timeline update in real time. This demonstrates the tool's ongoing utility beyond a one-time report.

### 13.5 Industry Benchmarking
Add a lightweight industry benchmark layer. When the user selects a business type (e.g., HVAC, restaurant, e-commerce), show how the business's margins, multiples, and risk factors compare to industry averages. Even if the benchmarks are simplified or drawn from publicly available SBA data, this adds credibility and context to the analysis.

### 13.6 Conversation Follow-Up (Claude-in-Claude)
After the report is generated, embed a chat interface where the buyer can ask follow-up questions about the analysis. This uses the Claude API with the full report context. For example: "What if I negotiate the price down to $600K?" or "Explain the owner dependence risk in more detail." This dramatically increases perceived product depth.

### 13.7 Risk Comparison to "Ideal Acquirable Business"
Show a side-by-side comparison of the analyzed business against an "Ideal Acquisition Profile" — a benchmark business with low owner dependence, diversified customers, high recurring revenue, documented processes, etc. This makes the risk scores more tangible ("your business scores 7/10 on owner dependence; an ideal acquisition would score 2/10").

### 13.8 Email-Ready Summary
Add a "Share with Advisor" button that generates a concise email-ready summary (3–5 key findings, risk score, recommendation) that the buyer can forward to their accountant, lawyer, or business advisor. This shows product thinking beyond the individual user.

### 13.9 Polish the Numbers
For the hackathon demo, ensure all currency values are formatted with commas and dollar signs, percentages have one decimal place, and ratios are displayed with meaningful context (e.g., "DSCR: 1.42 — A healthy DSCR is above 1.25. Your coverage ratio indicates the business generates enough cash to service its debt with a 17% cushion.").

### 13.10 Legal Disclaimer
Include a clear disclaimer at the bottom of every report: "This analysis is generated by AI and is intended for informational purposes only. It does not constitute financial, legal, or investment advice. Consult qualified professionals before making any acquisition decision." This shows maturity and responsibility, which judges will notice.

---

## 14. Risk & Assumptions

### Assumptions
1. Claude API can reliably extract structured financial data from typical small business financial documents (P&L, balance sheet, loan term sheets).
2. The user has access to at least an income statement and loan terms. The tool degrades gracefully with fewer inputs.
3. Financial documents are in English and use USD.
4. The MVP does not need user authentication, saved sessions, or multi-user support.

### Known Risks
1. **Document Parsing Accuracy:** Financial documents are inconsistent in format. Mitigation: Always present extracted data for user confirmation before analysis. Include manual entry fallback.
2. **LLM Math Errors:** LLMs can make arithmetic mistakes. Mitigation: All financial calculations are deterministic (coded in TypeScript), not delegated to the LLM. The LLM only generates narrative.
3. **Hallucinated Analysis:** The LLM might generate plausible-sounding but incorrect risk assessments. Mitigation: Risk scoring uses a structured algorithm with defined weights and thresholds. The LLM generates explanatory text around the computed scores, not the scores themselves.
4. **API Latency:** Full analysis requires multiple Claude API calls, which could add up to 30–60 seconds. Mitigation: Use streaming where possible. Show progressive loading states. Consider parallelizing the extraction calls.
5. **Scope Creep:** The feature set is ambitious for a hackathon. Mitigation: Prioritize the core flow (upload → parse → questions → report) and cut stretch goals aggressively if needed.

---

## 15. MVP Build Priority Order

If time is limited, build features in this exact order:

1. **Landing page** — Simple, professional, with "Analyze a Business" CTA.
2. **Manual data entry forms** — Skip document parsing initially. Let users type in financial data and answer the questionnaire.
3. **Deterministic calculation engine** — DSCR, margins, scenarios, break-even. This is the foundation.
4. **Risk scoring algorithm** — Weighted scoring from questionnaire answers. No AI needed for the scores themselves.
5. **AI report generation** — Single Claude API call that takes all computed data and generates the narrative report.
6. **Report display page** — Clean, scrollable, section-navigated report view.
7. **Document upload and AI parsing** — Add the upload flow and Claude-powered document extraction.
8. **PDF download** — Generate a downloadable PDF of the report.
9. **Demo mode** — Pre-loaded data for hackathon presentation.
10. **Streaming, charts, and polish** — Visual enhancements and real-time generation effects.

---

## 16. Success Criteria

For the hackathon demo, the product must:
1. Accept financial data (manually or via document upload) and produce a complete analysis report.
2. Generate accurate financial calculations (DSCR, margins, scenarios) that would hold up to scrutiny from a financial professional in the audience.
3. Produce a risk assessment that is specific to the input data (not generic boilerplate).
4. Display the report in a polished, professional UI that communicates credibility.
5. Complete the full analysis flow in under 2 minutes during a live demo.
6. Include at least one "wow" moment (streaming report, interactive chart, or follow-up chat).

---

*End of PRD — BizBuy v1.0 MVP*
