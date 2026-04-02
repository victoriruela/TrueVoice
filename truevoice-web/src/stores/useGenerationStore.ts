import { create } from "zustand";
import {
  generateAudio,
  getProgress,
  confirmSave,
  cancelGeneration,
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
  activeAudioId?: string;
  startedAt?: number;
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
  cancelAllInFlight: () => Promise<void>;
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
    get().updateTask(id, {
      status: "generating",
      progress: null,
      error: null,
      startedAt: Date.now(),
      activeAudioId: undefined,
    });

    try {
      const req: GenerateRequest = {
        text: task.text,
        custom_output_name: task.customName,
        audio_id_hint: audioIdHint,
        ...overrides,
      };

      const { data } = await generateAudio(req);
      if (!data.success || !data.audio_id) {
        throw new Error(data.message || "La generacion no pudo iniciarse");
      }

      const progressID = data.audio_id;
      get().updateTask(id, { activeAudioId: progressID });
      let completed = false;

      // Wait for real completion on backend instead of marking done immediately.
      for (let i = 0; i < 900; i++) {
        await new Promise((resolve) => setTimeout(resolve, 1000));

        let p: ProgressInfo;
        try {
          const resp = await getProgress(progressID);
          p = resp.data;
        } catch {
          // Keep waiting unless timeout is reached.
          continue;
        }

        get().updateTask(id, { progress: p });

        if (p.status === "done") {
          completed = true;
          break;
        }
        if (p.status === "error" || p.status === "cancelled") {
          throw new Error(p.error || `Generacion ${p.status}`);
        }
      }

      if (!completed) {
        throw new Error("Timeout esperando a que finalice la generacion");
      }

      get().updateTask(id, { status: "done", result: data });
    } catch (err: any) {
      get().updateTask(id, {
        status: "error",
        error: err?.response?.data?.detail || err.message || "Error",
      });
    } finally {
      get().updateTask(id, { activeAudioId: undefined });
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

  cancelAllInFlight: async () => {
    const generating = get().tasks.filter((t) => t.status === "generating" && t.activeAudioId);
    await Promise.all(
      generating.map(async (task) => {
        try {
          await cancelGeneration(task.activeAudioId!);
        } catch {
          // Best-effort cancellation on page lifecycle.
        }
      }),
    );

    set((s) => ({
      tasks: s.tasks.map((t) =>
        t.status === "generating"
          ? { ...t, status: "error", error: "Generacion cancelada por recarga", activeAudioId: undefined }
          : t,
      ),
    }));
  },
}));
