'use client';

import type { ReportOutput } from '@/lib/types';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { AnimatedCheckbox } from '@/components/report/AnimatedCheckbox';

const PRIORITY_CONFIG = {
  critical: { label: 'Critical', bg: 'bg-red-500/5', border: 'border-red-500/20', text: 'text-red-400', badge: 'bg-red-500/10 text-red-400 border-red-500/20' },
  important: { label: 'Important', bg: 'bg-yellow-500/5', border: 'border-yellow-500/20', text: 'text-yellow-400', badge: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
  nice_to_have: { label: 'Nice to Have', bg: 'bg-accent/5', border: 'border-accent/20', text: 'text-accent', badge: 'bg-accent/10 text-accent border-accent/20' },
};

export function DiligenceChecklist({ report }: { report: ReportOutput }) {
  const [checked, setChecked] = useState<Set<number>>(new Set());

  function toggle(i: number) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(i)) {
        next.delete(i);
      } else {
        next.add(i);
      }
      return next;
    });
  }

  const byPriority = {
    critical: report.diligenceChecklist.filter((d) => d.priority === 'critical'),
    important: report.diligenceChecklist.filter((d) => d.priority === 'important'),
    nice_to_have: report.diligenceChecklist.filter((d) => d.priority === 'nice_to_have'),
  };

  const total = report.diligenceChecklist.length;
  const done = checked.size;

  return (
    <section id="diligence-checklist" className="bg-surface rounded-2xl border border-white/[0.06] p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-xl font-display font-bold text-white">7. Due Diligence Checklist</h2>
        <span className="text-sm text-t-muted font-sans">{done}/{total} completed</span>
      </div>
      <div className="h-1.5 bg-raised rounded-full overflow-hidden">
        <div className="h-full bg-accent rounded-full transition-all" style={{ width: `${(done / total) * 100}%` }} />
      </div>

      {(['critical', 'important', 'nice_to_have'] as const).map((priority) => {
        const items = byPriority[priority];
        if (!items.length) return null;
        const config = PRIORITY_CONFIG[priority];
        const startIdx = priority === 'critical' ? 0 :
          priority === 'important' ? byPriority.critical.length :
          byPriority.critical.length + byPriority.important.length;

        return (
          <div key={priority} className="space-y-2">
            <h3 className={cn('text-sm font-bold', config.text)}>{config.label}</h3>
            <div className="space-y-2">
              {items.map((item, j) => {
                const globalIdx = startIdx + j;
                const isChecked = checked.has(globalIdx);
                return (
                  <div
                    key={j}
                    onClick={() => toggle(globalIdx)}
                    className={cn(
                      'flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all',
                      config.bg, config.border,
                      isChecked ? 'opacity-50' : ''
                    )}
                  >
                    <div className="flex-shrink-0 mt-0.5 pointer-events-none">
                      <AnimatedCheckbox checked={isChecked} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={cn('text-sm font-medium', isChecked ? 'line-through text-t-muted' : 'text-t-secondary')}>{item.item}</p>
                      <p className="text-xs text-t-muted mt-0.5">{item.reason}</p>
                    </div>
                    <span className={cn('flex-shrink-0 text-xs px-2 py-0.5 rounded-full font-medium hidden sm:block border', config.badge)}>
                      {item.category}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </section>
  );
}
