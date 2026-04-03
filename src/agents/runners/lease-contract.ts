import type { IngestionOutput } from '@/src/agents/schemas/ingestion.schema';
import type { LeaseContractOutput } from '@/src/agents/schemas/lease-contract.schema';
import { LeaseContractOutputSchema } from '@/src/agents/schemas/lease-contract.schema';
import type { AgentResult } from '@/src/types/pipeline';
import { callAgent } from '@/src/agents/utils/claude-client';
import { loadAgentPrompt } from '@/src/agents/utils/prompt-loader';
import { AGENT_REGISTRY } from '@/src/agents/registry';

interface LeaseData {
  leaseStart?: string;
  leaseEnd?: string;
  monthlyRent?: number;
}

interface ContractData {
  type?: string;
  counterparty?: string;
  termMonths?: number;
  totalValue?: number;
  annualValue?: number;
}

interface LeaseMetrics {
  remainingMonths: number | null;
  annualRent: number | null;
  rawLease: LeaseData | null;
}

function parseDateString(dateStr: string): Date | null {
  const parsed = new Date(dateStr);
  return isNaN(parsed.getTime()) ? null : parsed;
}

function computeRemainingMonths(leaseEnd: string): number | null {
  const endDate = parseDateString(leaseEnd);
  if (!endDate) return null;

  const now = new Date();
  const diffMs = endDate.getTime() - now.getTime();
  const diffMonths = diffMs / (1000 * 60 * 60 * 24 * 30.44);
  return Math.max(0, Math.round(diffMonths));
}

function extractLeaseData(ingestionOutput: IngestionOutput): LeaseData | null {
  for (const doc of ingestionOutput.documents) {
    if (doc.documentType !== 'lease_agreement') continue;

    for (const section of doc.sections) {
      const data = section.extractedData;

      const monthlyRent =
        typeof data['monthlyRent'] === 'number'
          ? data['monthlyRent']
          : typeof data['monthly_rent'] === 'number'
          ? data['monthly_rent']
          : typeof data['rent'] === 'number'
          ? data['rent']
          : undefined;

      const leaseStart =
        typeof data['leaseStart'] === 'string'
          ? data['leaseStart']
          : typeof data['lease_start'] === 'string'
          ? data['lease_start']
          : typeof data['startDate'] === 'string'
          ? data['startDate']
          : undefined;

      const leaseEnd =
        typeof data['leaseEnd'] === 'string'
          ? data['leaseEnd']
          : typeof data['lease_end'] === 'string'
          ? data['lease_end']
          : typeof data['endDate'] === 'string'
          ? data['endDate']
          : typeof data['expirationDate'] === 'string'
          ? data['expirationDate']
          : undefined;

      if (monthlyRent !== undefined || leaseStart !== undefined || leaseEnd !== undefined) {
        return { monthlyRent, leaseStart, leaseEnd };
      }
    }
  }

  return null;
}

function extractContracts(ingestionOutput: IngestionOutput): ContractData[] {
  const contracts: ContractData[] = [];

  for (const doc of ingestionOutput.documents) {
    if (doc.documentType !== 'contract') continue;

    for (const section of doc.sections) {
      const data = section.extractedData;

      const termMonths =
        typeof data['termMonths'] === 'number'
          ? data['termMonths']
          : typeof data['term_months'] === 'number'
          ? data['term_months']
          : undefined;

      const totalValue =
        typeof data['totalValue'] === 'number'
          ? data['totalValue']
          : typeof data['total_value'] === 'number'
          ? data['total_value']
          : undefined;

      const annualValue =
        typeof data['annualValue'] === 'number'
          ? data['annualValue']
          : typeof data['annual_value'] === 'number'
          ? data['annual_value']
          : typeof data['annualRevenue'] === 'number'
          ? data['annualRevenue']
          : undefined;

      contracts.push({
        type:
          typeof data['contractType'] === 'string'
            ? data['contractType']
            : typeof data['type'] === 'string'
            ? data['type']
            : undefined,
        counterparty:
          typeof data['counterparty'] === 'string'
            ? data['counterparty']
            : typeof data['vendor'] === 'string'
            ? data['vendor']
            : typeof data['party'] === 'string'
            ? data['party']
            : undefined,
        termMonths,
        totalValue,
        annualValue,
      });
    }
  }

  return contracts;
}

function computeLeaseMetrics(leaseData: LeaseData | null): LeaseMetrics {
  if (!leaseData) {
    return { remainingMonths: null, annualRent: null, rawLease: null };
  }

  const remainingMonths = leaseData.leaseEnd
    ? computeRemainingMonths(leaseData.leaseEnd)
    : null;

  const annualRent =
    leaseData.monthlyRent !== undefined ? leaseData.monthlyRent * 12 : null;

  return { remainingMonths, annualRent, rawLease: leaseData };
}

