import { create } from "zustand";
import {
  getConfig,
  updateConfig,
  listNarrators as apiListNarrators,
  upsertNarrator as apiUpsertNarrator,
  updateNarratorApi,
  deleteNarratorApi,
  setPrincipalNarratorApi,
  addCustomModel as apiAddCustomModel,
  deleteCustomModel as apiDeleteCustomModel,
  type NarratorConfig,
  type CustomModel,
} from "../api";

export type { NarratorConfig, CustomModel };

export interface AppConfig {
  selected_voice: string;
  selected_model_name: string;
  selected_model: string;
  output_format: string;
  cfg_scale: number;
  ddpm_steps: number;
  disable_prefill: boolean;
  voice_folder_type: string;
  custom_folder_path: string;
  output_folder_type: string;
  custom_output_path: string;
  texts_folder_type: string;
  custom_texts_path: string;
  output_directory: string;
  voice_directory: string;
  ollama_url: string;
  ollama_model: string;
  generation_tasks: any[];
  last_text_input: string;
  last_custom_name: string;
  last_race_session: string;
  audio_output_folder: string;
  texts_output_folder: string;
  voice_speed_factor: number;
  max_words_per_chunk: number;
  quantize_llm: string;
  temperature: number;
  top_p: number;
  use_sampling: boolean;
  narrators: NarratorConfig[];
  custom_models: CustomModel[];
  [key: string]: any;
}

const DEFAULT_CONFIG: AppConfig = {
  selected_voice: "Alice",
  selected_model_name: "VibeVoice 1.5B (recomendado)",
  selected_model: "microsoft/VibeVoice-1.5b",
  output_format: "wav",
  cfg_scale: 2.0,
  ddpm_steps: 30,
  disable_prefill: false,
  voice_folder_type: "default",
  custom_folder_path: "",
  output_folder_type: "default",
  custom_output_path: "",
  texts_folder_type: "default",
  custom_texts_path: "",
  output_directory: "",
  voice_directory: "",
  ollama_url: "http://localhost:11434",
  ollama_model: "llama3.2",
  generation_tasks: [],
  last_text_input: "",
  last_custom_name: "",
  last_race_session: "",
  audio_output_folder: "",
  texts_output_folder: "",
  voice_speed_factor: 1.0,
  max_words_per_chunk: 250,
  quantize_llm: "none",
  temperature: 0.95,
  top_p: 0.95,
  use_sampling: false,
  narrators: [],
  custom_models: [],
};

interface ConfigStore {
  config: AppConfig;
  loading: boolean;
  fetch: () => Promise<void>;
  patch: (updates: Partial<AppConfig>) => Promise<void>;
  fetchNarrators: () => Promise<void>;
  addNarrator: (n: NarratorConfig) => Promise<void>;
  updateNarrator: (key: string, n: Partial<NarratorConfig>) => Promise<void>;
  deleteNarrator: (key: string) => Promise<void>;
  setPrincipalNarrator: (key: string) => Promise<void>;
  addCustomModel: (m: CustomModel) => Promise<void>;
  deleteCustomModel: (id: string) => Promise<void>;
}

export const useConfigStore = create<ConfigStore>((set, get) => ({
  config: { ...DEFAULT_CONFIG },
  loading: false,

  fetch: async () => {
    set({ loading: true });
    try {
      const { data } = await getConfig();
      set({ config: { ...DEFAULT_CONFIG, ...data } });
    } catch {
      /* keep defaults */
    } finally {
      set({ loading: false });
    }
  },

  patch: async (updates) => {
    const merged = { ...get().config, ...updates };
    set({ config: merged });
    try {
      await updateConfig(updates);
    } catch {
      /* silent — local state already updated */
    }
  },

  fetchNarrators: async () => {
    try {
      const { data } = await apiListNarrators();
      set({ config: { ...get().config, narrators: data || [] } });
    } catch {
      /* silent */
    }
  },

  addNarrator: async (n) => {
    try {
      const { data } = await apiUpsertNarrator(n);
      set({ config: { ...get().config, narrators: data || [] } });
    } catch {
      /* silent */
    }
  },

  updateNarrator: async (key, patch) => {
    try {
      await updateNarratorApi(key, patch);
      await get().fetchNarrators();
    } catch {
      /* silent */
    }
  },

  deleteNarrator: async (key) => {
    try {
      await deleteNarratorApi(key);
      await get().fetchNarrators();
    } catch {
      /* silent */
    }
  },

  setPrincipalNarrator: async (key) => {
    try {
      const { data } = await setPrincipalNarratorApi(key);
      set({ config: { ...get().config, narrators: data || [] } });
    } catch {
      /* silent */
    }
  },

  addCustomModel: async (m) => {
    try {
      const { data } = await apiAddCustomModel(m);
      set({ config: { ...get().config, custom_models: data || [] } });
    } catch {
      /* silent */
    }
  },

  deleteCustomModel: async (id) => {
    try {
      await apiDeleteCustomModel(id);
      const cur = get().config.custom_models || [];
      set({
        config: {
          ...get().config,
          custom_models: cur.filter((m) => m.id !== id),
        },
      });
    } catch {
      /* silent */
    }
  },
}));
