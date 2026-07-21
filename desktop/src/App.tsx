import { AnimatePresence, motion } from 'framer-motion';
import { Stepper } from '@/components/Stepper';
import { useConnection } from '@/hooks/useConnection';
import { useWorkflowStore, type Step } from '@/stores/useWorkflowStore';
import { SelectImagesPage } from '@/pages/SelectImagesPage';
import { InspectPage } from '@/pages/InspectPage';
import { DevicePage } from '@/pages/DevicePage';
import { DateTimePage } from '@/pages/DateTimePage';
import { LocationPage } from '@/pages/LocationPage';
import { ReviewPage } from '@/pages/ReviewPage';
import { ExportPage } from '@/pages/ExportPage';

const PAGES: Record<Step, () => JSX.Element> = {
  select: SelectImagesPage,
  inspect: InspectPage,
  device: DevicePage,
  datetime: DateTimePage,
  location: LocationPage,
  review: ReviewPage,
  export: ExportPage,
};

export default function App() {
  const { status, error } = useConnection();
  const step = useWorkflowStore((s) => s.step);

  if (status === 'connecting') {
    return (
      <div className="center-status">
        <div className="spinner" />
        <p>Connecting to local engine…</p>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="center-status">
        <p style={{ color: 'var(--danger)' }}>Could not connect to the local backend.</p>
        <p className="hint" style={{ maxWidth: 420, textAlign: 'center' }}>
          {error}
        </p>
      </div>
    );
  }

  const Page = PAGES[step];

  return (
    <div className="app-shell">
      <header className="titlebar">
        <span className="brand">
          LensTrace<span className="dot"> ●</span> Studio
        </span>
        <span className="disclaimer">
          Local-only. Originals are never modified. Metadata does not prove capture facts.
        </span>
      </header>
      <div className="workspace">
        <Stepper />
        <main className="content">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18, ease: [0.22, 0.61, 0.36, 1] }}
            >
              <Page />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
