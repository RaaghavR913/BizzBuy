'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronRight, ChevronLeft, Info, AlertCircle, Plus, Trash2 } from 'lucide-react';
import { useAnalysis } from '@/context/AnalysisContext';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { FinancialData, IncomeStatement, BalanceSheet, LoanTerms, AddBack } from '@/lib/types';
import { formatCurrency } from '@/lib/calculations';

function NumericInput({
  label,
  value,
  onChange,
  hint,
  prefix = '$',
}: {
  label: string;
  value: number | null | undefined;
  onChange: (v: number | null) => void;
  hint?: string;
  prefix?: string;
}) {
  const [raw, setRaw] = useState(value?.toString() ?? '');

  useEffect(() => {
    setRaw(value?.toString() ?? '');
  }, [value]);

  return (
    <div className="space-y-1.5">
      <Label className="text-sm font-medium text-t-secondary">{label}</Label>
      <div className="relative">
        {prefix && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-t-muted text-sm">{prefix}</span>
        )}
        <Input
          type="number"
          value={raw}
          onChange={(e) => {
            setRaw(e.target.value);
            const num = parseFloat(e.target.value);
            onChange(isNaN(num) ? null : num);
          }}
          className={`bg-raised border-white/[0.08] text-white placeholder:text-t-muted focus:ring-accent/50 focus:border-accent/30 ${prefix ? 'pl-7' : ''}`}
          placeholder="0"
        />
      </div>
      {hint && <p className="text-xs text-t-muted">{hint}</p>}
    </div>
  );
}

