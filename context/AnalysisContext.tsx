'use client';

import React, { createContext, useContext, useReducer, useCallback, useEffect } from 'react';
import { getAnalysisJob } from '@/lib/api-client';
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

function getInitialState(): AnalysisState {
  if (typeof window === 'undefined') {
    return initialState;
  }

  const rawState = window.sessionStorage.getItem(STORAGE_KEY);
  if (!rawState) {
    return initialState;
  }

  try {
    return {
      ...initialState,
      ...JSON.parse(rawState),
    } as AnalysisState;
  } catch {
    return initialState;
  }
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
  const [state, dispatch] = useReducer(reducer, initialState, getInitialState);
  const analysisJobStatus = state.analysisJob?.status;

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

    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  useEffect(() => {
    const shouldPoll =
      Boolean(state.analysisId) &&
      Boolean(state.isLoading) &&
      !state.report &&
      (!analysisJobStatus || analysisJobStatus === 'queued' || analysisJobStatus === 'running');

    if (!shouldPoll || !state.analysisId) {
      return;
    }

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      try {
        const job = await getAnalysisJob(state.analysisId!);
        if (cancelled) {
          return;
        }

        dispatch({ type: 'SET_ANALYSIS_JOB', payload: job });
        dispatch({
          type: 'SET_LOADING',
          payload: {
            isLoading: job.status === 'queued' || job.status === 'running',
            message: job.progress.message,
          },
        });

        if (job.status === 'completed' && job.report) {
          dispatch({ type: 'SET_REPORT', payload: job.report });
          dispatch({ type: 'SET_STEP', payload: 4 });
          return;
        }

        if (job.status === 'failed') {
          dispatch({ type: 'SET_ERROR', payload: job.error || 'Analysis failed. Please try again.' });
          return;
        }

        timeoutId = setTimeout(poll, 1500);
      } catch {
        if (cancelled) {
          return;
        }
        timeoutId = setTimeout(poll, 2500);
      }
    };

    poll();

    return () => {
      cancelled = true;
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [analysisJobStatus, state.analysisId, state.isLoading, state.report]);

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
