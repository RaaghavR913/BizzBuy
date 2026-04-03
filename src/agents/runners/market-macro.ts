import Anthropic from '@anthropic-ai/sdk';
import { toJSONSchema } from 'zod';
import type { AgentResult } from '@/src/types/pipeline';
import type { IngestionOutput } from '@/src/agents/schemas/ingestion.schema';
import {
  MarketMacroOutputSchema,
  type MarketMacroOutput,
} from '@/src/agents/schemas/market-macro.schema';
import { validateAgentOutput, createRetryPrompt } from '../utils/validation';
import { loadAgentPrompt } from '../utils/prompt-loader';
import { AGENT_REGISTRY } from '../registry';

const MAX_RETRIES = 2;
const TOOL_NAME = 'structured_output';

const WEB_SEARCH_TOOL = {
  type: 'web_search_20250305' as const,
  name: 'web_search',
} as const;

let clientInstance: Anthropic | null = null;

function getClient(): Anthropic {
  if (!clientInstance) {
    clientInstance = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  }
  return clientInstance;
}

/**
 * Extracts business type from ingestion output by scanning document text for
 * business names, industry keywords, SIC/NAICS codes, and lease descriptions.
 */
function inferBusinessContext(ingestionOutput: IngestionOutput): {
  businessType: string | undefined;
  location: string | undefined;
  revenueRange: string | undefined;
  employeeCount: string | undefined;
} {
  const allText = ingestionOutput.documents
    .flatMap((d) => d.sections)
    .map((s) => s.rawText)
    .join('\n');

  // Heuristic: look for city/state patterns in document text
  const locationMatch = allText.match(
    /\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*([A-Z]{2})\b/
  );
  const location = locationMatch
    ? `${locationMatch[1]}, ${locationMatch[2]}`
    : undefined;

  // Revenue range from extracted financial data
  const revenueValues: number[] = [];
  for (const doc of ingestionOutput.documents) {
    for (const section of doc.sections) {
      const rev = section.extractedData?.revenue ?? section.extractedData?.totalRevenue;
      if (typeof rev === 'number' && rev > 0) {
        revenueValues.push(rev);
      }
    }
  }
  const maxRevenue = revenueValues.length > 0 ? Math.max(...revenueValues) : undefined;
  const revenueRange = maxRevenue
    ? `$${(maxRevenue / 1_000_000).toFixed(1)}M`
    : undefined;

  // Employee count from extracted data
  const employeeCounts: number[] = [];
  for (const doc of ingestionOutput.documents) {
    for (const section of doc.sections) {
      const emp =
        section.extractedData?.employees ?? section.extractedData?.employeeCount;
      if (typeof emp === 'number' && emp > 0) {
        employeeCounts.push(emp);
      }
    }
  }
  const employeeCount =
    employeeCounts.length > 0
      ? `approximately ${Math.max(...employeeCounts)}`
      : undefined;

  // Business type: check document types for clues
  const docTypes = ingestionOutput.documents.map((d) => d.documentType);
  let businessType: string | undefined;
  if (docTypes.includes('lease_agreement')) {
    // Lease docs often name the business — pull from raw text
    const leaseDoc = ingestionOutput.documents.find(
      (d) => d.documentType === 'lease_agreement'
    );
    const leaseText = leaseDoc?.sections[0]?.rawText ?? '';
    const bizMatch = leaseText.match(/(?:Tenant|Lessee):\s*([^\n,]+)/i);
    if (bizMatch) businessType = bizMatch[1].trim();
  }

  return { businessType, location, revenueRange, employeeCount };
}

