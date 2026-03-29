import type {
  QuestionnaireData,
  FinancialData,
  RiskDimensionScore,
} from './types';

export interface RiskScoreResult {
  dimensions: RiskDimensionScore[];
  overallScore: number;
  transferabilityScore: number;
  dealBreakers: string[];
}

const WEIGHTS = {
  ownerDependence: 0.25,
  customerConcentration: 0.20,
  revenueQuality: 0.20,
  employeeRisk: 0.15,
  supplierRisk: 0.10,
  financialRisk: 0.10,
};

function scoreOwnerDependence(q: QuestionnaireData['ownerDependence']): number {
  let score = 1;
  const salesPct = q.ownerSalesPercentage ?? 50;
  if (salesPct > 80) score += 3;
  else if (salesPct > 50) score += 2;
  else if (salesPct > 25) score += 1;

  if (q.ownerInvolvement === 'full_time') score += 2;
  else if (q.ownerInvolvement === 'part_time') score += 1;
  else if (q.ownerInvolvement === 'unknown') score += 1;

  if (q.ownerHoldsRelationships === true) score += 2;
  else if (q.ownerHoldsRelationships === null) score += 1;

  if (q.survives90DayAbsence === 'no') score += 2;
  else if (q.survives90DayAbsence === 'unlikely') score += 1.5;
  else if (q.survives90DayAbsence === 'unknown') score += 1;

  return Math.min(10, Math.round(score));
}

function scoreCustomerConcentration(q: QuestionnaireData['customerConcentration']): number {
  let score = 1;
  const topPct = q.topCustomerRevenuePercent ?? 20;
  const top5Pct = q.top5CustomersRevenuePercent ?? 50;

  if (topPct > 50) score += 3;
  else if (topPct > 30) score += 2;
  else if (topPct > 20) score += 1;

  if (top5Pct > 80) score += 2;
  else if (top5Pct > 60) score += 1.5;
  else if (top5Pct > 40) score += 1;

  if (q.contractType === 'mostly_handshake') score += 2;
  else if (q.contractType === 'mixed') score += 1;
  else if (q.contractType === 'unknown') score += 1;

  if (q.averageCustomerTenure === 'less_than_1_year') score += 1;
  else if (q.averageCustomerTenure === 'unknown') score += 0.5;

  return Math.min(10, Math.round(score));
}

function scoreRevenueQuality(q: QuestionnaireData['revenueQuality']): number {
  let score = 1;
  const recurring = q.recurringRevenuePercent ?? 30;

  if (recurring < 10) score += 3;
  else if (recurring < 20) score += 2;
  else if (recurring < 40) score += 1;

  if (q.revenueTrend === 'declining') score += 3;
  else if (q.revenueTrend === 'flat') score += 1;
  else if (q.revenueTrend === 'unknown') score += 1;

  if (q.knownUpcomingLosses === true) score += 2;
  else if (q.knownUpcomingLosses === null) score += 1;

  return Math.min(10, Math.round(score));
}

function scoreEmployeeRisk(q: QuestionnaireData['employeeRisk']): number {
  let score = 1;
  const total = q.totalEmployees ?? 5;
  const critical = q.missionCriticalEmployees ?? 2;
  const criticalRatio = total > 0 ? critical / total : 0.5;

  if (criticalRatio > 0.4) score += 2;
  else if (criticalRatio > 0.25) score += 1;

  if (q.hasSOPs === false) score += 2.5;
  else if (q.hasSOPs === null) score += 1.5;

  if (q.hasManagementLayer === false) score += 2;
  else if (q.hasManagementLayer === null) score += 1;

  return Math.min(10, Math.round(score));
}

function scoreSupplierRisk(q: QuestionnaireData['supplierRisk']): number {
  let score = 1;

  if (q.singleSupplierOver30Pct === true) score += 4;
  else if (q.singleSupplierOver30Pct === null) score += 2;

  if (q.supplierAgreementsDocumented === false) score += 3;
  else if (q.supplierAgreementsDocumented === null) score += 1.5;

  if (q.exclusiveVendorRelationships === true) score += 2;
  else if (q.exclusiveVendorRelationships === null) score += 1;

  return Math.min(10, Math.round(score));
}

function scoreFinancialRisk(
  q: QuestionnaireData['financialRisk'],
  financials: FinancialData | null
): number {
  let score = 1;

  if (q.addBacksExceed30Pct === true) score += 3;
  else if (q.hasAddBacks === true) score += 1.5;
  else if (q.hasAddBacks === null) score += 1;

  if (q.pendingLiabilities === true) score += 4;
  else if (q.pendingLiabilities === null) score += 2;

  // Check financial data for red flags
  if (financials?.incomeStatement) {
    const is = financials.incomeStatement;
    if (is.revenueByYear) {
      const years = Object.keys(is.revenueByYear).sort();
      if (years.length >= 2) {
        const last = is.revenueByYear[years[years.length - 1]];
        const prev = is.revenueByYear[years[years.length - 2]];
        if (last < prev) score += 1;
      }
    }
  }

  return Math.min(10, Math.round(score));
}

