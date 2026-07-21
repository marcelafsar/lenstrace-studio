import { SECTION_LABELS, useNavStore, type Section } from '@/stores/useNavStore';
import { useExportsStore } from '@/stores/useExportsStore';

// Plain, dependency-free glyphs (some platforms lack certain emoji).
const ICONS: Record<Section, string> = {
  editor: '✎',
  send: '→',
  bots: '⌘',
  diagnostics: '✓',
};

const ORDER: Section[] = ['editor', 'send', 'bots', 'diagnostics'];

export function NavRail() {
  const section = useNavStore((s) => s.section);
  const setSection = useNavStore((s) => s.setSection);
  const exportCount = useExportsStore((s) => s.items.length);

  return (
    <nav className="nav-rail" aria-label="Sections">
      <div className="nav-brand">
        LT<span className="dot"> ●</span>
      </div>
      {ORDER.map((s) => (
        <button
          key={s}
          className={`nav-item ${s === section ? 'active' : ''}`}
          onClick={() => setSection(s)}
          aria-current={s === section ? 'page' : undefined}
          title={SECTION_LABELS[s]}
        >
          <span className="nav-icon" aria-hidden>
            {ICONS[s]}
          </span>
          <span className="nav-label">{SECTION_LABELS[s]}</span>
          {s === 'send' && exportCount > 0 && <span className="nav-badge">{exportCount}</span>}
        </button>
      ))}
    </nav>
  );
}
