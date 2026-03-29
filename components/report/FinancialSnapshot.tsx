'use client';

import type { ReportOutput } from '@/lib/types';
import { cn } from '@/lib/utils';

export function FinancialSnapshot({ report }: { report: ReportOutput }) {
  const { financialSnapshot } = report;
  const multiple = financialSnapshot.valuationMultiple;
  const multipleStr = multiple === Infinity ? '∞' : `${multiple.toFixed(2)}x`;
  const multipleColor =
    multiple <= 2 ? 'text-emerald-600' :
    multiple <= 3.5 ? 'text-blue-600' :
    multiple <= 4.5 ? 'text-yellow-600' : 'text-red-600';

  return (
    <section id="financial-snapshot" className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
      <h2 className="text-xl font-bold text-slate-900">2. Financial Snapshot</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200">
              <th className="text-left py-2 px-3 text-slate-500 font-medium">Metric</th>
              <th className="text-right py-2 px-3 text-slate-500 font-medium">Value</th>
              <th className="text-left py-2 px-3 text-slate-500 font-medium hidden sm:table-cell">Notes</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(financialSnapshot.metrics).map(([key, m], i) => (
              <tr key={key} className={cn('border-b border-slate-100', i % 2 === 0 ? 'bg-white' : 'bg-slate-50/50')}>
                <td className="py-2.5 px-3 font-medium text-slate-800">{key}</td>
                <td className="py-2.5 px-3 text-right font-mono font-semibold text-slate-900">
                  {m.formatted}
                  {m.note?.includes('flag') && <span className="ml-2 text-red-500 text-xs">{m.note}</span>}
                </td>
                <td className="py-2.5 px-3 text-slate-400 text-xs hidden sm:table-cell">
                  {m.note && !m.note.includes('flag') ? m.note : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <span className="text-sm font-medium text-slate-700">Asking Price / SDE Multiple</span>
          <span className={cn('text-lg font-black', multipleColor)}>{multipleStr}</span>
        </div>
        <p className="text-sm text-slate-600 mt-1">{financialSnapshot.multipleAssessment}</p>
      </div>
    </section>
  );
}