function labelFromScore(score: number): 'Low' | 'Moderate' | 'High' | 'Critical' {
  if (score <= 3) return 'Low';
  if (score <= 5) return 'Moderate';
  if (score <= 7) return 'High';
  return 'Critical';
}

function keyFactorsOwner(q: QuestionnaireData['ownerDependence']): string[] {
  const factors: string[] = [];
  if ((q.ownerSalesPercentage ?? 0) > 50) factors.push(`Owner generates ${q.ownerSalesPercentage}% of sales`);
  if (q.ownerInvolvement === 'full_time') factors.push('Owner is full-time in operations');
  if (q.ownerHoldsRelationships) factors.push('Key customer relationships held personally by owner');
  if (q.survives90DayAbsence === 'no' || q.survives90DayAbsence === 'unlikely') factors.push('Business unlikely to survive 90-day owner absence');
  return factors.slice(0, 3);
}

function keyFactorsCustomer(q: QuestionnaireData['customerConcentration']): string[] {
  const factors: string[] = [];
  if ((q.topCustomerRevenuePercent ?? 0) > 20) factors.push(`Top customer = ${q.topCustomerRevenuePercent}% of revenue`);
  if ((q.top5CustomersRevenuePercent ?? 0) > 50) factors.push(`Top 5 customers = ${q.top5CustomersRevenuePercent}% of revenue`);
  if (q.contractType === 'mostly_handshake') factors.push('Customer relationships are primarily handshake-based');
  if (q.averageCustomerTenure === 'less_than_1_year') factors.push('Average customer tenure less than 1 year');
  return factors.slice(0, 3);
}

function keyFactorsRevenue(q: QuestionnaireData['revenueQuality']): string[] {
  const factors: string[] = [];
  if ((q.recurringRevenuePercent ?? 0) < 30) factors.push(`Only ${q.recurringRevenuePercent ?? 'unknown'}% of revenue is recurring`);
  if (q.revenueTrend === 'declining') factors.push('Revenue has declined over the past 3 years');
  if (q.revenueTrend === 'flat') factors.push('Revenue has been flat — no growth momentum');
  if (q.knownUpcomingLosses) factors.push('Known upcoming customer losses or contract expirations');
  return factors.slice(0, 3);
}

function keyFactorsEmployee(q: QuestionnaireData['employeeRisk']): string[] {
  const factors: string[] = [];
  if (!q.hasSOPs) factors.push('No documented standard operating procedures (SOPs)');
  if (!q.hasManagementLayer) factors.push('No management layer between owner and staff');
  if ((q.missionCriticalEmployees ?? 0) > 0) factors.push(`${q.missionCriticalEmployees} mission-critical employee(s)`);
  return factors.slice(0, 3);
}

function keyFactorsSupplier(q: QuestionnaireData['supplierRisk']): string[] {
  const factors: string[] = [];
  if (q.singleSupplierOver30Pct) factors.push('Single supplier accounts for >30% of COGS');
  if (!q.supplierAgreementsDocumented) factors.push('Supplier agreements not documented or transferable');
  if (q.exclusiveVendorRelationships) factors.push('Exclusive or hard-to-replace vendor relationships');
  return factors.slice(0, 3);
}

function keyFactorsFinancial(q: QuestionnaireData['financialRisk']): string[] {
  const factors: string[] = [];
  if (q.addBacksExceed30Pct) factors.push('Add-backs exceed 30% of stated EBITDA');
  if (q.pendingLiabilities) factors.push('Pending lawsuits, tax liabilities, or environmental issues');
  if (q.hasAddBacks) factors.push('Seller has presented add-backs to adjusted EBITDA');
  return factors.slice(0, 3);
}

