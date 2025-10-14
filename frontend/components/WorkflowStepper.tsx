'use client';

import React from 'react';

export type StepVisualStatus = 'pending' | 'in_progress' | 'blocked' | 'completed' | 'current';

export type StepSummary = {
  id: string;
  label: string;
  description?: string;
  status: StepVisualStatus;
};

const STATUS_STYLES: Record<StepVisualStatus, { border: string; background: string; text: string; indicator: string }> = {
  completed: {
    border: 'border-emerald-500',
    background: 'bg-emerald-50',
    text: 'text-emerald-700',
    indicator: 'bg-emerald-500'
  },
  current: {
    border: 'border-primary',
    background: 'bg-primary/5',
    text: 'text-primary',
    indicator: 'bg-primary'
  },
  in_progress: {
    border: 'border-amber-400',
    background: 'bg-amber-50',
    text: 'text-amber-700',
    indicator: 'bg-amber-400'
  },
  pending: {
    border: 'border-slate-200',
    background: 'bg-white',
    text: 'text-slate-500',
    indicator: 'bg-slate-300'
  },
  blocked: {
    border: 'border-slate-200 border-dashed',
    background: 'bg-slate-50',
    text: 'text-slate-400',
    indicator: 'bg-slate-300'
  }
};

function StatusIcon({ status }: { status: StepVisualStatus }) {
  if (status === 'completed') {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-white">
        <svg viewBox="0 0 20 20" className="h-4 w-4" aria-hidden="true">
          <path
            fill="currentColor"
            d="M8.143 13.314 4.83 9.992l1.18-1.18 2.133 2.132 5.845-5.846 1.18 1.18z"
          />
        </svg>
      </span>
    );
  }
  return <span className={`h-3 w-3 rounded-full ${STATUS_STYLES[status].indicator}`} aria-hidden="true" />;
}

export function WorkflowStepper({
  steps,
  activeStepId,
  onStepSelect
}: {
  steps: StepSummary[];
  activeStepId: string | null;
  onStepSelect?: (stepId: string) => void;
}) {
  return (
    <ol className="flex flex-col gap-3 md:flex-row md:items-stretch md:gap-4">
      {steps.map((step, index) => {
        const isActive = activeStepId === step.id;
        const visualStatus: StepVisualStatus = isActive && step.status !== 'completed' ? 'current' : step.status;
        const styles = STATUS_STYLES[visualStatus];
        const clickable = onStepSelect && step.status !== 'blocked';
        const content = (
          <div
            className={`flex h-full flex-col gap-2 rounded-2xl border ${styles.border} ${styles.background} p-4 text-left transition`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <StatusIcon status={visualStatus} />
                <span className={styles.text}>{`步骤 ${index + 1}`}</span>
              </div>
              <span className={`text-xs uppercase tracking-wide ${styles.text}`}>{step.status.replace('_', ' ')}</span>
            </div>
            <div className="space-y-1">
              <h3 className="text-base font-semibold text-slate-900">{step.label}</h3>
              {step.description && <p className="text-sm text-slate-600">{step.description}</p>}
            </div>
          </div>
        );

        if (!clickable) {
          return (
            <li key={step.id} className="flex-1">
              <div>{content}</div>
            </li>
          );
        }

        return (
          <li key={step.id} className="flex-1">
            <button
              type="button"
              onClick={() => onStepSelect?.(step.id)}
              className="h-full w-full text-left"
            >
              {content}
            </button>
          </li>
        );
      })}
    </ol>
  );
}
