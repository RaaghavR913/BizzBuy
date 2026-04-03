import { loadAgentPrompt } from '../utils/prompt-loader';
import { callAgent } from '../utils/claude-client';
import { SynthesisReportOutputSchema, type SynthesisReportOutput } from '../schemas/synthesis-report.schema';
import type { AgentResult } from '@/src/types/pipeline';
import type { IngestionOutput } from '../schemas/ingestion.schema';
import type { FinancialAnalysisOutput } from '../schemas/financial-analysis.schema';
import type { TaxComplianceOutput } from '../schemas/tax-compliance.schema';
import type { ARCollectionsOutput } from '../schemas/ar-collections.schema';
import type { CustomerConcentrationOutput } from '../schemas/customer-concentration.schema';
import type { OpsTransferabilityOutput } from '../schemas/operations-transferability.schema';
import type { LeaseContractOutput } from '../schemas/lease-contract.schema';
import type { MarketMacroOutput } from '../schemas/market-macro.schema';
import type { LendingAffordabilityOutput } from '../schemas/lending-affordability.schema';
import { AGENT_REGISTRY } from '../registry';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AllAgentOutputs {
  ingestion: AgentResult<IngestionOutput>;
  financialAnalysis: AgentResult<FinancialAnalysisOutput>;
  taxCompliance: AgentResult<TaxComplianceOutput>;
  arCollections: AgentResult<ARCollectionsOutput>;
  customerConcentration: AgentResult<CustomerConcentrationOutput>;
  operationsTransferability: AgentResult<OpsTransferabilityOutput>;
  leaseContract: AgentResult<LeaseContractOutput>;
  marketMacro: AgentResult<MarketMacroOutput>;
  lendingAffordability: AgentResult<LendingAffordabilityOutput>;
}

interface RawRedFlag {
  severity: string;
  source: string;
  title: string;
  description: string;
  financialImpact?: number;
}

interface RawGreenFlag {
  source: string;
  title: string;
  description: string;
}

interface CompositeScoreResult {
  score: number;
  successfulAgents: string[];
  failedAgents: string[];
  completeness: number;
}

// ---------------------------------------------------------------------------
// Agent weight configuration
// ---------------------------------------------------------------------------

const AGENT_WEIGHTS: Record<string, number> = {
  financialAnalysis: 0.25,
  taxCompliance: 0.10,
  arCollections: 0.10,
  customerConcentration: 0.15,
  operationsTransferability: 0.15,
  leaseContract: 0.10,
  marketMacro: 0.05,
  lendingAffordability: 0.10,
};

const AGENT_DISPLAY_NAMES: Record<string, string> = {
  financialAnalysis: 'Financial Analysis',
  taxCompliance: 'Tax Compliance',
  arCollections: 'AR/Collections',
  customerConcentration: 'Customer Concentration',
  operationsTransferability: 'Operations & Transferability',
  leaseContract: 'Lease & Contract',
  marketMacro: 'Market & Macro',
  lendingAffordability: 'Lending & Affordability',
};

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

// ---------------------------------------------------------------------------
// Step 1: Compute composite score
// ---------------------------------------------------------------------------

function getAgentScore(outputs: AllAgentOutputs, agentKey: string): number | null {
  const result = outputs[agentKey as keyof AllAgentOutputs] as AgentResult<{ overallScore: number }>;
  if (result.status === 'success') {
    return result.data.overallScore;
  }
  return null;
}

export function computeCompositeScore(outputs: AllAgentOutputs): CompositeScoreResult {
  const successfulAgents: string[] = [];
  const failedAgents: string[] = [];
  let totalAvailableWeight = 0;

  for (const agentKey of Object.keys(AGENT_WEIGHTS)) {
    const result = outputs[agentKey as keyof AllAgentOutputs];
    if (result.status === 'success') {
      successfulAgents.push(agentKey);
      totalAvailableWeight += AGENT_WEIGHTS[agentKey];
    } else {
      failedAgents.push(agentKey);
    }
  }

  if (successfulAgents.length === 0) {
    return { score: 0, successfulAgents, failedAgents, completeness: 0 };
  }

  let weightedSum = 0;
  for (const agentKey of successfulAgents) {
    const agentScore = getAgentScore(outputs, agentKey)!;
    const redistributedWeight = AGENT_WEIGHTS[agentKey] / totalAvailableWeight;
    weightedSum += agentScore * redistributedWeight;
  }

  const score = Math.round(weightedSum * 10);
  const completeness = successfulAgents.length / 8;

  return { score, successfulAgents, failedAgents, completeness };
}

