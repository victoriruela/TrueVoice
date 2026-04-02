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
  eventAudios: Record<string, string>;
  sessions: { name: string; modified: number }[];
  currentSession: string;
  loading: boolean;
  error: string | null;

  parseXml: (file: File) => Promise<void>;
  generateIntro: () => Promise<void>;
  generateDescriptions: () => Promise<void>;
  updateEventDescription: (index: number, description: string) => void;
  setIntroText: (text: string) => void;
  setIntroAudio: (filename: string) => void;
  setEventAudio: (index: number, filename: string) => void;

  fetchSessions: () => Promise<void>;
  loadSession: (name: string) => Promise<void>;
  saveSession: (name: string) => Promise<void>;
  deleteSession: (name: string) => Promise<void>;
  newSession: () => void;
}

export const useRaceStore = create<RaceStore>((set, get) => ({
  header: null,
  events: [],
  introText: "",
  introAudio: "",
  eventAudios: {},
  sessions: [],
  currentSession: "",
  loading: false,
  error: null,

  parseXml: async (file) => {
    set({ loading: true, error: null });
    try {
      const { data } = await raceParse(file);
      set({
        header: data.header,
        events: data.events,
        introText: data.header.intro_text || "",
        eventAudios: {},
        introAudio: "",
      });
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
      set({ events: data.events });
    } catch (err: any) {
      set({ error: err?.response?.data?.detail || "Error generating descriptions" });
    } finally {
      set({ loading: false });
    }
  },

  updateEventDescription: (index, description) => {
    set((s) => ({
      events: s.events.map((e, i) => (i === index ? { ...e, description } : e)),
    }));
  },

  setIntroText: (text) => set({ introText: text }),
  setIntroAudio: (filename) => set({ introAudio: filename }),
  setEventAudio: (index, filename) => {
    set((s) => ({
      eventAudios: { ...s.eventAudios, [String(index)]: filename },
    }));
  },

  fetchSessions: async () => {
    try {
      const { data } = await raceListSessions();
      set({ sessions: data });
    } catch {
      set({ sessions: [] });
    }
  },

  loadSession: async (name) => {
    set({ loading: true, error: null });
    try {
      const { data } = await raceGetSession(name);
      set({
        header: data.header,
        events: data.events,
        introText: data.intro_text,
        introAudio: data.intro_audio,
        eventAudios: data.event_audios,
        currentSession: name,
      });
    } catch (err: any) {
      set({ error: err?.response?.data?.detail || "Error loading session" });
    } finally {
      set({ loading: false });
    }
  },

  saveSession: async (name) => {
    const { header, events, introText, introAudio, eventAudios } = get();
    if (!header) return;
    const session: RaceSession = {
      intro_text: introText,
      intro_audio: introAudio,
      header,
      events,
      event_audios: eventAudios,
    };
    await raceSaveSession(name, session);
    set({ currentSession: name });
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
      currentSession: "",
    });
  },
}));
