import { create } from "zustand";
import {
  generateAudio,
  getProgress,
  confirmSave,
  GenerateRequest,
  GenerateResponse,
  ProgressInfo,
} from "../api";

export interface GenerationTask {
  id: number;
  text: string;
  customName: string;
  status: "idle" | "generating" | "done" | "error" | "saving";
  progress: ProgressInfo | null;
  result: GenerateResponse | null;
  error: string | null;
}

interface GenerationStore {
  tasks: GenerationTask[];
  nextId: number;
  addTask: (text?: string, customName?: string) => void;
  removeTask: (id: number) => void;
  updateTask: (id: number, patch: Partial<GenerationTask>) => void;
  generate: (
    id: number,
    overrides: Partial<GenerateRequest>,
  ) => Promise<void>;
  save: (id: number, outputDirectory?: string) => Promise<void>;
}

export const useGenerationStore = create<GenerationStore>((set, get) => ({
  tasks: [],
  nextId: 1,

  addTask: (text = "", customName = "") => {
    const { nextId } = get();
    const task: GenerationTask = {
      id: nextId,
      text,
      customName: customName || `audio_${nextId}`,
      status: "idle",
      progress: null,
      result: null,
      error: null,
    };
    set((s) => ({ tasks: [...s.tasks, task], nextId: s.nextId + 1 }));
  },

  removeTask: (id) => {
    set((s) => ({ tasks: s.tasks.filter((t) => t.id !== id) }));
  },

  updateTask: (id, patch) => {
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, ...patch } : t)),
    }));
  },

  generate: async (id, overrides) => {
    const task = get().tasks.find((t) => t.id === id);
    if (!task) return;

    const audioIdHint = `gen_${id}_${Date.now()}`;
    get().updateTask(id, { status: "generating", progress: null, error: null });

    // Start polling progress
    const pollInterval = setInterval(async () => {
      try {
        const { data } = await getProgress(audioIdHint);
        get().updateTask(id, { progress: data });
      } catch {
        /* not started yet */
      }
    }, 1000);

    try {
      const req: GenerateRequest = {
        text: task.text,
        custom_output_name: task.customName,
        audio_id_hint: audioIdHint,
        ...overrides,
      };
      const { data } = await generateAudio(req, overrides.voice_name ? undefined : undefined);
      get().updateTask(id, { status: "done", result: data });
    } catch (err: any) {
      get().updateTask(id, {
        status: "error",
        error: err?.response?.data?.detail || err.message || "Error",
      });
    } finally {
      clearInterval(pollInterval);
    }
  },

  save: async (id, outputDirectory) => {
    const task = get().tasks.find((t) => t.id === id);
    if (!task?.result?.audio_id) return;
    get().updateTask(id, { status: "saving" });
    try {
      await confirmSave(task.result.audio_id, outputDirectory);
      get().updateTask(id, { status: "done" });
    } catch (err: any) {
      get().updateTask(id, {
        status: "error",
        error: err?.response?.data?.detail || "Save failed",
      });
    }
  },
}));
