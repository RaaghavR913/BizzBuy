'use client';

import { useAnalysis } from '@/context/AnalysisContext';
import { Loader } from '@/components/ui/loader';

export function GlobalLoader() {
  const { state } = useAnalysis();

  if (!state.isLoading) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm animate-in fade-in duration-300">
      <Loader text={state.loadingMessage || 'Loading...'} />
    </div>
  );
}
