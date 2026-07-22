import { create } from 'zustand';

/** A completed export the user can send to their iPhone. */
export interface ExportedItem {
  exportId: string;
  name: string;
  thumbnailDataUri?: string | null;
}

interface ExportsState {
  items: ExportedItem[];
  selectedId: string | null;
  add: (item: ExportedItem) => void;
  select: (exportId: string) => void;
  clear: () => void;
}

export const useExportsStore = create<ExportsState>((set, get) => ({
  items: [],
  selectedId: null,
  add: (item) => {
    // De-duplicate by exportId; newest first.
    const existing = get().items.filter((i) => i.exportId !== item.exportId);
    set({ items: [item, ...existing], selectedId: item.exportId });
  },
  select: (exportId) => set({ selectedId: exportId }),
  clear: () => set({ items: [], selectedId: null }),
}));