// ---------------------------------------------------------------------------
// Step 2: Collect red flags from all agents
// ---------------------------------------------------------------------------

interface RiskItem {
  severity: string;
  title?: string;
  description: string;
  financialImpact?: number;
  potentialExposure?: number;
  amount?: number;
}

function extractRisks(outputs: AllAgentOutputs, agentKey: string): RiskItem[] {
  const result = outputs[agentKey as keyof AllAgentOutputs];
  if (result.status !== 'success') return [];

  const data = result.data as Record<string, unknown>;

  if (agentKey === 'taxCompliance') {
    return (data['complianceFlags'] as RiskItem[] | undefined) ?? [];
  }
  if (agentKey === 'arCollections') {
    return (data['collectibilityFlags'] as RiskItem[] | undefined) ?? [];
  }
  if (agentKey === 'customerConcentration') {
    return (data['contractRisks'] as RiskItem[] | undefined) ?? [];
  }
  if (agentKey === 'marketMacro') {
    return (data['threats'] as RiskItem[] | undefined) ?? [];
  }
  return (data['risks'] as RiskItem[] | undefined) ?? [];
}

export function collectRedFlags(outputs: AllAgentOutputs): RawRedFlag[] {
  const flags: RawRedFlag[] = [];

  for (const agentKey of Object.keys(AGENT_WEIGHTS)) {
    const risks = extractRisks(outputs, agentKey);
    const source = AGENT_DISPLAY_NAMES[agentKey] ?? agentKey;

    for (const risk of risks) {
      if (risk.severity === 'high' || risk.severity === 'critical') {
        flags.push({
          severity: risk.severity,
          source,
          title: risk.title ?? risk.description.slice(0, 80),
          description: risk.description,
          financialImpact: risk.financialImpact ?? risk.potentialExposure ?? risk.amount,
        });
      }
    }
  }

  flags.sort((a, b) => {
    const severityDiff = (SEVERITY_ORDER[a.severity] ?? 99) - (SEVERITY_ORDER[b.severity] ?? 99);
    if (severityDiff !== 0) return severityDiff;
    return (b.financialImpact ?? 0) - (a.financialImpact ?? 0);
  });

  return flags;
}

// ---------------------------------------------------------------------------
// Step 3: Collect green flags
// ---------------------------------------------------------------------------

export function collectGreenFlags(outputs: AllAgentOutputs): RawGreenFlag[] {
  const flags: RawGreenFlag[] = [];

  for (const agentKey of Object.keys(AGENT_WEIGHTS)) {
    const result = outputs[agentKey as keyof AllAgentOutputs];
    if (result.status !== 'success') continue;

    const data = result.data as { overallScore: number; summary: string };
    if (data.overallScore >= 7) {
      const displayName = AGENT_DISPLAY_NAMES[agentKey] ?? agentKey;
      flags.push({
        source: displayName,
        title: `${displayName} — Strong`,
        description: data.summary,
      });
    }
  }

  return flags;
}

// ---------------------------------------------------------------------------
// Step 4: Build compressed user message
// ---------------------------------------------------------------------------

