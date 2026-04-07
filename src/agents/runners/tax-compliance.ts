import type { AgentResult } from '@/src/types/pipeline';
import type { IngestionOutput, DocumentSection } from '@/src/agents/schemas/ingestion.schema';
import type { TaxComplianceOutput } from '@/src/agents/schemas/tax-compliance.schema';
import { TaxComplianceOutputSchema } from '@/src/agents/schemas/tax-compliance.schema';
import { loadAgentPrompt } from '@/src/agents/utils/prompt-loader';
import { callAgent } from '@/src/agents/utils/claude-client';
import { AGENT_REGISTRY } from '@/src/agents/registry';

// ---------------------------------------------------------------------------
// Types for pre-computed metrics
// ---------------------------------------------------------------------------

export interface RevenueDiscrepancy {
  year: number;
  revenuePerFinancials: number | null;
  revenuePerTaxReturn: number | null;
  absoluteDiscrepancy: number | null;
  percentageDiscrepancy: number | null;
  /** True if discrepancy exceeds 5% threshold */
  flagged: boolean;
}

export interface TaxYearCoverage {
  financialYears: number[];
  taxReturnYears: number[];
  overlappingYears: number[];
  missingTaxYears: number[];
}

export interface ComputedTaxMetrics {
  revenueDiscrepancies: RevenueDiscrepancy[];
  yearCoverage: TaxYearCoverage;
  hasTaxReturns: boolean;
  hasFinancials: boolean;
  /** True if any tax return shows revenue HIGHER than P&L (critical flag) */
  taxRevenueExceedsFinancials: boolean;
  /** Largest absolute discrepancy across all years */
  maxAbsoluteDiscrepancy: number | null;
  /** Largest percentage discrepancy across all years */
  maxPercentageDiscrepancy: number | null;
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
 * Extracts revenue by fiscal year from a set of document sections.
 * Tries multiple common field names for revenue.
 */
function extractRevenueByYear(sections: DocumentSection[]): Map<number, number> {
  const result = new Map<number, number>();

  for (const section of sections) {
    const year = section.timeframe.fiscalYear;
    if (!year) continue;

    const data = section.extractedData;
    const revenue = safeNum(
      data['revenue'] ??
      data['gross_revenue'] ??
      data['net_revenue'] ??
      data['total_revenue'] ??
      data['gross_receipts'] ??
      data['gross_sales']
    );

    if (revenue !== null && !result.has(year)) {
      result.set(year, revenue);
    }
  }

  return result;
}

/**
 * Deterministically computes revenue discrepancies between P&L and tax returns
 * for all overlapping fiscal years.
 */
export function computeTaxMetrics(sections: DocumentSection[]): ComputedTaxMetrics {
  const taxDocTypes = new Set([
    'tax_return_1120s',
    'tax_return_1040',
    'tax_return_schedule_c',
  ]);

  const financialSections = sections.filter((s) => s.documentType === 'profit_and_loss');
  const taxSections = sections.filter((s) => taxDocTypes.has(s.documentType));

  const hasTaxReturns = taxSections.length > 0;
  const hasFinancials = financialSections.length > 0;

  const revenueFromFinancials = extractRevenueByYear(financialSections);
  const revenueFromTaxReturns = extractRevenueByYear(taxSections);

  const financialYears = Array.from(revenueFromFinancials.keys()).sort();
  const taxReturnYears = Array.from(revenueFromTaxReturns.keys()).sort();
  const overlappingYears = financialYears.filter((y) => taxReturnYears.includes(y));
  const missingTaxYears = financialYears.filter((y) => !taxReturnYears.includes(y));

  const revenueDiscrepancies: RevenueDiscrepancy[] = overlappingYears.map((year) => {
    const revenuePerFinancials = revenueFromFinancials.get(year) ?? null;
    const revenuePerTaxReturn = revenueFromTaxReturns.get(year) ?? null;

    let absoluteDiscrepancy: number | null = null;
    let percentageDiscrepancy: number | null = null;

    if (revenuePerFinancials !== null && revenuePerTaxReturn !== null) {
      absoluteDiscrepancy = revenuePerFinancials - revenuePerTaxReturn;
      if (revenuePerFinancials !== 0) {
        percentageDiscrepancy = absoluteDiscrepancy / revenuePerFinancials;
      }
    }

    const flagged =
      percentageDiscrepancy !== null && Math.abs(percentageDiscrepancy) > 0.05;

    return {
      year,
      revenuePerFinancials,
      revenuePerTaxReturn,
      absoluteDiscrepancy,
      percentageDiscrepancy,
      flagged,
    };
  });

  const taxRevenueExceedsFinancials = revenueDiscrepancies.some(
    (d) => d.absoluteDiscrepancy !== null && d.absoluteDiscrepancy < 0
  );

  const flaggedDiscrepancies = revenueDiscrepancies.filter(
    (d) => d.absoluteDiscrepancy !== null
  );

  const maxAbsoluteDiscrepancy =
    flaggedDiscrepancies.length > 0
      ? Math.max(...flaggedDiscrepancies.map((d) => Math.abs(d.absoluteDiscrepancy!)))
      : null;

  const maxPercentageDiscrepancy =
    flaggedDiscrepancies.length > 0 && flaggedDiscrepancies.some((d) => d.percentageDiscrepancy !== null)
      ? Math.max(...flaggedDiscrepancies.filter((d) => d.percentageDiscrepancy !== null).map((d) => Math.abs(d.percentageDiscrepancy!)))
      : null;

  return {
    revenueDiscrepancies,
    yearCoverage: {
      financialYears,
      taxReturnYears,
      overlappingYears,
      missingTaxYears,
    },
    hasTaxReturns,
    hasFinancials,
    taxRevenueExceedsFinancials,
    maxAbsoluteDiscrepancy,
    maxPercentageDiscrepancy,
  };
}

// ---------------------------------------------------------------------------
// Runner
// ---------------------------------------------------------------------------

export async function runTaxCompliance(
  ingestionOutput: IngestionOutput
): Promise<AgentResult<TaxComplianceOutput>> {
  const config = AGENT_REGISTRY['tax-compliance'];

  const relevantDocTypes = new Set([
    'tax_return_1120s',
    'tax_return_1040',
    'tax_return_schedule_c',
    'profit_and_loss',
  ]);

  const relevantDocs = ingestionOutput.documents.filter((doc) =>
    relevantDocTypes.has(doc.documentType)
  );

  const allSections: DocumentSection[] = relevantDocs.flatMap((doc) => doc.sections);

  const metrics = computeTaxMetrics(allSections);

  // Handle missing tax returns gracefully — return success with low confidence
  if (!metrics.hasTaxReturns) {
    const systemPrompt = loadAgentPrompt('tax-compliance');

    const userMessage =
      `## Pre-Computed Tax Metrics\n` +
      JSON.stringify(metrics, null, 2) +
      `\n\n## Raw Extracted Data\n(No tax returns found in the document package)\n\n` +
      `⚠️ WARNING: No tax return documents were found in the diligence package. ` +
      `This is a significant gap — tax returns are essential for compliance review. ` +
      `Set confidence to 0.2, set unreportedIncomeRisk to "high", and explain clearly in your summary ` +
      `that tax returns must be obtained before close. Use empty arrays for revenueComparison and ` +
      `deductionAnalysis. Set overallScore to 3 to reflect the data gap.`;

    return callAgent<TaxComplianceOutput>({
      model: config.model,
      systemPrompt,
      userMessage,
      schema: TaxComplianceOutputSchema,
      maxTokens: config.maxTokens,
      temperature: 0,
    });
  }

  const systemPrompt = loadAgentPrompt('tax-compliance');

  const rawDataSummary = relevantDocs
    .map((doc) => {
      const sectionSummaries = doc.sections
        .map((s) => `  [FY${s.timeframe.fiscalYear ?? 'unknown'}] ${JSON.stringify(s.extractedData)}`)
        .join('\n');
      return `### ${doc.fileName} (${doc.documentType})\n${sectionSummaries}`;
    })
    .join('\n\n');

  const userMessage =
    `## Pre-Computed Tax Metrics\n` +
    JSON.stringify(metrics, null, 2) +
    `\n\n## Raw Extracted Data\n` +
    rawDataSummary;

  return callAgent<TaxComplianceOutput>({
    model: config.model,
    systemPrompt,
    userMessage,
    schema: TaxComplianceOutputSchema,
    maxTokens: config.maxTokens,
    temperature: 0,
  });
}
