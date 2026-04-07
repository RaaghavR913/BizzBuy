import type { IngestionOutput } from '@/src/agents/schemas/ingestion.schema';
import type { OpsTransferabilityOutput } from '@/src/agents/schemas/operations-transferability.schema';
import { OpsTransferabilityOutputSchema } from '@/src/agents/schemas/operations-transferability.schema';
import type { AgentResult } from '@/src/types/pipeline';
import { callAgent } from '@/src/agents/utils/claude-client';
import { loadAgentPrompt } from '@/src/agents/utils/prompt-loader';
import { AGENT_REGISTRY } from '@/src/agents/registry';

interface EmployeeRecord {
  name?: string;
  role?: string;
  hireDate?: string;
  tenureYears?: number;
}

interface EquipmentRecord {
  name?: string;
  estimatedValue?: number;
  age?: string;
  condition?: string;
}

interface InsuranceRecord {
  type?: string;
  annualPremium?: number;
  provider?: string;
}

interface LicenseRecord {
  type?: string;
  holder?: string;
  transferable?: boolean;
}

interface OpsMetrics {
  headcount: number;
  averageTenureYears: number | null;
  totalEquipmentValue: number;
  totalAnnualPremiums: number;
  licenseCount: number;
  transferableLicenseCount: number;
  employees: EmployeeRecord[];
  equipment: EquipmentRecord[];
  insurance: InsuranceRecord[];
  licenses: LicenseRecord[];
}

function parseEmployees(ingestionOutput: IngestionOutput): EmployeeRecord[] {
  const employees: EmployeeRecord[] = [];

  for (const doc of ingestionOutput.documents) {
    if (doc.documentType !== 'employee_roster') continue;

    for (const section of doc.sections) {
      const data = section.extractedData;
      const list: unknown[] =
        (data['employees'] as unknown[]) ??
        (data['roster'] as unknown[]) ??
        (data['rows'] as unknown[]) ??
        [];

      for (const item of list) {
        if (typeof item !== 'object' || item === null) continue;
        const record = item as Record<string, unknown>;
        employees.push({
          name: typeof record['name'] === 'string' ? record['name'] : undefined,
          role:
            typeof record['role'] === 'string'
              ? record['role']
              : typeof record['title'] === 'string'
              ? record['title']
              : undefined,
          hireDate:
            typeof record['hireDate'] === 'string'
              ? record['hireDate']
              : typeof record['hire_date'] === 'string'
              ? record['hire_date']
              : undefined,
          tenureYears:
            typeof record['tenureYears'] === 'number'
              ? record['tenureYears']
              : undefined,
        });
      }
    }
  }

  return employees;
}

function parseEquipment(ingestionOutput: IngestionOutput): EquipmentRecord[] {
  const items: EquipmentRecord[] = [];

  for (const doc of ingestionOutput.documents) {
    if (doc.documentType !== 'equipment_list') continue;

    for (const section of doc.sections) {
      const data = section.extractedData;
      const list: unknown[] =
        (data['equipment'] as unknown[]) ??
        (data['items'] as unknown[]) ??
        (data['rows'] as unknown[]) ??
        [];

      for (const item of list) {
        if (typeof item !== 'object' || item === null) continue;
        const record = item as Record<string, unknown>;
        items.push({
          name: typeof record['name'] === 'string' ? record['name'] : undefined,
          estimatedValue:
            typeof record['estimatedValue'] === 'number'
              ? record['estimatedValue']
              : typeof record['value'] === 'number'
              ? record['value']
              : undefined,
          age:
            typeof record['age'] === 'string'
              ? record['age']
              : typeof record['estimatedAge'] === 'string'
              ? record['estimatedAge']
              : undefined,
          condition:
            typeof record['condition'] === 'string'
              ? record['condition']
              : undefined,
        });
      }
    }
  }

  return items;
}

