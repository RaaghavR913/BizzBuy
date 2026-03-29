import { NextRequest, NextResponse } from 'next/server';
import type { AgentOutput, DealInfo, FinancialData, QuestionnaireData } from '@/lib/types';

interface AgentRequest {
  financialData: FinancialData;
  questionnaire: QuestionnaireData;
  dealInfo: DealInfo;
}

function buildOperationsOutput(financialData: FinancialData, questionnaire: QuestionnaireData): AgentOutput {
  const employeeRisk = questionnaire.employeeRisk;
  const supplierRisk = questionnaire.supplierRisk;
  const totalEmployees = employeeRisk.totalEmployees ?? 0;
  const criticalEmployees = employeeRisk.missionCriticalEmployees ?? 0;
  const criticalEmployeeRatio = totalEmployees > 0 ? criticalEmployees / totalEmployees : null;

  const processMaturityScore = employeeRisk.hasSOPs === true ? 85 : employeeRisk.hasSOPs === false ? 35 : 50;
  const managementDepthScore = employeeRisk.hasManagementLayer === true ? 80 : employeeRisk.hasManagementLayer === false ? 30 : 50;
  const supplierDependencyScore =
    supplierRisk.singleSupplierOver30Pct === true ? 75 :
      supplierRisk.singleSupplierOver30Pct === false ? 30 : 50;
  const ppeCoverageScore = financialData.balanceSheet?.totalAssets
    ? Math.min(100, Math.round(((financialData.balanceSheet.inventory ?? 0) / financialData.balanceSheet.totalAssets) * 100))
    : null;
  const operationsRiskScore = Math.round(
    ((100 - processMaturityScore) * 0.35) +
    ((100 - managementDepthScore) * 0.3) +
    (supplierDependencyScore * 0.2) +
    ((criticalEmployeeRatio ?? 0.25) * 100 * 0.15)
  );

  const flags: AgentOutput['flags'] = [];
  const notes: string[] = [];

  if (employeeRisk.hasSOPs === false) {
    flags.push({
      severity: 'warning',
      dimension: 'Operations',
      sourceAgent: 'operations',
      metric: 'hasSOPs',
      message: 'Documented SOPs are missing, increasing transfer risk and onboarding burden for a buyer.',
    });
  }

  if (employeeRisk.hasManagementLayer === false) {
    flags.push({
      severity: 'warning',
      dimension: 'Operations',
      sourceAgent: 'operations',
      metric: 'hasManagementLayer',
      message: 'There is no management layer between the owner and frontline staff.',
    });
  }

  if ((criticalEmployeeRatio ?? 0) > 0.4) {
    flags.push({
      severity: 'warning',
      dimension: 'Employees',
      sourceAgent: 'operations',
      metric: 'criticalEmployeeRatio',
      message: 'A large share of the workforce appears mission-critical, which raises continuity risk.',
    });
  }

  if (supplierRisk.singleSupplierOver30Pct === true) {
    flags.push({
      severity: 'warning',
      dimension: 'Vendor Dependence',
      sourceAgent: 'operations',
      metric: 'singleSupplierOver30Pct',
      message: 'Operations depend heavily on a single supplier representing more than 30% of spend or workflow.',
    });
  }

  if (ppeCoverageScore === null) {
    notes.push('PP&E is not separately broken out in the structured financial data, so asset-condition analysis is limited.');
  }

  return {
    agentId: 'operations',
    summary: `Operations agent estimated an operations risk score of ${operationsRiskScore}, driven by process maturity of ${processMaturityScore} and management depth of ${managementDepthScore}.`,
    confidence: 0.7,
    flags,
    notes,
    metrics: {
      processMaturityScore,
      managementDepthScore,
      supplierDependencyScore,
      criticalEmployeeRatio: criticalEmployeeRatio !== null ? Math.round(criticalEmployeeRatio * 100) / 100 : null,
      ppeCoverageScore,
      operationsRiskScore,
    },
  };
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as AgentRequest;
    const output = buildOperationsOutput(body.financialData, body.questionnaire);
    return NextResponse.json({ success: true, output });
  } catch (error) {
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : 'Operations agent failed' },
      { status: 500 }
    );
  }
}
