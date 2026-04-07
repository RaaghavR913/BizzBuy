import type { z } from 'zod';
import type { PipelinePhase } from '@/src/types/pipeline';
import type Anthropic from '@anthropic-ai/sdk';

import { IngestionOutputSchema } from './schemas/ingestion.schema';
import { FinancialAnalysisOutputSchema } from './schemas/financial-analysis.schema';
import { TaxComplianceOutputSchema } from './schemas/tax-compliance.schema';
import { ARCollectionsOutputSchema } from './schemas/ar-collections.schema';
import { CustomerConcentrationOutputSchema } from './schemas/customer-concentration.schema';
import { OpsTransferabilityOutputSchema } from './schemas/operations-transferability.schema';
import { LeaseContractOutputSchema } from './schemas/lease-contract.schema';
import { MarketMacroOutputSchema } from './schemas/market-macro.schema';
import { LendingAffordabilityOutputSchema } from './schemas/lending-affordability.schema';
import { SynthesisReportOutputSchema } from './schemas/synthesis-report.schema';

export interface AgentConfig {
  name: string;
  promptFile: string;
  schema: z.ZodType<any>;
  model: string;
  phase: PipelinePhase;
  dependsOn: string[];
  tools?: Anthropic.Messages.Tool[];
  maxTokens?: number;
}

export const AGENT_REGISTRY: Record<string, AgentConfig> = {
  'document-ingestion': {
    name: 'document-ingestion',
    promptFile: 'document-ingestion',
    schema: IngestionOutputSchema,
    model: 'claude-haiku-4-5-20251001',
    phase: 'ingestion',
    dependsOn: [],
    maxTokens: 8192,
  },
  'financial-analysis': {
    name: 'financial-analysis',
    promptFile: 'financial-analysis',
    schema: FinancialAnalysisOutputSchema,
    model: 'claude-sonnet-4-20250514',
    phase: 'parallel_analysis',
    dependsOn: ['document-ingestion'],
    maxTokens: 8192,
  },
  'tax-compliance': {
    name: 'tax-compliance',
    promptFile: 'tax-compliance',
    schema: TaxComplianceOutputSchema,
    model: 'claude-sonnet-4-20250514',
    phase: 'parallel_analysis',
    dependsOn: ['document-ingestion'],
    maxTokens: 4096,
  },
  'ar-collections': {
    name: 'ar-collections',
    promptFile: 'ar-collections',
    schema: ARCollectionsOutputSchema,
    model: 'claude-haiku-4-5-20251001',
    phase: 'parallel_analysis',
    dependsOn: ['document-ingestion'],
    maxTokens: 4096,
  },
  'customer-concentration': {
    name: 'customer-concentration',
    promptFile: 'customer-concentration',
    schema: CustomerConcentrationOutputSchema,
    model: 'claude-haiku-4-5-20251001',
    phase: 'parallel_analysis',
    dependsOn: ['document-ingestion'],
    maxTokens: 4096,
  },
  'operations-transferability': {
    name: 'operations-transferability',
    promptFile: 'operations-transferability',
    schema: OpsTransferabilityOutputSchema,
    model: 'claude-sonnet-4-20250514',
    phase: 'parallel_analysis',
    dependsOn: ['document-ingestion'],
    maxTokens: 4096,
  },
  'lease-contract': {
    name: 'lease-contract',
    promptFile: 'lease-contract',
    schema: LeaseContractOutputSchema,
    model: 'claude-sonnet-4-20250514',
    phase: 'parallel_analysis',
    dependsOn: ['document-ingestion'],
    maxTokens: 4096,
  },
  'market-macro': {
    name: 'market-macro',
    promptFile: 'market-macro',
    schema: MarketMacroOutputSchema,
    model: 'claude-sonnet-4-20250514',
    phase: 'parallel_analysis',
    dependsOn: ['document-ingestion'],
    maxTokens: 4096,
    tools: [
      { type: 'web_search_20250305', name: 'web_search' } as unknown as Anthropic.Messages.Tool,
    ],
  },
  'lending-affordability': {
    name: 'lending-affordability',
    promptFile: 'lending-affordability',
    schema: LendingAffordabilityOutputSchema,
    model: 'claude-sonnet-4-20250514',
    phase: 'lending',
    dependsOn: ['financial-analysis'],
    maxTokens: 4096,
  },
  'synthesis-report': {
    name: 'synthesis-report',
    promptFile: 'synthesis-report',
    schema: SynthesisReportOutputSchema,
    model: 'claude-opus-4-20250514',
    phase: 'synthesis',
    dependsOn: [
      'document-ingestion',
      'financial-analysis',
      'tax-compliance',
      'ar-collections',
      'customer-concentration',
      'operations-transferability',
      'lease-contract',
      'market-macro',
      'lending-affordability',
    ],
    maxTokens: 8192,
  },
};
