'use client';

import type { ReportOutput } from '@/lib/types';
import { cn } from '@/lib/utils';
import { TrendingUp } from 'lucide-react';

const DIFFICULTY_CONFIG = {
  easy: { label: 'Easy', color: 'bg-emerald-100 text-emerald-700' },
  moderate: { label: 'Moderate', color: 'bg-yellow-100 text-yellow-700' },
  hard: { label: 'Hard', color: 'bg-red-100 text-red-700' },
};

export function UpsideOpportunities({ report }: { report: ReportOutput }) {
  return (
    <section id="upside" className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
      <h2 className="text-xl font-bold text-slate-900">8. Upside & Opportunities</h2>
      <div className="space-y-3">
        {report.upsideOpportunities.map((opp, i) => {
          const diff = DIFFICULTY_CONFIG[opp.difficulty];
          return (
            <div key={i} className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 rounded-xl p-4">
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-blue-600 flex-shrink-0" />
                  <h3 className="font-semibold text-slate-900 text-sm">{opp.opportunity}</h3>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium', diff.color)}>{diff.label}</span>
                </div>
              </div>
              <p className="text-sm text-blue-700 font-medium mb-1">{opp.estimatedImpact}</p>
              <p className="text-sm text-slate-600">{opp.detail}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
