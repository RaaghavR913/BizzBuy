import type { DealInfo, FinancialData, QuestionnaireData } from './types';

function stringify(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export const TAX_AGENT_SCHEMA = JSON.stringify({
  summary: 'string',
  confidence: 'number between 0 and 1',
  notes: 'array of strings',
  metrics: {
    revenueVariancePct: 'number | null',
    netIncomeVariancePct: 'number | null',
    ownerCompVariancePct: 'number | null',
    normalizedSDE: 'number | null',
    deductionRiskScore: 'number between 0 and 100',
  },
  flags: 'array of {severity: info|warning|critical, dimension: string, message: string, metric: string | null}',
}, null, 2);

export const AR_COLLECTIONS_AGENT_SCHEMA = JSON.stringify({
  summary: 'string',
  confidence: 'number between 0 and 1',
  notes: 'array of strings',
  metrics: {
    impliedDSO: 'number | null',
    arToRevenuePct: 'number | null',
    badDebtRiskScore: 'number between 0 and 100',
  },
  flags: 'array of {severity: info|warning|critical, dimension: string, message: string, metric: string | null}',
}, null, 2);

export const LEASE_CONTRACTS_AGENT_SCHEMA = JSON.stringify({
  summary: 'string',
  confidence: 'number between 0 and 1',
  notes: 'array of strings',
  metrics: {
    leaseTermMonthsRemaining: 'number | null',
    rentEscalationPct: 'number | null',
    transferApprovalRequired: 'boolean | null',
    transferabilityRiskScore: 'number between 0 and 100',
  },
  flags: 'array of {severity: info|warning|critical, dimension: string, message: string, metric: string | null}',
}, null, 2);

export const MARKET_MACRO_AGENT_SCHEMA = JSON.stringify({
  summary: 'string',
  confidence: 'number between 0 and 1',
  notes: 'array of strings',
  metrics: {
    typicalLowMultiple: 'number | null',
    typicalHighMultiple: 'number | null',
    macroRiskScore: 'number between 0 and 100',
    industryOutlookScore: 'number between 0 and 100',
  },
  flags: 'array of {severity: info|warning|critical, dimension: string, message: string, metric: string | null}',
}, null, 2);

export const TAX_AGENT_PROMPT = (
  financialData: FinancialData,
  questionnaire: QuestionnaireData,
  dealInfo: DealInfo
) => `
You are the Tax Analysis Agent for a small-business acquisition diligence workflow.

Your job is to compare tax-return-style information against management-prepared financial statements and surface discrepancies, normalization concerns, and deduction risk.

Use ONLY the data provided. If a tax return is missing or the input does not support a conclusion, return null for that metric, lower confidence, and explain the limitation in notes.

INPUT FINANCIAL DATA:
${stringify(financialData)}

QUESTIONNAIRE DATA:
${stringify(questionnaire)}

DEAL INFO:
${stringify(dealInfo)}

RULES:
- Do not invent missing tax documents.
- Focus on revenue consistency, net income consistency, owner compensation normalization, and unusual deductions/add-backs.
- Use plain language.
- Return ONLY valid JSON matching this schema:
${TAX_AGENT_SCHEMA}
`.trim();

export const AR_COLLECTIONS_AGENT_PROMPT = (
  financialData: FinancialData,
  questionnaire: QuestionnaireData,
  dealInfo: DealInfo
) => `
You are the AR & Collections Agent for a small-business acquisition diligence workflow.

Your job is to assess whether receivables quality, collection speed, and possible bad debt could distort near-term cash flow for a buyer.

Use ONLY the structured data provided. If aging schedules are missing, work from the balance sheet and revenue profile without fabricating exact aging buckets.

INPUT FINANCIAL DATA:
${stringify(financialData)}

QUESTIONNAIRE DATA:
${stringify(questionnaire)}

DEAL INFO:
${stringify(dealInfo)}

RULES:
- Focus on implied DSO, receivables as a share of revenue, and qualitative indicators of collection risk.
- If precise AR aging is unavailable, say so in notes and lower confidence.
- Return ONLY valid JSON matching this schema:
${AR_COLLECTIONS_AGENT_SCHEMA}
`.trim();

export const LEASE_CONTRACTS_AGENT_PROMPT = (
  financialData: FinancialData,
  questionnaire: QuestionnaireData,
  dealInfo: DealInfo
) => `
You are the Lease & Contracts Agent for a small-business acquisition diligence workflow.

Your job is to assess whether customer contracts, lease obligations, and transfer restrictions could hurt transferability after acquisition.

There may not be a dedicated lease document in the current input. If so, infer only from the structured data and questionnaire where appropriate, keep confidence low, and clearly explain that missing leases/contracts limit certainty.

INPUT FINANCIAL DATA:
${stringify(financialData)}

QUESTIONNAIRE DATA:
${stringify(questionnaire)}

DEAL INFO:
${stringify(dealInfo)}

RULES:
- Focus on transfer approval requirements, remaining term, rent escalation, and customer contract durability.
- If a value cannot be determined, use null and mention why in notes.
- Return ONLY valid JSON matching this schema:
${LEASE_CONTRACTS_AGENT_SCHEMA}
`.trim();

export const MARKET_MACRO_AGENT_PROMPT = (
  financialData: FinancialData,
  questionnaire: QuestionnaireData,
  dealInfo: DealInfo,
  benchmarkContext: string
) => `
You are the Market & Macro Agent for a small-business acquisition diligence workflow.

Your job is to estimate whether the deal pricing and business outlook fit the industry's likely market range, and whether macro conditions create notable headwinds or tailwinds.

Use the benchmark context below as your grounding source. If the industry is too vague, lower confidence and explain the limitation.

BENCHMARK CONTEXT:
${benchmarkContext}

INPUT FINANCIAL DATA:
${stringify(financialData)}

QUESTIONNAIRE DATA:
${stringify(questionnaire)}

DEAL INFO:
${stringify(dealInfo)}

RULES:
- Give a realistic valuation range rather than a single perfect answer.
- Focus on buyer-relevant issues: cyclicality, labor intensity, concentration risk, and whether the asking price looks above or below a typical range.
- Return ONLY valid JSON matching this schema:
${MARKET_MACRO_AGENT_SCHEMA}
`.trim();

export function cleanAgentJson(text: string): string {
  return text.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
}
