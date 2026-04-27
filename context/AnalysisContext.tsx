'use client';

import React, { createContext, useContext, useReducer, useCallback, useEffect, useState } from 'react';
import { ensureAnalysisFlow, getAnalysisJob, getAnalysisJobEventsUrl } from '@/lib/api-client';
import type {
  AnalysisJobSnapshot,
  AnalysisState,
  AnyReportOutput,
  ClarificationAnswer,
  DealInfo,
  FinancialData,
  PipelineDocumentPayload,
  QuestionnaireData,
  SharedContext,
} from '@/lib/types';

const STORAGE_KEY = 'bizbuy-analysis-state';

type Action =
  | { type: 'SET_STEP'; payload: 1 | 2 | 3 | 4 }
  | { type: 'SET_FINANCIAL_DATA'; payload: FinancialData }
  | { type: 'SET_QUESTIONNAIRE'; payload: QuestionnaireData }
  | { type: 'SET_CLARIFICATIONS'; payload: ClarificationAnswer[] }
  | { type: 'SET_DEAL_INFO'; payload: DealInfo }
  | { type: 'SET_ANALYSIS_ID'; payload: string | null }
  | { type: 'SET_ANALYSIS_JOB'; payload: AnalysisJobSnapshot | null }
  | { type: 'SET_PIPELINE_DOCUMENTS'; payload: PipelineDocumentPayload[] }
  | { type: 'SET_SHARED_CONTEXT'; payload: SharedContext | null }
  | { type: 'SET_REPORT'; payload: AnyReportOutput }
  | { type: 'SET_LOADING'; payload: { isLoading: boolean; message?: string } }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'RESTORE_STATE'; payload: AnalysisState }
  | { type: 'RESET' };

const initialState: AnalysisState = {
  step: 1,
  financialData: null,
  questionnaire: null,
  clarifications: [],
  dealInfo: null,
  analysisId: null,
  analysisJob: null,
  pipelineDocuments: [],
  sharedContext: null,
  report: null,
  isLoading: false,
  loadingMessage: '',
  error: null,
};

function getStoredState(): AnalysisState {
  const rawState = window.sessionStorage.getItem(STORAGE_KEY);
  if (!rawState) {
    return initialState;
  }

  try {
    return {
      ...initialState,
      ...JSON.parse(rawState),
      error: null,
      isLoading: false,
      loadingMessage: '',
    } as AnalysisState;
  } catch {
    return initialState;
  }
}

function persistedState(state: AnalysisState): AnalysisState {
  return {
    ...state,
    error: null,
    isLoading: false,
    loadingMessage: '',
  };
}

function reducer(state: AnalysisState, action: Action): AnalysisState {
  switch (action.type) {
    case 'SET_STEP':
      return { ...state, step: action.payload };
    case 'SET_FINANCIAL_DATA':
      return { ...state, financialData: action.payload };
    case 'SET_QUESTIONNAIRE':
      return { ...state, questionnaire: action.payload };
    case 'SET_CLARIFICATIONS':
      return { ...state, clarifications: action.payload };
    case 'SET_DEAL_INFO':
      return { ...state, dealInfo: action.payload };
    case 'SET_ANALYSIS_ID':
      return { ...state, analysisId: action.payload };
    case 'SET_ANALYSIS_JOB':
      return { ...state, analysisJob: action.payload };
    case 'SET_PIPELINE_DOCUMENTS':
      return { ...state, pipelineDocuments: action.payload };
    case 'SET_SHARED_CONTEXT':
      return { ...state, sharedContext: action.payload };
    case 'SET_REPORT':
      return { ...state, report: action.payload };
    case 'SET_LOADING':
      return {
        ...state,
        isLoading: action.payload.isLoading,
        loadingMessage: action.payload.message || '',
      };
    case 'SET_ERROR':
      return { ...state, error: action.payload, isLoading: false };
    case 'RESTORE_STATE':
      return action.payload;
    case 'RESET':
      return initialState;
    default:
      return state;
  }
}

