'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAnalysis } from '@/context/AnalysisContext';
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
import { Loader2 } from 'lucide-react';

const SECTIONS = [
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

  useEffect(() => {
    setStep(4);
  }, [setStep]);

  if (state.isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
        <Loader2 className="w-10 h-10 animate-spin text-accent" />
        <p className="text-t-secondary font-medium">{state.loadingMessage || 'Generating your report...'}</p>
        <p className="text-sm text-t-muted">This usually takes 30–60 seconds</p>
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

  const report = state.report;

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  return (
    <div className="relative">
      <ReportHeader report={report} onReset={reset} />

      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex gap-8">
          {/* Sidebar nav — desktop */}
          <aside className="hidden lg:block w-48 flex-shrink-0">
            <div className="sticky top-32 space-y-1">
              <p className="text-xs font-semibold text-t-muted uppercase tracking-wider mb-3">Sections</p>
              {SECTIONS.map((s) => (
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
            <ExecutiveSummary report={report} />
            <FinancialSnapshot report={report} />
            <DebtServiceAnalysis report={report} />
            <RiskAssessment report={report} />
            <TransferabilityAnalysis report={report} />
            <SellerQuestions report={report} />
            <DiligenceChecklist report={report} />
            <UpsideOpportunities report={report} />
            <FinalRecommendation report={report} />
          </div>
        </div>
      </div>
    </div>
  );
}
