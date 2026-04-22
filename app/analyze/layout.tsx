'use client';

import { StepIndicator } from '@/components/layout/StepIndicator';
import { useAnalysis } from '@/context/AnalysisContext';

export default function AnalyzeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { state } = useAnalysis();

  return (
    <div className="min-h-full">
      <div className="bg-surface border-b border-white/[0.06] pt-20 pb-6 px-4">
        <div className="max-w-7xl mx-auto">
          <StepIndicator currentStep={state.step} />
        </div>
      </div>
      <div className="max-w-7xl mx-auto px-4 py-10">{children}</div>
    </div>
  );
}
