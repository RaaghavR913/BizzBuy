import type { PipelineInput, PipelineState, AgentResult, AgentError } from '@/src/types/pipeline';
import type { IngestionOutput } from './schemas/ingestion.schema';
import type { FinancialAnalysisOutput } from './schemas/financial-analysis.schema';
import type { TaxComplianceOutput } from './schemas/tax-compliance.schema';
import type { ARCollectionsOutput } from './schemas/ar-collections.schema';
import type { CustomerConcentrationOutput } from './schemas/customer-concentration.schema';
import type { OpsTransferabilityOutput } from './schemas/operations-transferability.schema';
import type { LeaseContractOutput } from './schemas/lease-contract.schema';
import type { MarketMacroOutput } from './schemas/market-macro.schema';
import type { LendingAffordabilityOutput } from './schemas/lending-affordability.schema';
import type { SynthesisReportOutput } from './schemas/synthesis-report.schema';
import { runDocumentIngestion } from './runners/document-ingestion';
import { runFinancialAnalysis } from './runners/financial-analysis';
import { runTaxCompliance } from './runners/tax-compliance';
import { runARCollections } from './runners/ar-collections';
import { runCustomerConcentration } from './runners/customer-concentration';
import { runOpsTransferability } from './runners/operations-transferability';
import { runLeaseContract } from './runners/lease-contract';
import { runMarketMacro } from './runners/market-macro';
import { runLendingAffordability } from './runners/lending-affordability';
import { runSynthesisReport } from './runners/synthesis-report';
import { AGENT_REGISTRY } from './registry';

// ---------------------------------------------------------------------------
// Cost estimation rates (USD per 1M tokens)
// ---------------------------------------------------------------------------