function buildUserMessage(
  ingestionOutput: IngestionOutput,
  leaseMetrics: LeaseMetrics,
  contracts: ContractData[],
  hasLease: boolean,
  hasContracts: boolean
): string {
  const sections: string[] = [];

  if (!hasLease && !hasContracts) {
    sections.push(
      '## Data Availability\n\nNo lease agreement or contract documents were found in the provided documents. ' +
      'This is a critical gap — most businesses with a physical location have a lease, and its absence means ' +
      'either the business operates without a formal lease (unusual), or the seller has not provided it. ' +
      'Please set lease to null, flag this as a critical risk, and assess with very low confidence.'
    );
  } else {
    sections.push('## Pre-Computed Lease & Contract Metrics');

    if (hasLease && leaseMetrics.rawLease) {
      sections.push('\n### Lease Metrics');

      if (leaseMetrics.remainingMonths !== null) {
        const years = (leaseMetrics.remainingMonths / 12).toFixed(1);
        sections.push(`Remaining Lease Term: ${leaseMetrics.remainingMonths} months (${years} years)`);
        if (leaseMetrics.remainingMonths < 60) {
          sections.push('⚠️ WARNING: Less than 5 years remaining — may be insufficient for SBA 7(a) financing');
        }
      } else {
        sections.push('Remaining Lease Term: Not determinable from available data');
      }

      if (leaseMetrics.annualRent !== null) {
        sections.push(`Monthly Rent: $${(leaseMetrics.annualRent / 12).toLocaleString()}`);
        sections.push(`Annual Rent: $${leaseMetrics.annualRent.toLocaleString()}`);
      }

      if (leaseMetrics.rawLease.leaseStart) {
        sections.push(`Lease Start: ${leaseMetrics.rawLease.leaseStart}`);
      }
      if (leaseMetrics.rawLease.leaseEnd) {
        sections.push(`Lease End: ${leaseMetrics.rawLease.leaseEnd}`);
      }
    } else if (!hasLease) {
      sections.push('\n### Lease\nNo lease agreement found in documents.');
    }

    if (contracts.length > 0) {
      sections.push('\n### Other Contracts');
      for (const contract of contracts) {
        const parts: string[] = [];
        if (contract.type) parts.push(`Type: ${contract.type}`);
        if (contract.counterparty) parts.push(`Counterparty: ${contract.counterparty}`);
        if (contract.termMonths) parts.push(`Term: ${contract.termMonths} months`);
        if (contract.totalValue !== undefined) {
          parts.push(`Total Value: $${contract.totalValue.toLocaleString()}`);
        }
        if (contract.annualValue !== undefined) {
          parts.push(`Annual Value: $${contract.annualValue.toLocaleString()}`);
        }
        sections.push(`- ${parts.join(' | ')}`);
      }
    }
  }

  // Include all raw document text for clause-level LLM interpretation
  const relevantDocs = ingestionOutput.documents.filter((d) =>
    ['lease_agreement', 'contract'].includes(d.documentType)
  );

  // Also include any "other" documents that may contain non-compete text
  const otherDocs = ingestionOutput.documents.filter(
    (d) => d.documentType === 'other'
  );

  const docsToInclude = [...relevantDocs, ...otherDocs];

  if (docsToInclude.length > 0) {
    sections.push('\n## Raw Document Data');
    for (const doc of docsToInclude) {
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

export async function runLeaseContract(
  ingestionOutput: IngestionOutput
): Promise<AgentResult<LeaseContractOutput>> {
  const config = AGENT_REGISTRY['lease-contract'];
  const systemPrompt = loadAgentPrompt('lease-contract');

  const hasLease = ingestionOutput.documents.some(
    (d) => d.documentType === 'lease_agreement'
  );
  const hasContracts = ingestionOutput.documents.some(
    (d) => d.documentType === 'contract'
  );

  const leaseData = extractLeaseData(ingestionOutput);
  const contracts = extractContracts(ingestionOutput);
  const leaseMetrics = computeLeaseMetrics(leaseData);

  const userMessage = buildUserMessage(
    ingestionOutput,
    leaseMetrics,
    contracts,
    hasLease,
    hasContracts
  );

  return callAgent<LeaseContractOutput>({
    model: config.model,
    systemPrompt,
    userMessage,
    schema: LeaseContractOutputSchema,
    maxTokens: config.maxTokens,
  });
}