interface AnalysisContextValue {
  state: AnalysisState;
  setStep: (step: 1 | 2 | 3 | 4) => void;
  setFinancialData: (data: FinancialData) => void;
  setQuestionnaire: (data: QuestionnaireData) => void;
  setClarifications: (data: ClarificationAnswer[]) => void;
  setDealInfo: (data: DealInfo) => void;
  setAnalysisId: (analysisId: string | null) => void;
  setAnalysisJob: (analysisJob: AnalysisJobSnapshot | null) => void;
  setPipelineDocuments: (documents: PipelineDocumentPayload[]) => void;
  setSharedContext: (data: SharedContext | null) => void;
  setReport: (report: AnyReportOutput) => void;
  setLoading: (isLoading: boolean, message?: string) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

const AnalysisContext = createContext<AnalysisContextValue | null>(null);

export function AnalysisProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [hasLoadedStoredState, setHasLoadedStoredState] = useState(false);
  const analysisJobStatus = state.analysisJob?.status;
  const hasAnalysisJob = Boolean(state.analysisJob);

  const setStep = useCallback((step: 1 | 2 | 3 | 4) => {
    dispatch({ type: 'SET_STEP', payload: step });
  }, []);

  const setFinancialData = useCallback((data: FinancialData) => {
    dispatch({ type: 'SET_FINANCIAL_DATA', payload: data });
  }, []);

  const setQuestionnaire = useCallback((data: QuestionnaireData) => {
    dispatch({ type: 'SET_QUESTIONNAIRE', payload: data });
  }, []);

  const setClarifications = useCallback((data: ClarificationAnswer[]) => {
    dispatch({ type: 'SET_CLARIFICATIONS', payload: data });
  }, []);

  const setDealInfo = useCallback((data: DealInfo) => {
    dispatch({ type: 'SET_DEAL_INFO', payload: data });
  }, []);

  const setAnalysisId = useCallback((analysisId: string | null) => {
    dispatch({ type: 'SET_ANALYSIS_ID', payload: analysisId });
  }, []);

  const setAnalysisJob = useCallback((analysisJob: AnalysisJobSnapshot | null) => {
    dispatch({ type: 'SET_ANALYSIS_JOB', payload: analysisJob });
  }, []);

  const setPipelineDocuments = useCallback((documents: PipelineDocumentPayload[]) => {
    dispatch({ type: 'SET_PIPELINE_DOCUMENTS', payload: documents });
  }, []);

  const setSharedContext = useCallback((data: SharedContext | null) => {
    dispatch({ type: 'SET_SHARED_CONTEXT', payload: data });
  }, []);

  const setReport = useCallback((report: AnyReportOutput) => {
    dispatch({ type: 'SET_REPORT', payload: report });
  }, []);

  const setLoading = useCallback((isLoading: boolean, message?: string) => {
    dispatch({ type: 'SET_LOADING', payload: { isLoading, message } });
  }, []);

  const setError = useCallback((error: string | null) => {
    dispatch({ type: 'SET_ERROR', payload: error });
  }, []);

