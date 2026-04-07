import type { AgentResult } from '@/src/types/pipeline';
import type { IngestionOutput, DocumentSection } from '@/src/agents/schemas/ingestion.schema';
import type { ARCollectionsOutput } from '@/src/agents/schemas/ar-collections.schema';
import { ARCollectionsOutputSchema } from '@/src/agents/schemas/ar-collections.schema';
import { loadAgentPrompt } from '@/src/agents/utils/prompt-loader';
import { callAgent } from '@/src/agents/utils/claude-client';
import { AGENT_REGISTRY } from '@/src/agents/registry';

// ---------------------------------------------------------------------------
// Types for pre-computed metrics
// ---------------------------------------------------------------------------

export interface AgingBucketMetrics {
  current: number;
  thirtyDay: number;
  sixtyDay: number;
  ninetyDay: number;
  over90: number;
}

export interface AgingBucketPercentages {
  current: number;
  thirtyDay: number;
  sixtyDay: number;
  ninetyDay: number;
  over90: number;
}

export interface CustomerConcentration {
  customerId: string;
  customerName: string | null;
  amount: number;
  percentage: number;
}

export interface ComputedARMetrics {
  totalAR: number;
  agingBuckets: AgingBucketMetrics;
  agingPercentages: AgingBucketPercentages;
  /** Days Sales Outstanding — null if annual revenue unavailable */
  dso: number | null;
  annualRevenueUsedForDso: number | null;
  customerConcentrations: CustomerConcentration[];
  topCustomerPercent: number;
  top5CustomersPercent: number;
  /** Estimated uncollectible amount — 90-day bucket × 50% + over90 × 90% */
  estimatedWriteOffAmount: number;
  estimatedWriteOffPercent: number;
  hasARData: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function safeNum(val: unknown): number | null {
  if (val === null || val === undefined || val === '') return null;
  const n = Number(val);
  return isFinite(n) ? n : null;
}

/**
 * Extracts the most recent annual revenue from P&L sections, used to compute DSO.
 */
function extractAnnualRevenue(sections: DocumentSection[]): number | null {
  const plSections = sections
    .filter((s) => s.documentType === 'profit_and_loss')
    .sort((a, b) => (b.timeframe.fiscalYear ?? 0) - (a.timeframe.fiscalYear ?? 0));

  for (const section of plSections) {
    const data = section.extractedData;
    const revenue = safeNum(
      data['revenue'] ??
      data['gross_revenue'] ??
      data['net_revenue'] ??
      data['total_revenue']
    );
    if (revenue !== null) return revenue;
  }

  return null;
}

/**
 * Extracts per-customer AR balances from AR aging extractedData.
 * Expects either a 'customers' array or individual customer_* keys.
 */
function extractCustomerConcentrations(
  data: Record<string, unknown>,
  totalAR: number
): CustomerConcentration[] {
  const customers = data['customers'];
  if (!Array.isArray(customers)) return [];

  return customers
    .filter((c): c is Record<string, unknown> => typeof c === 'object' && c !== null)
    .map((c, i) => {
      const amount = safeNum(c['total'] ?? c['balance'] ?? c['amount']) ?? 0;
      const percentage = totalAR > 0 ? amount / totalAR : 0;
      return {
        customerId: String(c['id'] ?? c['customer_id'] ?? `customer_${i}`),
        customerName: c['name'] ? String(c['name']) : null,
        amount,
        percentage,
      };
    })
    .sort((a, b) => b.amount - a.amount);
}

/**
 * Computes all AR metrics deterministically from ingested document sections.
 */
export function computeARMetrics(sections: DocumentSection[]): ComputedARMetrics {
  const arSections = sections.filter((s) => s.documentType === 'ar_aging_report');

  if (arSections.length === 0) {
    return {
      totalAR: 0,
      agingBuckets: { current: 0, thirtyDay: 0, sixtyDay: 0, ninetyDay: 0, over90: 0 },
      agingPercentages: { current: 0, thirtyDay: 0, sixtyDay: 0, ninetyDay: 0, over90: 0 },
      dso: null,
      annualRevenueUsedForDso: null,
      customerConcentrations: [],
      topCustomerPercent: 0,
      top5CustomersPercent: 0,
      estimatedWriteOffAmount: 0,
      estimatedWriteOffPercent: 0,
      hasARData: false,
    };
  }

  // Merge all AR sections (typically one report, but handle multiple gracefully)
  const merged: Record<string, unknown> = {};
  for (const section of arSections) {
    Object.assign(merged, section.extractedData);
  }

  const totalAR = safeNum(
    merged['total_ar'] ??
    merged['total_accounts_receivable'] ??
    merged['ar_total'] ??
    merged['total']
  ) ?? 0;

  const current = safeNum(merged['current'] ?? merged['current_amount']) ?? 0;
  const thirtyDay = safeNum(merged['30_days'] ?? merged['30day'] ?? merged['days_30'] ?? merged['bucket_30']) ?? 0;
  const sixtyDay = safeNum(merged['60_days'] ?? merged['60day'] ?? merged['days_60'] ?? merged['bucket_60']) ?? 0;
  const ninetyDay = safeNum(merged['90_days'] ?? merged['90day'] ?? merged['days_90'] ?? merged['bucket_90']) ?? 0;
  const over90 = safeNum(merged['over_90'] ?? merged['over90'] ?? merged['90plus'] ?? merged['bucket_over90']) ?? 0;

  const agingBuckets: AgingBucketMetrics = { current, thirtyDay, sixtyDay, ninetyDay, over90 };

  // Recompute total from buckets if not explicitly provided
  const computedTotal = current + thirtyDay + sixtyDay + ninetyDay + over90;
  const effectiveTotal = totalAR > 0 ? totalAR : computedTotal;

  const agingPercentages: AgingBucketPercentages =
    effectiveTotal > 0
      ? {
          current: current / effectiveTotal,
          thirtyDay: thirtyDay / effectiveTotal,
          sixtyDay: sixtyDay / effectiveTotal,
          ninetyDay: ninetyDay / effectiveTotal,
          over90: over90 / effectiveTotal,
        }
      : { current: 0, thirtyDay: 0, sixtyDay: 0, ninetyDay: 0, over90: 0 };

  // DSO: (Total AR / Annual Revenue) × 365
  const annualRevenueUsedForDso = extractAnnualRevenue(sections);
  const dso =
    annualRevenueUsedForDso && annualRevenueUsedForDso > 0 && effectiveTotal > 0
      ? (effectiveTotal / annualRevenueUsedForDso) * 365
      : null;

  const customerConcentrations = extractCustomerConcentrations(merged, effectiveTotal);

  const topCustomerPercent =
    customerConcentrations.length > 0 ? customerConcentrations[0].percentage : 0;

  const top5CustomersPercent =
    customerConcentrations.length > 0
      ? customerConcentrations
          .slice(0, 5)
          .reduce((sum, c) => sum + c.percentage, 0)
      : 0;

  // Estimated write-offs: 90-day × 50% uncollectible, over-90 × 90% uncollectible
  const estimatedWriteOffAmount = ninetyDay * 0.5 + over90 * 0.9;
  const estimatedWriteOffPercent =
    effectiveTotal > 0 ? estimatedWriteOffAmount / effectiveTotal : 0;

  return {
    totalAR: effectiveTotal,
    agingBuckets,
    agingPercentages,
    dso,
    annualRevenueUsedForDso,
    customerConcentrations,
    topCustomerPercent,
    top5CustomersPercent,
    estimatedWriteOffAmount,
    estimatedWriteOffPercent,
    hasARData: true,
  };
}

// ---------------------------------------------------------------------------
// Runner
// ---------------------------------------------------------------------------

export async function runARCollections(
  ingestionOutput: IngestionOutput
): Promise<AgentResult<ARCollectionsOutput>> {
  const config = AGENT_REGISTRY['ar-collections'];

  const relevantDocTypes = new Set(['ar_aging_report', 'profit_and_loss']);

  const relevantDocs = ingestionOutput.documents.filter((doc) =>
    relevantDocTypes.has(doc.documentType)
  );

  const allSections: DocumentSection[] = relevantDocs.flatMap((doc) => doc.sections);

  const metrics = computeARMetrics(allSections);

  const systemPrompt = loadAgentPrompt('ar-collections');

  // No AR data — return success with healthy defaults and low confidence
  if (!metrics.hasARData) {
    const userMessage =
      `## Pre-Computed AR Metrics\n` +
      JSON.stringify(metrics, null, 2) +
      `\n\n## Raw Extracted Data\n(No AR aging report found in the document package)\n\n` +
      `⚠️ INSTRUCTION: No AR aging report was provided. This may mean the business has no outstanding ` +
      `receivables (e.g., cash-only retail) or the document was not included in the package. ` +
      `Set totalAR to 0, all agingBuckets to 0, dso to 0, overallScore to 8 (assume healthy since ` +
      `no AR is often good), confidence to 0.2, and explain in the summary that no AR data was provided. ` +
      `Use empty array for collectibilityFlags. Set writeOffRisk amount to 0.`;

    return callAgent<ARCollectionsOutput>({
      model: config.model,
      systemPrompt,
      userMessage,
      schema: ARCollectionsOutputSchema,
      maxTokens: config.maxTokens,
      temperature: 0,
    });
  }

  const rawDataSummary = relevantDocs
    .filter((doc) => doc.documentType === 'ar_aging_report')
    .map((doc) => {
      const sectionSummaries = doc.sections
        .map((s) => `  [${s.timeframe.endDate ?? s.timeframe.fiscalYear ?? 'unknown date'}] ${JSON.stringify(s.extractedData)}`)
        .join('\n');
      return `### ${doc.fileName}\n${sectionSummaries}`;
    })
    .join('\n\n');

  const userMessage =
    `## Pre-Computed AR Metrics\n` +
    JSON.stringify(metrics, null, 2) +
    `\n\n## Raw Extracted AR Data\n` +
    rawDataSummary;

  return callAgent<ARCollectionsOutput>({
    model: config.model,
    systemPrompt,
    userMessage,
    schema: ARCollectionsOutputSchema,
    maxTokens: config.maxTokens,
    temperature: 0,
  });
}