export function computeRiskScores(
  questionnaire: QuestionnaireData,
  financials: FinancialData | null
): RiskScoreResult {
  const ownerScore = scoreOwnerDependence(questionnaire.ownerDependence);
  const customerScore = scoreCustomerConcentration(questionnaire.customerConcentration);
  const revenueScore = scoreRevenueQuality(questionnaire.revenueQuality);
  const employeeScore = scoreEmployeeRisk(questionnaire.employeeRisk);
  const supplierScore = scoreSupplierRisk(questionnaire.supplierRisk);
  const financialScore = scoreFinancialRisk(questionnaire.financialRisk, financials);

  const weightedScore =
    ownerScore * WEIGHTS.ownerDependence +
    customerScore * WEIGHTS.customerConcentration +
    revenueScore * WEIGHTS.revenueQuality +
    employeeScore * WEIGHTS.employeeRisk +
    supplierScore * WEIGHTS.supplierRisk +
    financialScore * WEIGHTS.financialRisk;

  const overallScore = Math.round(weightedScore * 10);

  // Transferability: inverse of owner dependence + process maturity + contract quality + team stability
  const transferabilityRaw =
    (10 - ownerScore) * 0.35 +
    (questionnaire.employeeRisk.hasSOPs ? 10 : 5) * 0.25 +
    (questionnaire.customerConcentration.contractType === 'mostly_contracted' ? 10 : questionnaire.customerConcentration.contractType === 'mixed' ? 6 : 3) * 0.25 +
    (questionnaire.employeeRisk.hasManagementLayer ? 10 : 4) * 0.15;

  const transferabilityScore = Math.round(transferabilityRaw * 10);

  const dimensions: RiskDimensionScore[] = [
    {
      dimension: 'Owner Dependence',
      score: ownerScore,
      label: labelFromScore(ownerScore),
      explanation: `The owner's role in the business ${ownerScore >= 7 ? 'is deeply embedded' : ownerScore >= 5 ? 'is significant' : 'is manageable'}. This measures how much the business relies on the owner personally to generate revenue, maintain customer relationships, and run operations.`,
      keyFactors: keyFactorsOwner(questionnaire.ownerDependence),
      isDealBreaker: ownerScore >= 9,
    },
    {
      dimension: 'Customer Concentration',
      score: customerScore,
      label: labelFromScore(customerScore),
      explanation: `Customer concentration ${customerScore >= 7 ? 'is a serious concern' : customerScore >= 5 ? 'warrants attention' : 'is within acceptable range'}. High concentration means losing one or two clients could severely impact revenue.`,
      keyFactors: keyFactorsCustomer(questionnaire.customerConcentration),
      isDealBreaker: customerScore >= 9,
    },
    {
      dimension: 'Revenue Quality',
      score: revenueScore,
      label: labelFromScore(revenueScore),
      explanation: `Revenue quality ${revenueScore >= 7 ? 'is low — heavily project-based with declining trends' : revenueScore >= 5 ? 'is moderate' : 'is solid with good recurring components'}. Recurring revenue is more predictable and valuable than one-time project work.`,
      keyFactors: keyFactorsRevenue(questionnaire.revenueQuality),
      isDealBreaker: revenueScore >= 9,
    },
    {
      dimension: 'Employee & Operational Risk',
      score: employeeScore,
      label: labelFromScore(employeeScore),
      explanation: `Operational risk ${employeeScore >= 7 ? 'is high — the business lacks documented processes and management depth' : employeeScore >= 5 ? 'is moderate' : 'is well-managed'}. Without SOPs and a management layer, institutional knowledge leaves with the owner.`,
      keyFactors: keyFactorsEmployee(questionnaire.employeeRisk),
      isDealBreaker: employeeScore >= 9,
    },
    {
      dimension: 'Supplier & Vendor Risk',
      score: supplierScore,
      label: labelFromScore(supplierScore),
      explanation: `Supplier risk ${supplierScore >= 7 ? 'is elevated — dependencies on key suppliers could disrupt operations post-acquisition' : supplierScore >= 5 ? 'is moderate' : 'is low'}. Undocumented or non-transferable supplier agreements are a common acquisition pitfall.`,
      keyFactors: keyFactorsSupplier(questionnaire.supplierRisk),
      isDealBreaker: supplierScore >= 9,
    },
    {
      dimension: 'Financial & Add-Back Risk',
      score: financialScore,
      label: labelFromScore(financialScore),
      explanation: `Financial risk ${financialScore >= 7 ? 'is significant — large add-backs or pending liabilities inflate the apparent profitability' : financialScore >= 5 ? 'requires scrutiny' : 'appears manageable'}. Add-backs reduce the stated earnings to normalize for owner-specific expenses.`,
      keyFactors: keyFactorsFinancial(questionnaire.financialRisk),
      isDealBreaker: financialScore >= 9,
    },
  ];

  const dealBreakers = dimensions
    .filter((d) => d.isDealBreaker)
    .map((d) => `${d.dimension}: Score ${d.score}/10 — ${d.keyFactors[0] || 'Critical risk identified'}`);

  return { dimensions, overallScore, transferabilityScore, dealBreakers };
}

export function getRiskLabel(score: number): 'Low' | 'Moderate' | 'High' | 'Very High' {
  if (score <= 35) return 'Low';
  if (score <= 65) return 'Moderate';
  if (score <= 80) return 'High';
  return 'Very High';
}

export function getTransferabilityLabel(score: number): 'High' | 'Moderate' | 'Low' | 'Very Low' {
  if (score >= 65) return 'High';
  if (score >= 40) return 'Moderate';
  if (score >= 20) return 'Low';
  return 'Very Low';
}
