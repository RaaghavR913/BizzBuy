import { NextRequest, NextResponse } from 'next/server';
import type { AgentOutput, DealInfo, FinancialData, QuestionnaireData } from '@/lib/types';
import {
  calculateDSCR,
  calculateGrossMargin,
  calculateMonthlyPayment,
  calculateSDE,
  calculateValuationMultiple,
  calculateWorkingCapital,
} from '@/lib/calculations';

interface AgentRequest {
  financialData: FinancialData;
  questionnaire: QuestionnaireData;
  dealInfo: DealInfo;
}

function buildFinancialAgentOutput(financialData: FinancialData, dealInfo: DealInfo): AgentOutput {
  const incomeStatement = financialData.incomeStatement;
  const balanceSheet = financialData.balanceSheet;
  const loanTerms = financialData.loanTerms;
  const cashFlow = financialData.cashFlow;

  const revenue = incomeStatement?.revenue ?? 0;
  const cogs = incomeStatement?.cogs ?? 0;
  const grossMargin = calculateGrossMargin(revenue, cogs);
  const operatingExpenses = incomeStatement?.operatingExpenses ?? 0;
  const netIncome = incomeStatement?.netIncome ?? 0;
  const ownerSalary = incomeStatement?.ownerSalary ?? 0;
  const addBacks = incomeStatement?.addBacks?.reduce((sum, item) => sum + item.amount, 0) ?? 0;
  const depreciationAmortization = incomeStatement?.depreciationAmortization ?? 0;
  const interestExpense = incomeStatement?.interestExpense ?? 0;
  const sde = incomeStatement?.sde ?? calculateSDE(netIncome, ownerSalary, addBacks, depreciationAmortization, interestExpense);
  const ebitda = incomeStatement?.ebitda ?? (netIncome + interestExpense + depreciationAmortization);
  const workingCapital = balanceSheet
    ? calculateWorkingCapital(balanceSheet.currentAssets, balanceSheet.currentLiabilities)
    : null;
  const debtToEquity = balanceSheet && balanceSheet.equity > 0
    ? balanceSheet.totalLiabilities / balanceSheet.equity
    : null;
  const annualDebtService = loanTerms
    ? (loanTerms.monthlyPayment ?? calculateMonthlyPayment(loanTerms.loanAmount, loanTerms.interestRate, loanTerms.termMonths || 120)) * 12
    : 0;
  const dscr = annualDebtService > 0 ? calculateDSCR(sde, annualDebtService) : null;
  const valuationMultiple = calculateValuationMultiple(dealInfo.askingPrice || loanTerms?.askingPrice || 0, sde);
  const operatingCashFlow = cashFlow?.operatingCashFlow ?? null;
  const freeCashFlow = cashFlow?.freeCashFlow ?? null;

  const flags: AgentOutput['flags'] = [];
  const notes: string[] = [];

  if (!incomeStatement) {
    flags.push({
      severity: 'critical',
      dimension: 'Financial Quality',
      sourceAgent: 'financial',
      metric: 'incomeStatement',
      message: 'Income statement is missing, which limits all P&L-based analysis.',
    });
  }

  if (grossMargin < 20 && revenue > 0) {
    flags.push({
      severity: 'warning',
      dimension: 'Profitability',
      sourceAgent: 'financial',
      metric: 'grossMargin',
      message: 'Gross margin is below 20%, which leaves limited cushion for debt service and owner income.',
    });
  }

  if (workingCapital !== null && workingCapital < 0) {
    flags.push({
      severity: 'warning',
      dimension: 'Liquidity',
      sourceAgent: 'financial',
      metric: 'workingCapital',
      message: 'Working capital is negative, which may create short-term cash pressure after closing.',
    });
  }

  if (dscr !== null && dscr < 1.25) {
    flags.push({
      severity: dscr < 1 ? 'critical' : 'warning',
      dimension: 'Debt Service',
      sourceAgent: 'financial',
      metric: 'dscr',
      message: dscr < 1
        ? 'Current earnings do not fully cover modeled debt service.'
        : 'Debt coverage is below a typical SBA comfort threshold of 1.25x.',
    });
  }

  if (valuationMultiple !== Infinity && valuationMultiple > 4.5) {
    flags.push({
      severity: 'warning',
      dimension: 'Valuation',
      sourceAgent: 'financial',
      metric: 'valuationMultiple',
      message: 'The asking price is above a typical small-business valuation range relative to SDE.',
    });
  }

  if (!cashFlow) {
    notes.push('Cash flow statement not provided; operating cash conversion could not be validated directly.');
  }

  if (!loanTerms) {
    notes.push('Loan terms missing; DSCR and modeled debt capacity are based on limited financing inputs.');
  }

  const confidence = [
    incomeStatement ? 0.4 : 0,
    balanceSheet ? 0.2 : 0,
    cashFlow ? 0.2 : 0,
    loanTerms ? 0.2 : 0,
  ].reduce((sum, value) => sum + value, 0);

  return {
    agentId: 'financial',
    summary: `Financial agent calculated SDE of ${Math.round(sde)} with ${grossMargin.toFixed(1)}% gross margin${dscr !== null ? ` and DSCR of ${dscr.toFixed(2)}` : ''}.`,
    confidence,
    flags,
    notes,
    metrics: {
      revenue,
      grossMargin: Number(grossMargin.toFixed(2)),
      operatingExpenses,
      netIncome,
      ownerSalary,
      addBacks,
      sde: Math.round(sde),
      ebitda: Math.round(ebitda),
      workingCapital: workingCapital !== null ? Math.round(workingCapital) : null,
      debtToEquity: debtToEquity !== null ? Number(debtToEquity.toFixed(2)) : null,
      annualDebtService: Math.round(annualDebtService),
      dscr: dscr !== null ? Number(dscr.toFixed(2)) : null,
      valuationMultiple: valuationMultiple === Infinity ? null : Number(valuationMultiple.toFixed(2)),
      operatingCashFlow,
      freeCashFlow,
    },
  };
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as AgentRequest;
    const output = buildFinancialAgentOutput(body.financialData, body.dealInfo);
    return NextResponse.json({ success: true, output });
  } catch (error) {
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : 'Financial agent failed' },
      { status: 500 }
    );
  }
}
