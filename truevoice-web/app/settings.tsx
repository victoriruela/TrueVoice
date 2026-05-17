import React, { useEffect, useState, useCallback, useRef } from "react";
import {
  View,
  Text,
  TextInput,
  ScrollView,
  Pressable,
  ActivityIndicator,
  Modal,
} from "react-native";
import { shared, colors } from "../src/theme";
import { useConfigStore } from "../src/stores/useConfigStore";
import {
  ollamaListModels, getSetupStatus, bootstrapSetup, SetupStatus,
  browseDrives, browseFolders, listModels, type ModelInfo,
  checkModelStatus, startModelDownload, getModelDownloadProgress,
} from "../src/api";

let settingsScrollMemory = 0;

const DEFAULT_MODEL_OPTIONS: ModelInfo[] = [
  { id: "microsoft/VibeVoice-1.5b", name: "VibeVoice 1.5B (recomendado)", size: "~6 GB" },
];

const QUANTIZE_OPTIONS = [
  { value: "none", label: "Precisión completa" },
  { value: "4bit", label: "4-bit (ahorro VRAM, req. GPU CUDA)" },
  { value: "8bit", label: "8-bit (equilibrado, req. GPU CUDA)" },
];

const FORMAT_OPTIONS = ["wav", "mp3", "flac", "ogg"];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={shared.card}>
      <Text style={[shared.label, { fontSize: 15, marginBottom: 8 }]}>{title}</Text>
      {children}
    </View>
  );
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <View style={{ marginBottom: 12 }}>
      <Text style={{ color: colors.textDim, marginBottom: 4 }}>
        {label}: <Text style={{ color: colors.primary }}>{value}</Text>
      </Text>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ width: "100%", accentColor: colors.primary }}
      />
    </View>
  );
}