function parseInsurance(ingestionOutput: IngestionOutput): InsuranceRecord[] {
  const policies: InsuranceRecord[] = [];

  for (const doc of ingestionOutput.documents) {
    if (doc.documentType !== 'insurance_policy') continue;

    for (const section of doc.sections) {
      const data = section.extractedData;

      // Support either a single policy or array
      const list: unknown[] = Array.isArray(data['policies'])
        ? (data['policies'] as unknown[])
        : [data];

      for (const item of list) {
        if (typeof item !== 'object' || item === null) continue;
        const record = item as Record<string, unknown>;
        policies.push({
          type:
            typeof record['type'] === 'string'
              ? record['type']
              : typeof record['policyType'] === 'string'
              ? record['policyType']
              : undefined,
          annualPremium:
            typeof record['annualPremium'] === 'number'
              ? record['annualPremium']
              : typeof record['premium'] === 'number'
              ? record['premium']
              : undefined,
          provider:
            typeof record['provider'] === 'string'
              ? record['provider']
              : typeof record['insurer'] === 'string'
              ? record['insurer']
              : undefined,
        });
      }
    }
  }

  return policies;
}

function parseLicenses(ingestionOutput: IngestionOutput): LicenseRecord[] {
  const licenses: LicenseRecord[] = [];

  for (const doc of ingestionOutput.documents) {
    for (const section of doc.sections) {
      const data = section.extractedData;
      const list: unknown[] = Array.isArray(data['licenses'])
        ? (data['licenses'] as unknown[])
        : [];

      for (const item of list) {
        if (typeof item !== 'object' || item === null) continue;
        const record = item as Record<string, unknown>;
        licenses.push({
          type:
            typeof record['type'] === 'string'
              ? record['type']
              : typeof record['licenseType'] === 'string'
              ? record['licenseType']
              : undefined,
          holder:
            typeof record['holder'] === 'string' ? record['holder'] : undefined,
          transferable:
            typeof record['transferable'] === 'boolean'
              ? record['transferable']
              : undefined,
        });
      }
    }
  }

  return licenses;
}

