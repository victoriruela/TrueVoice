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
  selectedTaskIds: number[];
  addTask: (text?: string, customName?: string) => void;
  removeTask: (id: number) => void;
  updateTask: (id: number, patch: Partial<GenerationTask>) => void;
  generate: (
    id: number,
    overrides: Partial<GenerateRequest>,
  ) => Promise<void>;
  save: (id: number, outputDirectory?: string) => Promise<void>;
  cancelAllInFlight: () => Promise<void>;
  toggleTaskSelection: (id: number) => void;
  clearSelection: () => void;
  selectAllTasks: () => void;
  removeSelectedTasks: () => void;
}

const GENERATION_STORAGE_KEY = "truevoice-generation-store-v1";

function canUseLocalStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function loadPersistedGeneration(): Pick<GenerationStore, "tasks" | "nextId" | "selectedTaskIds"> {
  if (!canUseLocalStorage()) {
    return { tasks: [], nextId: 1, selectedTaskIds: [] };
  }

  try {
    const raw = window.localStorage.getItem(GENERATION_STORAGE_KEY);
    if (!raw) {
      return { tasks: [], nextId: 1, selectedTaskIds: [] };
    }
    const parsed = JSON.parse(raw) as { tasks?: GenerationTask[]; nextId?: number; selectedTaskIds?: number[] };
    const tasks = Array.isArray(parsed.tasks) ? parsed.tasks : [];
    const nextId = typeof parsed.nextId === "number" && parsed.nextId > 0 ? parsed.nextId : tasks.length + 1;
    const selectedTaskIds = Array.isArray(parsed.selectedTaskIds) ? parsed.selectedTaskIds : [];

    return {
      tasks: tasks.map((t) =>
        t.status === "generating" || t.status === "saving"
          ? { ...t, status: "idle", progress: null, activeAudioId: undefined }
          : t,
      ),
      nextId,
      selectedTaskIds,
    };
  } catch {
    return { tasks: [], nextId: 1, selectedTaskIds: [] };
  }
}

function persistGeneration(tasks: GenerationTask[], nextId: number, selectedTaskIds: number[]) {
  if (!canUseLocalStorage()) {
    return;
  }
  try {
    window.localStorage.setItem(
      GENERATION_STORAGE_KEY,
      JSON.stringify({ tasks, nextId, selectedTaskIds }),
    );
  } catch {
    // Best-effort persistence.
  }
}

const initialGeneration = loadPersistedGeneration();

export const useGenerationStore = create<GenerationStore>((set, get) => ({
  tasks: initialGeneration.tasks,
  nextId: initialGeneration.nextId,
  selectedTaskIds: initialGeneration.selectedTaskIds,

  addTask: (text = "", customName = "") => {
    const { nextId, tasks } = get();
    
    // Calcular el siguiente número de audio basándose en las tareas existentes
    let autoName = customName;
    if (!autoName) {
      const audioNumbers = tasks
        .map(t => {
          const match = t.customName.match(/^audio_(\d+)$/);
          return match ? parseInt(match[1], 10) : 0;
        })
        .filter(n => n > 0);
      const maxNum = audioNumbers.length > 0 ? Math.max(...audioNumbers) : 0;
      autoName = `audio_${maxNum + 1}`;
    }
    
    const task: GenerationTask = {
      id: nextId,
      text,
      customName: autoName,
      status: "idle",
      progress: null,
      result: null,
      error: null,
    };
    set((s) => {
      const nextState = { tasks: [...s.tasks, task], nextId: s.nextId + 1 };
      persistGeneration(nextState.tasks, nextState.nextId, s.selectedTaskIds);
      return nextState;
    });
  },

  removeTask: (id) => {
    set((s) => {
      const nextTasks = s.tasks.filter((t) => t.id !== id);
      const nextSelected = s.selectedTaskIds.filter((tid) => tid !== id);
      persistGeneration(nextTasks, s.nextId, nextSelected);
      return { tasks: nextTasks, selectedTaskIds: nextSelected };
    });
  },

  updateTask: (id, patch) => {
    set((s) => {
      const nextTasks = s.tasks.map((t) => (t.id === id ? { ...t, ...patch } : t));
      persistGeneration(nextTasks, s.nextId, s.selectedTaskIds);
      return { tasks: nextTasks };
    });
  },

  generate: async (id, overrides) => {
    const task = get().tasks.find((t) => t.id === id);
    if (!task) return;

    const outputDir = (overrides.output_directory || "").trim();
    if (!outputDir) {
      if (typeof window !== "undefined") {
        window.alert("Debes seleccionar primero una carpeta de salida en la pestaña Config.");
      }
      get().updateTask(id, {
        status: "error",
        error: "Selecciona una carpeta de salida en Config antes de generar.",
      });
      return;
    }

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
      const pollIntervalMs = 3000;
      const maxWaitMs = 15 * 60 * 1000;
      const maxAttempts = Math.ceil(maxWaitMs / pollIntervalMs);
      for (let i = 0; i < maxAttempts; i++) {
        await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));

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

      const saveResp = await confirmSave(data.audio_id, req.output_directory);
      const finalAudioId = saveResp.data.audio_id || data.audio_id;
      const finalFilename = saveResp.data.filename || data.filename || null;
      get().updateTask(id, {
        status: "done",
        result: {
          ...data,
          audio_id: finalAudioId,
          filename: finalFilename,
          is_temp: false,
        },
      });
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
    const state = get();
    persistGeneration(state.tasks, state.nextId, state.selectedTaskIds);
  },

  toggleTaskSelection: (id) => {
    set((s) => {
      const isSelected = s.selectedTaskIds.includes(id);
      const nextSelected = isSelected
        ? s.selectedTaskIds.filter((tid) => tid !== id)
        : [...s.selectedTaskIds, id];
      persistGeneration(s.tasks, s.nextId, nextSelected);
      return { selectedTaskIds: nextSelected };
    });
  },

  clearSelection: () => {
    set((s) => {
      persistGeneration(s.tasks, s.nextId, []);
      return { selectedTaskIds: [] };
    });
  },

  selectAllTasks: () => {
    set((s) => {
      const allIds = s.tasks.map((t) => t.id);
      persistGeneration(s.tasks, s.nextId, allIds);
      return { selectedTaskIds: allIds };
    });
  },

  removeSelectedTasks: () => {
    set((s) => {
      const nextTasks = s.tasks.filter((t) => !s.selectedTaskIds.includes(t.id));
      persistGeneration(nextTasks, s.nextId, []);
      return { tasks: nextTasks, selectedTaskIds: [] };
    });
  },
}));
