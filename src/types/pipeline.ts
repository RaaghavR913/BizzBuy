import type { IngestionOutput } from '@/src/agents/schemas/ingestion.schema';
import type { FinancialAnalysisOutput } from '@/src/agents/schemas/financial-analysis.schema';
import type { TaxComplianceOutput } from '@/src/agents/schemas/tax-compliance.schema';
import type { ARCollectionsOutput } from '@/src/agents/schemas/ar-collections.schema';
import type { CustomerConcentrationOutput } from '@/src/agents/schemas/customer-concentration.schema';
import type { OpsTransferabilityOutput } from '@/src/agents/schemas/operations-transferability.schema';
import type { LeaseContractOutput } from '@/src/agents/schemas/lease-contract.schema';
import type { MarketMacroOutput } from '@/src/agents/schemas/market-macro.schema';
import type { LendingAffordabilityOutput } from '@/src/agents/schemas/lending-affordability.schema';
import type { SynthesisReportOutput } from '@/src/agents/schemas/synthesis-report.schema';

export interface UploadedDocument {
  id: string;
  filename: string;
  mimeType: string;
  /** Base64-encoded file content */
  content: string;
  sizeBytes: number;
}

export interface PipelineInput {
  documents: UploadedDocument[];
  /** Listing asking price in USD */
  askingPrice?: number;
  businessType?: string;
  location?: string;
}

export interface AgentError {
  agentName: string;
  errorType: 'validation' | 'api' | 'timeout' | 'unknown';
  message: string;
  timestamp: string;
  retryCount: number;
}

export type AgentResult<T> =
  | {
      status: 'success';
      data: T;
      tokenUsage: { input: number; output: number };
      latencyMs: number;
    }
  | {
      status: 'error';
      error: AgentError;
    };

export type PipelinePhase =
  | 'ingestion'
  | 'parallel_analysis'
  | 'lending'
  | 'synthesis';

export interface PipelineState {
  input: PipelineInput;
  ingestion?: AgentResult<IngestionOutput>;
  financialAnalysis?: AgentResult<FinancialAnalysisOutput>;
  taxCompliance?: AgentResult<TaxComplianceOutput>;
  arCollections?: AgentResult<ARCollectionsOutput>;
  customerConcentration?: AgentResult<CustomerConcentrationOutput>;
  operationsTransferability?: AgentResult<OpsTransferabilityOutput>;
  leaseContract?: AgentResult<LeaseContractOutput>;
  marketMacro?: AgentResult<MarketMacroOutput>;
  lendingAffordability?: AgentResult<LendingAffordabilityOutput>;
  synthesisReport?: AgentResult<SynthesisReportOutput>;
  metadata: {
    startedAt: string;
    completedAt?: string;
    /** Total tokens consumed across all agent calls */
    totalTokens: number;
    /** Estimated cost in USD */
    estimatedCost: number;
  };
}

export type {
  IngestionOutput,
  FinancialAnalysisOutput,
  TaxComplianceOutput,
  ARCollectionsOutput,
  CustomerConcentrationOutput,
  OpsTransferabilityOutput,
  LeaseContractOutput,
  MarketMacroOutput,
  LendingAffordabilityOutput,
  SynthesisReportOutput,
};
