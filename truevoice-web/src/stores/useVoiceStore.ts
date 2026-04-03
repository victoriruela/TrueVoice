import { create } from "zustand";
import {
  listVoices,
  uploadVoice,
  deleteVoice,
  VoiceInfo,
} from "../api";

interface VoiceStore {
  voices: VoiceInfo[];
  loading: boolean;
  fetch: (directory?: string) => Promise<void>;
  upload: (name: string, file: File) => Promise<void>;
  remove: (name: string) => Promise<void>;
}

export const useVoiceStore = create<VoiceStore>((set, get) => ({
  voices: [],
  loading: false,

  fetch: async (directory) => {
    set({ loading: true });
    try {
      const { data } = await listVoices(directory);
      set({ voices: data });
    } catch {
      set({ voices: [] });
    } finally {
      set({ loading: false });
    }
  },

  upload: async (name, file) => {
    await uploadVoice(name, file);
    await get().fetch();
  },

  remove: async (name) => {
    await deleteVoice(name);
    await get().fetch();
  },
}));
