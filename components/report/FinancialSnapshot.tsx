'use client';

import type { ReportOutput } from '@/lib/types';
import { cn } from '@/lib/utils';

export function FinancialSnapshot({ report }: { report: ReportOutput }) {
  const { financialSnapshot } = report;
  const multiple = financialSnapshot.valuationMultiple;
  const multipleStr = multiple === Infinity ? '∞' : `${multiple.toFixed(2)}x`;
  const multipleColor =
    multiple <= 2 ? 'text-emerald-400' :
    multiple <= 3.5 ? 'text-blue-400' :
    multiple <= 4.5 ? 'text-yellow-400' : 'text-red-400';

  return (
    <section id="financial-snapshot" className="bg-surface rounded-2xl border border-white/[0.06] p-6 space-y-4">
      <h2 className="text-xl font-display font-bold text-white">2. Financial Snapshot</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.06]">
              <th className="text-left py-2 px-3 text-t-muted font-medium">Metric</th>
              <th className="text-right py-2 px-3 text-t-muted font-medium">Value</th>
              <th className="text-left py-2 px-3 text-t-muted font-medium hidden sm:table-cell">Notes</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(financialSnapshot.metrics).map(([key, m], i) => (
              <tr key={key} className={cn('border-b border-white/[0.04]', i % 2 === 0 ? '' : 'bg-raised/30')}>
                <td className="py-2.5 px-3 font-medium text-t-secondary">{key}</td>
                <td className="py-2.5 px-3 text-right font-mono font-semibold text-white">
                  {m.formatted}
                  {m.note?.includes('flag') && <span className="ml-2 text-red-400 text-xs">{m.note}</span>}
                </td>
                <td className="py-2.5 px-3 text-t-muted text-xs hidden sm:table-cell">
                  {m.note && !m.note.includes('flag') ? m.note : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="bg-accent/10 border border-accent/20 rounded-xl p-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <span className="text-sm font-medium text-t-secondary">Asking Price / SDE Multiple</span>
          <span className={cn('text-lg font-black font-mono', multipleColor)}>{multipleStr}</span>
        </div>
        <p className="text-sm text-t-secondary mt-1">{financialSnapshot.multipleAssessment}</p>
      </div>
    </section>
  );
}