function buildUserMessage(
  ingestionOutput: IngestionOutput,
  businessContext: { businessType?: string; location?: string }
): string {
  const inferred = inferBusinessContext(ingestionOutput);

  const businessType =
    businessContext.businessType ?? inferred.businessType ?? 'Unknown (infer from documents)';
  const location =
    businessContext.location ?? inferred.location ?? 'Unknown (infer from documents)';

  const financialContext = [
    inferred.revenueRange && `Annual revenue: ~${inferred.revenueRange}`,
    inferred.employeeCount && `Employees: ${inferred.employeeCount}`,
  ]
    .filter(Boolean)
    .join('\n');

  const documentSummary = ingestionOutput.documents
    .map((d) => `- ${d.fileName} (${d.documentType})`)
    .join('\n');

  return `Please research current market conditions, industry trends, and macroeconomic factors relevant to acquiring this business.

## Business Profile
- **Business Type / Industry:** ${businessType}
- **Location:** ${location}
${financialContext ? `\n## Financial Indicators\n${financialContext}` : ''}

## Uploaded Documents
${documentSummary}

## Research Request
Using your web search capability, gather current data on:
1. Industry growth rate and national trends for this business type
2. Local market conditions in ${location}
3. Relevant regulatory changes (2025–2026)
4. Technology disruption risks to this business model
5. Current macroeconomic conditions — especially SBA lending rates (Prime + 2.75%), inflation, and labor market

Then call the structured_output tool with your complete MarketMacroOutput analysis. Provide at least 2 threats and 2 opportunities. Include current SBA lending conditions as a macroeconomic factor.`;
}

/**
 * Market & Macro agent runner.
 *
 * UNIQUE: This is the only agent that uses web search. The web_search tool is a
 * server-side tool — Claude invokes it automatically and the SDK manages the
 * multi-turn loop. We must NOT force tool_choice to structured_output while web
 * search is also configured, because Claude needs to freely call web_search
 * first. We use tool_choice: "auto" and loop until structured_output is called.
 */
export async function runMarketMacro(
  ingestionOutput: IngestionOutput,
  businessContext: { businessType?: string; location?: string } = {}
): Promise<AgentResult<MarketMacroOutput>> {
  const config = AGENT_REGISTRY['market-macro'];
  const client = getClient();
  const startTime = Date.now();

  const systemPrompt = loadAgentPrompt(config.promptFile);

  const jsonSchema = toJSONSchema(MarketMacroOutputSchema);
  const structuredOutputTool: Anthropic.Messages.Tool = {
    name: TOOL_NAME,
    description:
      'Submit the structured market & macro analysis output. You MUST call this tool after completing your web research.',
    input_schema: jsonSchema as Anthropic.Messages.Tool.InputSchema,
  };

  const userMessage = buildUserMessage(ingestionOutput, businessContext);

  let totalInputTokens = 0;
  let totalOutputTokens = 0;
  let lastValidationErrors: string | undefined;
  let currentUserMessage = userMessage;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const messages: Anthropic.Messages.MessageParam[] = [
        { role: 'user', content: currentUserMessage },
      ];

      const response = await client.messages.create({
        model: config.model,
        max_tokens: config.maxTokens ?? 4096,
        system: systemPrompt,
        tools: [WEB_SEARCH_TOOL as unknown as Anthropic.Messages.Tool, structuredOutputTool],
        tool_choice: { type: 'auto' },
        messages,
      });

      totalInputTokens += response.usage?.input_tokens ?? 0;
      totalOutputTokens += response.usage?.output_tokens ?? 0;

      const toolUseBlock = response.content.find(
        (block): block is Anthropic.Messages.ToolUseBlock =>
          block.type === 'tool_use' && block.name === TOOL_NAME
      );

      if (!toolUseBlock) {
        // Claude may have only called web_search in this turn and expects to
        // continue. If stop_reason is "tool_use" without our structured_output,
        // Claude is still working. This case is handled server-side by the SDK
        // for web_search — if we still don't see structured_output by end of
        // stream, treat as a validation failure and retry.
        if (attempt < MAX_RETRIES) {
          currentUserMessage = createRetryPrompt(
            userMessage,
            JSON.stringify(
              response.content
                .filter((b): b is Anthropic.Messages.TextBlock => b.type === 'text')
                .map((b) => b.text)
                .join('\n')
            ),
            'You did not call the structured_output tool. After completing your web research, you MUST call the structured_output tool with your complete MarketMacroOutput.'
          );
          continue;
        }
        return makeError(
          'validation',
          'Claude did not call the structured_output tool after web research',
          attempt,
          config.name
        );
      }

      const rawOutput = toolUseBlock.input;
      const validation = validateAgentOutput(MarketMacroOutputSchema, rawOutput);

      if (validation.success) {
        return {
          status: 'success',
          data: validation.data,
          tokenUsage: { input: totalInputTokens, output: totalOutputTokens },
          latencyMs: Date.now() - startTime,
        };
      }

      lastValidationErrors = validation.errors.join('\n');

      if (attempt < MAX_RETRIES) {
        currentUserMessage = createRetryPrompt(
          userMessage,
          JSON.stringify(rawOutput, null, 2),
          lastValidationErrors
        );
      }
    } catch (err) {
      const isTimeout =
        err instanceof Error && err.message.toLowerCase().includes('timeout');
      const isApi = err instanceof Anthropic.APIError;
      return makeError(
        isTimeout ? 'timeout' : isApi ? 'api' : 'unknown',
        err instanceof Error ? err.message : String(err),
        attempt,
        config.name
      );
    }
  }

  return makeError(
    'validation',
    `Output failed Zod validation after ${MAX_RETRIES + 1} attempts. Last errors:\n${lastValidationErrors}`,
    MAX_RETRIES,
    config.name
  );
}

function makeError(
  errorType: 'validation' | 'api' | 'timeout' | 'unknown',
  message: string,
  retryCount: number,
  agentName: string
): AgentResult<never> {
  return {
    status: 'error',
    error: {
      agentName,
      errorType,
      message,
      timestamp: new Date().toISOString(),
      retryCount,
    },
  };
}
