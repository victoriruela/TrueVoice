import React, { useEffect, useState, useCallback } from "react";
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
import { useVoiceStore } from "../src/stores/useVoiceStore";
import { ollamaListModels, getSetupStatus, bootstrapSetup, SetupStatus, browseDrives, browseFolders } from "../src/api";

let settingsScrollMemory = 0;

const MODEL_OPTIONS = [
  { label: "VibeVoice 1.5B (recomendado)", value: "microsoft/VibeVoice-1.5b" },
  { label: "VibeVoice 7B", value: "microsoft/VibeVoice-7b" },
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
  const { voices, fetch: fetchVoices } = useVoiceStore();
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [ollamaLoading, setOllamaLoading] = useState(false);
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [setupLoading, setSetupLoading] = useState(false);
  const [showAudioFolderPicker, setShowAudioFolderPicker] = useState(false);
  const scrollRef = React.useRef<any>(null);

  useEffect(() => {
    fetchVoices();
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
    <ScrollView ref={scrollRef} style={shared.screen} onScroll={onScroll} scrollEventThrottle={16}>
      <Text style={shared.title}>⚙️ Configuración</Text>

      {/* Voice */}
      <Section title="Voz">
        <Text style={{ color: colors.textDim, marginBottom: 6 }}>Voz seleccionada</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {voices.map((v) => (
            <Pressable
              key={v.name}
              onPress={() => patch({ selected_voice: v.name })}
              style={[
                shared.buttonSecondary,
                config.selected_voice === v.name && { borderColor: colors.primary },
              ]}
            >
              <Text
                style={[
                  shared.buttonText,
                  {
                    color:
                      config.selected_voice === v.name ? colors.primary : colors.text,
                  },
                ]}
              >
                {v.alias || v.name}
              </Text>
            </Pressable>
          ))}
        </View>
      </Section>

      {/* Model */}
      <Section title="Modelo">
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {MODEL_OPTIONS.map((m) => (
            <Pressable
              key={m.value}
              onPress={() =>
                patch({ selected_model: m.value, selected_model_name: m.label })
              }
              style={[
                shared.buttonSecondary,
                config.selected_model === m.value && { borderColor: colors.primary },
              ]}
            >
              <Text
                style={[
                  shared.buttonText,
                  {
                    color:
                      config.selected_model === m.value ? colors.primary : colors.text,
                  },
                ]}
              >
                {m.label}
              </Text>
            </Pressable>
          ))}
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
  );
}
