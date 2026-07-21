import { STEP_ORDER, useWorkflowStore, type Step } from '@/stores/useWorkflowStore';

const LABELS: Record<Step, string> = {
  select: 'Select images',
  inspect: 'Inspect metadata',
  device: 'Device & lens',
  datetime: 'Date & time',
  location: 'Location',
  review: 'Review changes',
  export: 'Export',
};

export function Stepper() {
  const step = useWorkflowStore((s) => s.step);
  const files = useWorkflowStore((s) => s.files);
  const setStep = useWorkflowStore((s) => s.setStep);

  const currentIndex = STEP_ORDER.indexOf(step);
  const hasFiles = files.length > 0;

  return (
    <nav className="stepper" aria-label="Workflow steps">
      {STEP_ORDER.map((s, i) => {
        const active = s === step;
        const done = i < currentIndex;
        // Every step after "select" needs at least one file.
        const disabled = i > 0 && !hasFiles;
        return (
          <button
            key={s}
            className={`step-item ${active ? 'active' : ''} ${done ? 'done' : ''}`}
            onClick={() => !disabled && setStep(s)}
            disabled={disabled}
            aria-current={active ? 'step' : undefined}
          >
            <span className="step-index">{done ? '✓' : i + 1}</span>
            {LABELS[s]}
          </button>
        );
      })}
    </nav>
  );
}
