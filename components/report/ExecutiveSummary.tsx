'use client';

import type { ReportOutput } from '@/lib/types';
import { ScoreBadge } from './ScoreBadge';
import { AlertTriangle } from 'lucide-react';

export function ExecutiveSummary({ report }: { report: ReportOutput }) {
  const { executiveSummary } = report;

  return (
    <section id="executive-summary" className="bg-surface rounded-2xl border border-white/[0.06] p-6 space-y-4">
      <h2 className="text-xl font-display font-bold text-white">1. Executive Summary</h2>

      <div className="flex flex-wrap gap-3">
        <div className="flex flex-col items-center gap-1 bg-raised rounded-xl p-4 min-w-[120px]">
          <ScoreBadge score={executiveSummary.riskScore} label="" size="lg" type="risk" />
          <span className="text-xs text-t-muted font-medium">Acquisition Risk</span>
          <span className="text-sm font-semibold text-t-secondary">{executiveSummary.riskLabel} Risk</span>
        </div>
        <div className="flex flex-col items-center gap-1 bg-raised rounded-xl p-4 min-w-[120px]">
          <ScoreBadge score={report.transferabilityAnalysis.score} label="" size="lg" type="transferability" />
          <span className="text-xs text-t-muted font-medium">Transferability</span>
          <span className="text-sm font-semibold text-t-secondary">{executiveSummary.transferabilityLabel}</span>
        </div>
      </div>

      <p className="text-t-secondary leading-relaxed">{executiveSummary.text}</p>
      <p className="text-t-muted italic text-sm">{executiveSummary.verdict}</p>

      {report.riskAssessment.dealBreakers.length > 0 && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
          <div className="flex items-center gap-2 text-red-400 font-semibold mb-2">
            <AlertTriangle className="w-4 h-4" />
            Potential Deal Breakers Identified
          </div>
          <ul className="space-y-1">
            {report.riskAssessment.dealBreakers.map((db, i) => (
              <li key={i} className="text-sm text-red-400/80 flex items-start gap-2">
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
