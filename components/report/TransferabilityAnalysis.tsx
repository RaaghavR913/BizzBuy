'use client';

import type { ReportOutput } from '@/lib/types';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';

export function TransferabilityAnalysis({ report }: { report: ReportOutput }) {
  const { transferabilityAnalysis, executiveSummary } = report;

  const scoreColor =
    transferabilityAnalysis.score >= 65 ? 'text-emerald-600' :
    transferabilityAnalysis.score >= 40 ? 'text-yellow-600' :
    transferabilityAnalysis.score >= 20 ? 'text-orange-600' : 'text-red-600';

  return (
    <section id="transferability" className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-xl font-bold text-slate-900">5. Transferability Analysis</h2>
        <div className="flex items-center gap-2">
          <span className={cn('text-2xl font-black', scoreColor)}>
            {transferabilityAnalysis.score}/100
          </span>
          <span className="text-sm text-slate-500">— {executiveSummary.transferabilityLabel}</span>
        </div>
      </div>

      <p className="text-slate-600 text-sm leading-relaxed">{transferabilityAnalysis.explanation}</p>

      {transferabilityAnalysis.keyFactors.length > 0 && (
        <div className="space-y-2">
          <h3 className="font-semibold text-slate-900 text-sm">Key Transferability Factors</h3>
          <div className="space-y-2">
            {transferabilityAnalysis.keyFactors.map((f, i) => {
              const Icon = f.impact === 'positive' ? TrendingUp : f.impact === 'negative' ? TrendingDown : Minus;
              const color = f.impact === 'positive' ? 'text-emerald-600 bg-emerald-50 border-emerald-200' :
                f.impact === 'negative' ? 'text-red-600 bg-red-50 border-red-200' :
                  'text-slate-500 bg-slate-50 border-slate-200';
              return (
                <div key={i} className={cn('flex items-start gap-3 p-3 rounded-lg border text-sm', color)}>
                  <Icon className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium">{f.factor}: </span>
                    <span className="opacity-80">{f.detail}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {transferabilityAnalysis.improvementSuggestions.length > 0 && (
        <div>
          <h3 className="font-semibold text-slate-900 text-sm mb-2">How to Improve Transferability</h3>
          <ul className="space-y-1">
            {transferabilityAnalysis.improvementSuggestions.map((s, i) => (
              <li key={i} className="text-sm text-slate-600 flex items-start gap-2">
                <span className="mt-1 flex-shrink-0 text-blue-400">→</span>
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
