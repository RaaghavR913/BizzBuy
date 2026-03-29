'use client';

import type { ReportOutput } from '@/lib/types';
import { ScoreBadge } from './ScoreBadge';
import { AlertTriangle } from 'lucide-react';

export function ExecutiveSummary({ report }: { report: ReportOutput }) {
  const { executiveSummary } = report;

  return (
    <section id="executive-summary" className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
      <h2 className="text-xl font-bold text-slate-900">1. Executive Summary</h2>

      <div className="flex flex-wrap gap-3">
        <div className="flex flex-col items-center gap-1 bg-slate-50 rounded-xl p-4 min-w-[120px]">
          <ScoreBadge score={executiveSummary.riskScore} label="" size="lg" type="risk" />
          <span className="text-xs text-slate-500 font-medium">Acquisition Risk</span>
          <span className="text-sm font-semibold text-slate-700">{executiveSummary.riskLabel} Risk</span>
        </div>
        <div className="flex flex-col items-center gap-1 bg-slate-50 rounded-xl p-4 min-w-[120px]">
          <ScoreBadge score={report.transferabilityAnalysis.score} label="" size="lg" type="transferability" />
          <span className="text-xs text-slate-500 font-medium">Transferability</span>
          <span className="text-sm font-semibold text-slate-700">{executiveSummary.transferabilityLabel}</span>
        </div>
      </div>

      <p className="text-slate-700 leading-relaxed">{executiveSummary.text}</p>
      <p className="text-slate-500 italic text-sm">{executiveSummary.verdict}</p>

      {report.riskAssessment.dealBreakers.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <div className="flex items-center gap-2 text-red-700 font-semibold mb-2">
            <AlertTriangle className="w-4 h-4" />
            Potential Deal Breakers Identified
          </div>
          <ul className="space-y-1">
            {report.riskAssessment.dealBreakers.map((db, i) => (
              <li key={i} className="text-sm text-red-600 flex items-start gap-2">
                <span className="mt-1 flex-shrink-0">•</span>
                {db}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
