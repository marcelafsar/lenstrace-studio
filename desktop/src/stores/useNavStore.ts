import { create } from 'zustand';

export type Section = 'editor' | 'send' | 'bots' | 'diagnostics';

export const SECTION_LABELS: Record<Section, string> = {
  editor: 'Editor',
  send: 'Send to iPhone',
  bots: 'Bots',
  diagnostics: 'Diagnostics',
};

interface NavState {
  section: Section;
  setSection: (section: Section) => void;
}

export const useNavStore = create<NavState>((set) => ({
  section: 'editor',
  setSection: (section) => set({ section }),
}));
