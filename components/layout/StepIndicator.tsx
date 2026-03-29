'use client';

import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

const STEPS = [
  { number: 1, label: 'Upload' },
  { number: 2, label: 'Review' },
  { number: 3, label: 'Questions' },
  { number: 4, label: 'Report' },
];

interface StepIndicatorProps {
  currentStep: 1 | 2 | 3 | 4;
}

export function StepIndicator({ currentStep }: StepIndicatorProps) {
  return (
    <div className="w-full">
      <div className="flex items-center justify-center">
        {STEPS.map((step, index) => (
          <div key={step.number} className="flex items-center">
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  'w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-200',
                  step.number < currentStep
                    ? 'bg-blue-600 text-white'
                    : step.number === currentStep
                    ? 'bg-blue-600 text-white ring-4 ring-blue-100'
                    : 'bg-slate-100 text-slate-400'
                )}
              >
                {step.number < currentStep ? (
                  <Check className="w-4 h-4" />
                ) : (
                  step.number
                )}
              </div>
              <span
                className={cn(
                  'text-xs mt-1.5 font-medium',
                  step.number === currentStep
                    ? 'text-blue-600'
                    : step.number < currentStep
                    ? 'text-slate-600'
                    : 'text-slate-400'
                )}
              >
                {step.label}
              </span>
            </div>
            {index < STEPS.length - 1 && (
              <div
                className={cn(
                  'h-0.5 w-16 sm:w-24 mx-2 mb-4 transition-all duration-200',
                  step.number < currentStep ? 'bg-blue-600' : 'bg-slate-200'
                )}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
