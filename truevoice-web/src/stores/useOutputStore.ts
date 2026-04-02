import { create } from "zustand";
import {
  listOutputs,
  deleteOutputs,
  OutputFileInfo,
} from "../api";

interface OutputStore {
  outputs: OutputFileInfo[];
  loading: boolean;
  selected: Set<string>;
  fetch: (directory?: string) => Promise<void>;
  toggleSelect: (filename: string) => void;
  selectAll: () => void;
  deselectAll: () => void;
  deleteSelected: (directory?: string) => Promise<void>;
}

export const useOutputStore = create<OutputStore>((set, get) => ({
  outputs: [],
  loading: false,
  selected: new Set(),

  fetch: async (directory) => {
    set({ loading: true });
    try {
      const { data } = await listOutputs(directory);
      set({ outputs: data, selected: new Set() });
    } catch {
      set({ outputs: [] });
    } finally {
      set({ loading: false });
    }
  },

  toggleSelect: (filename) => {
    const s = new Set(get().selected);
    if (s.has(filename)) s.delete(filename);
    else s.add(filename);
    set({ selected: s });
  },

  selectAll: () => {
    set({ selected: new Set(get().outputs.map((o) => o.filename)) });
  },

  deselectAll: () => {
    set({ selected: new Set() });
  },

  deleteSelected: async (directory) => {
    const filenames = Array.from(get().selected);
    if (filenames.length === 0) return;
    await deleteOutputs(filenames, directory);
    await get().fetch(directory);
  },
}));
