'use client';

import type { ReportOutput } from '@/lib/types';
import { cn } from '@/lib/utils';
import { TrendingUp } from 'lucide-react';

const DIFFICULTY_CONFIG = {
  easy: { label: 'Easy', color: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  moderate: { label: 'Moderate', color: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
  hard: { label: 'Hard', color: 'bg-red-500/10 text-red-400 border-red-500/20' },
};

export function UpsideOpportunities({ report }: { report: ReportOutput }) {
  return (
    <section
      id="upside"
      className="scroll-mt-32 bg-surface rounded-2xl border border-white/[0.06] p-6 md:p-8 space-y-5 md:space-y-6"
    >
      <h2 className="text-xl font-display font-bold text-white">8. Upside <span className="font-sans">&amp;</span> Opportunities</h2>
      <div className="space-y-3">
        {report.upsideOpportunities.map((opp, i) => {
          const diff = DIFFICULTY_CONFIG[opp.difficulty];
          return (
            <div key={i} className="bg-gradient-to-r from-accent/5 to-violet-500/5 border border-accent/10 rounded-xl p-4">
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-accent flex-shrink-0" />
                  <h3 className="font-semibold text-white text-sm">{opp.opportunity}</h3>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium border', diff.color)}>{diff.label}</span>
                </div>
              </div>
              <p className="text-sm text-accent font-medium mb-1">{opp.estimatedImpact}</p>
              <p className="text-sm text-t-secondary">{opp.detail}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
