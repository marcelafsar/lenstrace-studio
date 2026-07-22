import { AnimatePresence, motion } from 'framer-motion';
import { NavRail } from '@/components/NavRail';
import { Stepper } from '@/components/Stepper';
import { useConnection } from '@/hooks/useConnection';
import { useNavStore } from '@/stores/useNavStore';
import { useWorkflowStore, type Step } from '@/stores/useWorkflowStore';
import { SelectImagesPage } from '@/pages/SelectImagesPage';
import { InspectPage } from '@/pages/InspectPage';
import { DevicePage } from '@/pages/DevicePage';
import { CameraPage } from '@/pages/CameraPage';
import { DateTimePage } from '@/pages/DateTimePage';
import { LocationPage } from '@/pages/LocationPage';
import { ReviewPage } from '@/pages/ReviewPage';
import { ExportPage } from '@/pages/ExportPage';
import { DeliveryHub } from '@/features/delivery/DeliveryHub';
import { BotsPage } from '@/features/bots/BotsPage';
import { DiagnosticsPage } from '@/features/diagnostics/DiagnosticsPage';

const PAGES: Record<Step, () => JSX.Element> = {
  select: SelectImagesPage,
  inspect: InspectPage,
  device: DevicePage,
  camera: CameraPage,
  datetime: DateTimePage,
  location: LocationPage,
  review: ReviewPage,
  export: ExportPage,
};

function EditorSection() {
  const step = useWorkflowStore((s) => s.step);
  const Page = PAGES[step];
  return (
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
  );
}

export default function App() {
  const { status, error } = useConnection();
  const section = useNavStore((s) => s.section);

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
      <div className="app-body">
        <NavRail />
        {section === 'editor' && <EditorSection />}
        {section === 'send' && (
          <main className="content section-content">
            <DeliveryHub />
          </main>
        )}
        {section === 'bots' && (
          <main className="content section-content">
            <BotsPage />
          </main>
        )}
        {section === 'diagnostics' && (
          <main className="content section-content">
            <DiagnosticsPage />
          </main>
        )}
      </div>
    </div>
  );
}
