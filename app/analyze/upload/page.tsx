'use client';

import { Suspense } from 'react';
import { useState, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2, ChevronRight, PenLine, Zap } from 'lucide-react';
import { FileDropZone, type FileItem } from '@/components/upload/FileDropZone';
import { ClassificationReview } from '@/components/upload/ClassificationReview';
import { useAnalysis } from '@/context/AnalysisContext';
import { ingestDocuments, parseDocuments } from '@/lib/api-client';
import { DEMO_FINANCIAL_DATA } from '@/lib/demo-data';
import type { ClassifiedFileResult, FinancialData } from '@/lib/types';
import { AnimatedButton } from '@/components/ui/animated-button';

/**
 * Pair each local file row with a classification by original name and size.
 * Each server result is consumed at most once so duplicate filenames map correctly.
 */
function pairUploadsWithClassifications(
  items: FileItem[],
  classifiedFiles: ClassifiedFileResult[],
): Array<{ item: FileItem; classified: ClassifiedFileResult | null }> {
  const used = new Set<number>();
  return items.map((item, itemIndex) => {
    let idx = classifiedFiles.findIndex(
      (cf, i) =>
        !used.has(i) &&
        cf.originalName === item.file.name &&
        cf.sizeBytes === item.file.size,
    );
    // Backend exception stubs use sizeBytes=0 while the browser File still has the real size.
    if (idx === -1 && itemIndex < classifiedFiles.length && !used.has(itemIndex)) {
      const atIndex = classifiedFiles[itemIndex];
      if (
        atIndex.originalName === item.file.name &&
        (atIndex.sizeBytes === item.file.size || atIndex.sizeBytes === 0)
      ) {
        idx = itemIndex;
      }
    }
    if (idx === -1) return { item, classified: null };
    used.add(idx);
    return { item, classified: classifiedFiles[idx] };
  });
}

function UploadContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { state, setFinancialData, setStep, setLoading, setError, setAnalysisId, setAnalysisJob, setPipelineDocuments } = useAnalysis();
  const [files, setFiles] = useState<FileItem[]>([]);
  const [classifiedFiles, setClassifiedFiles] = useState<ClassifiedFileResult[]>([]);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [isClassifying, setIsClassifying] = useState(false);
  const [isClassified, setIsClassified] = useState(false);
  const isDemo = searchParams.get('demo') === 'true';

  useEffect(() => {
    setStep(1);
  }, [setStep]);

  useEffect(() => {
    if (isDemo) handleDemo();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDemo]);

  function handleDemo() {
    setAnalysisId(null);
    setAnalysisJob(null);
    setPipelineDocuments([]);
    setFinancialData(DEMO_FINANCIAL_DATA);
    setStep(2);
    router.push('/analyze/review?demo=true');
  }

  const handleClassify = useCallback(async () => {
    if (files.length === 0) return;

    setIsClassifying(true);
    setError(null);

    setFiles((prev) =>
      prev.map((f) => ({ ...f, classificationStatus: 'uploading' as const }))
    );

    try {
      setFiles((prev) =>
        prev.map((f) => ({ ...f, classificationStatus: 'classifying' as const }))
      );

      const result = await ingestDocuments(files.map((f) => f.file));

      setFiles((prev) => {
        const pairs = pairUploadsWithClassifications(prev, result.files);
        return pairs.map(({ item: f, classified }) => {
          if (!classified) {
            return {
              ...f,
              classificationStatus: 'error' as const,
              documentType: 'unknown',
            };
          }
          return {
            ...f,
            classificationStatus: classified.error ? ('error' as const) : ('classified' as const),
            documentType: classified.detectedType || 'unknown',
          };
        });
      });

      setClassifiedFiles(result.files);
      setIsClassified(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to classify documents.');
      setFiles((prev) =>
        prev.map((f) => ({ ...f, classificationStatus: 'error' as const }))
      );
    } finally {
      setIsClassifying(false);
    }
  }, [files, setError]);

  async function handleContinue() {
    setLoading(true, 'Reading your financials...');
    setError(null);

    const effectiveTypes = classifiedFiles.map((cf) =>
      overrides[cf.fileId] || cf.detectedType
    );

    try {
      const result = await parseDocuments(
        files.map((f) => f.file),
        effectiveTypes,
        classifiedFiles.map((cf) => cf.fileHash),
        classifiedFiles.map((cf) => cf.ocrArtifactRef),
      );
      setAnalysisId(result.analysisId ?? null);
      setAnalysisJob(null);
      setPipelineDocuments(result.pipelineDocuments ?? []);
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
    setAnalysisId(null);
    setAnalysisJob(null);
    setPipelineDocuments([]);
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

  function handleOverride(fileId: string, newType: string) {
    setOverrides((prev) => ({ ...prev, [fileId]: newType }));
  }

  function handleReset() {
    setFiles([]);
    setClassifiedFiles([]);
    setOverrides({});
    setIsClassified(false);
    setError(null);
  }

  const canClassify = files.length > 0 && !isClassifying && !isClassified;

  return (
    <div className="animate-fade-in-up">
      <div className="mb-8">
        <div className="inline-flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-4 py-1.5 text-sm text-emerald-400 font-semibold uppercase tracking-wider mb-4">
          Step 1 of 4
        </div>
        <h1 className="text-4xl font-display font-extrabold tracking-tight text-white mb-3">Upload Your Documents</h1>
        <p className="text-t-secondary text-lg max-w-xl">
          Upload the business&apos;s financial documents. AI will automatically detect what each
          document is — no manual labeling needed.
        </p>
      </div>

      {isDemo && (
        <div className="mb-6 p-4 bg-accent/10 border border-accent/20 rounded-xl flex items-start gap-3">
          <Zap className="w-5 h-5 text-accent flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-accent">Demo Mode — Loading sample data</p>
            <p className="text-sm text-t-secondary mt-0.5">
              We&apos;re loading pre-built data for Sunny&apos;s HVAC Services, a fictional
              $850K/year home services business with an SBA loan offer.
            </p>
          </div>
        </div>
      )}

      {state.error && (
        <div className="mb-6 p-4 bg-risk-critical/10 border border-risk-critical/20 rounded-xl text-sm text-risk-critical">
          {state.error}
        </div>
      )}

      <FileDropZone
        files={files}
        onFilesChange={setFiles}
        disabled={isClassifying || isClassified}
      />

      {isClassified && classifiedFiles.length > 0 && (
        <div className="mt-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Classification Results</h2>
            <button
              onClick={handleReset}
              className="text-sm text-t-secondary hover:text-white transition-colors"
            >
              Start over
            </button>
          </div>
          <ClassificationReview
            files={classifiedFiles}
            overrides={overrides}
            onOverride={handleOverride}
          />
        </div>
      )}

      <div className="mt-8 flex flex-col gap-3">
        {!isClassified ? (
          <AnimatedButton
            onClick={handleClassify}
            disabled={!canClassify || state.isLoading}
            variant="emerald"
            className="w-full flex-1 justify-center"
            text={
              isClassifying ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Classifying documents...
                </span>
              ) : (
                "Upload & Classify"
              )
            }
          />
        ) : (
          <AnimatedButton
            onClick={handleContinue}
            disabled={state.isLoading}
            variant="emerald"
            className="w-full flex-1 justify-center"
            text={
              state.isLoading ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  {state.loadingMessage || 'Processing...'}
                </span>
              ) : (
                "Continue with these classifications"
              )
            }
          />
        )}

        <button
          onClick={handleSkip}
          disabled={state.isLoading || isClassifying}
          className="w-full flex items-center justify-center gap-2 text-t-secondary hover:text-white border border-white/[0.08] hover:border-white/[0.15] bg-surface px-6 py-3 rounded-xl font-medium transition-all text-sm"
        >
          <PenLine className="w-4 h-4" />
          Skip — I&apos;ll enter data manually
        </button>

        <button
          onClick={handleDemo}
          disabled={state.isLoading || isClassifying}
          className="w-full flex items-center justify-center gap-2 text-emerald-400 hover:text-emerald-300 border border-emerald-500/20 hover:border-emerald-500/40 bg-emerald-500/5 hover:bg-emerald-500/10 px-6 py-3 rounded-xl font-medium transition-all text-sm"
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
        <Loader2 className="w-8 h-8 animate-spin text-accent" />
      </div>
    }>
      <UploadContent />
    </Suspense>
  );
}
