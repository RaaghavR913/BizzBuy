'use client';

import React from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CANONICAL_DOCUMENT_TYPES } from '@/lib/constants';
import type { ClassifiedFileResult } from '@/lib/types';
import { cn } from '@/lib/utils';

interface ClassificationReviewProps {
  files: ClassifiedFileResult[];
  overrides: Record<string, string>;
  onOverride: (fileId: string, newType: string) => void;
}

const TYPE_LABELS: Record<string, string> = Object.fromEntries(
  CANONICAL_DOCUMENT_TYPES.map((dt) => [dt.value, dt.label])
);

function typeBadgeColor(type: string): string {
  if (type === 'unknown') return 'bg-red-500/15 text-red-400 border-red-500/30';
  if (type === 'other') return 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30';
  return 'bg-accent/15 text-accent border-accent/30';
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const barColor =
    pct >= 85 ? 'bg-emerald-500' :
    pct >= 65 ? 'bg-yellow-500' :
    'bg-red-500';

  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-1.5 bg-white/[0.08] rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all', barColor)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-t-muted w-8 text-right">{pct}%</span>
    </div>
  );
}

export function ClassificationReview({ files, overrides, onOverride }: ClassificationReviewProps) {
  if (files.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="hidden sm:grid grid-cols-[1fr_160px_120px_180px] gap-3 px-4 text-xs text-t-muted font-medium uppercase tracking-wider">
        <span>Filename</span>
        <span>Detected Type</span>
        <span>Confidence</span>
        <span>Looks wrong?</span>
      </div>

      {files.map((file) => {
        const effectiveType = overrides[file.fileId] || file.detectedType;
        const isOverridden = Boolean(overrides[file.fileId]);

        return (
          <div
            key={file.fileId}
            className="grid grid-cols-1 sm:grid-cols-[1fr_160px_120px_180px] gap-2 sm:gap-3 items-center p-4 bg-surface border border-white/[0.06] rounded-xl"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium text-white truncate">{file.originalName}</p>
              {file.rationale && (
                <p className="text-xs text-t-muted mt-0.5 line-clamp-1">{file.rationale}</p>
              )}
            </div>

            <div>
              <span
                className={cn(
                  'inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-medium',
                  typeBadgeColor(effectiveType),
                  isOverridden && 'ring-1 ring-yellow-500/40'
                )}
              >
                {TYPE_LABELS[effectiveType] || effectiveType}
              </span>
            </div>

            <ConfidenceBar confidence={file.confidence} />

            <div>
              <Select
                value={overrides[file.fileId] || ''}
                onValueChange={(v) => onOverride(file.fileId, v)}
              >
                <SelectTrigger className="h-8 text-xs bg-raised border-white/[0.08]">
                  <SelectValue placeholder="Override type..." />
                </SelectTrigger>
                <SelectContent>
                  {CANONICAL_DOCUMENT_TYPES.map((dt) => (
                    <SelectItem key={dt.value} value={dt.value} className="text-xs">
                      {dt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        );
      })}
    </div>
  );
}