function FolderPicker({
  visible,
  onSelect,
  onClose,
  title,
}: {
  visible: boolean;
  onSelect: (path: string) => void;
  onClose: () => void;
  title: string;
}) {
  const [currentPath, setCurrentPath] = useState<string>("");
  const [drives, setDrives] = useState<string[]>([]);
  const [folders, setFolders] = useState<{ name: string; path: string }[]>([]);
  const [parentPath, setParentPath] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (visible && !currentPath) {
      loadDrives();
    }
  }, [visible]);

  const loadDrives = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await browseDrives();
      setDrives(data || []);
      setCurrentPath("");
      setFolders([]);
      setParentPath("");
    } catch (e) {
      console.error("Error loading drives:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadFolders = useCallback(async (path: string) => {
    setLoading(true);
    try {
      const { data } = await browseFolders(path);
      setCurrentPath(data.current);
      setFolders(data.folders || []);
      setParentPath(data.parent || "");
    } catch (e) {
      console.error("Error loading folders:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleNavigate = (path: string) => {
    loadFolders(path);
  };

  const handleBack = () => {
    if (parentPath) {
      loadFolders(parentPath);
    } else {
      loadDrives();
    }
  };

  const handleSelect = () => {
    onSelect(currentPath);
    onClose();
    setCurrentPath("");
    setDrives([]);
    setFolders([]);
    setParentPath("");
  };

  return (
    <Modal visible={visible} transparent animationType="fade">
      <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.7)", justifyContent: "center", alignItems: "center", padding: 16 }}>
        <View style={{ backgroundColor: colors.bg, borderRadius: 12, width: "90%", maxHeight: "80%", padding: 16 }}>
          <Text style={[shared.title, { marginBottom: 16, fontSize: 16 }]}>{title}</Text>

          {loading ? (
            <ActivityIndicator size="large" color={colors.primary} />
          ) : currentPath ? (
            <>
              <Text style={{ color: colors.textDim, marginBottom: 8, fontSize: 12 }}>
                {currentPath.length > 50 ? "..." + currentPath.slice(-47) : currentPath}
              </Text>

              <ScrollView style={{ maxHeight: "60%", marginBottom: 12, borderBottomWidth: 1, borderColor: colors.border, paddingBottom: 12 }}>
                {parentPath && (
                  <Pressable onPress={handleBack} style={{ paddingVertical: 8, paddingHorizontal: 12, backgroundColor: colors.border, marginBottom: 8, borderRadius: 6 }}>
                    <Text style={{ color: colors.text }}>📁 .. (Atrás)</Text>
                  </Pressable>
                )}
                {folders.length === 0 ? (
                  <Text style={{ color: colors.textDim }}>Sin carpetas</Text>
                ) : (
                  folders.map((folder) => (
                    <Pressable key={folder.path} onPress={() => handleNavigate(folder.path)} style={{ paddingVertical: 8, paddingHorizontal: 12 }}>
                      <Text style={{ color: colors.primary }}>📁 {folder.name}</Text>
                    </Pressable>
                  ))
                )}
              </ScrollView>

              <View style={{ flexDirection: "row", gap: 8 }}>
                <Pressable style={[shared.buttonSecondary, { flex: 1 }]} onPress={onClose}>
                  <Text style={[shared.buttonText, { color: colors.text }]}>Cancelar</Text>
                </Pressable>
                <Pressable style={[shared.button, { flex: 1 }]} onPress={handleSelect}>
                  <Text style={shared.buttonText}>Seleccionar</Text>
                </Pressable>
              </View>
            </>
          ) : (
            <>
              <ScrollView style={{ maxHeight: "70%", marginBottom: 12 }}>
                {drives.map((drive) => (
                  <Pressable key={drive} onPress={() => handleNavigate(drive)} style={{ paddingVertical: 10, paddingHorizontal: 12, borderBottomWidth: 1, borderColor: colors.border }}>
                    <Text style={{ color: colors.primary, fontSize: 14 }}>💾 {drive}</Text>
                  </Pressable>
                ))}
              </ScrollView>
              <Pressable style={shared.buttonSecondary} onPress={onClose}>
                <Text style={[shared.buttonText, { color: colors.text }]}>Cancelar</Text>
              </Pressable>
            </>
          )}
        </View>
      </View>
    </Modal>
  );
}

export default function SettingsScreen() {
  const { config, loading, patch } = useConfigStore();
  const addCustomModel = useConfigStore((s) => s.addCustomModel);
  const deleteCustomModel = useConfigStore((s) => s.deleteCustomModel);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [ollamaLoading, setOllamaLoading] = useState(false);
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [setupLoading, setSetupLoading] = useState(false);
  const [showAudioFolderPicker, setShowAudioFolderPicker] = useState(false);
  const [modelOptions, setModelOptions] = useState<ModelInfo[]>(DEFAULT_MODEL_OPTIONS);
  const [newModelId, setNewModelId] = useState("");
  const [newModelName, setNewModelName] = useState("");
  const scrollRef = React.useRef<any>(null);

  // Model download modal state
  const [downloadModal, setDownloadModal] = useState<{
    model: ModelInfo;
    status: "confirm" | "downloading" | "done" | "error";
    error?: string;
  } | null>(null);
  const downloadPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup poll on unmount
  useEffect(() => {
    return () => {
      if (downloadPollRef.current) clearInterval(downloadPollRef.current);
    };
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await listModels();
        if (Array.isArray(data) && data.length > 0) setModelOptions(data);
      } catch {
        /* keep defaults */
      }
    })();
  }, []);

  const refreshOllamaModels = useCallback(async () => {
    setOllamaLoading(true);
    try {
      const { data } = await ollamaListModels();
      setOllamaModels(data || []);
    } catch {
      setOllamaModels([]);
    }
    setOllamaLoading(false);
  }, [config.ollama_url]);

  useEffect(() => {
    refreshOllamaModels();
  }, [config.ollama_url]);

  const refreshSetupStatus = useCallback(async () => {
    try {
      const { data } = await getSetupStatus();
      setSetup(data);
    } catch {
      setSetup(null);
    }
  }, []);

  const runBootstrap = useCallback(async () => {
    setSetupLoading(true);
    try {
      await bootstrapSetup();
      await refreshSetupStatus();
    } finally {
      setSetupLoading(false);
    }
  }, [refreshSetupStatus]);

  const handleModelSelect = useCallback(async (m: ModelInfo) => {
    try {
      const { data } = await checkModelStatus(m.id);
      if (data.downloaded) {
        patch({ selected_model: m.id, selected_model_name: m.name });
      } else {
        setDownloadModal({ model: m, status: "confirm" });
      }
    } catch {
      // If we can't check, just select it
      patch({ selected_model: m.id, selected_model_name: m.name });
    }
  }, [patch]);

  const handleStartDownload = useCallback(async () => {
    if (!downloadModal) return;
    const m = downloadModal.model;
    setDownloadModal({ model: m, status: "downloading" });
    try {
      await startModelDownload(m.id);
      downloadPollRef.current = setInterval(async () => {
        try {
          const { data } = await getModelDownloadProgress(m.id);
          if (data.status === "done") {
            if (downloadPollRef.current) {
              clearInterval(downloadPollRef.current);
              downloadPollRef.current = null;
            }
            patch({ selected_model: m.id, selected_model_name: m.name });
            setDownloadModal({ model: m, status: "done" });
            setTimeout(() => setDownloadModal(null), 2500);
          } else if (data.status === "error") {
            if (downloadPollRef.current) {
              clearInterval(downloadPollRef.current);
              downloadPollRef.current = null;
            }
            setDownloadModal({
              model: m,
              status: "error",
              error: data.message || "Error desconocido",
            });
          }
        } catch {
          /* keep polling */
        }
      }, 5000);
    } catch (e: any) {
      setDownloadModal({
        model: m,
        status: "error",
        error: e?.message || "Error al iniciar descarga",
      });
    }
  }, [downloadModal, patch]);

  useEffect(() => {
    refreshSetupStatus();
  }, []);

  useEffect(() => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo?.({ y: settingsScrollMemory, animated: false });
    });
  }, []);

  const onScroll = useCallback((e: any) => {
    const y = e?.nativeEvent?.contentOffset?.y ?? 0;
    settingsScrollMemory = y;
  }, []);

  if (loading) {
    return (
      <View style={[shared.screen, { justifyContent: "center", alignItems: "center" }]}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <View style={{ flex: 1 }}>
    <ScrollView ref={scrollRef} style={shared.screen} onScroll={onScroll} scrollEventThrottle={16}>
      <Text style={shared.title}>⚙️ Configuración</Text>

      {/* Model */}
      <Section title="Modelo">
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {modelOptions.map((m) => (
            <Pressable
              key={m.id}
              onPress={() => handleModelSelect(m)}
              style={[
                shared.buttonSecondary,
                config.selected_model === m.id && { borderColor: colors.primary },
              ]}
            >
              <Text
                style={[
                  shared.buttonText,
                  {
                    color:
                      config.selected_model === m.id ? colors.primary : colors.text,
                  },
                ]}
              >
                {m.name} <Text style={{ color: colors.textDim, fontSize: 11 }}>({m.size})</Text>
              </Text>
            </Pressable>
          ))}
        </View>
      </Section>

      {/* Custom models */}
      <Section title="Modelos personalizados">
        <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 12 }}>
          Añade modelos personalizados por su HF repo ID (ej: <Text style={{ color: colors.accent }}>microsoft/VibeVoice-1.5b</Text>) o ruta absoluta a una carpeta local.
        </Text>

        {(config.custom_models || []).length === 0 ? (
          <Text style={{ color: colors.textDim, fontStyle: "italic", fontSize: 13, marginBottom: 12 }}>
            No hay modelos personalizados.
          </Text>
        ) : (
          (config.custom_models || []).map((m) => (
            <View
              key={m.id}
              style={{
                backgroundColor: colors.surfaceLight,
                borderRadius: 6,
                padding: 10,
                marginBottom: 8,
                borderWidth: 1,
                borderColor: colors.border,
                flexDirection: "row",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <View style={{ flex: 1 }}>
                <Text style={{ color: colors.text, fontWeight: "600", fontSize: 14 }}>{m.name}</Text>
                <Text style={{ color: colors.textDim, fontSize: 11 }}>{m.id}  ·  {m.size}</Text>
              </View>
              <Pressable
                onPress={() => {
                  if (window.confirm(`¿Eliminar modelo "${m.name}"?`)) deleteCustomModel(m.id);
                }}
                style={{ paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, borderColor: colors.error, borderRadius: 4 }}
              >
                <Text style={{ color: colors.error, fontSize: 11, fontWeight: "600" }}>Eliminar</Text>
              </Pressable>
            </View>
          ))
        )}

        <View style={{ marginTop: 8 }}>
          <Text style={shared.label}>Nombre</Text>
          <TextInput
            style={shared.input}
            value={newModelName}
            onChangeText={setNewModelName}
            placeholder="ej: VibeVoice Local"
            placeholderTextColor={colors.textDim}
          />
          <Text style={shared.label}>ID / Ruta local</Text>
          <TextInput
            style={shared.input}
            value={newModelId}
            onChangeText={setNewModelId}
            placeholder="microsoft/VibeVoice-1.5b o C:\modelos\mi_modelo"
            placeholderTextColor={colors.textDim}
            autoCapitalize="none"
          />
          <Pressable
            onPress={async () => {
              const id = newModelId.trim();
              const name = newModelName.trim() || id;
              if (!id) {
                window.alert("Indica un ID o ruta");
                return;
              }
              await addCustomModel({ id, name, size: "?" });
              setNewModelId("");
              setNewModelName("");
              try {
                const { data } = await listModels();
                if (Array.isArray(data) && data.length > 0) setModelOptions(data);
              } catch { /* */ }
            }}
            style={[shared.button, { alignSelf: "flex-start", minWidth: 160 }]}
          >
            <Text style={shared.buttonText}>Añadir modelo</Text>
          </Pressable>
        </View>
      </Section>

      {/* Output format */}
      <Section title="Formato de salida">
        <View style={shared.row}>
          {FORMAT_OPTIONS.map((f) => (
            <Pressable
              key={f}
              onPress={() => patch({ output_format: f })}
              style={[
                shared.buttonSecondary,
                config.output_format === f && { borderColor: colors.primary },
              ]}
            >
              <Text
                style={[
                  shared.buttonText,
                  { color: config.output_format === f ? colors.primary : colors.text },
                ]}
              >
                {f.toUpperCase()}
              </Text>
            </Pressable>
          ))}
        </View>
      </Section>

      {/* Synthesis params */}
      <Section title="Parámetros de síntesis">
        <Slider
          label="CFG Scale"
          value={config.cfg_scale}
          min={0.5}
          max={5.0}
          step={0.1}
          onChange={(v) => patch({ cfg_scale: v })}
        />
        <Slider
          label="DDPM Steps"
          value={config.ddpm_steps}
          min={1}
          max={200}
          step={1}
          onChange={(v) => patch({ ddpm_steps: v })}
        />
        <Pressable
          onPress={() => patch({ disable_prefill: !config.disable_prefill })}
          style={shared.row}
        >
          <View
            style={{
              width: 20,
              height: 20,
              borderRadius: 4,
              borderWidth: 2,
              borderColor: config.disable_prefill ? colors.primary : colors.border,
              backgroundColor: config.disable_prefill ? colors.primary : "transparent",
              marginRight: 8,
              justifyContent: "center",
              alignItems: "center",
            }}
          >
            {config.disable_prefill && (
              <Text style={{ color: colors.bg, fontSize: 12, fontWeight: "bold" }}>✓</Text>
            )}
          </View>
          <Text style={{ color: colors.text }}>Desactivar clonación de voz (prefill)</Text>
        </Pressable>
      </Section>

      {/* Advanced generation */}
      <Section title="Generación avanzada">
        <Slider
          label="Velocidad de voz"
          value={config.voice_speed_factor ?? 1.0}
          min={0.8}
          max={1.2}
          step={0.01}
          onChange={(v) => patch({ voice_speed_factor: v })}
        />
        <Slider
          label="Palabras por bloque (chunking)"
          value={config.max_words_per_chunk ?? 250}
          min={100}
          max={500}
          step={10}
          onChange={(v) => patch({ max_words_per_chunk: v })}
        />

        <Text style={{ color: colors.textDim, marginBottom: 6, marginTop: 4 }}>Cuantización LLM</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
          {QUANTIZE_OPTIONS.map((q) => (
            <Pressable
              key={q.value}
              onPress={() => patch({ quantize_llm: q.value })}
              style={[
                shared.buttonSecondary,
                (config.quantize_llm || "none") === q.value && { borderColor: colors.primary },
              ]}
            >
              <Text
                style={[
                  shared.buttonText,
                  {
                    color:
                      (config.quantize_llm || "none") === q.value ? colors.primary : colors.text,
                  },
                ]}
              >
                {q.label}
              </Text>
            </Pressable>
          ))}
        </View>
        <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 12 }}>
          La cuantización solo funciona con GPU CUDA.
        </Text>

        <Pressable
          onPress={() => patch({ use_sampling: !config.use_sampling })}
          style={[shared.row, { marginBottom: 8 }]}
        >
          <View
            style={{
              width: 20,
              height: 20,
              borderRadius: 4,
              borderWidth: 2,
              borderColor: config.use_sampling ? colors.primary : colors.border,
              backgroundColor: config.use_sampling ? colors.primary : "transparent",
              marginRight: 8,
              justifyContent: "center",
              alignItems: "center",
            }}
          >
            {config.use_sampling && (
              <Text style={{ color: colors.bg, fontSize: 12, fontWeight: "bold" }}>✓</Text>
            )}
          </View>
          <Text style={{ color: colors.text }}>Modo sampling (variación creativa)</Text>
        </Pressable>

        {config.use_sampling && (
          <>
            <Slider
              label="Temperature"
              value={config.temperature ?? 0.95}
              min={0.1}
              max={2.0}
              step={0.05}
              onChange={(v) => patch({ temperature: v })}
            />
            <Slider
              label="Top-p"
              value={config.top_p ?? 0.95}
              min={0.1}
              max={1.0}
              step={0.05}
              onChange={(v) => patch({ top_p: v })}
            />
          </>
        )}
      </Section>

      {/* Output directory */}
      <Section title="📂 Carpeta de salida de audios">
        <View style={{ marginBottom: 12 }}>
          <Text style={{ color: colors.textDim, marginBottom: 8, fontSize: 12 }}>
            {config.output_directory ? (config.output_directory.length > 50 ? "..." + config.output_directory.slice(-47) : config.output_directory) : "No seleccionado - usar carpeta por defecto"}
          </Text>
          <View style={{ flexDirection: "row", gap: 8 }}>
            <Pressable style={[shared.button, { minWidth: 180 }]} onPress={() => setShowAudioFolderPicker(true)}>
              <Text style={shared.buttonText}>Seleccionar carpeta</Text>
            </Pressable>
            {config.output_directory && (
              <Pressable style={[shared.buttonSecondary, { minWidth: 110 }]} onPress={() => patch({ output_directory: "" })}>
                <Text style={[shared.buttonText, { color: colors.text }]}>Limpiar</Text>
              </Pressable>
            )}
          </View>
        </View>
      </Section>

      {/* Ollama */}
      <Section title="Ollama (IA para narraciones)">
        <Text style={{ color: colors.textDim, marginBottom: 4 }}>URL</Text>
        <TextInput
          style={[shared.input, { marginBottom: 12 }]}
          value={config.ollama_url}
          onChangeText={(v) => patch({ ollama_url: v })}
          placeholder="http://localhost:11434"
          placeholderTextColor={colors.textDim}
        />

        <View style={[shared.row, { marginBottom: 8 }]}>
          <Text style={{ color: colors.textDim, flex: 1 }}>Modelo</Text>
          <Pressable style={shared.buttonSecondary} onPress={refreshOllamaModels}>
            <Text style={[shared.buttonText, { color: colors.text }]}>
              {ollamaLoading ? "..." : "Refrescar"}
            </Text>
          </Pressable>
        </View>

        {ollamaModels.length > 0 ? (
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {ollamaModels.map((m) => (
              <Pressable
                key={m}
                onPress={() => patch({ ollama_model: m })}
                style={[
                  shared.buttonSecondary,
                  config.ollama_model === m && { borderColor: colors.primary },
                ]}
              >
                <Text
                  style={[
                    shared.buttonText,
                    { color: config.ollama_model === m ? colors.primary : colors.text },
                  ]}
                >
                  {m}
                </Text>
              </Pressable>
            ))}
          </View>
        ) : (
          <TextInput
            style={shared.input}
            value={config.ollama_model}
            onChangeText={(v) => patch({ ollama_model: v })}
            placeholder="Nombre del modelo Ollama"
            placeholderTextColor={colors.textDim}
          />
        )}
      </Section>

      <Section title="Runtime VibeVoice (Python sidecar)">
        <Text style={{ color: colors.textDim, marginBottom: 4 }}>
          Estado: <Text style={{ color: setup?.ready ? colors.success : colors.accent }}>{setup?.stage || "desconocido"}</Text>
        </Text>
        <Text style={{ color: colors.textDim, marginBottom: 4 }} numberOfLines={1}>
          Python: {setup?.python_path || "-"}
        </Text>
        <Text style={{ color: colors.textDim, marginBottom: 8 }} numberOfLines={1}>
          Runtime: {setup?.runtime_path || "-"}
        </Text>
        {setup?.error ? (
          <Text style={{ color: colors.error, marginBottom: 8 }}>{setup.error}</Text>
        ) : null}
        <View style={shared.row}>
          <Pressable style={[shared.buttonSecondary, { minWidth: 160 }]} onPress={refreshSetupStatus}>
            <Text style={[shared.buttonText, { color: colors.text }]}>Refrescar estado</Text>
          </Pressable>
          <Pressable style={[shared.button, { minWidth: 170 }]} onPress={runBootstrap}>
            <Text style={shared.buttonText}>{setupLoading ? "Preparando..." : "Preparar runtime"}</Text>
          </Pressable>
        </View>
      </Section>

      <View style={{ height: 40 }} />

      {/* Folder Pickers */}
      <FolderPicker
        visible={showAudioFolderPicker}
        onSelect={(path) => patch({ output_directory: path })}
        onClose={() => setShowAudioFolderPicker(false)}
        title="Seleccionar carpeta de salida de audios"
      />
    </ScrollView>

    {/* ── Model download modal ─────────────────────────────────── */}
    {downloadModal && (
      <Modal visible transparent animationType="fade">
        <View
          style={{
            flex: 1,
            backgroundColor: "rgba(0,0,0,0.7)",
            justifyContent: "center",
            alignItems: "center",
            padding: 20,
          }}
        >
          <View
            style={{
              backgroundColor: colors.surface,
              borderRadius: 8,
              padding: 20,
              borderWidth: 1,
              borderColor: colors.border,
              maxWidth: 480,
              width: "100%",
            }}
          >
            {downloadModal.status === "confirm" && (
              <>
                <Text style={{ color: colors.text, fontSize: 16, fontWeight: "700", marginBottom: 8 }}>
                  Modelo no descargado
                </Text>
                <Text style={{ color: colors.textDim, marginBottom: 16 }}>
                  {downloadModal.model.name}
                  {downloadModal.model.size ? ` (${downloadModal.model.size})` : ""} no está en la caché local.{"\n\n"}
                  ¿Deseas descargarlo ahora? Puede tardar varios minutos.
                </Text>
                <View style={{ flexDirection: "row", gap: 8, justifyContent: "flex-end" }}>
                  <Pressable style={shared.buttonSecondary} onPress={() => setDownloadModal(null)}>
                    <Text style={[shared.buttonText, { color: colors.text }]}>Cancelar</Text>
                  </Pressable>
                  <Pressable style={shared.button} onPress={handleStartDownload}>
                    <Text style={shared.buttonText}>Descargar</Text>
                  </Pressable>
                </View>
              </>
            )}
            {downloadModal.status === "downloading" && (
              <>
                <Text style={{ color: colors.text, fontSize: 16, fontWeight: "700", marginBottom: 8 }}>
                  Descargando modelo
                </Text>
                <ActivityIndicator color={colors.primary} style={{ marginVertical: 12 }} />
                <Text style={{ color: colors.textDim, marginBottom: 4 }}>
                  Descargando {downloadModal.model.name}...
                </Text>
                <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 12 }}>
                  Esto puede tardar varios minutos dependiendo de tu conexión.
                </Text>
                <Pressable
                  style={[shared.buttonSecondary, { alignSelf: "flex-start" }]}
                  onPress={() => {
                    if (downloadPollRef.current) {
                      clearInterval(downloadPollRef.current);
                      downloadPollRef.current = null;
                    }
                    setDownloadModal(null);
                  }}
                >
                  <Text style={[shared.buttonText, { color: colors.text }]}>Cancelar</Text>
                </Pressable>
              </>
            )}
            {downloadModal.status === "done" && (
              <>
                <Text style={{ color: colors.success, fontSize: 16, fontWeight: "700" }}>
                  ✓ Descarga completada
                </Text>
                <Text style={{ color: colors.textDim, marginTop: 8 }}>
                  El modelo ha sido descargado y seleccionado.
                </Text>
              </>
            )}
            {downloadModal.status === "error" && (
              <>
                <Text style={{ color: colors.error, fontSize: 16, fontWeight: "700", marginBottom: 8 }}>
                  Error en la descarga
                </Text>
                <Text style={{ color: colors.textDim, marginBottom: 16 }}>{downloadModal.error}</Text>
                <Pressable style={shared.button} onPress={() => setDownloadModal(null)}>
                  <Text style={shared.buttonText}>Cerrar</Text>
                </Pressable>
              </>
            )}
          </View>
        </View>
      </Modal>
    )}
    </View>
  );
}
