export const RISK_WEIGHTS = {
  ownerDependence: 0.25,
  customerConcentration: 0.2,
  revenueQuality: 0.2,
  employeeRisk: 0.15,
  supplierRisk: 0.1,
  financialRisk: 0.1,
};

export const RISK_THRESHOLDS = {
  dscr: {
    critical: 1.0,
    warning: 1.25,
    good: 1.5,
    excellent: 2.0,
  },
  valuationMultiple: {
    attractive: 2.0,
    market: 3.5,
    premium: 4.5,
  },
  addBacksPercent: 30,
  topCustomerConcentration: 30,
  top5Concentration: 70,
  recurringRevenueMin: 20,
};

export const RISK_SCORE_COLORS = {
  low: { bg: 'bg-emerald-100', text: 'text-emerald-700', border: 'border-emerald-300', hex: '#10b981' },
  moderate: { bg: 'bg-yellow-100', text: 'text-yellow-700', border: 'border-yellow-300', hex: '#f59e0b' },
  high: { bg: 'bg-orange-100', text: 'text-orange-700', border: 'border-orange-300', hex: '#f97316' },
  veryHigh: { bg: 'bg-red-100', text: 'text-red-700', border: 'border-red-300', hex: '#ef4444' },
};

export const RECOMMENDATION_COLORS = {
  proceed: { bg: 'bg-emerald-600', text: 'text-white', label: 'Proceed' },
  proceed_with_caution: { bg: 'bg-yellow-500', text: 'text-white', label: 'Proceed with Caution' },
  walk_away: { bg: 'bg-red-600', text: 'text-white', label: 'Walk Away' },
};

export const BUSINESS_TYPES = [
  { value: 'home_services', label: 'Home Services (HVAC, Plumbing, Electrical)' },
  { value: 'restaurant', label: 'Restaurant / Food & Beverage' },
  { value: 'retail', label: 'Retail Store' },
  { value: 'ecommerce', label: 'E-Commerce' },
  { value: 'professional_services', label: 'Professional Services (Consulting, Accounting)' },
  { value: 'healthcare', label: 'Healthcare / Medical Practice' },
  { value: 'auto_services', label: 'Auto Services / Car Repair' },
  { value: 'fitness', label: 'Fitness / Gym' },
  { value: 'childcare', label: 'Childcare / Education' },
  { value: 'manufacturing', label: 'Manufacturing / Production' },
  { value: 'distribution', label: 'Distribution / Logistics' },
  { value: 'construction', label: 'Construction / Contracting' },
  { value: 'technology', label: 'Technology / Software / SaaS' },
  { value: 'franchise', label: 'Franchise' },
  { value: 'other', label: 'Other' },
];

export const CANONICAL_DOCUMENT_TYPES = [
  // Financial Statements
  { value: 'profit_and_loss',            label: 'Profit & Loss Statement',                        group: 'Financial Statements' },
  { value: 'balance_sheet',              label: 'Balance Sheet',                                   group: 'Financial Statements' },
  { value: 'cash_flow_statement',        label: 'Cash Flow Statement',                             group: 'Financial Statements' },
  { value: 'sde_worksheet',              label: 'SDE / Seller\'s Discretionary Earnings Worksheet', group: 'Financial Statements' },
  { value: 'financial_projections',      label: 'Financial Projections',                           group: 'Financial Statements' },
  { value: 'bank_statement',             label: 'Bank Statement',                                  group: 'Financial Statements' },
  { value: 'aged_trial_balance',         label: 'Aged Trial Balance',                              group: 'Financial Statements' },
  // Tax
  { value: 'tax_return_1120s',           label: 'Tax Return 1120-S',                               group: 'Tax' },
  { value: 'tax_return_1040',            label: 'Tax Return 1040',                                 group: 'Tax' },
  { value: 'tax_return_schedule_c',      label: 'Tax Return Schedule C',                           group: 'Tax' },
  { value: 'tax_return_1065',            label: 'Tax Return 1065 (Partnership)',                   group: 'Tax' },
  { value: 'sales_tax_filing',           label: 'Sales Tax Filings',                               group: 'Tax' },
  { value: 'payroll_tax_941',            label: 'Payroll Tax Filing (941)',                        group: 'Tax' },
  // Receivables & Customers
  { value: 'ar_aging_report',            label: 'A/R Aging Report',                                group: 'Receivables & Customers' },
  { value: 'customer_list',              label: 'Customer List',                                   group: 'Receivables & Customers' },
  { value: 'top_customer_concentration', label: 'Top Customer Concentration Report',               group: 'Receivables & Customers' },
  // Contracts & Legal
  { value: 'contract',                   label: 'Contract',                                        group: 'Contracts & Legal' },
  { value: 'lease_agreement',            label: 'Lease Agreement',                                 group: 'Contracts & Legal' },
  { value: 'letter_of_intent',           label: 'Letter of Intent (LOI)',                          group: 'Contracts & Legal' },
  { value: 'asset_purchase_agreement',   label: 'Asset Purchase Agreement (APA)',                  group: 'Contracts & Legal' },
  { value: 'operating_agreement',        label: 'Operating Agreement',                             group: 'Contracts & Legal' },
  { value: 'franchise_agreement',        label: 'Franchise Agreement',                             group: 'Contracts & Legal' },
  { value: 'employment_agreement',       label: 'Employment Agreement',                            group: 'Contracts & Legal' },
  { value: 'non_compete_nda',            label: 'Non-Compete / NDA',                               group: 'Contracts & Legal' },
  // Operational
  { value: 'employee_roster',            label: 'Employee Roster',                                 group: 'Operational' },
  { value: 'insurance_policy',           label: 'Insurance Policy',                                group: 'Operational' },
  { value: 'equipment_list',             label: 'Equipment List',                                  group: 'Operational' },
  { value: 'supplier_vendor_list',       label: 'Supplier / Vendor List',                          group: 'Operational' },
  { value: 'permits_licenses',           label: 'Permits & Licenses',                              group: 'Operational' },
  { value: 'business_overview_memo',     label: 'Business Overview / Offering Memo',               group: 'Operational' },
  // Financing
  { value: 'loan_term_sheet',            label: 'Loan Term Sheet / Offer Letter',                  group: 'Financing' },
  { value: 'personal_financial_statement', label: 'Personal Financial Statement',                  group: 'Financing' },
  // Other
  { value: 'other',                      label: 'Other',                                           group: 'Other' },
  { value: 'unknown',                    label: 'Unknown',                                         group: 'Other' },
] as const;

// Legacy upload options remain in place until the pipeline-first document flow is switched over.
export const DOCUMENT_TYPES = [
  { value: 'income_statement', label: 'Income Statement / P&L' },
  { value: 'balance_sheet', label: 'Balance Sheet' },
  { value: 'cash_flow', label: 'Cash Flow Statement' },
  { value: 'loan_terms', label: 'Loan Term Sheet / Offer Letter' },
  { value: 'tax_return', label: 'Tax Return (Schedule C / Business)' },
];

export const ANALYSIS_VERSION = '1.0.0';

export const DISCLAIMERS = [
  'This analysis is generated by AI and is intended for informational purposes only.',
  'It does not constitute financial, legal, or investment advice.',
  'Financial calculations are deterministic and based solely on the data provided.',
  'Consult qualified professionals (accountant, attorney, business broker) before making any acquisition decision.',
  'AI-generated narrative sections reflect patterns in the provided data and should be independently verified.',
];
