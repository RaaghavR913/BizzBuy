import fs from 'fs';
import path from 'path';

const cache = new Map<string, string>();

/**
 * Loads a markdown prompt file from src/agents/prompts/ and performs
 * {{variable}} template interpolation. Results are cached in memory.
 */
export function loadAgentPrompt(
  agentName: string,
  variables?: Record<string, string>
): string {
  const cacheKey = variables
    ? `${agentName}::${JSON.stringify(variables)}`
    : agentName;

  const cached = cache.get(cacheKey);
  if (cached) return cached;

  const filePath = path.join(
    process.cwd(),
    'src',
    'agents',
    'prompts',
    agentName + '.md'
  );

  let content: string;
  try {
    content = fs.readFileSync(filePath, 'utf-8');
  } catch (err) {
    throw new Error(
      `Failed to load prompt for agent "${agentName}" at ${filePath}: ${
        err instanceof Error ? err.message : String(err)
      }`
    );
  }

  if (variables) {
    content = interpolate(content, variables);
  }

  cache.set(cacheKey, content);
  return content;
}

function interpolate(
  template: string,
  variables: Record<string, string>
): string {
  return template.replace(/\{\{(\w+)\}\}/g, (match, key: string) => {
    if (key in variables) return variables[key];
    return match;
  });
}
