import type {
  AgentFlag,
  AgentId,
  AgentOutput,
  DealInfo,
  FinancialData,
  QuestionnaireData,
  SharedContext,
} from './types';

function numericMetric(output: AgentOutput | undefined, key: string): number | null {
  const value = output?.metrics[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function dedupeFlags(flags: AgentFlag[]): AgentFlag[] {
  const seen = new Set<string>();
  return flags.filter((flag) => {
    const key = `${flag.sourceAgent}:${flag.dimension}:${flag.message}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function sortFlags(flags: AgentFlag[]): AgentFlag[] {
  const severityRank: Record<AgentFlag['severity'], number> = {
    critical: 0,
    warning: 1,
    info: 2,
  };

  return [...flags].sort((a, b) => {
    const severityDelta = severityRank[a.severity] - severityRank[b.severity];
    if (severityDelta !== 0) return severityDelta;
    return a.dimension.localeCompare(b.dimension);
  });
}

function computeValidatedSDE(outputs: Partial<Record<AgentId, AgentOutput>>, financialData: FinancialData) {
  const financialSDE =
    numericMetric(outputs.financial, 'sde') ??
    financialData.incomeStatement?.sde ??
    0;
  const taxSDE = numericMetric(outputs.tax, 'normalizedSDE');

  if (taxSDE === null || financialSDE <= 0) {
    return {
      validatedSDE: financialSDE,
      sdeConflict: false,
    };
  }

  const variance = Math.abs(financialSDE - taxSDE) / Math.max(Math.abs(financialSDE), 1);
  return {
    validatedSDE: variance > 0.15 ? Math.min(financialSDE, taxSDE) : Math.round((financialSDE + taxSDE) / 2),
    sdeConflict: variance > 0.15,
  };
}

function buildConflictFlag(financialOutput: AgentOutput | undefined, taxOutput: AgentOutput | undefined): AgentFlag | null {
  const financialSDE = numericMetric(financialOutput, 'sde');
  const taxSDE = numericMetric(taxOutput, 'normalizedSDE');

  if (financialSDE === null || taxSDE === null) return null;

  const variance = Math.abs(financialSDE - taxSDE) / Math.max(Math.abs(financialSDE), 1);
  if (variance <= 0.15) return null;

  return {
    severity: 'critical',
    dimension: 'Financial Quality',
    sourceAgent: 'tax',
    metric: 'normalizedSDE',
    message: `Tax-normalized earnings differ materially from financial-agent SDE (${Math.round(variance * 100)}% variance).`,
  };
}

export function aggregateConfidence(outputs: Partial<Record<AgentId, AgentOutput>>): number {
  const values = Object.values(outputs)
    .map((output) => output?.confidence)
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));

  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export function buildSharedContext(
  financialData: FinancialData,
  questionnaire: QuestionnaireData,
  dealInfo: DealInfo,
  agentOutputs: Partial<Record<AgentId, AgentOutput>>
): SharedContext {
  const allFlags = Object.values(agentOutputs).flatMap((output) => output?.flags ?? []);
  const conflictFlag = buildConflictFlag(agentOutputs.financial, agentOutputs.tax);
  const mergedFlags = sortFlags(dedupeFlags(conflictFlag ? [...allFlags, conflictFlag] : allFlags));
  const { validatedSDE, sdeConflict } = computeValidatedSDE(agentOutputs, financialData);

  return {
    financialData,
    questionnaire,
    dealInfo,
    agentOutputs,
    mergedFlags,
    validatedSDE,
    sdeConflict,
    dataCompleteness: financialData.dataCompleteness,
  };
}
