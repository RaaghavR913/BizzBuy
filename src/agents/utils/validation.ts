import { z } from 'zod';

export function validateAgentOutput<T>(
  schema: z.ZodType<T>,
  raw: unknown
): { success: true; data: T } | { success: false; errors: string[] } {
  const result = schema.safeParse(raw);
  if (result.success) {
    return { success: true, data: result.data };
  }
  return { success: false, errors: formatZodErrorsToList(result.error) };
}

export function formatZodErrors(error: z.ZodError): string {
  return error.issues
    .map((issue) => {
      const path = issue.path.length > 0 ? issue.path.join('.') : '(root)';
      return `  - ${path}: ${issue.message}`;
    })
    .join('\n');
}

function formatZodErrorsToList(error: z.ZodError): string[] {
  return error.issues.map((issue) => {
    const path = issue.path.length > 0 ? issue.path.join('.') : '(root)';
    return `${path}: ${issue.message}`;
  });
}

export function createRetryPrompt(
  originalPrompt: string,
  previousOutput: string,
  validationErrors: string
): string {
  return [
    'Your previous output did not pass validation. Please fix the errors and try again.',
    '',
    '## Validation Errors',
    validationErrors,
    '',
    '## Your Previous Output (with errors)',
    '```json',
    previousOutput,
    '```',
    '',
    '## Original Instructions',
    originalPrompt,
    '',
    'Please produce a corrected output that satisfies all validation constraints.',
  ].join('\n');
}