const MODEL_PRICING: Record<string, { input: number; output: number }> = {
  'claude-haiku-4-5-20251001': { input: 0.80, output: 4.00 },
  'claude-sonnet-4-20250514':  { input: 3.00, output: 15.00 },
  'claude-opus-4-20250514':    { input: 15.00, output: 75.00 },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function settledToAgentResult<T>(
  settled: PromiseSettledResult<AgentResult<T>>,
  agentName: string
): AgentResult<T> {
  if (settled.status === 'fulfilled') {
    return settled.value;
  }
  return {
    status: 'error',
    error: {
      agentName,
      errorType: 'unknown',
      message: settled.reason instanceof Error ? settled.reason.message : 'Unknown error during agent execution',
      timestamp: new Date().toISOString(),
      retryCount: 0,
    },
  };
}

function computeTotalTokens(state: PipelineState): number {
  let total = 0;
  const agentFields: (keyof PipelineState)[] = [
    'ingestion',
    'financialAnalysis',
    'taxCompliance',
    'arCollections',
    'customerConcentration',
    'operationsTransferability',
    'leaseContract',
    'marketMacro',
    'lendingAffordability',
    'synthesisReport',
  ];

  for (const field of agentFields) {
    const result = state[field] as AgentResult<unknown> | undefined;
    if (result?.status === 'success') {
      total += result.tokenUsage.input + result.tokenUsage.output;
    }
  }

  return total;
}

const AGENT_FIELD_TO_REGISTRY_KEY: Record<string, string> = {
  ingestion: 'document-ingestion',
  financialAnalysis: 'financial-analysis',
  taxCompliance: 'tax-compliance',
  arCollections: 'ar-collections',
  customerConcentration: 'customer-concentration',
  operationsTransferability: 'operations-transferability',
  leaseContract: 'lease-contract',
  marketMacro: 'market-macro',
  lendingAffordability: 'lending-affordability',
  synthesisReport: 'synthesis-report',
};

export function computeEstimatedCost(state: PipelineState): number {
  let totalCost = 0;
  const agentFields: (keyof PipelineState)[] = [
    'ingestion',
    'financialAnalysis',
    'taxCompliance',
    'arCollections',
    'customerConcentration',
    'operationsTransferability',
    'leaseContract',
    'marketMacro',
    'lendingAffordability',
    'synthesisReport',
  ];

  for (const field of agentFields) {
    const result = state[field] as AgentResult<unknown> | undefined;
    if (result?.status !== 'success') continue;

    const registryKey = AGENT_FIELD_TO_REGISTRY_KEY[field as string];
    const config = AGENT_REGISTRY[registryKey];
    if (!config) continue;

    const pricing = MODEL_PRICING[config.model];
    if (!pricing) continue;

    const { input, output } = result.tokenUsage;
    totalCost +=
      (input / 1_000_000) * pricing.input +
      (output / 1_000_000) * pricing.output;
  }

  return totalCost;
}

// ---------------------------------------------------------------------------
// Pipeline orchestrator
// ---------------------------------------------------------------------------

export async function runPipeline(input: PipelineInput): Promise<PipelineState> {
  const state: PipelineState = {
    input,
    metadata: {
      startedAt: new Date().toISOString(),
      totalTokens: 0,
      estimatedCost: 0,
    },
  };

  // -----------------------------------------------------------------------
  // Phase 1 — Document Ingestion (Sequential, Blocking)
  // -----------------------------------------------------------------------

  console.log('[Pipeline] Phase 1: Document Ingestion — starting');
  const ingestionStart = Date.now();
  const ingestionResult = await runDocumentIngestion(input);
  console.log(`[Pipeline] Phase 1: Document Ingestion — completed in ${Date.now() - ingestionStart}ms`);

  state.ingestion = ingestionResult;

  if (ingestionResult.status === 'error') {
    console.error('[Pipeline] Phase 1 FAILED — aborting pipeline');
    const abortError: AgentError = {
      agentName: 'pipeline',
      errorType: 'unknown',
      message: 'Pipeline aborted: Document ingestion failed. No documents could be parsed.',
      timestamp: new Date().toISOString(),
      retryCount: 0,
    };

    state.financialAnalysis = { status: 'error', error: abortError };
    state.taxCompliance = { status: 'error', error: abortError };
    state.arCollections = { status: 'error', error: abortError };
    state.customerConcentration = { status: 'error', error: abortError };
    state.operationsTransferability = { status: 'error', error: abortError };
    state.leaseContract = { status: 'error', error: abortError };
    state.marketMacro = { status: 'error', error: abortError };
    state.lendingAffordability = { status: 'error', error: abortError };
    state.synthesisReport = { status: 'error', error: abortError };

    state.metadata.completedAt = new Date().toISOString();
    state.metadata.totalTokens = computeTotalTokens(state);
    state.metadata.estimatedCost = computeEstimatedCost(state);
    return state;
  }

  const ingestionOutput = ingestionResult.data;

  // -----------------------------------------------------------------------
  // Phase 2 — Parallel Analysis (7 agents via Promise.allSettled)
  // -----------------------------------------------------------------------

  console.log('[Pipeline] Phase 2: Parallel Analysis — starting 7 agents');
  const phase2Start = Date.now();

  const phase2Results = await Promise.allSettled([
    runFinancialAnalysis(ingestionOutput),
    runTaxCompliance(ingestionOutput),
    runARCollections(ingestionOutput),
    runCustomerConcentration(ingestionOutput),
    runOpsTransferability(ingestionOutput),
    runLeaseContract(ingestionOutput),
    runMarketMacro(ingestionOutput, {
      businessType: input.businessType,
      location: input.location,
    }),
  ]);

  console.log(`[Pipeline] Phase 2: Parallel Analysis — completed in ${Date.now() - phase2Start}ms`);

  state.financialAnalysis = settledToAgentResult<FinancialAnalysisOutput>(phase2Results[0], 'financial-analysis');
  state.taxCompliance = settledToAgentResult<TaxComplianceOutput>(phase2Results[1], 'tax-compliance');
  state.arCollections = settledToAgentResult<ARCollectionsOutput>(phase2Results[2], 'ar-collections');
  state.customerConcentration = settledToAgentResult<CustomerConcentrationOutput>(phase2Results[3], 'customer-concentration');
  state.operationsTransferability = settledToAgentResult<OpsTransferabilityOutput>(phase2Results[4], 'operations-transferability');
  state.leaseContract = settledToAgentResult<LeaseContractOutput>(phase2Results[5], 'lease-contract');
  state.marketMacro = settledToAgentResult<MarketMacroOutput>(phase2Results[6], 'market-macro');

  const phase2Agents = [
    'financial-analysis',
    'tax-compliance',
    'ar-collections',
    'customer-concentration',
    'operations-transferability',
    'lease-contract',
    'market-macro',
  ];
  phase2Results.forEach((result, i) => {
    const status = result.status === 'fulfilled' && result.value.status === 'success' ? 'SUCCESS' : 'FAILED';
    console.log(`[Pipeline]   ${phase2Agents[i]}: ${status}`);
  });

  // -----------------------------------------------------------------------
  // Phase 3 — Lending & Affordability (Sequential, Conditional)
  // -----------------------------------------------------------------------

  console.log('[Pipeline] Phase 3: Lending & Affordability — starting');
  const phase3Start = Date.now();

  if (state.financialAnalysis.status === 'success') {
    state.lendingAffordability = await runLendingAffordability(
      ingestionOutput,
      state.financialAnalysis.data,
      input.askingPrice
    );
  } else {
    console.warn('[Pipeline] Phase 3: Skipping — Financial Analysis not available');
    state.lendingAffordability = {
      status: 'error',
      error: {
        agentName: 'lending-affordability',
        errorType: 'unknown',
        message: 'Cannot assess lending affordability: Financial Analysis agent failed, so validated SDE is not available.',
        timestamp: new Date().toISOString(),
        retryCount: 0,
      },
    };
  }

  console.log(`[Pipeline] Phase 3: Lending & Affordability — completed in ${Date.now() - phase3Start}ms`);

  // -----------------------------------------------------------------------
  // Phase 4 — Synthesis Report (Sequential, Always Runs)
  // -----------------------------------------------------------------------

  console.log('[Pipeline] Phase 4: Synthesis Report — starting');
  const phase4Start = Date.now();

  state.synthesisReport = await runSynthesisReport({
    ingestion: state.ingestion,
    financialAnalysis: state.financialAnalysis,
    taxCompliance: state.taxCompliance,
    arCollections: state.arCollections,
    customerConcentration: state.customerConcentration,
    operationsTransferability: state.operationsTransferability,
    leaseContract: state.leaseContract,
    marketMacro: state.marketMacro,
    lendingAffordability: state.lendingAffordability,
  });

  console.log(`[Pipeline] Phase 4: Synthesis Report — completed in ${Date.now() - phase4Start}ms`);

  // -----------------------------------------------------------------------
  // Finalize metadata
  // -----------------------------------------------------------------------

  state.metadata.completedAt = new Date().toISOString();
  state.metadata.totalTokens = computeTotalTokens(state);
  state.metadata.estimatedCost = computeEstimatedCost(state);

  const totalTime = Date.now() - new Date(state.metadata.startedAt).getTime();
  console.log(
    `[Pipeline] COMPLETE — Total time: ${totalTime}ms | Tokens: ${state.metadata.totalTokens} | Cost: $${state.metadata.estimatedCost.toFixed(4)}`
  );

  return state;
}
