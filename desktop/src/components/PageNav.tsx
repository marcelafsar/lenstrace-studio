import { motion } from 'framer-motion';
import { useWorkflowStore } from '@/stores/useWorkflowStore';

interface Props {
  nextLabel?: string;
  nextDisabled?: boolean;
  onNext?: () => void;
  hideBack?: boolean;
}

export function PageNav({ nextLabel = 'Continue', nextDisabled, onNext, hideBack }: Props) {
  const back = useWorkflowStore((s) => s.back);
  const next = useWorkflowStore((s) => s.next);

  return (
    <div className="btn-row">
      {!hideBack && (
        <button className="btn ghost" onClick={back}>
          Back
        </button>
      )}
      <span className="spacer" />
      <motion.button
        className="btn primary"
        whileTap={{ scale: 0.97 }}
        disabled={nextDisabled}
        onClick={() => (onNext ? onNext() : next())}
      >
        {nextLabel}
      </motion.button>
    </div>
  );
}
