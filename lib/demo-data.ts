import type { FinancialData } from './types';

export const DEMO_FINANCIAL_DATA: FinancialData = {
  incomeStatement: {
    revenue: 850000,
    cogs: 340000,
    grossProfit: 510000,
    operatingExpenses: 280000,
    depreciationAmortization: 18000,
    interestExpense: 0,
    netIncome: 212000,
    ownerSalary: 95000,
    addBacks: [
      { description: 'Owner salary', amount: 95000, category: 'owner_salary' },
      { description: 'Personal vehicle (partial)', amount: 8400, category: 'personal_expense' },
      { description: 'One-time equipment repair', amount: 12500, category: 'one_time_expense' },
    ],
    sde: 327900,
    ebitda: 230000,
    periods: ['2022', '2023', '2024'],
    revenueByYear: { '2022': 790000, '2023': 825000, '2024': 850000 },
    netIncomeByYear: { '2022': 180000, '2023': 195000, '2024': 212000 },
  },
  balanceSheet: {
    currentAssets: 120000,
    cashAndEquivalents: 45000,
    accountsReceivable: 62000,
    inventory: 13000,
    currentLiabilities: 85000,
    accountsPayable: 38000,
    totalAssets: 450000,
    totalLiabilities: 200000,
    equity: 250000,
  },
  loanTerms: {
    loanAmount: 600000,
    interestRate: 0.085,
    termMonths: 120,
    monthlyPayment: 7432,
    downPayment: 150000,
    askingPrice: 750000,
    loanType: 'sba_7a',
  },
  cashFlow: null,
  parsingNotes: [],
  dataCompleteness: 0.85,
};

