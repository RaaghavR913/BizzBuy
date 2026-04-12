'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronRight, ChevronLeft, Info, AlertCircle, Plus, Trash2, CheckCircle2, Calculator } from 'lucide-react';
import { useAnalysis } from '@/context/AnalysisContext';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { SpotlightCard } from '@/components/ui/spotlight-card';
import { ShinyText } from '@/components/ui/shiny-text';
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
      <Label className="text-[13px] font-semibold text-slate-200 tracking-wide uppercase">{label}</Label>
      <div className="relative group">
        {prefix && (
          <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 font-medium group-focus-within:text-blue-400 transition-colors z-10">{prefix}</span>
        )}
        <Input
          type="number"
          value={raw}
          onChange={(e) => {
            setRaw(e.target.value);
            const num = parseFloat(e.target.value);
            onChange(isNaN(num) ? null : num);
          }}
          className={`h-11 bg-white/[0.04] border-white/10 hover:border-white/20 text-white placeholder:text-slate-500 focus:bg-white/[0.06] focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500/50 shadow-inner rounded-xl transition-all duration-200 ${prefix ? 'pl-8' : 'pl-4'}`}
          placeholder="0.00"
        />
      </div>
      {hint && <p className="text-xs text-slate-400 mt-1">{hint}</p>}
    </div>
  );
}

