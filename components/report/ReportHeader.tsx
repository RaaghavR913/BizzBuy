'use client';

import type { ReportOutput } from '@/lib/types';
import { generatePDF } from '@/lib/api-client';
import { ScoreBadge } from './ScoreBadge';
import { Download, RotateCcw, AlertTriangle, CheckCircle2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useState } from 'react';
import Link from 'next/link';

interface ReportHeaderProps {
  report: ReportOutput;
  onReset: () => void;
}

export function ReportHeader({ report, onReset }: ReportHeaderProps) {
  const [downloading, setDownloading] = useState(false);
  const { action } = report.finalRecommendation;

  const recConfig = {
    proceed: { color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', icon: CheckCircle2, label: 'Proceed' },
    proceed_with_caution: { color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30', icon: AlertCircle, label: 'Proceed with Caution' },
    walk_away: { color: 'bg-red-500/20 text-red-400 border-red-500/30', icon: AlertTriangle, label: 'Walk Away' },
  }[action];

  const RecIcon = recConfig.icon;

  async function handleDownload() {
    setDownloading(true);
    try {
      await generatePDF(report);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="sticky top-16 z-40 bg-surface/95 backdrop-blur-xl border-b border-white/[0.06] shadow-sm py-4 md:py-5 px-4 sm:px-6">
      <div className="max-w-6xl mx-auto flex items-center justify-between gap-4 gap-y-3 flex-wrap">
        <div className="flex items-center gap-4 flex-wrap">
          <ScoreBadge
            score={report.executiveSummary.riskScore}
            label={`Risk — ${report.executiveSummary.riskLabel}`}
            type="risk"
            size="sm"
          />
          <ScoreBadge
            score={report.transferabilityAnalysis.score}
            label={`Transfer — ${report.executiveSummary.transferabilityLabel}`}
            type="transferability"
            size="sm"
          />
          <span className={cn('inline-flex items-center gap-1.5 text-sm px-3 py-1 rounded-full font-semibold border', recConfig.color)}>
            <RecIcon className="w-3.5 h-3.5" />
            {recConfig.label}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="flex items-center gap-1.5 text-sm px-3 py-2 border border-white/[0.08] rounded-lg text-t-secondary hover:text-white hover:bg-white/[0.05] transition-all disabled:opacity-50"
          >
            <Download className="w-4 h-4" />
            {downloading ? 'Preparing...' : 'Download'}
          </button>
          <Link
            href="/"
            onClick={onReset}
            className="flex items-center gap-1.5 text-sm px-3 py-2 border border-white/[0.08] rounded-lg text-t-secondary hover:text-white hover:bg-white/[0.05] transition-all"
          >
            <RotateCcw className="w-4 h-4" />
            New Analysis
          </Link>
        </div>
      </div>
    </div>
  );
}
