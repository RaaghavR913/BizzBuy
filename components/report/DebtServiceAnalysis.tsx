'use client';

import type { ReportOutput } from '@/lib/types';
import { formatCurrency } from '@/lib/calculations';
import { cn } from '@/lib/utils';

function DSCRGauge({ dscr }: { dscr: number }) {
  const display = dscr === 999 ? '∞' : dscr.toFixed(2);
  const color =
    dscr >= 2.0 ? 'text-emerald-600' :
    dscr >= 1.5 ? 'text-blue-600' :
    dscr >= 1.25 ? 'text-yellow-600' :
    dscr >= 1.0 ? 'text-orange-600' : 'text-red-600';
  const label =
    dscr >= 2.0 ? 'Excellent' :
    dscr >= 1.5 ? 'Strong' :
    dscr >= 1.25 ? 'Adequate' :
    dscr >= 1.0 ? 'Marginal' : 'Critical';

  return (
    <div className="flex items-center gap-3">
      <span className={cn('text-4xl font-black', color)}>{display}</span>
      <div>
        <span className={cn('text-sm font-bold', color)}>{label}</span>
        <p className="text-xs text-slate-400">Min. target: 1.25x (SBA standard)</p>
      </div>
    </div>
  );
}

export function DebtServiceAnalysis({ report }: { report: ReportOutput }) {
  const { debtServiceAnalysis } = report;
  const { sbaLoanSizing } = report;

  if (debtServiceAnalysis.annualDebtService === 0) {
    return (
      <section id="debt-service" className="bg-white rounded-2xl border border-slate-200 p-6">
        <h2 className="text-xl font-bold text-slate-900 mb-3">3. Debt Service & Affordability</h2>
        <p className="text-slate-500">No loan terms were provided. If you are financing this acquisition, enter loan terms in the review step to see a full affordability analysis.</p>
      </section>
    );
  }

  return (
    <section id="debt-service" className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5">
      <h2 className="text-xl font-bold text-slate-900">3. Debt Service & Affordability</h2>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-slate-50 rounded-xl p-4 text-center">
          <p className="text-xs text-slate-400 font-medium mb-1">Monthly Debt Service</p>
          <p className="text-2xl font-black text-slate-900">{formatCurrency(debtServiceAnalysis.monthlyDebtService)}</p>
        </div>
        <div className="bg-slate-50 rounded-xl p-4 text-center">
          <p className="text-xs text-slate-400 font-medium mb-1">Annual Debt Service</p>
          <p className="text-2xl font-black text-slate-900">{formatCurrency(debtServiceAnalysis.annualDebtService)}</p>
        </div>
        <div className="bg-slate-50 rounded-xl p-4 text-center">
          <p className="text-xs text-slate-400 font-medium mb-1">DSCR</p>
          <DSCRGauge dscr={debtServiceAnalysis.dscr} />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-blue-50 rounded-xl p-4 text-center border border-blue-200">
          <p className="text-xs text-blue-500 font-medium mb-1">Estimated SBA Max Loan</p>
          <p className="text-2xl font-black text-blue-900">{formatCurrency(sbaLoanSizing.maxSupportedLoan)}</p>
        </div>
        <div className="bg-blue-50 rounded-xl p-4 text-center border border-blue-200">
          <p className="text-xs text-blue-500 font-medium mb-1">Bankability Score</p>
          <p className="text-2xl font-black text-blue-900">{sbaLoanSizing.bankabilityScore}/100</p>
          <p className="text-xs text-blue-700 mt-1">{sbaLoanSizing.bankabilityLabel}</p>
        </div>
        <div className="bg-blue-50 rounded-xl p-4 text-center border border-blue-200">
          <p className="text-xs text-blue-500 font-medium mb-1">SBA Stress DSCR</p>
          <p className="text-2xl font-black text-blue-900">
            {sbaLoanSizing.estimatedDSCR === Infinity ? '∞' : sbaLoanSizing.estimatedDSCR.toFixed(2)}
          </p>
        </div>
      </div>

      <p className="text-sm text-slate-600">{debtServiceAnalysis.dscrAssessment}</p>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        {Object.entries(debtServiceAnalysis.loanSummary).map(([k, v]) => (
          <div key={k} className="bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-400 font-medium">{k}</p>
            <p className="font-semibold text-slate-800 mt-0.5">{v}</p>
          </div>
        ))}
      </div>

      {debtServiceAnalysis.scenarios.length > 0 && (
        <div>
          <h3 className="font-semibold text-slate-900 mb-3">Performance Scenarios</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="text-left py-2.5 px-3 font-medium text-slate-600">Scenario</th>
                  <th className="text-right py-2.5 px-3 font-medium text-slate-600">Revenue</th>
                  <th className="text-right py-2.5 px-3 font-medium text-slate-600">DSCR</th>
                  <th className="text-right py-2.5 px-3 font-medium text-slate-600">Owner Income</th>
                </tr>
              </thead>
              <tbody>
                {debtServiceAnalysis.scenarios.map((s, i) => {
                  const dscrOk = s.dscr >= 1.25;
                  return (
                    <tr key={i} className="border-b border-slate-100">
                      <td className="py-2.5 px-3 font-medium text-slate-800">{s.label}</td>
                      <td className="py-2.5 px-3 text-right font-mono">{formatCurrency(s.annualRevenue)}</td>
                      <td className={cn('py-2.5 px-3 text-right font-mono font-bold', dscrOk ? 'text-emerald-600' : 'text-red-600')}>
                        {s.dscr.toFixed(2)}
                      </td>
                      <td className={cn('py-2.5 px-3 text-right font-mono', s.annualOwnerIncome > 0 ? 'text-slate-900' : 'text-red-600')}>
                        {formatCurrency(s.annualOwnerIncome)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
        <p className="text-sm text-blue-800 font-medium">Affordability Summary</p>
        <p className="text-sm text-blue-700 mt-1">{debtServiceAnalysis.affordabilityVerdict}</p>
        <p className="text-sm text-blue-700 mt-2">{sbaLoanSizing.explanation}</p>
      </div>
    </section>
  );
}
