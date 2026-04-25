'use client';

import { cn } from '@/lib/utils';
import type {
  DeepReviewAgentReview,
  EvidenceReference,
  MissingDataDetail,
  NormalizedFinding,
  NormalizedMetric,
  ReportOutputV2,
  ScoreConflict,
} from '@/lib/types';
import { AlertTriangle, ChevronDown, FileSearch, FolderSearch, Scale, ShieldAlert } from 'lucide-react';

function formatTitle(value: string): string {
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function formatMetricValue(metric: NormalizedMetric, key: string): string {
  if (metric.displayValue) return metric.displayValue;

  if (typeof metric.value === 'number') {
    if (metric.unit === 'usd' || key.includes('price') || key.includes('cash') || key.includes('sde') || key.includes('capital')) {
      return metric.value.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
    }
    if (metric.unit === 'ratio' || metric.unit === 'x' || key === 'dscr' || key.endsWith('_multiple')) {
      return `${metric.value.toFixed(2)}x`;
    }
    if (key.endsWith('_pct') || key.includes('pct')) {
      return `${metric.value.toFixed(metric.value < 10 ? 1 : 0)}%`;
    }
    return metric.value.toLocaleString('en-US', { maximumFractionDigits: 2 });
  }

  if (typeof metric.value === 'boolean') {
    return metric.value ? 'Yes' : 'No';
  }

  if (typeof metric.value === 'string') {
    return metric.value;
  }

  return 'N/A';
}

function severityClasses(severity: NormalizedFinding['severity']): string {
  switch (severity) {
    case 'critical':
      return 'border-red-500/30 bg-red-500/10 text-red-300';
    case 'high':
      return 'border-orange-500/30 bg-orange-500/10 text-orange-300';
    case 'medium':
      return 'border-yellow-500/30 bg-yellow-500/10 text-yellow-300';
    default:
      return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
  }
}

function confidenceLabel(confidence?: number): string | null {
  if (typeof confidence !== 'number') return null;
  return `${Math.round(confidence * 100)}% confidence`;
}

function EvidenceList({ evidence }: { evidence: EvidenceReference[] }) {
  if (!evidence.length) {
    return <p className="text-sm text-t-muted">No direct evidence references were attached to this item.</p>;
  }

  return (
    <div className="space-y-3">
      {evidence.map((item, index) => {
        const extractedEntries = Object.entries(item.extractedFields ?? {});

        return (
          <div key={`${item.documentId}-${item.sectionId ?? index}`} className="rounded-xl border border-white/[0.08] bg-black/10 p-4 space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-semibold text-white">{item.fileName || item.documentId}</span>
              {typeof item.page === 'number' && (
                <span className="rounded-full border border-white/[0.08] px-2 py-0.5 text-xs text-t-muted">Page {item.page}</span>
              )}
              {item.sectionId && (
                <span className="rounded-full border border-white/[0.08] px-2 py-0.5 text-xs text-t-muted">Section {item.sectionId}</span>
              )}
              {confidenceLabel(item.confidence) && (
                <span className="rounded-full border border-white/[0.08] px-2 py-0.5 text-xs text-t-muted">{confidenceLabel(item.confidence)}</span>
              )}
            </div>

            {item.snippet && <p className="text-sm leading-relaxed text-t-secondary">{item.snippet}</p>}

            {extractedEntries.length > 0 && (
              <dl className="grid gap-2 sm:grid-cols-2">
                {extractedEntries.map(([key, value]) => (
                  <div key={key} className="rounded-lg bg-white/[0.03] px-3 py-2">
                    <dt className="text-xs uppercase tracking-wide text-t-muted">{formatTitle(key)}</dt>
                    <dd className="mt-1 text-sm font-medium text-white">{String(value)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        );
      })}
    </div>
  );
}

function FindingCard({ finding }: { finding: NormalizedFinding }) {
  const hasEvidence = finding.evidence.length > 0;

  return (
    <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-4 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn('rounded-full border px-2.5 py-1 text-xs font-semibold', severityClasses(finding.severity))}>
              {finding.severity.toUpperCase()}
            </span>
            <span className="text-xs uppercase tracking-wide text-t-muted">{formatTitle(finding.category)}</span>
            {finding.missingData && (
              <span className="rounded-full border border-white/[0.08] px-2.5 py-1 text-xs font-semibold text-t-muted">Missing data</span>
            )}
          </div>
          <h4 className="text-base font-semibold text-white">{finding.title}</h4>
          <p className="text-sm leading-relaxed text-t-secondary">{finding.description}</p>
        </div>

        <div className="text-right text-xs text-t-muted">
          <div>{formatTitle(finding.sourceAgent)}</div>
          {confidenceLabel(finding.confidence) && <div>{confidenceLabel(finding.confidence)}</div>}
        </div>
      </div>

      {finding.deterministicTags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {finding.deterministicTags.map((tag) => (
            <span key={tag} className="rounded-full bg-white/[0.04] px-2.5 py-1 text-xs text-t-muted">
              {formatTitle(tag)}
            </span>
          ))}
        </div>
      )}

      <details className="group rounded-xl border border-white/[0.08] bg-black/10">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium text-t-secondary">
          <span>{hasEvidence ? `Evidence drilldown (${finding.evidence.length})` : 'Evidence drilldown'}</span>
          <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
        </summary>
        <div className="border-t border-white/[0.08] px-4 py-4">
          <EvidenceList evidence={finding.evidence} />
        </div>
      </details>
    </div>
  );
}

function ConflictCard({ conflict }: { conflict: ScoreConflict }) {
  return (
    <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 space-y-3">
      <div className="flex items-start gap-3">
        <ShieldAlert className="mt-0.5 h-5 w-5 text-red-300" />
        <div className="space-y-1">
          <h4 className="text-base font-semibold text-white">{conflict.description}</h4>
          <p className="text-sm text-t-secondary">Conflict key: {formatTitle(conflict.key)}</p>
          {conflict.conservativeValue !== undefined && (
            <p className="text-sm text-red-200">Conservative value used in scoring: {String(conflict.conservativeValue)}</p>
          )}
        </div>
      </div>

      <dl className="grid gap-2 sm:grid-cols-2">
        {Object.entries(conflict.conflictingValues).map(([source, value]) => (
          <div key={source} className="rounded-lg border border-white/[0.08] bg-black/10 px-3 py-2">
            <dt className="text-xs uppercase tracking-wide text-t-muted">{formatTitle(source)}</dt>
            <dd className="mt-1 text-sm font-medium text-white">{String(value)}</dd>
          </div>
        ))}
      </dl>

      <details className="group rounded-xl border border-white/[0.08] bg-black/10">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium text-t-secondary">
          <span>Supporting evidence</span>
          <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
        </summary>
        <div className="border-t border-white/[0.08] px-4 py-4">
          <EvidenceList evidence={conflict.evidence} />
        </div>
      </details>
    </div>
  );
}

function MissingDataCard({ item }: { item: MissingDataDetail }) {
  return (
    <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/5 p-4 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="text-base font-semibold text-white">{item.description}</h4>
          <p className="text-sm text-t-secondary">{item.impactSummary || item.reason || 'This missing support reduced confidence in the report.'}</p>
        </div>
        <span className={cn(
          'rounded-full px-2.5 py-1 text-xs font-semibold',
          item.required ? 'bg-red-500/15 text-red-300' : 'bg-white/[0.06] text-t-muted'
        )}>
          {item.required ? 'Required' : 'Optional'}
        </span>
      </div>

      <div className="flex flex-wrap gap-2 text-xs text-t-muted">
        {item.documentType && (
          <span className="rounded-full border border-white/[0.08] px-2.5 py-1">{formatTitle(item.documentType)}</span>
        )}
        {item.affectedAgents.map((agent) => (
          <span key={agent} className="rounded-full border border-white/[0.08] px-2.5 py-1">{formatTitle(agent)}</span>
        ))}
      </div>

      {item.relatedFindings.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-wide text-t-muted">Related findings</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {item.relatedFindings.map((findingId) => (
              <span key={findingId} className="rounded-full bg-white/[0.04] px-2.5 py-1 text-xs text-t-secondary">
                {findingId}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function AgentReviewCard({ review }: { review: DeepReviewAgentReview }) {
  const metrics = Object.entries(review.keyMetrics);

  return (
    <details className="group rounded-2xl border border-white/[0.08] bg-raised/40">
      <summary className="flex cursor-pointer list-none items-start justify-between gap-4 px-5 py-4">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-accent/15 px-2.5 py-1 text-xs font-semibold text-accent">
              {formatTitle(review.agentName)}
            </span>
            {typeof review.technicalScore === 'number' && (
              <span className="rounded-full border border-white/[0.08] px-2.5 py-1 text-xs text-t-muted">
                Technical score: {review.technicalScore.toFixed(1)}/10
              </span>
            )}
            {confidenceLabel(review.confidence) && (
              <span className="rounded-full border border-white/[0.08] px-2.5 py-1 text-xs text-t-muted">
                {confidenceLabel(review.confidence)}
              </span>
            )}
          </div>
          <h3 className="text-lg font-semibold text-white">{review.headline || formatTitle(review.agentName)}</h3>
          <p className="text-sm text-t-secondary">{review.summary || 'No specialist summary was included for this review.'}</p>
        </div>
        <ChevronDown className="mt-1 h-5 w-5 text-t-muted transition-transform group-open:rotate-180" />
      </summary>

      <div className="border-t border-white/[0.08] px-5 py-5 space-y-5">
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border border-white/[0.08] bg-black/10 p-4">
            <p className="text-xs uppercase tracking-wide text-t-muted">Scoring impact</p>
            <p className="mt-2 text-sm text-white">
              {typeof review.scoringImpact.riskContribution === 'number'
                ? `${review.scoringImpact.riskContribution > 0 ? '+' : ''}${review.scoringImpact.riskContribution} risk points`
                : 'No explicit point contribution returned'}
            </p>
          </div>
          <div className="rounded-xl border border-white/[0.08] bg-black/10 p-4 md:col-span-2">
            <p className="text-xs uppercase tracking-wide text-t-muted">Buyer-facing dimensions touched</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {review.scoringImpact.buyerFacingDimensions.length > 0 ? review.scoringImpact.buyerFacingDimensions.map((dimension) => (
                <span key={dimension} className="rounded-full bg-white/[0.04] px-2.5 py-1 text-xs text-t-secondary">
                  {formatTitle(dimension)}
                </span>
              )) : <span className="text-sm text-t-muted">No buyer-facing dimensions were attached.</span>}
            </div>
          </div>
        </div>

        {metrics.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-semibold uppercase tracking-wide text-t-muted">Key metrics</h4>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {metrics.map(([key, metric]) => (
                <div key={key} className="rounded-xl border border-white/[0.08] bg-black/10 p-4">
                  <p className="text-xs uppercase tracking-wide text-t-muted">{formatTitle(key)}</p>
                  <p className="mt-2 text-lg font-semibold text-white">{formatMetricValue(metric, key)}</p>
                  {confidenceLabel(metric.confidence) && (
                    <p className="mt-1 text-xs text-t-muted">{confidenceLabel(metric.confidence)}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {review.findings.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-semibold uppercase tracking-wide text-t-muted">Findings</h4>
            <div className="space-y-3">
              {review.findings.map((finding) => (
                <FindingCard key={finding.findingId} finding={finding} />
              ))}
            </div>
          </div>
        )}

        {review.missingInputs.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-semibold uppercase tracking-wide text-t-muted">Missing inputs</h4>
            <div className="flex flex-wrap gap-2">
              {review.missingInputs.map((input) => (
                <span key={`${review.agentName}-${input.key}`} className="rounded-full border border-white/[0.08] px-2.5 py-1 text-xs text-t-secondary">
                  {input.description}
                </span>
              ))}
            </div>
          </div>
        )}

        {review.evidence.length > 0 && (
          <details className="group rounded-xl border border-white/[0.08] bg-black/10">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium text-t-secondary">
              <span>Agent evidence index ({review.evidence.length})</span>
              <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
            </summary>
            <div className="border-t border-white/[0.08] px-4 py-4">
              <EvidenceList evidence={review.evidence} />
            </div>
          </details>
        )}
      </div>
    </details>
  );
}

export function DeepReview({ report }: { report: ReportOutputV2 }) {
  const deepReview = report.deepReview;
  const hasDeepContent = Boolean(
    deepReview &&
    (
      deepReview.agentReviews.length ||
      deepReview.missingData.length ||
      deepReview.evidenceIndex.length ||
      deepReview.auditTrail.length ||
      report.scorecard.conflicts.length
    )
  );

  if (!report.modeAvailable.deep || !deepReview || !hasDeepContent) {
    return null;
  }

  return (
    <section
      id="deep-review"
      className="scroll-mt-32 bg-surface rounded-2xl border border-white/[0.06] p-6 md:p-8 space-y-6 md:space-y-8"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-accent">
            <FileSearch className="h-3.5 w-3.5" />
            Analyst-Grade Deep Review
          </div>
          <h2 className="text-xl font-display font-bold text-white">10. Deep Review</h2>
          <p className="max-w-3xl text-sm leading-relaxed text-t-secondary">
            This optional view exposes the same scoring path used by the summary report, but with specialist sections, evidence drilldowns,
            and explicit conflicts so you can inspect how the conclusion was supported.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-white/[0.08] bg-black/10 px-4 py-3">
            <p className="text-xs uppercase tracking-wide text-t-muted">Agent reviews</p>
            <p className="mt-1 text-2xl font-semibold text-white">{deepReview.agentReviews.length}</p>
          </div>
          <div className="rounded-xl border border-white/[0.08] bg-black/10 px-4 py-3">
            <p className="text-xs uppercase tracking-wide text-t-muted">Score conflicts</p>
            <p className="mt-1 text-2xl font-semibold text-white">{report.scorecard.conflicts.length}</p>
          </div>
        </div>
      </div>

      {report.scorecard.conflicts.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Scale className="h-4 w-4 text-red-300" />
            <h3 className="text-sm font-semibold uppercase tracking-wide text-t-muted">Conflicts</h3>
          </div>
          <div className="space-y-3">
            {report.scorecard.conflicts.map((conflict) => (
              <ConflictCard key={conflict.key} conflict={conflict} />
            ))}
          </div>
        </div>
      )}

      {deepReview.agentReviews.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <FolderSearch className="h-4 w-4 text-accent" />
            <h3 className="text-sm font-semibold uppercase tracking-wide text-t-muted">Specialist sections</h3>
          </div>
          <div className="space-y-4">
            {deepReview.agentReviews.map((review) => (
              <AgentReviewCard key={review.agentName} review={review} />
            ))}
          </div>
        </div>
      )}

      {deepReview.missingData.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-yellow-300" />
            <h3 className="text-sm font-semibold uppercase tracking-wide text-t-muted">Missing data detail</h3>
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            {deepReview.missingData.map((item) => (
              <MissingDataCard key={item.key} item={item} />
            ))}
          </div>
        </div>
      )}

      {(deepReview.auditTrail.length > 0 || deepReview.evidenceIndex.length > 0) && (
        <div className="grid gap-4 lg:grid-cols-2">
          {deepReview.auditTrail.length > 0 && (
            <div className="rounded-2xl border border-white/[0.08] bg-black/10 p-5 space-y-3">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-t-muted">Audit trail</h3>
              <ol className="space-y-2">
                {deepReview.auditTrail.map((entry, index) => (
                  <li key={`${entry}-${index}`} className="flex gap-3 text-sm text-t-secondary">
                    <span className="mt-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-white/[0.06] text-xs font-semibold text-white">
                      {index + 1}
                    </span>
                    <span>{entry}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {deepReview.evidenceIndex.length > 0 && (
            <details className="group rounded-2xl border border-white/[0.08] bg-black/10 p-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-semibold uppercase tracking-wide text-t-muted">
                <span>Evidence index ({deepReview.evidenceIndex.length})</span>
                <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
              </summary>
              <div className="mt-4 border-t border-white/[0.08] pt-4">
                <EvidenceList evidence={deepReview.evidenceIndex} />
              </div>
            </details>
          )}
        </div>
      )}
    </section>
  );
}
