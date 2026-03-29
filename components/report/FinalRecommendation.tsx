'use client';

import type { ReportOutput } from '@/lib/types';
import { CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

export function FinalRecommendation({ report }: { report: ReportOutput }) {
  const { finalRecommendation } = report;
  const action = finalRecommendation.action;

  const config = {
    proceed: {
      bg: 'bg-emerald-600',
      border: 'border-emerald-700',
      label: 'PROCEED',
      icon: CheckCircle2,
      subtitle: 'This deal shows sufficient promise to move forward.',
    },
    proceed_with_caution: {
      bg: 'bg-yellow-500',
      border: 'border-yellow-600',
      label: 'PROCEED WITH CAUTION',
      icon: AlertTriangle,
      subtitle: 'This deal may be viable, but requires careful due diligence.',
    },
    walk_away: {
      bg: 'bg-red-600',
      border: 'border-red-700',
      label: 'WALK AWAY',
      icon: XCircle,
      subtitle: 'This deal presents risks that outweigh the potential rewards.',
    },
  }[action];

  const Icon = config.icon;

  return (
    <section id="final-recommendation" className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5">
      <h2 className="text-xl font-bold text-slate-900">9. Final Recommendation</h2>

      <div className={cn('rounded-2xl p-6 text-white', config.bg, 'border', config.border)}>
        <div className="flex items-center gap-3 mb-2">
          <Icon className="w-7 h-7" />
          <span className="text-2xl font-black">{config.label}</span>
        </div>
        <p className="opacity-90 text-sm">{config.subtitle}</p>
        <p className="mt-3 font-medium">{finalRecommendation.summaryStatement}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
          <h3 className="font-semibold text-emerald-800 mb-3 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            Top Strengths
          </h3>
          <ul className="space-y-2">
            {finalRecommendation.strengths.map((s, i) => (
              <li key={i} className="text-sm text-emerald-700 flex items-start gap-2">
                <span className="mt-1 flex-shrink-0">•</span>
                {s}
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <h3 className="font-semibold text-red-800 mb-3 flex items-center gap-2">
            <XCircle className="w-4 h-4" />
            Top Risks
          </h3>
          <ul className="space-y-2">
            {finalRecommendation.risks.map((r, i) => (
              <li key={i} className="text-sm text-red-700 flex items-start gap-2">
                <span className="mt-1 flex-shrink-0">•</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
        <h3 className="font-semibold text-blue-900 mb-3">Suggested Next Steps</h3>
        <div className="space-y-2">
          {finalRecommendation.nextSteps.map((step, i) => (
            <div key={i} className="flex items-start gap-3 text-sm text-blue-800">
              <div className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
                {i + 1}
              </div>
              {step}
            </div>
          ))}
        </div>
      </div>

      <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-1">
        {report.metadata.disclaimers.map((d, i) => (
          <p key={i} className="text-xs text-slate-400">{d}</p>
        ))}
      </div>
    </section>
  );
}
