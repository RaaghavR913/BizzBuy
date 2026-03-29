'use client';

import type { ReportOutput } from '@/lib/types';
import { useState } from 'react';
import { cn } from '@/lib/utils';

const PRIORITY_CONFIG = {
  critical: { label: 'Critical', bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700', badge: 'bg-red-100 text-red-700' },
  important: { label: 'Important', bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-700', badge: 'bg-yellow-100 text-yellow-700' },
  nice_to_have: { label: 'Nice to Have', bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700', badge: 'bg-blue-100 text-blue-700' },
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
    <section id="diligence-checklist" className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-xl font-bold text-slate-900">7. Due Diligence Checklist</h2>
        <span className="text-sm text-slate-500">{done}/{total} completed</span>
      </div>
      <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
        <div className="h-full bg-blue-600 rounded-full transition-all" style={{ width: `${(done / total) * 100}%` }} />
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
                    <div className={cn(
                      'w-4 h-4 rounded border-2 flex-shrink-0 mt-0.5 flex items-center justify-center transition-all',
                      isChecked ? 'bg-blue-600 border-blue-600' : 'border-slate-300 bg-white'
                    )}>
                      {isChecked && <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={cn('text-sm font-medium', isChecked ? 'line-through text-slate-400' : 'text-slate-800')}>{item.item}</p>
                      <p className="text-xs text-slate-400 mt-0.5">{item.reason}</p>
                    </div>
                    <span className={cn('flex-shrink-0 text-xs px-2 py-0.5 rounded-full font-medium hidden sm:block', config.badge)}>
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
