'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAnalysis } from '@/context/AnalysisContext';
import { DeepReview } from '@/components/report/DeepReview';
import { ReportHeader } from '@/components/report/ReportHeader';
import { ExecutiveSummary } from '@/components/report/ExecutiveSummary';
import { FinancialSnapshot } from '@/components/report/FinancialSnapshot';
import { DebtServiceAnalysis } from '@/components/report/DebtServiceAnalysis';
import { RiskAssessment } from '@/components/report/RiskAssessment';
import { TransferabilityAnalysis } from '@/components/report/TransferabilityAnalysis';
import { SellerQuestions } from '@/components/report/SellerQuestions';
import { DiligenceChecklist } from '@/components/report/DiligenceChecklist';
import { UpsideOpportunities } from '@/components/report/UpsideOpportunities';
import { FinalRecommendation } from '@/components/report/FinalRecommendation';
import { isReportOutputV2, normalizeReportOutput } from '@/lib/report-normalization';
import { Loader2, AlertTriangle, RefreshCw, RotateCcw } from 'lucide-react';

const SUMMARY_SECTIONS = [
  { id: 'executive-summary', label: 'Executive Summary' },
  { id: 'financial-snapshot', label: 'Financials' },
  { id: 'debt-service', label: 'Debt Service' },
  { id: 'risk-assessment', label: 'Risk Assessment' },
  { id: 'transferability', label: 'Transferability' },
  { id: 'seller-questions', label: 'Seller Questions' },
  { id: 'diligence-checklist', label: 'Diligence' },
  { id: 'upside', label: 'Upside' },
  { id: 'final-recommendation', label: 'Recommendation' },
];

export default function ReportPage() {
  const router = useRouter();
  const { state, setStep, reset } = useAnalysis();
  const [showDeepReview, setShowDeepReview] = useState(false);

  useEffect(() => {
    setStep(4);
  }, [setStep]);

  if (state.isLoading) {
    const progressPercent = state.analysisJob ? Math.round(state.analysisJob.progress.progress * 100) : null;
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
        <Loader2 className="w-10 h-10 animate-spin text-accent" />
        <p className="text-t-secondary font-medium">{state.loadingMessage || 'Generating your report...'}</p>
        <p className="text-sm text-t-muted">
          {progressPercent !== null ? `${progressPercent}% complete` : 'This usually takes 30-60 seconds'}
        </p>
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4 max-w-xl mx-auto px-4">
        <div className="w-full rounded-2xl border border-red-500/25 bg-red-500/10 p-5 text-center space-y-2">
          <div className="flex items-center justify-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <p className="text-sm font-semibold text-red-400">Analysis failed</p>
          </div>
          <p className="text-sm text-t-secondary">{state.error}</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => router.push('/analyze/questions')}
            className="flex items-center gap-2 border border-white/10 hover:border-white/20 text-t-secondary hover:text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-all"
          >
            <RefreshCw className="w-4 h-4" />
            Adjust answers and retry
          </button>
          <button
            onClick={() => { reset(); router.push('/analyze/upload'); }}
            className="flex items-center gap-2 bg-accent hover:bg-accent-hover text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-all"
          >
            <RotateCcw className="w-4 h-4" />
            Start over
          </button>
        </div>
      </div>
    );
  }

  if (!state.report) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
        <p className="text-t-secondary">No report found. Please complete the analysis flow.</p>
        <button
          onClick={() => router.push('/analyze/upload')}
          className="bg-accent hover:bg-accent-hover text-white px-6 py-3 rounded-xl font-semibold transition-all"
        >
          Start Analysis
        </button>
      </div>
    );
  }

  const summaryReport = normalizeReportOutput(state.report);
  const deepReviewReport = isReportOutputV2(state.report) ? state.report : null;
  const canRenderDeepReview = Boolean(
    deepReviewReport?.modeAvailable.deep &&
      deepReviewReport.deepReview &&
      (
        deepReviewReport.deepReview.agentReviews.length ||
        deepReviewReport.deepReview.evidenceIndex.length ||
        deepReviewReport.deepReview.auditTrail.length ||
        deepReviewReport.deepReview.missingData.length ||
        deepReviewReport.scorecard.conflicts.length
      )
  );
  const sections = canRenderDeepReview && showDeepReview
    ? [...SUMMARY_SECTIONS, { id: 'deep-review', label: 'Deep Review' }]
    : SUMMARY_SECTIONS;

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  return (
    <div className="relative">
      <ReportHeader report={summaryReport} onReset={reset} />

      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex gap-8">
          {/* Sidebar nav — desktop */}
          <aside className="hidden lg:block w-48 flex-shrink-0">
            <div className="sticky top-32 space-y-1">
              <p className="text-xs font-semibold text-t-muted uppercase tracking-wider mb-3">Sections</p>
              {sections.map((s) => (
                <button
                  key={s.id}
                  onClick={() => scrollTo(s.id)}
                  className="w-full text-left text-sm text-t-secondary hover:text-white hover:bg-white/[0.05] px-3 py-2 rounded-lg transition-colors"
                >
                  {s.label}
                </button>
              ))}
            </div>
          </aside>

          {/* Report content */}
          <div className="flex-1 min-w-0 space-y-6">
            {canRenderDeepReview && (
              <section className="bg-surface rounded-2xl border border-white/[0.06] p-5 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">Deep review available</p>
                    <p className="text-sm text-t-secondary">
                      Keep the summary report as the default view, or open the deeper analyst review when you want
                      specialist evidence, finding drilldowns, and explicit score conflicts.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowDeepReview((current) => !current)}
                    className="rounded-xl border border-accent/25 bg-accent/10 px-4 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent/15"
                  >
                    {showDeepReview ? 'Hide Deep Review' : 'Show Deep Review'}
                  </button>
                </div>
              </section>
            )}

            <ExecutiveSummary report={summaryReport} />
            <FinancialSnapshot report={summaryReport} />
            <DebtServiceAnalysis report={summaryReport} />
            <RiskAssessment report={summaryReport} />
            <TransferabilityAnalysis report={summaryReport} />
            <SellerQuestions report={summaryReport} />
            <DiligenceChecklist report={summaryReport} />
            <UpsideOpportunities report={summaryReport} />
            <FinalRecommendation report={summaryReport} />
            {canRenderDeepReview && showDeepReview && deepReviewReport && <DeepReview report={deepReviewReport} />}
          </div>
        </div>
      </div>
    </div>
  );
}