function getAgentSummary(
  outputs: AllAgentOutputs,
  agentKey: string
): { score: number; confidence: number; summary: string; topRisks: string[] } | null {
  const result = outputs[agentKey as keyof AllAgentOutputs];
  if (result.status !== 'success') return null;

  const data = result.data as {
    overallScore: number;
    confidence: number;
    summary: string;
  };

  const risks = extractRisks(outputs, agentKey);
  const topRisks = risks
    .sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 99) - (SEVERITY_ORDER[b.severity] ?? 99))
    .slice(0, 3)
    .map((r) => `[${r.severity.toUpperCase()}] ${r.title ?? r.description.slice(0, 100)}`);

  return {
    score: data.overallScore,
    confidence: data.confidence,
    summary: data.summary,
    topRisks,
  };
}

export function buildSynthesisUserMessage(
  outputs: AllAgentOutputs,
  compositeScore: number,
  redFlags: RawRedFlag[],
  greenFlags: RawGreenFlag[],
  completeness: number
): string {
  const lines: string[] = [];

  lines.push('## Pre-Computed Assessment Metrics');
  lines.push(`- **Composite Score:** ${compositeScore}/100`);
  lines.push(`- **Data Completeness:** ${(completeness * 100).toFixed(0)}%`);
  lines.push(`- **Red Flags (HIGH/CRITICAL):** ${redFlags.length}`);
  lines.push(`- **Green Flags (score >= 7):** ${greenFlags.length}`);
  lines.push('');

  lines.push('## Agent Summaries');
  lines.push('');

  for (const agentKey of Object.keys(AGENT_WEIGHTS)) {
    const displayName = AGENT_DISPLAY_NAMES[agentKey] ?? agentKey;
    const result = outputs[agentKey as keyof AllAgentOutputs];

    if (result.status === 'success') {
      const summary = getAgentSummary(outputs, agentKey)!;
      lines.push(`### ${displayName}`);
      lines.push(`- **Score:** ${summary.score}/10 | **Confidence:** ${summary.confidence}`);
      lines.push(`- **Summary:** ${summary.summary}`);
      if (summary.topRisks.length > 0) {
        lines.push(`- **Top Risks:**`);
        for (const risk of summary.topRisks) {
          lines.push(`  - ${risk}`);
        }
      }
    } else {
      const errorMsg = result.error.message;
      lines.push(`### ${displayName}`);
      lines.push(`- **Status:** FAILED`);
      lines.push(`- **Error:** ${errorMsg}`);
    }
    lines.push('');
  }

  if (redFlags.length > 0) {
    lines.push('## Pre-Collected Red Flags');
    for (const flag of redFlags) {
      const impact = flag.financialImpact ? ` ($${flag.financialImpact.toLocaleString()} impact)` : '';
      lines.push(`- [${flag.severity.toUpperCase()}] **${flag.title}** (${flag.source})${impact}: ${flag.description}`);
    }
    lines.push('');
  }

  if (greenFlags.length > 0) {
    lines.push('## Pre-Collected Green Flags');
    for (const flag of greenFlags) {
      lines.push(`- **${flag.title}**: ${flag.description}`);
    }
    lines.push('');
  }

  lines.push('## Your Task');
  lines.push(
    'Synthesize these findings into a unified acquisition assessment. The composite score and red/green flags ' +
    'have been pre-computed — validate they make sense and build your narrative around them. ' +
    'Call the structured_output tool with your complete SynthesisReportOutput.'
  );

  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Step 5: Main runner
// ---------------------------------------------------------------------------

export async function runSynthesisReport(
  allAgentOutputs: AllAgentOutputs
): Promise<AgentResult<SynthesisReportOutput>> {
  const config = AGENT_REGISTRY['synthesis-report'];

  const { score, completeness } = computeCompositeScore(allAgentOutputs);
  const redFlags = collectRedFlags(allAgentOutputs);
  const greenFlags = collectGreenFlags(allAgentOutputs);

  const systemPrompt = loadAgentPrompt('synthesis-report');
  const userMessage = buildSynthesisUserMessage(
    allAgentOutputs,
    score,
    redFlags,
    greenFlags,
    completeness
  );

  return callAgent<SynthesisReportOutput>({
    model: config.model,
    systemPrompt,
    userMessage,
    schema: SynthesisReportOutputSchema,
    maxTokens: config.maxTokens ?? 4096,
    temperature: 0,
  });
}
