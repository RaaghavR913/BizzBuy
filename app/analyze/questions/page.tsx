'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronLeft, ChevronRight, FileSearch, HelpCircle, Loader2, ShieldAlert } from 'lucide-react';
import { Slider } from '@/components/ui/slider';
import { useAnalysis } from '@/context/AnalysisContext';
import { analyzeData, startAnalysisJob } from '@/lib/api-client';
import {
  buildClarificationAnswers,
  DEFAULT_QUESTIONNAIRE,
  generateClarificationQuestions,
  questionnaireFromClarifications,
} from '@/lib/clarification-service';
import type { ClarificationQuestion } from '@/lib/types';
import { cn } from '@/lib/utils';
import { Slider } from '@/components/ui/slider';
import { BlurText } from '@/components/ui/blur-text';

type ResponseValue = string | number | boolean | null;

function ToggleQuestion({
  question,
  value,
  onChange,
}: {
  question: ClarificationQuestion;
  value: boolean | null;
  onChange: (next: boolean | null) => void;
}) {
  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-t-secondary">{question.prompt}</p>
      <div className="flex gap-2">
        {[
          { value: true, label: 'Yes' },
          { value: false, label: 'No' },
          { value: null, label: "Don't know" },
        ].map((option) => (
          <button
            key={String(option.value)}
            type="button"
            onClick={() => onChange(option.value)}
            className={cn(
              'flex-1 rounded-xl border px-4 py-3 text-sm font-medium transition-all',
              value === option.value
                ? 'border-accent bg-accent/10 text-accent'
                : 'border-white/[0.08] bg-raised text-t-secondary hover:border-accent/30'
            )}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function SelectQuestion({
  question,
  value,
  onChange,
}: {
  question: ClarificationQuestion;
  value: string | null;
  onChange: (next: string | null) => void;
}) {
  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-t-secondary">{question.prompt}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {(question.options ?? []).map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={cn(
              'rounded-xl border px-4 py-3 text-left transition-all',
              value === option.value
                ? 'border-accent bg-accent/10 text-accent'
                : 'border-white/[0.08] bg-raised text-t-secondary hover:border-accent/30'
            )}
          >
            <span className="block text-sm font-medium">{option.label}</span>
            {option.sublabel ? <span className="mt-1 block text-xs text-t-muted">{option.sublabel}</span> : null}
          </button>
        ))}
        <button
          type="button"
          onClick={() => onChange(null)}
          className={cn(
            'rounded-xl border px-4 py-3 text-left transition-all',
            value === null
              ? 'border-accent bg-accent/10 text-accent'
              : 'border-white/[0.08] bg-raised text-t-secondary hover:border-accent/30'
          )}
        >
          <span className="block text-sm font-medium">I don&apos;t know</span>
        </button>
      </div>
    </div>
  );
}

function PercentQuestion({
  question,
  value,
  onChange,
}: {
  question: ClarificationQuestion;
  value: number | null;
  onChange: (next: number | null) => void;
}) {
  const sliderValue = value ?? 25;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm font-medium text-t-secondary">{question.prompt}</p>
        <button
          type="button"
          onClick={() => onChange(null)}
          className="flex items-center gap-1 text-xs text-t-muted transition-colors hover:text-t-secondary"
        >
          <HelpCircle className="h-3.5 w-3.5" />
          Unknown
        </button>
      </div>
      <Slider
        value={[sliderValue]}
        onValueChange={(values) => onChange(Array.isArray(values) ? values[0] : values)}
        min={0}
        max={100}
        step={5}
      />
      <div className="flex items-center justify-between text-xs text-t-muted">
        <span>0%</span>
        <span className="font-mono text-accent">{value === null ? 'Unspecified' : `${value}%`}</span>
        <span>100%</span>
      </div>
    </div>
  );
}

function renderQuestion(
  question: ClarificationQuestion,
  value: ResponseValue,
  onChange: (next: ResponseValue) => void
) {
  if (question.answerType === 'boolean') {
    return <ToggleQuestion question={question} value={typeof value === 'boolean' ? value : null} onChange={onChange} />;
  }

  if (question.answerType === 'percent') {
    return <PercentQuestion question={question} value={typeof value === 'number' ? value : null} onChange={onChange} />;
  }

  return <SelectQuestion question={question} value={typeof value === 'string' ? value : null} onChange={onChange} />;
}

