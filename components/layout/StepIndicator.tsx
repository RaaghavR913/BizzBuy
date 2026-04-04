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
                  'w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-300',
                  step.number < currentStep
                    ? 'bg-accent/20 text-accent'
                    : step.number === currentStep
                    ? 'bg-accent text-white ring-4 ring-accent/20 shadow-lg shadow-accent/20'
                    : 'bg-raised text-t-muted border border-white/[0.08]'
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
                  'text-xs mt-2 font-medium transition-colors',
                  step.number === currentStep
                    ? 'text-accent'
                    : step.number < currentStep
                    ? 'text-t-secondary'
                    : 'text-t-muted'
                )}
              >
                {step.label}
              </span>
            </div>
            {index < STEPS.length - 1 && (
              <div className="relative h-0.5 w-16 sm:w-24 mx-3 mb-5 rounded-full overflow-hidden bg-raised">
                <div
                  className={cn(
                    'absolute inset-y-0 left-0 rounded-full transition-all duration-500 ease-out',
                    step.number < currentStep
                      ? 'w-full bg-accent'
                      : 'w-0 bg-accent'
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
