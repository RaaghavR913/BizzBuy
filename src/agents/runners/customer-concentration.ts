import type { IngestionOutput } from '@/src/agents/schemas/ingestion.schema';
import type { CustomerConcentrationOutput } from '@/src/agents/schemas/customer-concentration.schema';
import { CustomerConcentrationOutputSchema } from '@/src/agents/schemas/customer-concentration.schema';
import type { AgentResult } from '@/src/types/pipeline';
import { callAgent } from '@/src/agents/utils/claude-client';
import { loadAgentPrompt } from '@/src/agents/utils/prompt-loader';
import { AGENT_REGISTRY } from '@/src/agents/registry';

interface CustomerData {
  name: string;
  annualRevenue: number;
}

interface ConcentrationMetrics {
  totalRevenue: number;
  customers: Array<CustomerData & { revenuePercent: number }>;
  herfindahlIndex: number;
  topCustomerPercent: number;
  top5Percent: number;
  top10Percent: number;
  singleCustomerDependency: boolean;
}

function computeConcentrationMetrics(
  customerRows: Array<CustomerData>
): ConcentrationMetrics {
  const totalRevenue = customerRows.reduce((sum, c) => sum + c.annualRevenue, 0);

  const customersWithPercent = customerRows
    .map((c) => ({
      ...c,
      revenuePercent: totalRevenue > 0 ? (c.annualRevenue / totalRevenue) * 100 : 0,
    }))
    .sort((a, b) => b.revenuePercent - a.revenuePercent);

  const herfindahlIndex = customersWithPercent.reduce(
    (sum, c) => sum + Math.pow(c.revenuePercent, 2),
    0
  );

  const topCustomerPercent = customersWithPercent[0]?.revenuePercent ?? 0;

  const top5Percent = customersWithPercent
    .slice(0, 5)
    .reduce((sum, c) => sum + c.revenuePercent, 0);

  const top10Percent = customersWithPercent
    .slice(0, 10)
    .reduce((sum, c) => sum + c.revenuePercent, 0);

  const singleCustomerDependency = topCustomerPercent > 25;

  return {
    totalRevenue,
    customers: customersWithPercent,
    herfindahlIndex,
    topCustomerPercent,
    top5Percent,
    top10Percent,
    singleCustomerDependency,
  };
}

function extractCustomerRows(ingestionOutput: IngestionOutput): CustomerData[] {
  const rows: CustomerData[] = [];

  for (const doc of ingestionOutput.documents) {
    if (doc.documentType !== 'customer_list') continue;

    for (const section of doc.sections) {
      const data = section.extractedData;

      // Support array of customer records keyed as customers, rows, or items
      const list: unknown[] =
        (data['customers'] as unknown[]) ??
        (data['rows'] as unknown[]) ??
        (data['items'] as unknown[]) ??
        [];

      for (const item of list) {
        if (typeof item !== 'object' || item === null) continue;
        const record = item as Record<string, unknown>;

        const name =
          typeof record['name'] === 'string'
            ? record['name']
            : typeof record['customer'] === 'string'
            ? record['customer']
            : typeof record['customerName'] === 'string'
            ? record['customerName']
            : null;

        const revenue =
          typeof record['annualRevenue'] === 'number'
            ? record['annualRevenue']
            : typeof record['revenue'] === 'number'
            ? record['revenue']
            : typeof record['annual_revenue'] === 'number'
            ? record['annual_revenue']
            : null;

        if (name && revenue !== null && revenue >= 0) {
          rows.push({ name, annualRevenue: revenue });
        }
      }
    }
  }

  return rows;
}

function buildUserMessage(
  ingestionOutput: IngestionOutput,
  metrics: ConcentrationMetrics | null,
  noDataFound: boolean
): string {
  const sections: string[] = [];

  if (noDataFound) {
    sections.push(
      '## Data Availability\n\nNo customer list was found in the provided documents. ' +
      'Customer concentration analysis cannot be performed with the available data. ' +
      'Please assess with low confidence and note the gap.'
    );
  } else if (metrics) {
    sections.push('## Pre-Computed Concentration Metrics');
    sections.push(`Total Revenue: $${metrics.totalRevenue.toLocaleString()}`);
    sections.push(`Herfindahl-Hirschman Index (HHI): ${metrics.herfindahlIndex.toFixed(0)}`);
    sections.push(`Top Customer Revenue %: ${metrics.topCustomerPercent.toFixed(1)}%`);
    sections.push(`Top 5 Customers Revenue %: ${metrics.top5Percent.toFixed(1)}%`);
    sections.push(`Top 10 Customers Revenue %: ${metrics.top10Percent.toFixed(1)}%`);
    sections.push(`Single Customer Dependency Flag (>25%): ${metrics.singleCustomerDependency}`);

    sections.push('\n## Customer Revenue Breakdown (sorted by revenue share)');
    for (const c of metrics.customers) {
      sections.push(`- ${c.name}: $${c.annualRevenue.toLocaleString()} (${c.revenuePercent.toFixed(1)}%)`);
    }
  }

  // Include raw contract document text for the LLM to interpret
  const contractDocs = ingestionOutput.documents.filter(
    (d) => d.documentType === 'contract' || d.documentType === 'customer_list'
  );
  if (contractDocs.length > 0) {
    sections.push('\n## Raw Document Data');
    for (const doc of contractDocs) {
      sections.push(`\n### ${doc.fileName} (${doc.documentType})`);
      for (const section of doc.sections) {
        if (section.rawText) {
          sections.push(section.rawText);
        }
      }
    }
  }

  return sections.join('\n');
}

export async function runCustomerConcentration(
  ingestionOutput: IngestionOutput
): Promise<AgentResult<CustomerConcentrationOutput>> {
  const config = AGENT_REGISTRY['customer-concentration'];
  const systemPrompt = loadAgentPrompt('customer-concentration');

  const customerRows = extractCustomerRows(ingestionOutput);
  const noDataFound = customerRows.length === 0;

  if (noDataFound) {
    const userMessage = buildUserMessage(ingestionOutput, null, true);

    return callAgent<CustomerConcentrationOutput>({
      model: config.model,
      systemPrompt,
      userMessage,
      schema: CustomerConcentrationOutputSchema,
      maxTokens: config.maxTokens,
    });
  }

  const metrics = computeConcentrationMetrics(customerRows);
  const userMessage = buildUserMessage(ingestionOutput, metrics, false);

  return callAgent<CustomerConcentrationOutput>({
    model: config.model,
    systemPrompt,
    userMessage,
    schema: CustomerConcentrationOutputSchema,
    maxTokens: config.maxTokens,
  });
}
