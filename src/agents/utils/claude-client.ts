import Anthropic from '@anthropic-ai/sdk';
import { type z, toJSONSchema } from 'zod';
import type { AgentResult, AgentError } from '@/src/types/pipeline';
import {
  validateAgentOutput,
  createRetryPrompt,
} from './validation';

const TOOL_NAME = 'structured_output';
const MAX_RETRIES = 2;

let clientInstance: Anthropic | null = null;

function getClient(): Anthropic {
  if (!clientInstance) {
    clientInstance = new Anthropic({
      apiKey: process.env.ANTHROPIC_API_KEY,
    });
  }
  return clientInstance;
}

export interface CallAgentOptions<T> {
  model: string;
  systemPrompt: string;
  userMessage: string;
  schema: z.ZodType<T>;
  maxTokens?: number;
  tools?: Anthropic.Messages.Tool[];
  temperature?: number;
}

/**
 * Calls the Claude API with structured output via tool-use pattern.
 * Converts the Zod schema to JSON Schema and sends it as a tool definition,
 * forcing Claude to "call" the tool with validated structured output.
 * Includes automatic retry (up to 2) if Zod validation fails.
 */
export async function callAgent<T>(
  options: CallAgentOptions<T>
): Promise<AgentResult<T>> {
  const {
    model,
    systemPrompt,
    userMessage,
    schema,
    maxTokens = 4096,
    tools: extraTools = [],
    temperature = 0,
  } = options;

  const client = getClient();
  const startTime = Date.now();

  const jsonSchema = toJSONSchema(schema);

  const structuredOutputTool: Anthropic.Messages.Tool = {
    name: TOOL_NAME,
    description:
      'Submit the structured analysis output. You MUST call this tool with your complete analysis.',
    input_schema: jsonSchema as Anthropic.Messages.Tool.InputSchema,
  };

  const allTools = [structuredOutputTool, ...extraTools];

  let lastOutput: string | undefined;
  let lastValidationErrors: string | undefined;
  let currentUserMessage = userMessage;
  let totalInputTokens = 0;
  let totalOutputTokens = 0;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await client.messages.create({
        model,
        max_tokens: maxTokens,
        temperature,
        system: systemPrompt,
        tools: allTools,
        tool_choice: { type: 'tool', name: TOOL_NAME },
        messages: [{ role: 'user', content: currentUserMessage }],
      });

      totalInputTokens += response.usage?.input_tokens ?? 0;
      totalOutputTokens += response.usage?.output_tokens ?? 0;

      const toolUseBlock = response.content.find(
        (block): block is Anthropic.Messages.ToolUseBlock =>
          block.type === 'tool_use' && block.name === TOOL_NAME
      );

      if (!toolUseBlock) {
        const errorResult = makeError(
          'validation',
          'Claude did not produce a tool_use block with structured output',
          attempt,
          model
        );
        if (attempt < MAX_RETRIES) {
          currentUserMessage = createRetryPrompt(
            userMessage,
            JSON.stringify(
              response.content
                .filter(
                  (b): b is Anthropic.Messages.TextBlock => b.type === 'text'
                )
                .map((b) => b.text)
                .join('\n')
            ),
            'No structured output tool call was found in your response. You MUST call the structured_output tool.'
          );
          continue;
        }
        return errorResult;
      }

      const rawOutput = toolUseBlock.input;
      lastOutput = JSON.stringify(rawOutput, null, 2);

      const validation = validateAgentOutput(schema, rawOutput);
      if (validation.success) {
        return {
          status: 'success',
          data: validation.data,
          tokenUsage: {
            input: totalInputTokens,
            output: totalOutputTokens,
          },
          latencyMs: Date.now() - startTime,
        };
      }

      lastValidationErrors = validation.errors.join('\n');

      if (attempt < MAX_RETRIES) {
        currentUserMessage = createRetryPrompt(
          userMessage,
          lastOutput,
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
        model
      );
    }
  }

  return makeError(
    'validation',
    `Output failed Zod validation after ${MAX_RETRIES + 1} attempts. Last errors:\n${lastValidationErrors}`,
    MAX_RETRIES,
    model
  );
}

function makeError(
  errorType: AgentError['errorType'],
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
