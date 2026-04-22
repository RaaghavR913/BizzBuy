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
                  'w-14 h-14 rounded-full flex items-center justify-center text-base font-bold transition-all duration-300',
                  step.number < currentStep
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : step.number === currentStep
                    ? 'bg-emerald-500 text-white ring-4 ring-emerald-500/20 shadow-lg shadow-emerald-500/20'
                    : 'bg-raised text-t-muted border border-white/[0.08]'
                )}
              >
                {step.number < currentStep ? (
                  <Check className="w-5 h-5" />
                ) : (
                  step.number
                )}
              </div>
              <span
                className={cn(
                  'text-sm mt-2.5 font-semibold transition-colors',
                  step.number === currentStep
                    ? 'text-emerald-400'
                    : step.number < currentStep
                    ? 'text-t-secondary'
                    : 'text-t-muted'
                )}
              >
                {step.label}
              </span>
            </div>
            {index < STEPS.length - 1 && (
              <div className="relative h-0.5 w-20 sm:w-32 mx-4 mb-6 rounded-full overflow-hidden bg-raised">
                <div
                  className={cn(
                    'absolute inset-y-0 left-0 rounded-full transition-all duration-500 ease-out',
                    step.number < currentStep
                      ? 'w-full bg-emerald-500'
                      : 'w-0 bg-emerald-500'
                  )}
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
