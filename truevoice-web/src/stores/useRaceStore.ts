import { create } from "zustand";
import {
  raceParse,
  raceGenerateIntro,
  raceGenerateDescriptions,
  raceListSessions,
  raceGetSession,
  raceSaveSession,
  raceDeleteSession,
  RaceHeaderData,
  RaceEventData,
  RaceSession,
} from "../api";

interface RaceStore {
  header: RaceHeaderData | null;
  events: RaceEventData[];
  introText: string;
  introAudio: string;
  currentAudioItem: string;
  currentAudioStartedAt: number | null;
  batchGenerating: boolean;
  batchDone: number;
  batchTotal: number;
  batchCurrentItem: string;
  batchStartedAt: number | null;
  eventAudios: Record<string, string>;
  hiddenEventIndices: Set<number>;
  selectedEventIndices: Set<number>;
  sessions: { name: string; modified: number }[];
  currentSession: string;
  loading: boolean;
  error: string | null;

  parseXml: (file: File) => Promise<void>;
  generateIntro: () => Promise<void>;
  generateDescriptions: () => Promise<void>;
  generateDescriptionForEvent: (index: number) => Promise<void>;
  updateEventDescription: (index: number, description: string) => void;
  setIntroText: (text: string) => void;
  setIntroAudio: (filename: string) => void;
  setCurrentAudioGeneration: (item: string, startedAt: number | null) => void;
  setBatchProgress: (patch: Partial<Pick<RaceStore, "batchGenerating" | "batchDone" | "batchTotal" | "batchCurrentItem" | "batchStartedAt">>) => void;
  clearBatchProgress: () => void;
  setEventAudio: (index: number, filename: string) => void;
  setEvents: (events: RaceEventData[]) => void;
  insertEventAfter: (index: number) => void;
  toggleEventSelected: (index: number) => void;
  selectAllEvents: () => void;
  clearEventSelection: () => void;
  deleteEvent: (index: number) => Promise<void>;
  deleteSelectedEvents: () => Promise<void>;
  toggleEventHidden: (index: number) => Promise<void>;

  fetchSessions: () => Promise<void>;
  loadSession: (name: string) => Promise<void>;
  saveSession: (name: string) => Promise<void>;
  deleteSession: (name: string) => Promise<void>;
  newSession: () => void;
  removeAudioReferencesByIds: (audioIds: string[]) => void;
  loadFromCSV: (
    events: RaceEventData[],
    eventAudios: Record<string, string>,
    introText: string,
    introAudio: string,
  ) => void;
}

interface RaceDraft {
  header: RaceHeaderData | null;
  events: RaceEventData[];
  introText: string;
  introAudio: string;
  eventAudios: Record<string, string>;
  hiddenEventIndices: number[];
  selectedEventIndices: number[];
  currentSession: string;
}

const RACE_DRAFT_STORAGE_KEY = "truevoice-race-draft-v1";

function canUseLocalStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function buildSessionPayload(state: Pick<RaceStore, "introText" | "introAudio" | "header" | "events" | "eventAudios" | "hiddenEventIndices" | "selectedEventIndices">): RaceSession {
  return {
    intro_text: state.introText,
    intro_audio: state.introAudio,
    header: state.header!,
    events: state.events,
    event_audios: state.eventAudios,
    hidden_event_indices: Array.from(state.hiddenEventIndices).sort((a, b) => a - b),
    selected_event_indices: Array.from(state.selectedEventIndices).sort((a, b) => a - b),
  };
}

function reindexAfterDelete(
  events: RaceEventData[],
  eventAudios: Record<string, string>,
  hidden: Set<number>,
  selected: Set<number>,
  toDelete: Set<number>,
) {
  const nextEvents: RaceEventData[] = [];
  const nextAudios: Record<string, string> = {};
  const nextHidden = new Set<number>();
  const nextSelected = new Set<number>();

  let newIndex = 0;
  for (let oldIndex = 0; oldIndex < events.length; oldIndex++) {
    if (toDelete.has(oldIndex)) {
      continue;
    }
    nextEvents.push(events[oldIndex]);
    const audio = eventAudios[String(oldIndex)];
    if (audio) {
      nextAudios[String(newIndex)] = audio;
    }
    if (hidden.has(oldIndex)) {
      nextHidden.add(newIndex);
    }
    if (selected.has(oldIndex)) {
      nextSelected.add(newIndex);
    }
    newIndex++;
  }

  return { nextEvents, nextAudios, nextHidden, nextSelected };
}

