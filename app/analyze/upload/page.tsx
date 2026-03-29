'use client';

import { Suspense } from 'react';
import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2, ChevronRight, PenLine, Zap } from 'lucide-react';
import { FileDropZone, type FileItem } from '@/components/upload/FileDropZone';
import { useAnalysis } from '@/context/AnalysisContext';
import { parseDocuments } from '@/lib/api-client';
import { DEMO_FINANCIAL_DATA } from '@/lib/demo-data';
import type { FinancialData } from '@/lib/types';

function UploadContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { state, setFinancialData, setStep, setLoading, setError } = useAnalysis();
  const [files, setFiles] = useState<FileItem[]>([]);
  const isDemo = searchParams.get('demo') === 'true';

  useEffect(() => {
    setStep(1);
  }, [setStep]);

  useEffect(() => {
    if (isDemo) handleDemo();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDemo]);

  function handleDemo() {
    setFinancialData(DEMO_FINANCIAL_DATA);
    setStep(2);
    router.push('/analyze/review?demo=true');
  }

  async function handleUpload() {
    const missingType = files.find((f) => !f.documentType);
    if (missingType) {
      setError('Please select a document type for each uploaded file.');
      return;
    }

    setLoading(true, 'Reading your financials...');
    setError(null);

    try {
      const result = await parseDocuments(
        files.map((f) => f.file),
        files.map((f) => f.documentType)
      );
      setFinancialData(result.extractedData);
      setStep(2);
      router.push('/analyze/review');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to parse documents. Try manual entry.');
    } finally {
      setLoading(false);
    }
  }

  function handleSkip() {
    const empty: FinancialData = {
      incomeStatement: null,
      balanceSheet: null,
      loanTerms: null,
      cashFlow: null,
      parsingNotes: ['Data entered manually by user.'],
      dataCompleteness: 0,
    };
    setFinancialData(empty);
    setStep(2);
    router.push('/analyze/review');
  }

  const canUpload = files.length > 0 && files.every((f) => f.documentType);

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Upload Your Documents</h1>
        <p className="text-slate-500">
          Upload the business&apos;s financial documents. We&apos;ll extract the data using AI and
          ask you to confirm before analysis.
        </p>
      </div>

      {isDemo && (
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-xl flex items-start gap-3">
          <Zap className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-blue-800">Demo Mode — Loading sample data</p>
            <p className="text-sm text-blue-700 mt-0.5">
              We&apos;re loading pre-built data for Sunny&apos;s HVAC Services, a fictional
              $850K/year home services business with an SBA loan offer.
            </p>
          </div>
        </div>
      )}

      {state.error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
          {state.error}
        </div>
      )}

      <FileDropZone files={files} onFilesChange={setFiles} />

      <div className="mt-8 flex flex-col gap-3">
        <button
          onClick={handleUpload}
          disabled={!canUpload || state.isLoading}
          className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white px-6 py-4 rounded-xl font-semibold transition-colors"
        >
          {state.isLoading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              {state.loadingMessage || 'Processing...'}
            </>
          ) : (
            <>
              Analyze Documents
              <ChevronRight className="w-5 h-5" />
            </>
          )}
        </button>

        <button
          onClick={handleSkip}
          disabled={state.isLoading}
          className="w-full flex items-center justify-center gap-2 text-slate-600 hover:text-slate-900 border border-slate-200 hover:border-slate-300 bg-white px-6 py-3 rounded-xl font-medium transition-colors text-sm"
        >
          <PenLine className="w-4 h-4" />
          Skip — I&apos;ll enter data manually
        </button>

        <button
          onClick={handleDemo}
          disabled={state.isLoading}
          className="w-full flex items-center justify-center gap-2 text-blue-600 hover:text-blue-700 border border-blue-200 hover:border-blue-300 bg-blue-50 px-6 py-3 rounded-xl font-medium transition-colors text-sm"
        >
          <Zap className="w-4 h-4" />
          Load Demo — Sunny&apos;s HVAC Services
        </button>
      </div>
    </div>
  );
}

export default function UploadPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    }>
      <UploadContent />
    </Suspense>
  );
}