  const reset = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.sessionStorage.removeItem(STORAGE_KEY);
    }
    dispatch({ type: 'RESET' });
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    dispatch({ type: 'RESTORE_STATE', payload: getStoredState() });
    setHasLoadedStoredState(true);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined' || !hasLoadedStoredState) {
      return;
    }

    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(persistedState(state)));
  }, [hasLoadedStoredState, state]);

  useEffect(() => {
    // Subscribe to job updates via Server-Sent Events. Falls back to HTTP polling if the
    // stream errors (proxies, network blips). Partial reports while running are included
    // in the same payload shape as GET /analyses/:id.
    const isTerminal =
      analysisJobStatus === 'completed' || analysisJobStatus === 'failed';

    // The parse step returns an analysisId for ingestion artifacts before the
    // report job record exists. Do not poll /analyses/:id until a job has been
    // started, except on the report page where ?aid=... is used to resume.
    const shouldSubscribe =
      Boolean(state.analysisId) &&
      (hasAnalysisJob || state.step === 4) &&
      (!analysisJobStatus || !isTerminal);

    if (!shouldSubscribe || !state.analysisId) {
      return;
    }

    const analysisId = state.analysisId;
    let cancelled = false;
    let timeoutId: number | null = null;
    let completedNullRetried = false;
    let eventSource: EventSource | null = null;
    let streamFinished = false;
    const startedAt = Date.now();
    const HARD_CAP_MS = 20 * 60 * 1000; // 20 min

    const closeEventSource = () => {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
    };

    type ApplyResult = 'stop' | 'continue' | 'need_null_report_retry';

    const applyJobSnapshot = (job: AnalysisJobSnapshot): ApplyResult => {
      dispatch({ type: 'SET_ANALYSIS_JOB', payload: job });
      dispatch({
        type: 'SET_LOADING',
        payload: {
          isLoading: job.status === 'queued' || job.status === 'running',
          message: job.progress.message,
        },
      });

      if (job.status === 'completed') {
        if (job.report) {
          dispatch({ type: 'SET_REPORT', payload: job.report });
          dispatch({ type: 'SET_STEP', payload: 4 });
          return 'stop';
        }
        if (!completedNullRetried) {
          completedNullRetried = true;
          return 'need_null_report_retry';
        }
        dispatch({
          type: 'SET_ERROR',
          payload: 'Report artifacts are missing — please start a new analysis.',
        });
        return 'stop';
      }

      if (job.status === 'failed') {
        dispatch({
          type: 'SET_ERROR',
          payload: job.error || 'Analysis failed. Please try again.',
        });
        return 'stop';
      }

      if (job.report) {
        dispatch({ type: 'SET_REPORT', payload: job.report });
      }
      return 'continue';
    };

    const handleApplyResult = (r: ApplyResult) => {
      if (r === 'stop') {
        streamFinished = true;
        closeEventSource();
        return;
      }
      if (r === 'need_null_report_retry') {
        timeoutId = window.setTimeout(async () => {
          if (cancelled) return;
          try {
            const job = await getAnalysisJob(analysisId);
            if (cancelled) return;
            const r2 = applyJobSnapshot(job);
            handleApplyResult(r2);
          } catch {
            if (!cancelled) {
              dispatch({
                type: 'SET_ERROR',
                payload: 'Failed to load analysis report. Please try again.',
              });
            }
          }
        }, 1500);
      }
    };

    const hardCapTimer = window.setTimeout(() => {
      if (cancelled) return;
      streamFinished = true;
      closeEventSource();
      dispatch({
        type: 'SET_ERROR',
        payload: 'Analysis is taking longer than expected. Please retry or start a new analysis.',
      });
    }, HARD_CAP_MS);

    // Fallback when EventSource is unavailable or errors (CORS, proxy, etc.)
    const pollFallback = async () => {
      if (cancelled || streamFinished || Date.now() - startedAt > HARD_CAP_MS) {
        return;
      }
      try {
        const job = await getAnalysisJob(analysisId);
        if (cancelled) return;
        const r = applyJobSnapshot(job);
        if (r === 'stop') {
          return;
        }
        if (r === 'need_null_report_retry') {
          handleApplyResult(r);
          return;
        }
        timeoutId = window.setTimeout(pollFallback, 1500);
      } catch {
        if (cancelled) return;
        timeoutId = window.setTimeout(pollFallback, 2500);
      }
    };

    const openEventStream = async () => {
      try {
        await ensureAnalysisFlow();
        if (cancelled) return;
        eventSource = new EventSource(getAnalysisJobEventsUrl(analysisId));
        eventSource.onmessage = (ev) => {
          if (cancelled) return;
          let job: AnalysisJobSnapshot;
          try {
            job = JSON.parse(ev.data) as AnalysisJobSnapshot;
          } catch {
            return;
          }
          const r = applyJobSnapshot(job);
          handleApplyResult(r);
        };
        eventSource.onerror = () => {
          if (cancelled || streamFinished) return;
          closeEventSource();
          pollFallback();
        };
      } catch {
        pollFallback();
      }
    };

    if (typeof window.EventSource === 'undefined') {
      pollFallback();
    } else {
      void openEventStream();
    }

    return () => {
      cancelled = true;
      clearTimeout(hardCapTimer);
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      closeEventSource();
    };
  }, [analysisJobStatus, hasAnalysisJob, state.analysisId, state.step]);

  return (
    <AnalysisContext.Provider
      value={{
        state,
        setStep,
        setFinancialData,
        setQuestionnaire,
        setClarifications,
        setDealInfo,
        setAnalysisId,
        setAnalysisJob,
        setPipelineDocuments,
        setSharedContext,
        setReport,
        setLoading,
        setError,
        reset,
      }}
    >
      {children}
    </AnalysisContext.Provider>
  );
}

export function useAnalysis(): AnalysisContextValue {
  const ctx = useContext(AnalysisContext);
  if (!ctx) throw new Error('useAnalysis must be used within AnalysisProvider');
  return ctx;
}