function ConfidenceBadge({ confidence }: { confidence?: number }) {
  if (!confidence) return null;
  const pct = Math.round(confidence * 100);
  const color = pct >= 85 ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' :
    pct >= 70 ? 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20' :
      'text-red-400 bg-red-500/10 border-red-500/20';
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded border font-medium ${color}`}>
      <Info className="w-3 h-3" />
      {pct}% confidence — please verify
    </span>
  );
}

export default function ReviewPage() {
  const router = useRouter();
  const { state, setFinancialData, setDealInfo, setStep } = useAnalysis();
  const [data, setData] = useState<FinancialData>(
    state.financialData ?? {
      incomeStatement: null,
      balanceSheet: null,
      loanTerms: null,
      cashFlow: null,
      parsingNotes: [],
      dataCompleteness: 0,
    }
  );
  const [askingPrice, setAskingPrice] = useState(
    state.dealInfo?.askingPrice ?? state.financialData?.loanTerms?.askingPrice ?? null
  );
  const [businessType, setBusinessType] = useState(state.dealInfo?.businessType ?? '');
  const [yearsOp, setYearsOp] = useState<number | null>(state.dealInfo?.yearsInOperation ?? null);
  const [reasonForSale, setReasonForSale] = useState(state.dealInfo?.reasonForSale ?? '');

  useEffect(() => {
    setStep(2);
  }, [setStep]);

  function updateIS(updates: Partial<IncomeStatement>) {
    setData((prev) => ({
      ...prev,
      incomeStatement: {
        revenue: 0, cogs: 0, grossProfit: 0, operatingExpenses: 0, netIncome: 0, periods: [],
        ...(prev.incomeStatement ?? {}),
        ...updates,
      },
    }));
  }

  function updateBS(updates: Partial<BalanceSheet>) {
    setData((prev) => ({
      ...prev,
      balanceSheet: {
        currentAssets: 0, currentLiabilities: 0, totalAssets: 0, totalLiabilities: 0, equity: 0,
        ...(prev.balanceSheet ?? {}),
        ...updates,
      },
    }));
  }

  function updateLT(updates: Partial<LoanTerms>) {
    setData((prev) => ({
      ...prev,
      loanTerms: {
        loanAmount: 0, interestRate: 0, termMonths: 0, askingPrice: askingPrice ?? 0,
        ...(prev.loanTerms ?? {}),
        ...updates,
      },
    }));
  }

  function addAddBack() {
    const newAddBack: AddBack = { description: '', amount: 0, category: 'other' };
    updateIS({ addBacks: [...(data.incomeStatement?.addBacks ?? []), newAddBack] });
  }

  function updateAddBack(idx: number, updates: Partial<AddBack>) {
    const addBacks = [...(data.incomeStatement?.addBacks ?? [])];
    addBacks[idx] = { ...addBacks[idx], ...updates };
    updateIS({ addBacks });
  }

  function removeAddBack(idx: number) {
    const addBacks = (data.incomeStatement?.addBacks ?? []).filter((_, i) => i !== idx);
    updateIS({ addBacks });
  }

  const hasIncomeData = data.incomeStatement?.revenue && data.incomeStatement.revenue > 0;

  function handleContinue() {
    setFinancialData(data);
    setDealInfo({
      askingPrice: askingPrice ?? 0,
      businessType: businessType || 'other',
      yearsInOperation: yearsOp,
      reasonForSale: reasonForSale || null,
    });
    setStep(3);
    router.push('/analyze/questions');
  }

  const BUSINESS_TYPES = [
    'Home Services (HVAC, Plumbing)', 'Restaurant / Food & Beverage', 'Retail Store',
    'E-Commerce', 'Professional Services', 'Healthcare / Medical', 'Auto Services',
    'Fitness / Gym', 'Construction / Contracting', 'Technology / SaaS', 'Other',
  ];

  return (
    <div className="animate-fade-in-up">
      <div className="mb-8">
        <div className="inline-flex items-center gap-2 bg-accent/10 border border-accent/20 rounded-full px-3 py-1 text-xs text-accent font-medium mb-3">
          Step 2 of 4
        </div>
        <h1 className="text-2xl font-display font-bold text-white mb-2">Review Financial Data</h1>
        <p className="text-t-secondary">
          Confirm or fill in the financial data below. This is used for all calculations.
        </p>
      </div>

      {data.parsingNotes && data.parsingNotes.length > 0 && (
        <div className="mb-6 space-y-2">
          {data.parsingNotes.map((note, i) => (
            <div key={i} className="flex items-start gap-2 text-sm text-yellow-400 bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-4 py-3">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              {note}
            </div>
          ))}
        </div>
      )}

      <Tabs defaultValue="income" className="space-y-6">
        <TabsList className="grid grid-cols-4 w-full bg-raised border border-white/[0.06]">
          <TabsTrigger value="income" className="data-[state=active]:bg-accent data-[state=active]:text-white text-t-secondary">Income</TabsTrigger>
          <TabsTrigger value="balance" className="data-[state=active]:bg-accent data-[state=active]:text-white text-t-secondary">Balance Sheet</TabsTrigger>
          <TabsTrigger value="loan" className="data-[state=active]:bg-accent data-[state=active]:text-white text-t-secondary">Loan Terms</TabsTrigger>
          <TabsTrigger value="deal" className="data-[state=active]:bg-accent data-[state=active]:text-white text-t-secondary">Deal Info</TabsTrigger>
        </TabsList>

        {/* Income Statement */}
        <TabsContent value="income" className="space-y-6">
          <div className="bg-surface border border-white/[0.06] rounded-xl p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-white">Income Statement / P&L</h3>
              {/* @ts-expect-error confidence is on parsed data */}
              {data.incomeStatement?.confidence && <ConfidenceBadge confidence={data.incomeStatement.confidence as number} />}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <NumericInput label="Total Revenue" value={data.incomeStatement?.revenue} onChange={(v) => updateIS({ revenue: v ?? 0 })} hint="Trailing 12 months or most recent annual" />
              <NumericInput label="Cost of Goods Sold (COGS)" value={data.incomeStatement?.cogs} onChange={(v) => updateIS({ cogs: v ?? 0 })} />
              <NumericInput label="Operating Expenses" value={data.incomeStatement?.operatingExpenses} onChange={(v) => updateIS({ operatingExpenses: v ?? 0 })} hint="Excludes COGS and owner salary" />
              <NumericInput label="Net Income" value={data.incomeStatement?.netIncome} onChange={(v) => updateIS({ netIncome: v ?? 0 })} />
              <NumericInput label="Owner Salary (if included in expenses)" value={data.incomeStatement?.ownerSalary} onChange={(v) => updateIS({ ownerSalary: v ?? undefined })} hint="Owner compensation run through the business" />
              <NumericInput label="Depreciation & Amortization" value={data.incomeStatement?.depreciationAmortization} onChange={(v) => updateIS({ depreciationAmortization: v ?? undefined })} />
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium text-t-secondary">Add-Backs</Label>
                <button onClick={addAddBack} className="text-sm text-accent hover:text-accent-hover flex items-center gap-1 transition-colors">
                  <Plus className="w-3.5 h-3.5" />Add add-back
                </button>
              </div>
              {(data.incomeStatement?.addBacks ?? []).map((ab, i) => (
                <div key={i} className="flex items-center gap-2">
                  <Input
                    placeholder="Description"
                    value={ab.description}
                    onChange={(e) => updateAddBack(i, { description: e.target.value })}
                    className="flex-1 bg-raised border-white/[0.08] text-white placeholder:text-t-muted"
                  />
                  <div className="relative w-32">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-t-muted text-sm">$</span>
                    <Input
                      type="number"
                      value={ab.amount}
                      onChange={(e) => updateAddBack(i, { amount: parseFloat(e.target.value) || 0 })}
                      className="pl-7 w-32 bg-raised border-white/[0.08] text-white"
                    />
                  </div>
                  <button onClick={() => removeAddBack(i)} className="text-t-muted hover:text-risk-critical transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>

            {data.incomeStatement?.revenue && data.incomeStatement.revenue > 0 && (
              <div className="bg-accent/10 border border-accent/20 rounded-lg px-4 py-3 text-sm text-accent">
                <strong>SDE estimate:</strong>{' '}
                {formatCurrency(
                  (data.incomeStatement.netIncome ?? 0) +
                  (data.incomeStatement.ownerSalary ?? 0) +
                  (data.incomeStatement.addBacks?.reduce((s, a) => s + a.amount, 0) ?? 0) +
                  (data.incomeStatement.depreciationAmortization ?? 0)
                )}{' '}
                (net income + owner salary + add-backs + D&A)
              </div>
            )}
          </div>
        </TabsContent>

        {/* Balance Sheet */}
        <TabsContent value="balance" className="space-y-6">
          <div className="bg-surface border border-white/[0.06] rounded-xl p-6 space-y-5">
            <h3 className="font-semibold text-white">Balance Sheet (optional but recommended)</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <NumericInput label="Current Assets" value={data.balanceSheet?.currentAssets} onChange={(v) => updateBS({ currentAssets: v ?? 0 })} hint="Cash + receivables + inventory" />
              <NumericInput label="Current Liabilities" value={data.balanceSheet?.currentLiabilities} onChange={(v) => updateBS({ currentLiabilities: v ?? 0 })} hint="Payables + short-term debt" />
              <NumericInput label="Total Assets" value={data.balanceSheet?.totalAssets} onChange={(v) => updateBS({ totalAssets: v ?? 0 })} />
              <NumericInput label="Total Liabilities" value={data.balanceSheet?.totalLiabilities} onChange={(v) => updateBS({ totalLiabilities: v ?? 0 })} />
              <NumericInput label="Owner's Equity" value={data.balanceSheet?.equity} onChange={(v) => updateBS({ equity: v ?? 0 })} />
              <NumericInput label="Cash & Equivalents" value={data.balanceSheet?.cashAndEquivalents} onChange={(v) => updateBS({ cashAndEquivalents: v ?? undefined })} />
            </div>
            {data.balanceSheet?.currentAssets && data.balanceSheet.currentLiabilities ? (
              <div className="bg-accent/10 border border-accent/20 rounded-lg px-4 py-3 text-sm text-accent">
                <strong>Working capital:</strong>{' '}
                {formatCurrency(data.balanceSheet.currentAssets - data.balanceSheet.currentLiabilities)}
                {data.balanceSheet.currentAssets < data.balanceSheet.currentLiabilities && (
                  <span className="text-risk-critical font-medium ml-1">(negative — flag!)</span>
                )}
              </div>
            ) : null}
          </div>
        </TabsContent>

        {/* Loan Terms */}
        <TabsContent value="loan" className="space-y-6">
          <div className="bg-surface border border-white/[0.06] rounded-xl p-6 space-y-5">
            <h3 className="font-semibold text-white">Loan Terms / Financing</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <NumericInput label="Loan Amount" value={data.loanTerms?.loanAmount} onChange={(v) => updateLT({ loanAmount: v ?? 0 })} />
              <NumericInput label="Down Payment" value={data.loanTerms?.downPayment} onChange={(v) => updateLT({ downPayment: v ?? undefined })} />
              <NumericInput
                label="Interest Rate (%)"
                value={data.loanTerms?.interestRate ? data.loanTerms.interestRate * 100 : undefined}
                onChange={(v) => updateLT({ interestRate: v !== null ? v / 100 : 0 })}
                prefix="%"
                hint="Annual interest rate, e.g. 8.5"
              />
              <NumericInput label="Loan Term (months)" value={data.loanTerms?.termMonths} onChange={(v) => updateLT({ termMonths: v ?? 0 })} prefix="" hint="e.g. 120 for 10 years" />
              <NumericInput label="Monthly Payment (if known)" value={data.loanTerms?.monthlyPayment} onChange={(v) => updateLT({ monthlyPayment: v ?? undefined })} hint="Leave blank to auto-calculate" />
            </div>
          </div>
        </TabsContent>

        {/* Deal Info */}
        <TabsContent value="deal" className="space-y-6">
          <div className="bg-surface border border-white/[0.06] rounded-xl p-6 space-y-5">
            <h3 className="font-semibold text-white">Deal Information</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <NumericInput label="Asking Price" value={askingPrice} onChange={(v) => setAskingPrice(v)} />
              <NumericInput label="Years in Operation" value={yearsOp} onChange={(v) => setYearsOp(v)} prefix="" />
              <div className="space-y-1.5">
                <Label className="text-sm font-medium text-t-secondary">Business Type</Label>
                <Select value={businessType} onValueChange={(v) => setBusinessType(v ?? '')}>
                  <SelectTrigger className="bg-raised border-white/[0.08] text-white"><SelectValue placeholder="Select type..." /></SelectTrigger>
                  <SelectContent>
                    {BUSINESS_TYPES.map((t) => (
                      <SelectItem key={t} value={t.toLowerCase().replace(/ /g, '_')}>{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm font-medium text-t-secondary">Reason for Sale</Label>
                <Select value={reasonForSale} onValueChange={(v) => setReasonForSale(v ?? '')}>
                  <SelectTrigger className="bg-raised border-white/[0.08] text-white"><SelectValue placeholder="Select reason..." /></SelectTrigger>
                  <SelectContent>
                    {['Retirement', 'New Opportunity', 'Health Reasons', 'Partnership Dispute', 'Financial Difficulties', 'Relocating', 'Unknown'].map((r) => (
                      <SelectItem key={r} value={r.toLowerCase()}>{r}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      <div className="mt-8 flex gap-3">
        <button
          onClick={() => router.push('/analyze/upload')}
          className="flex items-center gap-2 border border-white/[0.08] bg-surface text-t-secondary hover:text-white hover:border-white/[0.15] px-5 py-3 rounded-xl font-medium transition-all text-sm"
        >
          <ChevronLeft className="w-4 h-4" />
          Back
        </button>
        <button
          onClick={handleContinue}
          disabled={!hasIncomeData}
          className="flex-1 flex items-center justify-center gap-2 bg-accent hover:bg-accent-hover disabled:bg-raised disabled:text-t-muted disabled:cursor-not-allowed text-white px-6 py-3 rounded-xl font-semibold transition-all"
        >
          Continue to Risk Assessment
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>
      {!hasIncomeData && (
        <p className="text-center text-xs text-t-muted mt-3">
          Enter at least Revenue and Net Income in the Income tab to continue.
        </p>
      )}
    </div>
  );
}