export default function QuestionsPage() {
  const router = useRouter();
  const {
    state,
    setClarifications,
    setQuestionnaire,
    setSharedContext,
    setReport,
    setStep,
    setLoading,
    setError,
    setAnalysisJob,
  } = useAnalysis();
  const clarificationQuestions = generateClarificationQuestions(state.pipelineDocuments, state.financialData);
  const [responses, setResponses] = useState<Record<string, ResponseValue>>(
    () => Object.fromEntries(state.clarifications.map((clarification) => [clarification.questionId, clarification.value]))
  );

  useEffect(() => {
    setStep(3);
  }, [setStep]);

  function updateResponse(questionId: string, value: ResponseValue) {
    setResponses((current) => ({ ...current, [questionId]: value }));
  }

  async function handleGenerate() {
    if (!state.financialData || !state.dealInfo) {
      setError('Missing financial data. Please go back and re-enter your financials.');
      return;
    }

    const hasPipelineDocuments = state.pipelineDocuments.some((document) => document.sections.length > 0);
    const clarificationAnswers = buildClarificationAnswers(clarificationQuestions, responses);
    const questionnaire = questionnaireFromClarifications(
      clarificationAnswers,
      state.questionnaire ?? DEFAULT_QUESTIONNAIRE
    );

    setClarifications(clarificationAnswers);
    setQuestionnaire(questionnaire);
    setSharedContext(null);
    setLoading(true, hasPipelineDocuments ? 'Running document-first analysis...' : 'Running deterministic backend analysis...');
    setError(null);

    try {
      if (hasPipelineDocuments) {
        const job = await startAnalysisJob(state.financialData, questionnaire, state.dealInfo, {
          analysisId: state.analysisId,
          pipelineDocuments: state.pipelineDocuments,
          clarifications: clarificationAnswers,
        });
        setAnalysisJob(job);
        setStep(4);
        router.push('/analyze/report');
        return;
      }

      const result = await analyzeData(state.financialData, questionnaire, state.dealInfo, {
        analysisId: state.analysisId,
        pipelineDocuments: state.pipelineDocuments,
        clarifications: clarificationAnswers,
      });
      setAnalysisJob(null);
      setReport(result.report);
      setStep(4);
      router.push('/analyze/report');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed. Please try again.');
    } finally {
      if (!hasPipelineDocuments) {
        setLoading(false);
      }
    }
  }

  return (
    <div className="animate-fade-in-up">
      <div className="mb-6">
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent/10 px-3 py-1 text-xs font-medium text-accent">
          Step 3 of 4
        </div>
        <h1 className="mb-2 text-2xl font-display font-bold text-white">Targeted Clarifications</h1>
        <p className="max-w-2xl text-sm text-t-secondary">
          We only ask for follow-ups where the uploaded package leaves a meaningful gap. Your answers are stored as supplemental evidence and do not outweigh the documents by default.
        </p>
      </div>

      <div className="space-y-4">
        <div className="rounded-2xl border border-white/[0.06] bg-surface p-5">
          <div className="flex items-start gap-3">
            <div className="rounded-xl border border-amber-500/25 bg-amber-500/10 p-3 text-amber-300">
              <ShieldAlert className="h-5 w-5" />
            </div>
            <div className="space-y-1">
              <p className="text-sm font-semibold text-white">Evidence handling</p>
              <p className="text-sm text-t-secondary">
                Clarifications help close document gaps, but they remain tagged as buyer-provided assertions until corroborated.
              </p>
            </div>
          </div>
        </div>

        {clarificationQuestions.length === 0 ? (
          <div className="rounded-2xl border border-white/[0.06] bg-surface p-8 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-emerald-500/25 bg-emerald-500/10 text-emerald-300">
              <FileSearch className="h-5 w-5" />
            </div>
            <h2 className="text-lg font-semibold text-white">No follow-up questions required</h2>
            <p className="mt-2 text-sm text-t-secondary">
              The current package already covers the main diligence inputs needed for this pass. You can continue straight to report generation.
            </p>
          </div>
        ) : (
          clarificationQuestions.map((question, index) => (
            <div key={question.id} className="rounded-2xl border border-white/[0.06] bg-surface p-6">
              <div className="mb-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent/80">
                  Clarification {index + 1}
                </p>
                <p className="mt-2 text-sm text-t-muted">{question.helpText}</p>
              </div>
              {renderQuestion(question, responses[question.id] ?? null, (next) => updateResponse(question.id, next))}
            </div>
          ))
        )}
      </div>

      {state.error ? (
        <div className="mt-4 rounded-lg border border-risk-critical/20 bg-risk-critical/10 px-4 py-3 text-sm text-risk-critical">
          {state.error}
        </div>
      ) : null}

      <div className="mt-6 flex gap-3">
        <button
          onClick={() => router.push('/analyze/review')}
          className="flex items-center gap-2 rounded-xl border border-white/[0.08] bg-surface px-5 py-3 text-sm font-medium text-t-secondary transition-all hover:border-white/[0.15] hover:text-white"
        >
          <ChevronLeft className="h-4 w-4" />
          Back to Review
        </button>

        <button
          onClick={handleGenerate}
          disabled={state.isLoading}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-accent px-6 py-3 font-semibold text-white transition-all hover:bg-accent-hover disabled:cursor-not-allowed disabled:bg-raised disabled:text-t-muted"
        >
          {state.isLoading ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              {state.loadingMessage || 'Generating report...'}
            </>
          ) : (
            <>
              Generate Report
              <ChevronRight className="h-5 w-5" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
