import { create } from "zustand";
import {
  ContextTemplateData,
  deleteContext,
  getContext,
  getContextState,
  listContexts,
  loadContext,
  saveContext,
} from "../api";

interface ContextStore {
  contexts: ContextTemplateData[];
  inUseName: string;
  inUseIntroText: string;
  inUseEventsText: string;
  draftIntroText: string;
  draftEventsText: string;
  loading: boolean;
  error: string | null;

  fetchAll: () => Promise<void>;
  loadByName: (name: string) => Promise<void>;
  saveDraftAs: (name: string) => Promise<void>;
  deleteByName: (name: string) => Promise<void>;
  setDraftIntroText: (text: string) => void;
  setDraftEventsText: (text: string) => void;
}

function normalizeError(err: any, fallback: string): string {
  return err?.response?.data?.detail || fallback;
}

export const useContextStore = create<ContextStore>((set, get) => ({
  contexts: [],
  inUseName: "",
  inUseIntroText: "",
  inUseEventsText: "",
  draftIntroText: "",
  draftEventsText: "",
  loading: false,
  error: null,

  fetchAll: async () => {
    set({ loading: true, error: null });
    try {
      const [{ data: contextsResp }, { data: stateResp }] = await Promise.all([
        listContexts(),
        getContextState(),
      ]);
      set({
        contexts: contextsResp.contexts || [],
        inUseName: stateResp.in_use_name || "",
        inUseIntroText: stateResp.in_use_intro_text || "",
        inUseEventsText: stateResp.in_use_events_text || "",
        draftIntroText: stateResp.in_use_intro_text || "",
        draftEventsText: stateResp.in_use_events_text || "",
      });
    } catch (err: any) {
      set({ error: normalizeError(err, "Error loading contexts") });
    } finally {
      set({ loading: false });
    }
  },

  loadByName: async (name: string) => {
    set({ loading: true, error: null });
    try {
      await loadContext(name);
      const [{ data: contextResp }, { data: contextsResp }] = await Promise.all([
        getContext(name),
        listContexts(),
      ]);
      set({
        contexts: contextsResp.contexts || [],
        inUseName: contextResp.name,
        inUseIntroText: contextResp.intro_text || "",
        inUseEventsText: contextResp.events_text || "",
        draftIntroText: contextResp.intro_text || "",
        draftEventsText: contextResp.events_text || "",
      });
    } catch (err: any) {
      set({ error: normalizeError(err, "Error loading context") });
    } finally {
      set({ loading: false });
    }
  },

  saveDraftAs: async (name: string) => {
    const trimmed = name.trim();
    if (!trimmed) {
      set({ error: "Context name is required" });
      return;
    }

    const { draftIntroText, draftEventsText } = get();
    set({ loading: true, error: null });
    try {
      const { data: saveResp } = await saveContext(trimmed, draftIntroText, draftEventsText);
      const { data: contextsResp } = await listContexts();
      const loadedResp = saveResp.context;
      set({
        contexts: contextsResp.contexts || [],
        inUseName: loadedResp.name,
        inUseIntroText: loadedResp.intro_text || "",
        inUseEventsText: loadedResp.events_text || "",
        draftIntroText: loadedResp.intro_text || "",
        draftEventsText: loadedResp.events_text || "",
      });
    } catch (err: any) {
      set({ error: normalizeError(err, "Error saving context") });
    } finally {
      set({ loading: false });
    }
  },

  deleteByName: async (name: string) => {
    set({ loading: true, error: null });
    try {
      await deleteContext(name);
      const [{ data: contextsResp }, { data: stateResp }] = await Promise.all([
        listContexts(),
        getContextState(),
      ]);

      const stillSameDraft =
        get().draftIntroText === get().inUseIntroText &&
        get().draftEventsText === get().inUseEventsText;

      set({
        contexts: contextsResp.contexts || [],
        inUseName: stateResp.in_use_name || "",
        inUseIntroText: stateResp.in_use_intro_text || "",
        inUseEventsText: stateResp.in_use_events_text || "",
        draftIntroText: stillSameDraft ? (stateResp.in_use_intro_text || "") : get().draftIntroText,
        draftEventsText: stillSameDraft ? (stateResp.in_use_events_text || "") : get().draftEventsText,
      });
    } catch (err: any) {
      set({ error: normalizeError(err, "Error deleting context") });
    } finally {
      set({ loading: false });
    }
  },

  setDraftIntroText: (text: string) => {
    set({ draftIntroText: text, error: null });
  },

  setDraftEventsText: (text: string) => {
    set({ draftEventsText: text, error: null });
  },
}));
