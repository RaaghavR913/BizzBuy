'use client';

import { cn } from '@/lib/utils';

interface ScoreBadgeProps {
  score: number;
  maxScore?: number;
  label?: string;
  type?: 'risk' | 'transferability' | 'dimension';
  size?: 'sm' | 'md' | 'lg';
}

function getRiskStyle(score: number, max: number, type: string) {
  const normalized = max === 10 ? score : score;
  if (type === 'transferability') {
    if (normalized >= 65) return { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20', bar: 'bg-emerald-500' };
    if (normalized >= 40) return { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/20', bar: 'bg-amber-500' };
    if (normalized >= 20) return { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/20', bar: 'bg-orange-500' };
    return { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/20', bar: 'bg-red-500' };
  }
  if (max === 100) {
    if (normalized <= 35) return { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20', bar: 'bg-emerald-500' };
    if (normalized <= 65) return { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/20', bar: 'bg-amber-500' };
    if (normalized <= 80) return { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/20', bar: 'bg-orange-500' };
    return { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/20', bar: 'bg-red-500' };
  }
  // dimension 1-10
  if (score <= 3) return { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20', bar: 'bg-emerald-500' };
  if (score <= 5) return { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/20', bar: 'bg-amber-500' };
  if (score <= 7) return { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/20', bar: 'bg-orange-500' };
  return { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/20', bar: 'bg-red-500' };
}

export function ScoreBadge({ score, maxScore = 100, label, type = 'risk', size = 'md' }: ScoreBadgeProps) {
  const style = getRiskStyle(score, maxScore, type);
  const sizeClass = size === 'sm' ? 'text-sm px-2.5 py-1' : size === 'lg' ? 'text-xl px-4 py-2 font-black' : 'text-base px-3 py-1.5 font-bold';

  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 rounded-full border font-semibold',
      style.bg, style.text, style.border, sizeClass
    )}>
      {score}/{maxScore}
      {label && <span className="opacity-75">— {label}</span>}
    </span>
  );
}

export function RiskBar({ score, max = 10 }: { score: number; max?: number }) {
  const pct = (score / max) * 100;
  const style = getRiskStyle(score, max, 'risk');
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-raised rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all', style.bar)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={cn('text-sm font-bold w-10 text-right font-sans', style.text)}>
        {score}/{max}
      </span>
    </div>
  );
}
