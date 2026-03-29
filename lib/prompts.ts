export const DOCUMENT_EXTRACTION_PROMPT = (documentType: string, schema: string) => `
You are a financial document parser for a business acquisition analysis tool.

You will be given a financial document. Your job is to extract all relevant financial data into a structured JSON format.

RULES:
1. Extract exact dollar amounts. Do not round.
2. If a value is not present in the document, set it to null. Do NOT infer or estimate missing values.
3. Identify the time period(s) covered by the document.
4. If the document contains multiple years of data, extract all years.
5. Note any items that appear unusual or require clarification in the "parsingNotes" array.
6. Return ONLY valid JSON. No markdown, no explanation text, no code fences.

DOCUMENT TYPE: ${documentType}

Return JSON in this exact schema:
${schema}

IMPORTANT: If you cannot confidently extract a value, set it to null and add a note in parsingNotes explaining what was unclear. Accuracy is more important than completeness.
`.trim();

export const INCOME_STATEMENT_SCHEMA = JSON.stringify({
  revenue: 'number | null',
  cogs: 'number | null',
  grossProfit: 'number | null',
  operatingExpenses: 'number | null',
  depreciationAmortization: 'number | null',
  interestExpense: 'number | null',
  netIncome: 'number | null',
  ownerSalary: 'number | null',
  addBacks: 'array of {description: string, amount: number, category: string} | null',
  sde: 'number | null',
  ebitda: 'number | null',
  periods: 'array of year strings e.g. ["2022","2023","2024"]',
  revenueByYear: 'object like {"2022": 800000, "2023": 850000} | null',
  netIncomeByYear: 'object like {"2022": 180000, "2023": 230000} | null',
  confidence: 'number between 0 and 1',
  parsingNotes: 'array of strings',
}, null, 2);

export const BALANCE_SHEET_SCHEMA = JSON.stringify({
  currentAssets: 'number | null',
  cashAndEquivalents: 'number | null',
  accountsReceivable: 'number | null',
  inventory: 'number | null',
  currentLiabilities: 'number | null',
  accountsPayable: 'number | null',
  totalAssets: 'number | null',
  totalLiabilities: 'number | null',
  equity: 'number | null',
  confidence: 'number between 0 and 1',
  parsingNotes: 'array of strings',
}, null, 2);

export const LOAN_TERMS_SCHEMA = JSON.stringify({
  loanAmount: 'number | null',
  interestRate: 'decimal e.g. 0.085 for 8.5% | null',
  termMonths: 'number | null',
  monthlyPayment: 'number | null',
  downPayment: 'number | null',
  askingPrice: 'number | null',
  loanType: 'sba_7a | sba_504 | conventional | seller_financing | other | null',
  confidence: 'number between 0 and 1',
  parsingNotes: 'array of strings',
}, null, 2);

export const CASH_FLOW_SCHEMA = JSON.stringify({
  operatingCashFlow: 'number | null',
  investingCashFlow: 'number | null',
  financingCashFlow: 'number | null',
  netCashFlow: 'number | null',
  capitalExpenditures: 'number | null',
  freeCashFlow: 'number | null',
  confidence: 'number between 0 and 1',
  parsingNotes: 'array of strings',
}, null, 2);

export const RISK_ANALYSIS_PROMPT = (
  financials: string,
  computedMetrics: string,
  questionnaire: string,
  dealInfo: string,
  reportSchema: string
) => `
You are a business acquisition risk analyst. You are helping a non-expert buyer evaluate whether a small business is worth acquiring.

You will receive:
1. Structured financial data (already extracted and confirmed by the buyer).
2. Pre-computed financial metrics (DSCR, margins, scenarios — these are calculated deterministically, DO NOT recalculate them).
3. Questionnaire answers about the business's operational characteristics.
4. Deal information (asking price, business type, years in operation).
5. Specialized agent findings and red flags from tax, AR/collections, customer, operations, lease/contracts, and market analysis.

FINANCIAL DATA:
${financials}

PRE-COMPUTED METRICS (do not recalculate):
${computedMetrics}

QUESTIONNAIRE ANSWERS:
${questionnaire}

DEAL INFO:
${dealInfo}

YOUR TASK:
For each risk dimension, provide:
- A numeric score (1–10, where 1 = very low risk, 10 = critical risk) — USE THE PRE-COMPUTED SCORES PROVIDED IN computedMetrics, do not invent your own
- A 2–3 sentence explanation written for a non-expert buyer (plain language, no jargon)
- A list of 1–3 specific key risk factors from the actual data
- Whether this dimension is a potential deal breaker (only true if score >= 9)

ALSO GENERATE:
- A 3–5 sentence executive summary a non-expert buyer can immediately understand
- 8–15 targeted questions the buyer should ask the seller, grouped by risk category
- A customized diligence checklist with priority levels (critical, important, nice_to_have) — 10–20 items
- 3–5 upside opportunities (operational improvements, revenue additions, cost reductions) with estimated impact and difficulty
- A final recommendation: proceed, proceed_with_caution, or walk_away
- Top 3 strengths and top 3 risks
- 3–5 suggested next steps

Return ONLY valid JSON matching this schema:
${reportSchema}

IMPORTANT:
- Write all text for a non-expert audience. Avoid jargon. If you use a financial term, define it briefly.
- Be specific. Reference actual numbers from the data. Do not use generic language.
- Use the specialized agent findings when drafting risks, seller questions, and diligence items.
- Be honest about uncertainty. If the data is incomplete, say so.
- The buyer's financial future depends on this analysis. Be thorough and accurate.
`.trim();

export const REPORT_NARRATIVE_SCHEMA = JSON.stringify({
  executiveSummaryText: 'string (3-5 sentences)',
  verdict: 'string (one sentence)',
  riskDimensionExplanations: {
    ownerDependence: 'string',
    customerConcentration: 'string',
    revenueQuality: 'string',
    employeeRisk: 'string',
    supplierRisk: 'string',
    financialRisk: 'string',
  },
  transferabilityExplanation: 'string',
  transferabilityKeyFactors: 'array of {factor: string, impact: positive|negative|neutral, detail: string}',
  transferabilityImprovements: 'array of strings',
  questionsForSeller: 'array of {category: string, questions: array of strings}',
  diligenceChecklist: 'array of {item: string, category: string, priority: critical|important|nice_to_have, reason: string}',
  upsideOpportunities: 'array of {opportunity: string, estimatedImpact: string, difficulty: easy|moderate|hard, detail: string}',
  recommendation: 'proceed | proceed_with_caution | walk_away',
  strengths: 'array of 3 strings',
  risks: 'array of 3 strings',
  nextSteps: 'array of 3-5 strings',
  summaryStatement: 'string (one compelling sentence)',
  dscrAssessment: 'string plain language explanation of DSCR',
  affordabilityVerdict: 'string plain language affordability summary',
  multipleAssessment: 'string plain language valuation multiple assessment',
}, null, 2);