function ConfidenceBadge({ confidence }: { confidence?: number }) {
  if (!confidence) return null;
  const pct = Math.round(confidence * 100);
  const color = pct >= 85 ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' :
    pct >= 70 ? 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20' :
      'text-red-400 bg-red-400/10 border-red-500/20';
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border shadow-sm ${color}`}>
      {pct >= 85 ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Info className="w-3.5 h-3.5" />}
      <span className="font-semibold">{pct}% confidence</span>
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
    <div className="max-w-4xl mx-auto w-full pb-20 animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      {/* Header Section */}
      <div className="mb-10 text-center space-y-4">
        <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 rounded-full px-4 py-1.5 text-xs text-blue-400 font-semibold uppercase tracking-wider backdrop-blur-sm">
          <Calculator className="w-4 h-4" />
          Step 2 of 4
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight">
          <ShinyText text="Review Financial Data" className="text-white" />
        </h1>
        <p className="text-slate-400 max-w-xl mx-auto text-lg">
          Please verify or fill in the financial details below to refine our analysis.
        </p>
      </div>

      {data.parsingNotes && data.parsingNotes.length > 0 && (
        <div className="mb-8 space-y-3">
          {data.parsingNotes.map((note, i) => (
            <div key={i} className="flex items-start gap-3 text-sm text-yellow-200 bg-yellow-500/10 border border-yellow-500/20 shadow-lg rounded-xl px-5 py-4 backdrop-blur-md">
              <AlertCircle className="w-5 h-5 flex-shrink-0 text-yellow-500" />
              <div className="leading-relaxed">{note}</div>
            </div>
          ))}
        </div>
      )}

      {/* Main Tabs UI */}
      <Tabs defaultValue="income" className="flex flex-col space-y-8 w-full">
        <TabsList className="flex flex-row flex-wrap w-full bg-white/[0.03] p-1.5 rounded-2xl border border-white/10 shadow-inner overflow-hidden">
          <TabsTrigger value="income" className="flex-1 rounded-xl text-slate-400 data-[state=active]:bg-gradient-to-br data-[state=active]:from-blue-600 data-[state=active]:to-indigo-600 data-[state=active]:text-white data-[state=active]:shadow-lg py-3 text-sm font-bold transition-all">Income</TabsTrigger>
          <TabsTrigger value="balance" className="flex-1 rounded-xl text-slate-400 data-[state=active]:bg-gradient-to-br data-[state=active]:from-blue-600 data-[state=active]:to-indigo-600 data-[state=active]:text-white data-[state=active]:shadow-lg py-3 text-sm font-bold transition-all">Balance Sheet</TabsTrigger>
          <TabsTrigger value="loan" className="flex-1 rounded-xl text-slate-400 data-[state=active]:bg-gradient-to-br data-[state=active]:from-blue-600 data-[state=active]:to-indigo-600 data-[state=active]:text-white data-[state=active]:shadow-lg py-3 text-sm font-bold transition-all">Loan Terms</TabsTrigger>
          <TabsTrigger value="deal" className="flex-1 rounded-xl text-slate-400 data-[state=active]:bg-gradient-to-br data-[state=active]:from-blue-600 data-[state=active]:to-indigo-600 data-[state=active]:text-white data-[state=active]:shadow-lg py-3 text-sm font-bold transition-all">Deal Info</TabsTrigger>
        </TabsList>

        <SpotlightCard className="p-8">
          {/* Subtle accent glow */}
          <div className="absolute top-0 right-0 -mr-20 -mt-20 w-64 h-64 bg-blue-500/10 rounded-full blur-3xl pointer-events-none"></div>

          {/* Income Statement */}
          <TabsContent value="income" className="space-y-8 m-0 w-full animate-in fade-in zoom-in-95 duration-300">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <h3 className="text-xl font-bold text-white flex items-center gap-2">
                Income Statement / P&L
              </h3>
              {/* @ts-expect-error confidence is on parsed data */}
              {data.incomeStatement?.confidence && <ConfidenceBadge confidence={data.incomeStatement.confidence as number} />}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
              <NumericInput label="Total Revenue" value={data.incomeStatement?.revenue} onChange={(v) => updateIS({ revenue: v ?? 0 })} hint="Trailing 12 months or most recent annual" />
              <NumericInput label="Cost of Goods Sold (COGS)" value={data.incomeStatement?.cogs} onChange={(v) => updateIS({ cogs: v ?? 0 })} />
              <NumericInput label="Operating Expenses" value={data.incomeStatement?.operatingExpenses} onChange={(v) => updateIS({ operatingExpenses: v ?? 0 })} hint="Excludes COGS and owner salary" />
              <NumericInput label="Net Income" value={data.incomeStatement?.netIncome} onChange={(v) => updateIS({ netIncome: v ?? 0 })} />
              <NumericInput label="Owner Salary (if included in expenses)" value={data.incomeStatement?.ownerSalary} onChange={(v) => updateIS({ ownerSalary: v ?? undefined })} hint="Owner compensation run through the business" />
              <NumericInput label="Depreciation & Amortization" value={data.incomeStatement?.depreciationAmortization} onChange={(v) => updateIS({ depreciationAmortization: v ?? undefined })} />
            </div>

            <div className="pt-6 border-t border-white/10 space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-[13px] font-semibold text-slate-200 tracking-wide uppercase">Add-Backs</h4>
                <button onClick={addAddBack} className="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1.5 transition-colors font-semibold px-3 py-1.5 hover:bg-blue-500/10 rounded-lg">
                  <Plus className="w-4 h-4" /> Add Add-back
                </button>
              </div>
              
              {(!data.incomeStatement?.addBacks || data.incomeStatement.addBacks.length === 0) && (
                <div className="text-center py-6 bg-white/[0.02] border border-dashed border-white/10 rounded-xl text-slate-500 text-sm">
                  No add-backs specified. Click "Add Add-back" to include one.
                </div>
              )}

              <div className="space-y-3">
                {(data.incomeStatement?.addBacks ?? []).map((ab, i) => (
                  <div key={i} className="flex flex-col sm:flex-row items-center gap-3 bg-white/[0.02] p-2 rounded-xl border border-white/5">
                    <Input
                      placeholder="Description (e.g. Personal Vehicle)"
                      value={ab.description}
                      onChange={(e) => updateAddBack(i, { description: e.target.value })}
                      className="flex-1 h-11 bg-white/[0.04] border-white/10 hover:border-white/20 text-white placeholder:text-slate-500 focus:bg-white/[0.06] rounded-lg transition-all"
                    />
                    <div className="relative w-full sm:w-40">
                      <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 font-medium">$</span>
                      <Input
                        type="number"
                        value={ab.amount}
                        onChange={(e) => updateAddBack(i, { amount: parseFloat(e.target.value) || 0 })}
                        className="pl-8 h-11 w-full bg-white/[0.04] border-white/10 hover:border-white/20 text-white rounded-lg transition-all"
                        placeholder="Amount"
                      />
                    </div>
                    <button onClick={() => removeAddBack(i)} className="p-3 text-slate-400 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all" title="Remove">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {data.incomeStatement?.revenue && data.incomeStatement.revenue > 0 && (
              <div className="bg-gradient-to-r from-blue-900/40 to-indigo-900/40 border border-blue-500/30 rounded-xl p-5 flex items-start gap-4">
                <div className="bg-blue-500/20 p-2.5 rounded-lg text-blue-400">
                  <Calculator className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-sm text-slate-300 font-medium mb-1">Estimated SDE (Seller\'s Discretionary Earnings)</div>
                  <div className="text-2xl font-bold text-white tracking-tight">
                    {formatCurrency(
                      (data.incomeStatement.netIncome ?? 0) +
                      (data.incomeStatement.ownerSalary ?? 0) +
                      (data.incomeStatement.addBacks?.reduce((s, a) => s + a.amount, 0) ?? 0) +
                      (data.incomeStatement.depreciationAmortization ?? 0)
                    )}
                  </div>
                  <div className="text-xs text-slate-400 mt-1">Calculated as: Net income + Owner salary + Add-backs + D&A</div>
                </div>
              </div>
            )}
          </TabsContent>

          {/* Balance Sheet */}
          <TabsContent value="balance" className="space-y-8 m-0 w-full animate-in fade-in zoom-in-95 duration-300">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
               <h3 className="text-xl font-bold text-white">Balance Sheet <span className="text-sm font-normal text-slate-400 ml-2">(Optional but recommended)</span></h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
              <NumericInput label="Current Assets" value={data.balanceSheet?.currentAssets} onChange={(v) => updateBS({ currentAssets: v ?? 0 })} hint="Cash + receivables + inventory" />
              <NumericInput label="Current Liabilities" value={data.balanceSheet?.currentLiabilities} onChange={(v) => updateBS({ currentLiabilities: v ?? 0 })} hint="Payables + short-term debt" />
              <NumericInput label="Total Assets" value={data.balanceSheet?.totalAssets} onChange={(v) => updateBS({ totalAssets: v ?? 0 })} />
              <NumericInput label="Total Liabilities" value={data.balanceSheet?.totalLiabilities} onChange={(v) => updateBS({ totalLiabilities: v ?? 0 })} />
              <NumericInput label="Owner's Equity" value={data.balanceSheet?.equity} onChange={(v) => updateBS({ equity: v ?? 0 })} />
              <NumericInput label="Cash & Equivalents" value={data.balanceSheet?.cashAndEquivalents} onChange={(v) => updateBS({ cashAndEquivalents: v ?? undefined })} />
            </div>
            {data.balanceSheet?.currentAssets && data.balanceSheet.currentLiabilities ? (
              <div className="bg-slate-800/50 border border-white/10 rounded-xl p-5 flex items-center justify-between">
                <div>
                  <div className="text-sm text-slate-300 font-medium mb-1">Working Capital</div>
                  <div className="text-xl font-bold flex items-center gap-2">
                    <span className="text-white">{formatCurrency(data.balanceSheet.currentAssets - data.balanceSheet.currentLiabilities)}</span>
                    {data.balanceSheet.currentAssets < data.balanceSheet.currentLiabilities && (
                      <span className="text-red-400 text-sm font-medium bg-red-400/10 border border-red-500/20 px-2.5 py-0.5 rounded-md ml-2">Negative Warning</span>
                    )}
                  </div>
                </div>
              </div>
            ) : null}
          </TabsContent>

          {/* Loan Terms */}
          <TabsContent value="loan" className="space-y-8 m-0 w-full animate-in fade-in zoom-in-95 duration-300">
             <div className="flex items-center justify-between border-b border-white/10 pb-4">
               <h3 className="text-xl font-bold text-white">Loan Terms / Financing</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
              <NumericInput label="Loan Amount" value={data.loanTerms?.loanAmount} onChange={(v) => updateLT({ loanAmount: v ?? 0 })} />
              <NumericInput label="Down Payment" value={data.loanTerms?.downPayment} onChange={(v) => updateLT({ downPayment: v ?? undefined })} />
              <NumericInput
                label="Interest Rate"
                value={data.loanTerms?.interestRate ? data.loanTerms.interestRate * 100 : undefined}
                onChange={(v) => updateLT({ interestRate: v !== null ? v / 100 : 0 })}
                prefix="%"
                hint="Annual interest rate, e.g. 8.5"
              />
              <NumericInput label="Loan Term (months)" value={data.loanTerms?.termMonths} onChange={(v) => updateLT({ termMonths: v ?? 0 })} prefix="" hint="e.g. 120 for 10 years" />
              <NumericInput label="Monthly Payment" value={data.loanTerms?.monthlyPayment} onChange={(v) => updateLT({ monthlyPayment: v ?? undefined })} hint="Leave blank to auto-calculate" />
            </div>
          </TabsContent>

          {/* Deal Info */}
          <TabsContent value="deal" className="space-y-8 m-0 w-full animate-in fade-in zoom-in-95 duration-300">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
               <h3 className="text-xl font-bold text-white">Deal Information</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
              <NumericInput label="Asking Price" value={askingPrice} onChange={(v) => setAskingPrice(v)} />
              <NumericInput label="Years in Operation" value={yearsOp} onChange={(v) => setYearsOp(v)} prefix="" />
              <div className="space-y-1.5">
                <Label className="text-[13px] font-semibold text-slate-200 tracking-wide uppercase">Business Type</Label>
                <Select value={businessType} onValueChange={(v) => setBusinessType(v ?? '')}>
                  <SelectTrigger className="h-11 bg-white/[0.04] border-white/10 hover:border-white/20 text-white rounded-xl focus:ring-2 focus:ring-blue-500/40">
                    <SelectValue placeholder="Select industry..." />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-800 border-white/10 text-white rounded-xl backdrop-blur-xl">
                    {BUSINESS_TYPES.map((t) => (
                      <SelectItem key={t} value={t.toLowerCase().replace(/ /g, '_')} className="hover:bg-white/5 focus:bg-white/10 cursor-pointer">{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-[13px] font-semibold text-slate-200 tracking-wide uppercase">Reason for Sale</Label>
                <Select value={reasonForSale} onValueChange={(v) => setReasonForSale(v ?? '')}>
                  <SelectTrigger className="h-11 bg-white/[0.04] border-white/10 hover:border-white/20 text-white rounded-xl focus:ring-2 focus:ring-blue-500/40">
                    <SelectValue placeholder="Select reason..." />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-800 border-white/10 text-white rounded-xl backdrop-blur-xl">
                    {['Retirement', 'New Opportunity', 'Health Reasons', 'Partnership Dispute', 'Financial Difficulties', 'Relocating', 'Unknown'].map((r) => (
                      <SelectItem key={r} value={r.toLowerCase()} className="hover:bg-white/5 focus:bg-white/10 cursor-pointer">{r}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </TabsContent>
        </SpotlightCard>
      </Tabs>

      <div className="mt-10 flex flex-col sm:flex-row gap-4 items-center w-full">
        <button
          onClick={() => router.push('/analyze/upload')}
          className="w-full sm:w-auto flex items-center justify-center gap-2 border border-white/10 bg-white/[0.02] hover:bg-white/[0.05] text-slate-300 hover:text-white px-6 py-4 rounded-2xl font-medium transition-all text-sm shadow-sm"
        >
          <ChevronLeft className="w-5 h-5" />
          Back
        </button>
        <button
          onClick={handleContinue}
          disabled={!hasIncomeData}
          className="w-full sm:flex-1 flex items-center justify-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:from-slate-700 disabled:to-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed text-white px-8 py-4 rounded-2xl font-bold text-lg shadow-xl shadow-blue-900/20 hover:shadow-blue-900/40 transition-all duration-300 transform hover:-translate-y-0.5 active:translate-y-0"
        >
          Continue to Risk Assessment
          <ChevronRight className="w-6 h-6" />
        </button>
      </div>
      {!hasIncomeData && (
        <p className="text-center text-sm font-medium text-slate-400 mt-6 animate-pulse">
          Please enter <strong className="text-white">Revenue</strong> and <strong className="text-white">Net Income</strong> to proceed.
        </p>
      )}
    </div>
  );
}

