'use client';

import React, { createContext, useContext, useReducer, useCallback } from 'react';
import type { AnalysisState, FinancialData, QuestionnaireData, DealInfo, ReportOutput, SharedContext } from '@/lib/types';

type Action =
  | { type: 'SET_STEP'; payload: 1 | 2 | 3 | 4 }
  | { type: 'SET_FINANCIAL_DATA'; payload: FinancialData }
  | { type: 'SET_QUESTIONNAIRE'; payload: QuestionnaireData }
  | { type: 'SET_DEAL_INFO'; payload: DealInfo }
  | { type: 'SET_SHARED_CONTEXT'; payload: SharedContext | null }
  | { type: 'SET_REPORT'; payload: ReportOutput }
  | { type: 'SET_LOADING'; payload: { isLoading: boolean; message?: string } }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'RESET' };

const initialState: AnalysisState = {
  step: 1,
  financialData: null,
  questionnaire: null,
  dealInfo: null,
  sharedContext: null,
  report: null,
  isLoading: false,
  loadingMessage: '',
  error: null,
};

function reducer(state: AnalysisState, action: Action): AnalysisState {
  switch (action.type) {
    case 'SET_STEP':
      return { ...state, step: action.payload };
    case 'SET_FINANCIAL_DATA':
      return { ...state, financialData: action.payload };
    case 'SET_QUESTIONNAIRE':
      return { ...state, questionnaire: action.payload };
    case 'SET_DEAL_INFO':
      return { ...state, dealInfo: action.payload };
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
  setDealInfo: (data: DealInfo) => void;
  setSharedContext: (data: SharedContext | null) => void;
  setReport: (report: ReportOutput) => void;
  setLoading: (isLoading: boolean, message?: string) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

const AnalysisContext = createContext<AnalysisContextValue | null>(null);

export function AnalysisProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const setStep = useCallback((step: 1 | 2 | 3 | 4) => {
    dispatch({ type: 'SET_STEP', payload: step });
  }, []);

  const setFinancialData = useCallback((data: FinancialData) => {
    dispatch({ type: 'SET_FINANCIAL_DATA', payload: data });
  }, []);

  const setQuestionnaire = useCallback((data: QuestionnaireData) => {
    dispatch({ type: 'SET_QUESTIONNAIRE', payload: data });
  }, []);

  const setDealInfo = useCallback((data: DealInfo) => {
    dispatch({ type: 'SET_DEAL_INFO', payload: data });
  }, []);

  const setSharedContext = useCallback((data: SharedContext | null) => {
    dispatch({ type: 'SET_SHARED_CONTEXT', payload: data });
  }, []);

  const setReport = useCallback((report: ReportOutput) => {
    dispatch({ type: 'SET_REPORT', payload: report });
  }, []);

  const setLoading = useCallback((isLoading: boolean, message?: string) => {
    dispatch({ type: 'SET_LOADING', payload: { isLoading, message } });
  }, []);

  const setError = useCallback((error: string | null) => {
    dispatch({ type: 'SET_ERROR', payload: error });
  }, []);

  const reset = useCallback(() => {
    dispatch({ type: 'RESET' });
  }, []);

  return (
    <AnalysisContext.Provider
      value={{
        state,
        setStep,
        setFinancialData,
        setQuestionnaire,
        setDealInfo,
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
