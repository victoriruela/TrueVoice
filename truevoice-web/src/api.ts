import axios from "axios";

const API_BASE =
  typeof window !== "undefined" && window.location.hostname !== "localhost"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://localhost:8000";

const api = axios.create({ baseURL: API_BASE, timeout: 600_000 });

/* ── Health ─────────────────────────────────────────────────────────── */
export const healthCheck = () => api.get<{ status: string }>("/");

/* ── Config ─────────────────────────────────────────────────────────── */
export const getConfig = () => api.get<Record<string, any>>("/config");
export const updateConfig = (patch: Record<string, any>) =>
  api.put<Record<string, any>>("/config", patch);

/* ── Voices ─────────────────────────────────────────────────────────── */
export interface VoiceInfo {
  name: string;
  filename: string;
  alias: string | null;
}
export const listVoices = (directory?: string) =>
  api.get<VoiceInfo[]>("/voices", { params: directory ? { directory } : {} });
export const uploadVoice = (name: string, file: File) => {
  const fd = new FormData();
  fd.append("voice_name", name);
  fd.append("audio_file", file);
  return api.post<VoiceInfo>("/voices/upload", fd);
};
export const deleteVoice = (name: string) => api.delete(`/voices/${name}`);

/* ── Models ─────────────────────────────────────────────────────────── */
export interface ModelInfo {
  id: string;
  name: string;
  size: string;
}
export const listModels = () => api.get<ModelInfo[]>("/models");

/* ── Generation ─────────────────────────────────────────────────────── */
export interface GenerateRequest {
  text: string;
  voice_name?: string;
  custom_output_name?: string;
  output_directory?: string;
  audio_id_hint?: string;
  model?: string;
  output_format?: string;
  cfg_scale?: number;
  ddpm_steps?: number;
  disable_prefill?: boolean;
}
export interface GenerateResponse {
  success: boolean;
  message: string;
  audio_id: string | null;
  filename: string | null;
  is_temp: boolean;
}
export const generateAudio = (
  req: GenerateRequest,
  voiceDirectory?: string,
) =>
  api.post<GenerateResponse>("/generate", req, {
    params: voiceDirectory ? { voice_directory: voiceDirectory } : {},
  });

export interface ProgressInfo {
  total: number;
  current: number;
  status: string;
  error?: string;
  start_time: number;
  last_update: number;
}
export const getProgress = (id: string) =>
  api.get<ProgressInfo>(`/progress/${id}`);

export const cancelGeneration = (id: string) => api.post(`/cancel/${id}`);

export const confirmSave = (audioId: string, outputDirectory?: string) =>
  api.post("/confirm_save", { audio_id: audioId, output_directory: outputDirectory });

export const getAudioUrl = (id: string, directory?: string) => {
  const params = directory ? `?directory=${encodeURIComponent(directory)}` : "";
  return `${API_BASE}/audio/${id}${params}`;
};

/* ── Outputs ────────────────────────────────────────────────────────── */
export interface OutputFileInfo {
  id: string;
  filename: string;
  path: string;
  size: number;
  created: number;
}
export const listOutputs = (directory?: string) =>
  api.get<OutputFileInfo[]>("/outputs", {
    params: directory ? { directory } : {},
  });
export const deleteOutputs = (filenames: string[], directory?: string) =>
  api.delete("/outputs/delete", {
    params: { filenames, ...(directory ? { directory } : {}) },
  });

export const cleanupTemp = () => api.post("/cleanup_temp");

/* ── Runtime setup ──────────────────────────────────────────────────── */
export interface SetupStatus {
  running: boolean;
  ready: boolean;
  stage: string;
  error?: string;
  last_update: number;
  python_path: string;
  runtime_path: string;
}
export const getSetupStatus = () => api.get<SetupStatus>("/setup/status");
export const bootstrapSetup = () => api.post<{ status: string; python_path: string; runtime_path: string }>("/setup/bootstrap");

/* ── Ollama ─────────────────────────────────────────────────────────── */
export const ollamaListModels = () =>
  api.get<string[]>("/ollama/models");
export const ollamaGenerate = (
  prompt: string,
  model?: string,
  options?: Record<string, any>,
) => api.post<{ text: string; model: string }>("/ollama/generate", { prompt, model, options });

/* ── Browse ─────────────────────────────────────────────────────────── */
export const browseDrives = () => api.get<string[]>("/browse/drives");
export interface BrowseResult {
  current: string;
  parent: string;
  folders: { name: string; path: string }[];
}
export const browseFolders = (path: string) =>
  api.get<BrowseResult>("/browse/folders", { params: { path } });

/* ── Race ───────────────────────────────────────────────────────────── */
export interface RaceHeaderData {
  track_event: string;
  track_length: number;
  race_laps: number;
  num_drivers: number;
  grid_order: string[];
  intro_text: string;
}
export interface RaceEventData {
  lap: number;
  timestamp: number;
  event_type: number;
  summary: string;
  description: string;
}
export const raceParse = (file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return api.post<{ header: RaceHeaderData; events: RaceEventData[] }>(
    "/race/parse",
    fd,
  );
};
export const raceGenerateIntro = (header: RaceHeaderData) =>
  api.post<{ intro_text: string }>("/race/intro", { header });
export const raceGenerateDescriptions = (events: RaceEventData[]) =>
  api.post<{ events: RaceEventData[] }>("/race/descriptions", { events });

export interface RaceSession {
  intro_text: string;
  intro_audio: string;
  header: RaceHeaderData;
  events: RaceEventData[];
  event_audios: Record<string, string>;
}
export const raceListSessions = () =>
  api.get<{ name: string; filename: string; size: number; modified: number }[]>(
    "/race/sessions",
  );
export const raceGetSession = (name: string) =>
  api.get<RaceSession>(`/race/sessions/${encodeURIComponent(name)}`);
export const raceSaveSession = (name: string, session: RaceSession) =>
  api.post(`/race/sessions/${encodeURIComponent(name)}`, session);
export const raceDeleteSession = (name: string) =>
  api.delete(`/race/sessions/${encodeURIComponent(name)}`);
export const raceExcelUrl = (name: string) =>
  `${API_BASE}/race/sessions/${encodeURIComponent(name)}/excel`;

export default api;
