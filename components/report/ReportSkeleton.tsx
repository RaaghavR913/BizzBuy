'use client';

import { useEffect, useState } from 'react';
import { CheckCircle2, Circle, Loader2 } from 'lucide-react';
import type { AnalysisJobSnapshot } from '@/lib/types';

interface ReportSkeletonProps {
  job: AnalysisJobSnapshot | null;
}

const SECTION_LABELS = [
  'Executive Summary',
  'Financials',
  'Debt Service',
  'Risk Assessment',
  'Transferability',
  'Seller Questions',
  'Diligence',
  'Upside',
  'Recommendation',
];

// Maps backend stage_key → human label for the 8 specialist pills.
const AGENT_PILLS: { key: string; label: string }[] = [
  { key: 'ingestion', label: 'Ingestion' },
  { key: 'financial_analysis', label: 'Financial' },
  { key: 'tax_compliance', label: 'Tax' },
  { key: 'ar_collections', label: 'AR' },
  { key: 'customer_concentration', label: 'Customers' },
  { key: 'operations_transferability', label: 'Operations' },
  { key: 'lease_contract', label: 'Lease' },
  { key: 'market_macro', label: 'Market' },
];

function useElapsed(startedAt: string | null | undefined): string {
  const [elapsed, setElapsed] = useState('0:00');

  useEffect(() => {
    if (!startedAt) return;
    const origin = new Date(startedAt).getTime();

    const tick = () => {
      const secs = Math.floor((Date.now() - origin) / 1000);
      const m = Math.floor(secs / 60);
      const s = secs % 60;
      setElapsed(`${m}:${s.toString().padStart(2, '0')}`);
    };

    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  return elapsed;
}

export function ReportSkeleton({ job }: ReportSkeletonProps) {
  const progress = job?.progress.progress ?? 0;
  const message = job?.progress.message ?? 'Preparing analysis…';
  const completedAgents = job?.progress.completedAgents ?? [];
  const elapsed = useElapsed(job?.startedAt);
  const progressPercent = Math.round(progress * 100);

  // Ingestion is complete when any specialist agent has been emitted,
  // or when the stage is past ingestion.
  const ingestionDone =
    completedAgents.length > 0 ||
    (job?.progress.stage !== 'ingestion' && job?.progress.stage !== 'queued' && !!job?.progress.stage);

  const isAgentDone = (key: string) => {
    if (key === 'ingestion') return ingestionDone;
    return completedAgents.includes(key);
  };

  return (
    <div className="animate-fade-in-up">
      {/* ── Top stage strip ──────────────────────────────────────────────── */}
      <div className="sticky top-0 z-20 bg-surface/95 backdrop-blur border-b border-white/[0.06] px-4 py-3">
        <div className="max-w-6xl mx-auto space-y-2">
          {/* Stage label + elapsed + spinner */}
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 min-w-0">
              <Loader2 className="w-4 h-4 animate-spin text-accent flex-shrink-0" />
              <span className="text-sm font-medium text-white truncate">{message}</span>
            </div>
            <div className="flex items-center gap-3 flex-shrink-0">
              <span className="text-xs text-t-muted font-sans">{elapsed}</span>
              <span className="text-xs font-semibold text-accent">{progressPercent}%</span>
            </div>
          </div>

          {/* Progress bar */}
          <div className="h-1 bg-white/[0.06] rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all duration-700 ease-out"
              style={{ width: `${Math.max(3, progressPercent)}%` }}
            />
          </div>

          {/* Agent pills */}
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            {AGENT_PILLS.map(({ key, label }) => {
              const done = isAgentDone(key);
              return (
                <span
                  key={key}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium transition-colors ${
                    done
                      ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25'
                      : 'bg-white/[0.04] text-t-muted border border-white/[0.06]'
                  }`}
                >
                  {done ? (
                    <CheckCircle2 className="w-3 h-3" />
                  ) : (
                    <Circle className="w-3 h-3 opacity-50" />
                  )}
                  {label}
                </span>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Layout skeleton ──────────────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex gap-8">
          {/* Sidebar nav skeleton */}
          <aside className="hidden lg:block w-48 flex-shrink-0">
            <div className="sticky top-36 space-y-1">
              <p className="text-xs font-semibold text-t-muted uppercase tracking-wider mb-3">Sections</p>
              {SECTION_LABELS.map((label) => (
                <div
                  key={label}
                  className="w-full text-left text-sm text-t-muted px-3 py-2 rounded-lg select-none"
                >
                  {label}
                </div>
              ))}
            </div>
          </aside>

          {/* Section skeletons */}
          <div className="flex-1 min-w-0 space-y-4">
            {SECTION_LABELS.map((label, i) => (
              <SectionShell key={label} label={label} index={i} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function SectionShell({ label, index }: { label: string; index: number }) {
  // Stagger the pulse animation slightly so sections don't all pulse together.
  const delay = `${index * 80}ms`;

  return (
    <div
      className="rounded-2xl border border-white/[0.06] bg-surface p-5 space-y-3"
      style={{ animationDelay: delay }}
    >
      {/* Section title row */}
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-white">{index + 1}. {label}</h2>
        <span className="inline-flex items-center gap-1.5 text-xs text-t-muted">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          Analyzing…
        </span>
      </div>

      {/* Skeleton lines */}
      <div className="space-y-2 animate-pulse">
        <div className="h-3 bg-white/[0.06] rounded-full w-4/5" />
        <div className="h-3 bg-white/[0.06] rounded-full w-3/5" />
        <div className="h-3 bg-white/[0.06] rounded-full w-2/3" />
      </div>

      {/* Metric row skeleton */}
      {index < 3 && (
        <div className="grid grid-cols-3 gap-3 pt-1 animate-pulse">
          {[...Array(3)].map((_, j) => (
            <div key={j} className="h-14 bg-white/[0.04] rounded-xl" />
          ))}
        </div>
      )}
    </div>
  );
}
