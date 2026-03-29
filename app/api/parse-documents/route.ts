import { NextRequest, NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';
import Papa from 'papaparse';
import type { FinancialData, LoanTerms } from '@/lib/types';
import {
  DOCUMENT_EXTRACTION_PROMPT,
  INCOME_STATEMENT_SCHEMA,
  BALANCE_SHEET_SCHEMA,
  LOAN_TERMS_SCHEMA,
  CASH_FLOW_SCHEMA,
} from '@/lib/prompts';

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

function getSchemaForType(docType: string): string {
  switch (docType) {
    case 'income_statement': return INCOME_STATEMENT_SCHEMA;
    case 'balance_sheet': return BALANCE_SHEET_SCHEMA;
    case 'loan_terms': return LOAN_TERMS_SCHEMA;
    case 'cash_flow': return CASH_FLOW_SCHEMA;
    default: return INCOME_STATEMENT_SCHEMA;
  }
}

function labelForDocType(docType: string): string {
  const labels: Record<string, string> = {
    income_statement: 'Income Statement / Profit & Loss',
    balance_sheet: 'Balance Sheet',
    loan_terms: 'Loan Term Sheet / Offer Letter',
    cash_flow: 'Cash Flow Statement',
    tax_return: 'Tax Return',
  };
  return labels[docType] ?? 'Financial Document';
}

async function parseCSV(text: string, docType: string): Promise<Record<string, unknown>> {
  const parsed = Papa.parse(text, { header: true, skipEmptyLines: true });
  const prompt = DOCUMENT_EXTRACTION_PROMPT(labelForDocType(docType), getSchemaForType(docType));

  const response = await client.messages.create({
    model: 'claude-opus-4-5',
    max_tokens: 2000,
    messages: [
      {
        role: 'user',
        content: `${prompt}\n\nCSV DATA:\n${JSON.stringify(parsed.data, null, 2)}`,
      },
    ],
  });

  const text2 = response.content[0].type === 'text' ? response.content[0].text : '{}';
  return JSON.parse(text2);
}

async function parseDocumentWithClaude(
  fileBuffer: Buffer,
  mimeType: string,
  docType: string
): Promise<Record<string, unknown>> {
  const base64 = fileBuffer.toString('base64');
  const prompt = DOCUMENT_EXTRACTION_PROMPT(labelForDocType(docType), getSchemaForType(docType));

  const isPDF = mimeType === 'application/pdf' || mimeType.includes('pdf');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const contentBlock: any = isPDF
    ? {
        type: 'document',
        source: { type: 'base64', media_type: 'application/pdf', data: base64 },
      }
    : {
        type: 'image',
        source: {
          type: 'base64',
          media_type: mimeType as 'image/png' | 'image/jpeg' | 'image/webp' | 'image/gif',
          data: base64,
        },
      };

  const response = await client.messages.create({
    model: 'claude-opus-4-5',
    max_tokens: 2000,
    messages: [
      {
        role: 'user',
        content: [contentBlock, { type: 'text', text: prompt }],
      },
    ],
  });

  const text = response.content[0].type === 'text' ? response.content[0].text : '{}';
  const clean = text.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  return JSON.parse(clean);
}

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const files = formData.getAll('files') as File[];
    const fileTypesRaw = formData.get('fileTypes') as string;
    const fileTypes: string[] = fileTypesRaw ? JSON.parse(fileTypesRaw) : [];

    if (!files.length) {
      return NextResponse.json({ success: false, error: 'No files provided' }, { status: 400 });
    }

    const result: FinancialData = {
      incomeStatement: null,
      balanceSheet: null,
      loanTerms: null,
      cashFlow: null,
      parsingNotes: [],
      dataCompleteness: 0,
    };

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const docType = fileTypes[i] ?? 'income_statement';

      try {
        let extracted: Record<string, unknown>;

        if (file.type === 'text/csv' || file.name.endsWith('.csv')) {
          const text = await file.text();
          extracted = await parseCSV(text, docType);
        } else {
          const buffer = Buffer.from(await file.arrayBuffer());
          extracted = await parseDocumentWithClaude(buffer, file.type || 'application/pdf', docType);
        }

        const notes: string[] = (extracted.parsingNotes as string[]) ?? [];
        result.parsingNotes.push(...notes);

        switch (docType) {
          case 'income_statement':
          case 'tax_return':
            result.incomeStatement = {
              revenue: (extracted.revenue as number) ?? 0,
              cogs: (extracted.cogs as number) ?? 0,
              grossProfit: (extracted.grossProfit as number) ?? (((extracted.revenue as number) ?? 0) - ((extracted.cogs as number) ?? 0)),
              operatingExpenses: (extracted.operatingExpenses as number) ?? 0,
              netIncome: (extracted.netIncome as number) ?? 0,
              ownerSalary: extracted.ownerSalary as number | undefined,
              depreciationAmortization: extracted.depreciationAmortization as number | undefined,
              addBacks: extracted.addBacks as FinancialData['incomeStatement'] extends null ? never : NonNullable<FinancialData['incomeStatement']>['addBacks'],
              sde: extracted.sde as number | undefined,
              ebitda: extracted.ebitda as number | undefined,
              periods: (extracted.periods as string[]) ?? [],
              revenueByYear: extracted.revenueByYear as Record<string, number> | undefined,
              netIncomeByYear: extracted.netIncomeByYear as Record<string, number> | undefined,
              // @ts-expect-error confidence stored for UI display
              confidence: extracted.confidence,
            };
            break;
          case 'balance_sheet':
            result.balanceSheet = {
              currentAssets: (extracted.currentAssets as number) ?? 0,
              currentLiabilities: (extracted.currentLiabilities as number) ?? 0,
              totalAssets: (extracted.totalAssets as number) ?? 0,
              totalLiabilities: (extracted.totalLiabilities as number) ?? 0,
              equity: (extracted.equity as number) ?? 0,
              cashAndEquivalents: extracted.cashAndEquivalents as number | undefined,
              accountsReceivable: extracted.accountsReceivable as number | undefined,
              inventory: extracted.inventory as number | undefined,
              accountsPayable: extracted.accountsPayable as number | undefined,
            };
            break;
          case 'loan_terms':
            result.loanTerms = {
              loanAmount: (extracted.loanAmount as number) ?? 0,
              interestRate: (extracted.interestRate as number) ?? 0,
              termMonths: (extracted.termMonths as number) ?? 0,
              monthlyPayment: extracted.monthlyPayment as number | undefined,
              downPayment: extracted.downPayment as number | undefined,
              askingPrice: (extracted.askingPrice as number) ?? 0,
              loanType: extracted.loanType as LoanTerms['loanType'],
            };
            break;
          case 'cash_flow':
            result.cashFlow = {
              operatingCashFlow: (extracted.operatingCashFlow as number) ?? 0,
              netCashFlow: (extracted.netCashFlow as number) ?? 0,
              investingCashFlow: extracted.investingCashFlow as number | undefined,
              financingCashFlow: extracted.financingCashFlow as number | undefined,
              capitalExpenditures: extracted.capitalExpenditures as number | undefined,
              freeCashFlow: extracted.freeCashFlow as number | undefined,
            };
            break;
        }
      } catch (err) {
        result.parsingNotes.push(
          `Could not parse ${file.name}: ${err instanceof Error ? err.message : 'Unknown error'}. Please enter values manually.`
        );
      }
    }

    // Calculate data completeness
    let filled = 0;
    if (result.incomeStatement) filled += 0.5;
    if (result.balanceSheet) filled += 0.25;
    if (result.loanTerms) filled += 0.15;
    if (result.cashFlow) filled += 0.1;
    result.dataCompleteness = filled;

    return NextResponse.json({ success: true, extractedData: result });
  } catch (err) {
    console.error('Parse error:', err);
    return NextResponse.json(
      { success: false, error: err instanceof Error ? err.message : 'Failed to parse documents' },
      { status: 500 }
    );
  }
}