function normalizeHeader(header: RaceHeaderData | null | undefined): RaceHeaderData | null {
  if (!header) {
    return null;
  }
  return {
    ...header,
    grid_order: Array.isArray(header.grid_order) ? header.grid_order : [],
  };
}

function normalizeEvents(events: RaceEventData[] | null | undefined): RaceEventData[] {
  return Array.isArray(events) ? events : [];
}

function normalizeSessionsList(sessions: { name: string; modified: number }[] | null | undefined) {
  return Array.isArray(sessions) ? sessions : [];
}

function normalizeIndices(indices: number[] | null | undefined): Set<number> {
  return new Set(Array.isArray(indices) ? indices : []);
}

function toDraft(state: Pick<RaceStore, "header" | "events" | "introText" | "introAudio" | "eventAudios" | "hiddenEventIndices" | "selectedEventIndices" | "currentSession">): RaceDraft {
  return {
    header: state.header,
    events: state.events,
    introText: state.introText,
    introAudio: state.introAudio,
    eventAudios: state.eventAudios,
    hiddenEventIndices: Array.from(state.hiddenEventIndices),
    selectedEventIndices: Array.from(state.selectedEventIndices),
    currentSession: state.currentSession,
  };
}

function loadRaceDraft(): RaceDraft | null {
  if (!canUseLocalStorage()) {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(RACE_DRAFT_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const data = JSON.parse(raw) as Partial<RaceDraft>;
    return {
      header: normalizeHeader(data.header as RaceHeaderData | null | undefined),
      events: normalizeEvents(data.events as RaceEventData[] | null | undefined),
      introText: typeof data.introText === "string" ? data.introText : "",
      introAudio: typeof data.introAudio === "string" ? data.introAudio : "",
      eventAudios: data.eventAudios && typeof data.eventAudios === "object" ? data.eventAudios : {},
      hiddenEventIndices: Array.isArray(data.hiddenEventIndices) ? data.hiddenEventIndices : [],
      selectedEventIndices: Array.isArray(data.selectedEventIndices) ? data.selectedEventIndices : [],
      currentSession: typeof data.currentSession === "string" ? data.currentSession : "",
    };
  } catch {
    return null;
  }
}

function persistRaceDraft(state: Pick<RaceStore, "header" | "events" | "introText" | "introAudio" | "eventAudios" | "hiddenEventIndices" | "selectedEventIndices" | "currentSession">) {
  if (!canUseLocalStorage()) {
    return;
  }
  try {
    window.localStorage.setItem(RACE_DRAFT_STORAGE_KEY, JSON.stringify(toDraft(state)));
  } catch {
    // Best effort persistence.
  }
}

export const useRaceStore = create<RaceStore>((set, get) => {
  const draft = loadRaceDraft();

  const persistNow = () => {
    const state = get();
    persistRaceDraft(state);
  };

  const autosaveCurrentSession = async () => {
    const state = get();
    if (!state.currentSession || !state.header) {
      return;
    }
    try {
      await raceSaveSession(state.currentSession, buildSessionPayload(state));
    } catch {
      // Best effort autosave.
    }
  };

  return {
    header: draft?.header || null,
    events: draft?.events || [],
    introText: draft?.introText || "",
    introAudio: draft?.introAudio || "",
    currentAudioItem: "",
    currentAudioStartedAt: null,
    batchGenerating: false,
    batchDone: 0,
    batchTotal: 0,
    batchCurrentItem: "",
    batchStartedAt: null,
    eventAudios: draft?.eventAudios || {},
    hiddenEventIndices: normalizeIndices(draft?.hiddenEventIndices),
    selectedEventIndices: normalizeIndices(draft?.selectedEventIndices),
    sessions: [],
    currentSession: draft?.currentSession || "",
    loading: false,
    error: null,

    parseXml: async (file) => {
      set({ loading: true, error: null });
      try {
        const { data } = await raceParse(file);
        const header = normalizeHeader(data.header);
        set({
          header,
          events: normalizeEvents(data.events),
          introText: header?.intro_text || "",
          eventAudios: {},
          introAudio: "",
          hiddenEventIndices: new Set(),
          selectedEventIndices: new Set(),
        });
        persistNow();
      } catch (err: any) {
        set({ error: err?.response?.data?.detail || "Error parsing XML" });
      } finally {
        set({ loading: false });
      }
    },

    generateIntro: async () => {
      const { header } = get();
      if (!header) return;
      set({ loading: true, error: null });
      try {
        const { data } = await raceGenerateIntro(header);
        set({ introText: data.intro_text });
        persistNow();
      } catch (err: any) {
        set({ error: err?.response?.data?.detail || "Error generating intro" });
      } finally {
        set({ loading: false });
      }
    },

    generateDescriptions: async () => {
      const { events } = get();
      if (events.length === 0) return;
      set({ loading: true, error: null });
      try {
        const { data } = await raceGenerateDescriptions(events);
        set({ events: normalizeEvents(data.events) });
        persistNow();
      } catch (err: any) {
        set({ error: err?.response?.data?.detail || "Error generating descriptions" });
      } finally {
        set({ loading: false });
      }
    },

    generateDescriptionForEvent: async (index) => {
      const { events } = get();
      if (index < 0 || index >= events.length) return;
      const ev = events[index];

      set({ loading: true, error: null });
      try {
        const { data } = await raceGenerateDescriptions([ev]);
        const generated = data.events?.[0];
        if (!generated) return;
        set((s) => ({
          events: s.events.map((item, i) =>
            i === index ? { ...item, description: generated.description || item.description } : item,
          ),
        }));
        persistNow();
      } catch (err: any) {
        set({ error: err?.response?.data?.detail || "Error generating event description" });
      } finally {
        set({ loading: false });
      }
    },

    updateEventDescription: (index, description) => {
      set((s) => ({
        events: s.events.map((e, i) => (i === index ? { ...e, description } : e)),
      }));
      persistNow();
    },

    setIntroText: (text) => {
      set({ introText: text });
      persistNow();
    },
    setIntroAudio: (filename) => {
      set({ introAudio: filename });
      persistNow();
    },
    setCurrentAudioGeneration: (item, startedAt) => {
      set({ currentAudioItem: item, currentAudioStartedAt: startedAt });
    },
    setBatchProgress: (patch) => {
      set((s) => ({ ...s, ...patch }));
    },
    clearBatchProgress: () => {
      set({
        batchGenerating: false,
        batchDone: 0,
        batchTotal: 0,
        batchCurrentItem: "",
        batchStartedAt: null,
      });
    },
    setEventAudio: (index, filename) => {
      set((s) => ({
        eventAudios: { ...s.eventAudios, [String(index)]: filename },
      }));
      persistNow();
    },

    setEvents: (events) => {
      set({ events });
      persistNow();
    },

    insertEventAfter: (index) => {
      set((s) => {
        if (index < 0 || index >= s.events.length) return s;

        const curr = s.events[index];
        const next = s.events[index + 1];
        const midTimestamp = next
          ? Math.max(curr.timestamp, Math.floor((curr.timestamp + next.timestamp) / 2))
          : curr.timestamp + 3;

        const newEvent: RaceEventData = {
          lap: curr.lap,
          timestamp: midTimestamp,
          event_type: 0,
          summary: "Evento manual",
          description: "",
        };

        const newEvents = [...s.events];
        newEvents.splice(index + 1, 0, newEvent);

        const newEventAudios: Record<string, string> = {};
        Object.entries(s.eventAudios).forEach(([k, v]) => {
          const oldIdx = Number(k);
          const newIdx = oldIdx > index ? oldIdx + 1 : oldIdx;
          newEventAudios[String(newIdx)] = v;
        });

        const newHidden = new Set<number>();
        s.hiddenEventIndices.forEach((oldIdx) => {
          newHidden.add(oldIdx > index ? oldIdx + 1 : oldIdx);
        });

        const newSelected = new Set<number>();
        s.selectedEventIndices.forEach((oldIdx) => {
          newSelected.add(oldIdx > index ? oldIdx + 1 : oldIdx);
        });

        return {
          ...s,
          events: newEvents,
          eventAudios: newEventAudios,
          hiddenEventIndices: newHidden,
          selectedEventIndices: newSelected,
        };
      });
      persistNow();
      autosaveCurrentSession();
    },

    toggleEventSelected: (index) => {
      set((s) => {
        const next = new Set(s.selectedEventIndices);
        if (next.has(index)) {
          next.delete(index);
        } else {
          next.add(index);
        }
        return { ...s, selectedEventIndices: next };
      });
      persistNow();
    },

    selectAllEvents: () => {
      set((s) => {
        const next = new Set<number>();
        s.events.forEach((_, i) => {
          if (!s.hiddenEventIndices.has(i)) {
            next.add(i);
          }
        });
        return { ...s, selectedEventIndices: next };
      });
      persistNow();
    },

    clearEventSelection: () => {
      set((s) => ({ ...s, selectedEventIndices: new Set() }));
      persistNow();
    },

    deleteEvent: async (index) => {
      set((s) => {
        const deleted = new Set<number>([index]);
        const { nextEvents, nextAudios, nextHidden, nextSelected } = reindexAfterDelete(
          s.events,
          s.eventAudios,
          s.hiddenEventIndices,
          s.selectedEventIndices,
          deleted,
        );
        return {
          ...s,
          events: nextEvents,
          eventAudios: nextAudios,
          hiddenEventIndices: nextHidden,
          selectedEventIndices: nextSelected,
        };
      });
      persistNow();
      await autosaveCurrentSession();
    },

    deleteSelectedEvents: async () => {
      const toDelete = new Set(get().selectedEventIndices);
      if (toDelete.size === 0) {
        return;
      }

      set((s) => {
        const { nextEvents, nextAudios, nextHidden } = reindexAfterDelete(
          s.events,
          s.eventAudios,
          s.hiddenEventIndices,
          s.selectedEventIndices,
          toDelete,
        );
        return {
          ...s,
          events: nextEvents,
          eventAudios: nextAudios,
          hiddenEventIndices: nextHidden,
          selectedEventIndices: new Set(),
        };
      });

      persistNow();

      await autosaveCurrentSession();
    },

    toggleEventHidden: async (index) => {
      set((s) => {
        const nextHidden = new Set(s.hiddenEventIndices);
        if (nextHidden.has(index)) {
          nextHidden.delete(index);
        } else {
          nextHidden.add(index);
        }

        const nextSelected = new Set(s.selectedEventIndices);
        nextSelected.delete(index);

        return {
          ...s,
          hiddenEventIndices: nextHidden,
          selectedEventIndices: nextSelected,
        };
      });

      persistNow();

      await autosaveCurrentSession();
    },

    fetchSessions: async () => {
      try {
        const { data } = await raceListSessions();
        set({ sessions: normalizeSessionsList(data) });
      } catch {
        set({ sessions: [] });
      }
    },

    loadSession: async (name) => {
      set({ loading: true, error: null });
      try {
        const { data } = await raceGetSession(name);
        const header = normalizeHeader(data.header);
        set({
          header,
          events: normalizeEvents(data.events),
          introText: data.intro_text || "",
          introAudio: data.intro_audio || "",
          eventAudios: data.event_audios || {},
          hiddenEventIndices: normalizeIndices(data.hidden_event_indices),
          selectedEventIndices: normalizeIndices(data.selected_event_indices),
          currentSession: name,
        });
        persistNow();
      } catch (err: any) {
        set({ error: err?.response?.data?.detail || "Error loading session" });
      } finally {
        set({ loading: false });
      }
    },

    saveSession: async (name) => {
      const state = get();
      if (!state.header) return;
      await raceSaveSession(name, buildSessionPayload(state));
      set({ currentSession: name });
      persistNow();
      await get().fetchSessions();
    },

    deleteSession: async (name) => {
      await raceDeleteSession(name);
      if (get().currentSession === name) {
        get().newSession();
      }
      await get().fetchSessions();
    },

    newSession: () => {
      set({
        header: null,
        events: [],
        introText: "",
        introAudio: "",
        eventAudios: {},
        hiddenEventIndices: new Set(),
        selectedEventIndices: new Set(),
        currentSession: "",
      });
      persistNow();
    },

    removeAudioReferencesByIds: (audioIds) => {
      const target = new Set((audioIds || []).map((s) => s.trim()).filter(Boolean));
      if (target.size === 0) {
        return;
      }

      set((s) => {
        const nextEventAudios: Record<string, string> = {};
        Object.entries(s.eventAudios).forEach(([k, v]) => {
          if (!target.has((v || "").trim())) {
            nextEventAudios[k] = v;
          }
        });

        const nextIntroAudio = target.has((s.introAudio || "").trim()) ? "" : s.introAudio;

        return {
          ...s,
          introAudio: nextIntroAudio,
          eventAudios: nextEventAudios,
        };
      });
      persistNow();
    },

    loadFromCSV: (events, eventAudios, introText, introAudio) => {
      set({
        events: normalizeEvents(events),
        eventAudios,
        introText: introText || "",
        introAudio: introAudio || "",
        hiddenEventIndices: new Set(),
        selectedEventIndices: new Set(),
        currentSession: "",
      });
      persistNow();
    },
  };
});