function computeAverageTenure(employees: EmployeeRecord[]): number | null {
  const knownTenures = employees
    .filter((e) => e.tenureYears !== undefined)
    .map((e) => e.tenureYears as number);

  if (knownTenures.length === 0) {
    // Try to derive from hire dates
    const now = new Date();
    const derived = employees
      .filter((e) => e.hireDate)
      .map((e) => {
        const hire = new Date(e.hireDate!);
        if (isNaN(hire.getTime())) return null;
        return (now.getTime() - hire.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
      })
      .filter((y): y is number => y !== null && y >= 0);

    if (derived.length === 0) return null;
    return derived.reduce((sum, y) => sum + y, 0) / derived.length;
  }

  return knownTenures.reduce((sum, y) => sum + y, 0) / knownTenures.length;
}

function computeOpsMetrics(ingestionOutput: IngestionOutput): OpsMetrics {
  const employees = parseEmployees(ingestionOutput);
  const equipment = parseEquipment(ingestionOutput);
  const insurance = parseInsurance(ingestionOutput);
  const licenses = parseLicenses(ingestionOutput);

  const totalEquipmentValue = equipment.reduce(
    (sum, e) => sum + (e.estimatedValue ?? 0),
    0
  );

  const totalAnnualPremiums = insurance.reduce(
    (sum, p) => sum + (p.annualPremium ?? 0),
    0
  );

  const transferableLicenseCount = licenses.filter(
    (l) => l.transferable === true
  ).length;

  return {
    headcount: employees.length,
    averageTenureYears: computeAverageTenure(employees),
    totalEquipmentValue,
    totalAnnualPremiums,
    licenseCount: licenses.length,
    transferableLicenseCount,
    employees,
    equipment,
    insurance,
    licenses,
  };
}

function buildUserMessage(
  ingestionOutput: IngestionOutput,
  metrics: OpsMetrics,
  hasOperationalDocs: boolean
): string {
  const sections: string[] = [];

  if (!hasOperationalDocs) {
    sections.push(
      '## Data Availability\n\nNo operational documents (employee roster, insurance policies, equipment list) ' +
      'were found in the provided documents. Operations and transferability analysis cannot be fully performed. ' +
      'Please assess with low confidence and note the data gaps.'
    );
  } else {
    sections.push('## Pre-Computed Operational Metrics');
    sections.push(`Total Headcount: ${metrics.headcount}`);
    sections.push(
      metrics.averageTenureYears !== null
        ? `Average Employee Tenure: ${metrics.averageTenureYears.toFixed(1)} years`
        : 'Average Employee Tenure: Not determinable from available data'
    );
    sections.push(`Total Equipment Estimated Value: $${metrics.totalEquipmentValue.toLocaleString()}`);
    sections.push(`Total Annual Insurance Premiums: $${metrics.totalAnnualPremiums.toLocaleString()}`);
    sections.push(`Licenses Found: ${metrics.licenseCount}`);
    sections.push(`Transferable Licenses: ${metrics.transferableLicenseCount} of ${metrics.licenseCount}`);

    if (metrics.employees.length > 0) {
      sections.push('\n## Employee Roster');
      for (const emp of metrics.employees) {
        const tenureStr =
          emp.tenureYears !== undefined
            ? `${emp.tenureYears} yrs tenure`
            : emp.hireDate
            ? `hired ${emp.hireDate}`
            : 'tenure unknown';
        sections.push(`- ${emp.name ?? 'Unknown'} | ${emp.role ?? 'Unknown role'} | ${tenureStr}`);
      }
    }

    if (metrics.equipment.length > 0) {
      sections.push('\n## Equipment List');
      for (const item of metrics.equipment) {
        const value = item.estimatedValue !== undefined
          ? `$${item.estimatedValue.toLocaleString()}`
          : 'value unknown';
        sections.push(
          `- ${item.name ?? 'Unknown'} | ${value} | age: ${item.age ?? 'unknown'} | condition: ${item.condition ?? 'unknown'}`
        );
      }
    }

    if (metrics.insurance.length > 0) {
      sections.push('\n## Insurance Policies');
      for (const policy of metrics.insurance) {
        const premium = policy.annualPremium !== undefined
          ? `$${policy.annualPremium.toLocaleString()}/yr`
          : 'premium unknown';
        sections.push(
          `- ${policy.type ?? 'Unknown'} | ${policy.provider ?? 'Unknown provider'} | ${premium}`
        );
      }
    }

    if (metrics.licenses.length > 0) {
      sections.push('\n## Licenses & Certifications');
      for (const lic of metrics.licenses) {
        const transferStr =
          lic.transferable === true
            ? 'Transferable'
            : lic.transferable === false
            ? 'NOT transferable'
            : 'Transferability unknown';
        sections.push(
          `- ${lic.type ?? 'Unknown'} | Held by: ${lic.holder ?? 'unknown'} | ${transferStr}`
        );
      }
    }
  }

  // Include raw document text for qualitative LLM analysis
  const opsDocs = ingestionOutput.documents.filter((d) =>
    ['employee_roster', 'insurance_policy', 'equipment_list', 'other'].includes(
      d.documentType
    )
  );
  if (opsDocs.length > 0) {
    sections.push('\n## Raw Document Data');
    for (const doc of opsDocs) {
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

export async function runOpsTransferability(
  ingestionOutput: IngestionOutput
): Promise<AgentResult<OpsTransferabilityOutput>> {
  const config = AGENT_REGISTRY['operations-transferability'];
  const systemPrompt = loadAgentPrompt('operations-transferability');

  const hasEmployeeRoster = ingestionOutput.documents.some(
    (d) => d.documentType === 'employee_roster'
  );
  const hasInsurance = ingestionOutput.documents.some(
    (d) => d.documentType === 'insurance_policy'
  );
  const hasEquipment = ingestionOutput.documents.some(
    (d) => d.documentType === 'equipment_list'
  );
  const hasOperationalDocs = hasEmployeeRoster || hasInsurance || hasEquipment;

  const metrics = computeOpsMetrics(ingestionOutput);
  const userMessage = buildUserMessage(ingestionOutput, metrics, hasOperationalDocs);

  return callAgent<OpsTransferabilityOutput>({
    model: config.model,
    systemPrompt,
    userMessage,
    schema: OpsTransferabilityOutputSchema,
    maxTokens: config.maxTokens,
  });
}
