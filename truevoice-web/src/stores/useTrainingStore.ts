import { create } from "zustand";
import api from "../api";

export interface DatasetFile {
  audio_path: string;
  transcript_path: string;
  base_name: string;
  valid: boolean;
  error_msg?: string;
}

export interface TrainingJob {
  job_id: string;
  lora_name: string;
  status: "preparing" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  start_time: string;
  end_time?: string;
  error?: string;
  logs?: string[];
  log_lines?: number;
}

export interface TrainingConfig {
  session_id: string;
  lora_name: string;
  model_base: string;
  epochs: number;
  batch_size: number;
  learning_rate: number;
  voice_prompt_drop_rate: number;
}

export interface LoRA {
  name: string;
  path: string;
  config: any;
  size_mb: number;
  modified: string;
}

interface TrainingStore {
  sessionId: string;
  uploadedFiles: string[];
  validatedFiles: DatasetFile[];
  jobs: TrainingJob[];
  loras: LoRA[];
  currentJob: TrainingJob | null;
  uploading: boolean;
  validating: boolean;
  
  // Actions
  generateSessionId: () => void;
  uploadFiles: (files: File[]) => Promise<void>;
  validateDataset: () => Promise<void>;
  prepareAndStart: (config: Omit<TrainingConfig, "session_id">) => Promise<void>;
  fetchJobs: () => Promise<void>;
  fetchJob: (jobId: string) => Promise<void>;
  pollJob: (jobId: string, interval?: number) => void;
  stopPolling: () => void;
  cancelJob: (jobId: string) => Promise<void>;
  fetchLoRAs: () => Promise<void>;
  deleteLoRA: (name: string) => Promise<void>;
  clearDataset: () => Promise<void>;
  reset: () => void;
}

let pollInterval: NodeJS.Timeout | null = null;

export const useTrainingStore = create<TrainingStore>((set, get) => ({
  sessionId: "",
  uploadedFiles: [],
  validatedFiles: [],
  jobs: [],
  loras: [],
  currentJob: null,
  uploading: false,
  validating: false,

  generateSessionId: () => {
    const id = `session_${Date.now()}_${Math.random().toString(36).substring(7)}`;
    set({ sessionId: id });
  },

  uploadFiles: async (files: File[]) => {
    const { sessionId } = get();
    if (!sessionId) {
      get().generateSessionId();
    }

    set({ uploading: true });
    try {
      const formData = new FormData();
      formData.append("session_id", get().sessionId);
      files.forEach((file) => {
        formData.append("files", file);
      });

      const response = await api.post("/training/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      set({ uploadedFiles: response.data.uploaded });
    } catch (error) {
      console.error("Upload failed:", error);
      throw error;
    } finally {
      set({ uploading: false });
    }
  },

  validateDataset: async () => {
    const { sessionId } = get();
    if (!sessionId) return;

    set({ validating: true });
    try {
      const response = await api.post("/training/validate", { session_id: sessionId });
      set({ validatedFiles: response.data.files });
    } catch (error) {
      console.error("Validation failed:", error);
      throw error;
    } finally {
      set({ validating: false });
    }
  },

  prepareAndStart: async (config: Omit<TrainingConfig, "session_id">) => {
    const { sessionId } = get();
    if (!sessionId) throw new Error("No session ID");

    try {
      // Prepare dataset and create job
      const prepareResponse = await api.post("/training/prepare", {
        session_id: sessionId,
        ...config,
      });

      const jobId = prepareResponse.data.job_id;

      // Start training
      await api.post("/training/start", { job_id: jobId });

      // Fetch updated job
      await get().fetchJob(jobId);
      
      // Start polling
      get().pollJob(jobId);
    } catch (error) {
      console.error("Training start failed:", error);
      throw error;
    }
  },

  fetchJobs: async () => {
    try {
      const response = await api.get("/training/jobs");
      set({ jobs: response.data });
    } catch (error) {
      console.error("Fetch jobs failed:", error);
    }
  },

  fetchJob: async (jobId: string) => {
    try {
      const response = await api.get(`/training/jobs/${jobId}`);
      set({ currentJob: response.data });
      
      // Update job in jobs list
      set((state) => ({
        jobs: state.jobs.map((j) =>
          j.job_id === jobId ? response.data : j
        ),
      }));
    } catch (error) {
      console.error("Fetch job failed:", error);
    }
  },

  pollJob: (jobId: string, interval = 2000) => {
    // Clear existing interval
    if (pollInterval) {
      clearInterval(pollInterval);
    }

    // Poll immediately
    get().fetchJob(jobId);

    // Set up polling
    pollInterval = setInterval(async () => {
      await get().fetchJob(jobId);

      // Check updated state AFTER fetch
      const { currentJob } = get();
      if (currentJob && ["completed", "failed", "cancelled"].includes(currentJob.status)) {
        get().stopPolling();
        // Refresh LoRAs list if completed
        if (currentJob.status === "completed") {
          await get().fetchLoRAs();
        }
      }
    }, interval);
  },

  stopPolling: () => {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  },

  cancelJob: async (jobId: string) => {
    try {
      await api.post(`/training/jobs/${jobId}/cancel`);
      await get().fetchJob(jobId);
      get().stopPolling();
    } catch (error) {
      console.error("Cancel job failed:", error);
      throw error;
    }
  },

  fetchLoRAs: async () => {
    try {
      const response = await api.get("/training/loras");
      set({ loras: response.data });
    } catch (error) {
      console.error("Fetch LoRAs failed:", error);
    }
  },

  deleteLoRA: async (name: string) => {
    try {
      await api.delete(`/training/loras/${name}`);
      await get().fetchLoRAs();
    } catch (error) {
      console.error("Delete LoRA failed:", error);
      throw error;
    }
  },

  clearDataset: async () => {
    const { sessionId } = get();
    if (!sessionId) return;

    try {
      await api.post("/training/clear-dataset", { session_id: sessionId });
      set({ uploadedFiles: [], validatedFiles: [] });
    } catch (error) {
      console.error("Clear dataset failed:", error);
      throw error;
    }
  },

  reset: () => {
    get().stopPolling();
    set({
      sessionId: "",
      uploadedFiles: [],
      validatedFiles: [],
      currentJob: null,
    });
  },
}));
