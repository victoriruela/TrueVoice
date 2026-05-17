import React, { useEffect, useState, useCallback, useRef } from "react";
import { View, Text, ScrollView, Pressable, ActivityIndicator, Alert } from "react-native";
import { shared, colors } from "../src/theme";
import { useTrainingStore, type DatasetFile, type TrainingJob } from "../src/stores/useTrainingStore";

// ── Types for audio split ──────────────────────────────────────────────────
interface SplitJobStatus {
  id: string;
  status: "running" | "done" | "error";
  progress: number;
  total: number;
  done: number;
  error?: string;
  segments?: Array<{ audio: string; audio_dir: string; transcript?: string }>;
}

export default function EntrenarScreen() {
  const {
    sessionId,
    uploadedFiles,
    validatedFiles,
    currentJob,
    loras,
    uploading,
    validating,
    generateSessionId,
    uploadFiles,
    validateDataset,
    prepareAndStart,
    fetchJobs,
    fetchLoRAs,
    cancelJob,
    deleteLoRA,
    clearDataset,
    reset,
  } = useTrainingStore();

  const [loraName, setLoraName] = useState("");
  const [modelBase, setModelBase] = useState("microsoft/VibeVoice-1.5B");
  const [epochs, setEpochs] = useState(1);
  const [batchSize, setBatchSize] = useState(4);
  const [learningRate, setLearningRate] = useState(2.5e-5);
  const [voicePromptDropRate, setVoicePromptDropRate] = useState(1.0);

  // Audio splitter state
  const [splitJobId, setSplitJobId] = useState<string | null>(null);
  const [splitStatus, setSplitStatus] = useState<SplitJobStatus | null>(null);
  const [splitPolling, setSplitPolling] = useState(false);
  const [whisperModel, setWhisperModel] = useState<string>("base");
  const [silenceThreshold, setSilenceThreshold] = useState("-35");
  const [speakerNumber, setSpeakerNumber] = useState(1);
  const splitPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioInputRef = useRef<HTMLInputElement | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    generateSessionId();
    fetchLoRAs();
    fetchJobs();
  }, []);

  const handleFileSelect = useCallback(() => {
    if (typeof document === "undefined") return;
    
    if (!fileInputRef.current) {
      const input = document.createElement("input");
      input.type = "file";
      input.multiple = true;
      input.accept = ".wav,.mp3,.flac,.ogg,.txt";
      fileInputRef.current = input;
    }

    const input = fileInputRef.current;
    input.onchange = async (e: any) => {
      const files = Array.from(e.target.files || []) as File[];
      if (files.length === 0) return;

      try {
        await uploadFiles(files);
        await validateDataset();
      } catch (error: any) {
        Alert.alert("Error", error.message || "Failed to upload files");
      }
    };
    input.click();
  }, [uploadFiles, validateDataset]);

  const handleStartTraining = useCallback(async () => {
    if (!loraName.trim()) {
      Alert.alert("Error", "Por favor ingresa un nombre para el LoRA");
      return;
    }

    const validCount = validatedFiles.filter((f) => f.valid).length;
    if (validCount === 0) {
      Alert.alert("Error", "No hay archivos válidos para entrenar");
      return;
    }

    try {
      await prepareAndStart({
        lora_name: loraName,
        model_base: modelBase,
        epochs,
        batch_size: batchSize,
        learning_rate: learningRate,
        voice_prompt_drop_rate: voicePromptDropRate,
      });
    } catch (error: any) {
      Alert.alert("Error", error.message || "Failed to start training");
    }
  }, [loraName, modelBase, epochs, batchSize, learningRate, voicePromptDropRate, validatedFiles, prepareAndStart]);

  const handleCancelJob = useCallback(async () => {
    if (!currentJob) return;
    try {
      await cancelJob(currentJob.job_id);
    } catch (error: any) {
      Alert.alert("Error", error.message || "Failed to cancel job");
    }
  }, [currentJob, cancelJob]);

  const handleDeleteLoRA = useCallback(async (name: string) => {
    if (!confirm(`¿Eliminar LoRA "${name}"?`)) return;
    try {
      await deleteLoRA(name);
    } catch (error: any) {
      Alert.alert("Error", error.message || "Failed to delete LoRA");
    }
  }, [deleteLoRA]);

  const handleClearDataset = useCallback(async () => {
    if (!confirm("¿Limpiar dataset cargado?")) return;
    try {
      await clearDataset();
    } catch (error: any) {
      Alert.alert("Error", error.message || "Failed to clear dataset");
    }
  }, [clearDataset]);

  // ── Audio splitter handlers ──────────────────────────────────────────────
  const handleSplitAudioSelect = useCallback(() => {
    if (typeof document === "undefined") return;
    if (!audioInputRef.current) {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".wav,.mp3,.flac,.ogg,.m4a,.mp4,.aac";
      audioInputRef.current = input;
    }
    const input = audioInputRef.current;
    input.onchange = async (e: any) => {
      const file = e.target.files?.[0] as File;
      if (!file) return;
      const form = new FormData();
      form.append("audio", file);
      form.append("session_id", sessionId || "split_" + Date.now());
      form.append("whisper_model", whisperModel);
      form.append("silence_threshold", silenceThreshold);
      form.append("speaker_number", String(speakerNumber));
      try {
        const res = await fetch("/training/split-audio", { method: "POST", body: form });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        setSplitJobId(data.job_id);
        setSplitStatus({ id: data.job_id, status: "running", progress: 0, total: 0, done: 0 });
        setSplitPolling(true);
      } catch (err: any) {
        Alert.alert("Error", err.message || "Failed to start split");
      }
    };
    input.click();
  }, [sessionId, whisperModel, silenceThreshold, speakerNumber]);

  useEffect(() => {
    if (!splitPolling || !splitJobId) return;
    const poll = setInterval(async () => {
      try {
        const res = await fetch(`/training/split-progress/${splitJobId}`);
        if (!res.ok) return;
        const data: SplitJobStatus = await res.json();
        setSplitStatus(data);
        if (data.status === "done" || data.status === "error") {
          setSplitPolling(false);
          clearInterval(poll);
        }
      } catch {
        /* silent */
      }
    }, 1000);
    splitPollRef.current = poll;
    return () => clearInterval(poll);
  }, [splitPolling, splitJobId]);

  const handleAddSegmentsToDataset = useCallback(async () => {
    if (!splitStatus?.segments || splitStatus.segments.length === 0) return;
    // Upload all segment WAV + TXT files from the output dir to the training dataset
    // We re-use the /training/upload endpoint by fetching each file via the server
    // Actually, segments are already on the server in output_dir; we can validate them directly
    // by calling /training/validate with the session_id and pointing it to the segments dir.
    // For now, we alert the user to proceed to the Dataset section.
    Alert.alert(
      "Segmentos listos",
      `${splitStatus.done} segmentos generados. Los archivos están en la carpeta de training data. Puedes cargarlos directamente en la sección Dataset.`,
    );
  }, [splitStatus]);

  const validCount = validatedFiles.filter((f) => f.valid).length;
  const invalidCount = validatedFiles.length - validCount;

  return (
    <ScrollView style={shared.screen} contentContainerStyle={{ paddingBottom: 80 }}>
      <View style={shared.container}>
        <Text style={shared.h1}>🧠 Entrenar LoRA</Text>
        <Text style={shared.p}>
          Entrena un adaptador LoRA personalizado con tus propios audios y transcripciones.
        </Text>

        {/* ── Prepare dataset section ────────────────────────────────── */}
        <View style={{ ...shared.section, marginTop: 16 }}>
          <Text style={shared.h2}>🎵 Preparar Dataset</Text>
          <Text style={{ ...shared.labelText, color: colors.textDim, marginBottom: 10, fontSize: 12 }}>
            ¿Tienes un audio largo? Divídelo automáticamente en fragmentos y transcríbelos con Whisper.
          </Text>

          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 12, marginBottom: 10 }}>
            <View style={{ flex: 1, minWidth: 140 }}>
              <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 4 }}>Modelo Whisper</Text>
              <select
                value={whisperModel}
                onChange={(e) => setWhisperModel(e.target.value)}
                style={{ width: "100%", padding: "6px 8px", backgroundColor: colors.surface, color: colors.text, borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }}
              >
                <option value="tiny">tiny (~75 MB, más rápido)</option>
                <option value="base">base (~145 MB, recomendado)</option>
                <option value="small">small (~465 MB, más preciso)</option>
                <option value="medium">medium (~1.5 GB)</option>
              </select>
            </View>

            <View style={{ flex: 1, minWidth: 120 }}>
              <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 4 }}>Umbral silencio (dB)</Text>
              <input
                type="number"
                value={silenceThreshold}
                onChange={(e) => setSilenceThreshold(e.target.value)}
                style={{ width: "100%", padding: "6px 8px", backgroundColor: colors.surface, color: colors.text, borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }}
              />
            </View>

            <View style={{ flex: 1, minWidth: 120 }}>
              <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 4 }}>Número de hablante</Text>
              <input
                type="number"
                min={1}
                max={4}
                value={speakerNumber}
                onChange={(e) => setSpeakerNumber(Number(e.target.value))}
                style={{ width: "100%", padding: "6px 8px", backgroundColor: colors.surface, color: colors.text, borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }}
              />
            </View>
          </View>

          <Pressable
            onPress={handleSplitAudioSelect}
            style={[shared.button, { alignSelf: "flex-start", marginBottom: 12 }]}
          >
            <Text style={shared.buttonText}>📂 Seleccionar audio largo...</Text>
          </Pressable>

          {splitStatus && (
            <View style={{ padding: 10, backgroundColor: colors.surfaceLight, borderRadius: 8, marginBottom: 8 }}>
              {splitStatus.status === "running" && (
                <>
                  <View style={{ flexDirection: "row", alignItems: "center", marginBottom: 6 }}>
                    <ActivityIndicator size="small" color={colors.primary} style={{ marginRight: 8 }} />
                    <Text style={{ color: colors.text, fontWeight: "600" }}>Procesando...</Text>
                  </View>
                  {splitStatus.total > 0 && (
                    <Text style={{ color: colors.textDim, fontSize: 12 }}>
                      Segmento {splitStatus.progress} / {splitStatus.total}
                    </Text>
                  )}
                  <View style={{ height: 4, backgroundColor: colors.border, borderRadius: 2, marginTop: 6 }}>
                    <View style={{
                      height: 4, borderRadius: 2, backgroundColor: colors.primary,
                      width: `${splitStatus.total > 0 ? Math.round(splitStatus.progress / splitStatus.total * 100) : 0}%`
                    }} />
                  </View>
                </>
              )}
              {splitStatus.status === "done" && (
                <>
                  <Text style={{ color: colors.success, fontWeight: "600", marginBottom: 6 }}>
                    ✅ {splitStatus.done} segmentos generados
                  </Text>
                  <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 8 }}>
                    Los archivos están en la carpeta training_data. Cárgalos en la sección Dataset.
                  </Text>
                  <Pressable onPress={handleAddSegmentsToDataset} style={[shared.buttonSecondary, { alignSelf: "flex-start" }]}>
                    <Text style={{ color: colors.primary }}>Ver detalles</Text>
                  </Pressable>
                </>
              )}
              {splitStatus.status === "error" && (
                <Text style={{ color: colors.error, fontWeight: "600" }}>
                  ❌ Error: {splitStatus.error}
                </Text>
              )}
            </View>
          )}
        </View>

        {/* Upload section */}
        <View style={{ ...shared.section, marginTop: 16 }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <Text style={shared.h2}>📁 Dataset</Text>
            {uploadedFiles.length > 0 && (
              <Pressable onPress={handleClearDataset}>
                <Text style={{ color: colors.danger, fontSize: 14 }}>Limpiar</Text>
              </Pressable>
            )}
          </View>
          <Text style={{ ...shared.labelText, marginBottom: 8 }}>
            Sube archivos de audio (.wav, .mp3, .flac) y sus transcripciones (.txt) con el mismo nombre base.
          </Text>
          <Text style={{ ...shared.labelText, color: colors.textDim, marginBottom: 12, fontSize: 12 }}>
            Ejemplo: <Text style={{ color: colors.accent }}>narrador_01.wav</Text> + <Text style={{ color: colors.accent }}>narrador_01.txt</Text>
            {"\n"}
            Cada archivo .txt debe contener: <Text style={{ color: colors.accent }}>Speaker 1: texto aquí</Text>
          </Text>

          <Pressable
            onPress={handleFileSelect}
            disabled={uploading}
            style={{
              backgroundColor: colors.accent,
              paddingVertical: 12,
              paddingHorizontal: 20,
              borderRadius: 8,
              alignItems: "center",
              marginBottom: 12,
              opacity: uploading ? 0.5 : 1,
            }}
          >
            {uploading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={{ color: "#fff", fontWeight: "600" }}>
                {uploadedFiles.length > 0 ? "Añadir más archivos" : "Seleccionar archivos"}
              </Text>
            )}
          </Pressable>

          {uploadedFiles.length > 0 && (
            <Text style={{ fontSize: 12, color: colors.textDim, marginBottom: 8 }}>
              📦 {uploadedFiles.length} archivo(s) subido(s)
            </Text>
          )}

          {validating && (
            <View style={{ paddingVertical: 8 }}>
              <ActivityIndicator color={colors.accent} />
              <Text style={{ color: colors.textDim, textAlign: "center", marginTop: 4 }}>Validando...</Text>
            </View>
          )}

          {validatedFiles.length > 0 && !validating && (
            <View style={{ marginTop: 8 }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 8 }}>
                <Text style={{ color: colors.success, fontWeight: "600" }}>✓ Válidos: {validCount}</Text>
                {invalidCount > 0 && (
                  <Text style={{ color: colors.danger, fontWeight: "600" }}>✗ Inválidos: {invalidCount}</Text>
                )}
              </View>
              <ScrollView style={{ maxHeight: 200, backgroundColor: colors.surface, padding: 8, borderRadius: 4 }}>
                {validatedFiles.map((file, idx) => (
                  <View
                    key={idx}
                    style={{
                      paddingVertical: 4,
                      borderBottomWidth: idx < validatedFiles.length - 1 ? 1 : 0,
                      borderBottomColor: colors.border,
                    }}
                  >
                    <View style={{ flexDirection: "row", alignItems: "center" }}>
                      <Text style={{ fontSize: 16, marginRight: 8 }}>
                        {file.valid ? "✅" : "❌"}
                      </Text>
                      <Text style={{ color: file.valid ? colors.text : colors.danger, flex: 1, fontSize: 12 }}>
                        {file.base_name}
                      </Text>
                    </View>
                    {!file.valid && file.error_msg && (
                      <Text style={{ color: colors.danger, fontSize: 11, marginLeft: 24, marginTop: 2 }}>
                        {file.error_msg}
                      </Text>
                    )}
                  </View>
                ))}
              </ScrollView>
            </View>
          )}
        </View>

        {/* Training config */}
        {validCount > 0 && (
          <View style={{ ...shared.section, marginTop: 16 }}>
            <Text style={shared.h2}>⚙️ Configuración</Text>

            <View style={{ marginTop: 12 }}>
              <Text style={shared.labelText}>Nombre del LoRA</Text>
              <input
                type="text"
                value={loraName}
                onChange={(e) => setLoraName(e.target.value)}
                placeholder="mi_narrador"
                style={{
                  backgroundColor: colors.surface,
                  color: colors.text,
                  border: `1px solid ${colors.border}`,
                  borderRadius: 4,
                  padding: 8,
                  fontSize: 14,
                  marginTop: 4,
                  fontFamily: "inherit",
                }}
              />
            </View>

            <View style={{ marginTop: 12 }}>
              <Text style={shared.labelText}>Modelo base</Text>
              <select
                value={modelBase}
                onChange={(e) => setModelBase(e.target.value)}
                style={{
                  backgroundColor: colors.surface,
                  color: colors.text,
                  border: `1px solid ${colors.border}`,
                  borderRadius: 4,
                  padding: 8,
                  fontSize: 14,
                  marginTop: 4,
                  fontFamily: "inherit",
                }}
              >
                <option value="microsoft/VibeVoice-1.5B">VibeVoice 1.5B (recomendado)</option>
                <option value="aoi-ot/VibeVoice-Large">VibeVoice Large</option>
                <option value="FabioSarracino/VibeVoice-Large-Q8">VibeVoice Large Q8</option>
                <option value="DevParker/VibeVoice7b-low-vram">VibeVoice Large Q4</option>
              </select>
            </View>

            <View style={{ marginTop: 12 }}>
              <Text style={shared.labelText}>Epochs (épocas)</Text>
              <input
                type="number"
                value={epochs}
                onChange={(e) => setEpochs(parseInt(e.target.value) || 1)}
                min={1}
                max={5}
                style={{
                  backgroundColor: colors.surface,
                  color: colors.text,
                  border: `1px solid ${colors.border}`,
                  borderRadius: 4,
                  padding: 8,
                  fontSize: 14,
                  marginTop: 4,
                  fontFamily: "inherit",
                }}
              />
            </View>

            <View style={{ marginTop: 12 }}>
              <Text style={shared.labelText}>Batch size (tamaño de lote)</Text>
              <input
                type="number"
                value={batchSize}
                onChange={(e) => setBatchSize(parseInt(e.target.value) || 4)}
                min={1}
                max={16}
                style={{
                  backgroundColor: colors.surface,
                  color: colors.text,
                  border: `1px solid ${colors.border}`,
                  borderRadius: 4,
                  padding: 8,
                  fontSize: 14,
                  marginTop: 4,
                  fontFamily: "inherit",
                }}
              />
              <Text style={{ fontSize: 11, color: colors.textDim, marginTop: 4 }}>
                Menor = menos VRAM, más lento. Mayor = más VRAM, más rápido.
              </Text>
            </View>

            <View style={{ marginTop: 12 }}>
              <Text style={shared.labelText}>Voice prompt drop rate</Text>
              <input
                type="number"
                value={voicePromptDropRate}
                onChange={(e) => setVoicePromptDropRate(parseFloat(e.target.value) || 1.0)}
                min={0}
                max={1}
                step={0.1}
                style={{
                  backgroundColor: colors.surface,
                  color: colors.text,
                  border: `1px solid ${colors.border}`,
                  borderRadius: 4,
                  padding: 8,
                  fontSize: 14,
                  marginTop: 4,
                  fontFamily: "inherit",
                }}
              />
              <Text style={{ fontSize: 11, color: colors.textDim, marginTop: 4 }}>
                1.0 = solo genera esa voz (sin clonación). 0.0 = mantiene capacidad de clonación.
              </Text>
            </View>

            <Pressable
              onPress={handleStartTraining}
              disabled={!loraName.trim() || (currentJob && currentJob.status === "running")}
              style={{
                backgroundColor: loraName.trim() && !(currentJob && currentJob.status === "running")
                  ? colors.success
                  : colors.border,
                paddingVertical: 14,
                paddingHorizontal: 20,
                borderRadius: 8,
                alignItems: "center",
                marginTop: 16,
              }}
            >
              <Text style={{ color: "#fff", fontWeight: "700", fontSize: 16 }}>
                🚀 Iniciar entrenamiento
              </Text>
            </Pressable>
          </View>
        )}

        {/* Training progress */}
        {currentJob && (
          <View style={{ ...shared.section, marginTop: 16 }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Text style={shared.h2}>📊 Progreso</Text>
              {currentJob.status === "running" && (
                <Pressable onPress={handleCancelJob}>
                  <Text style={{ color: colors.danger, fontWeight: "600" }}>Cancelar</Text>
                </Pressable>
              )}
            </View>

            <View style={{ marginTop: 12, padding: 12, backgroundColor: colors.surface, borderRadius: 8 }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 8 }}>
                <Text style={{ color: colors.text, fontWeight: "600" }}>
                  {currentJob.lora_name}
                </Text>
                <Text
                  style={{
                    color:
                      currentJob.status === "completed"
                        ? colors.success
                        : currentJob.status === "running"
                        ? colors.accent
                        : currentJob.status === "failed"
                        ? colors.danger
                        : colors.textDim,
                    fontWeight: "600",
                  }}
                >
                  {currentJob.status === "preparing" && "Preparando..."}
                  {currentJob.status === "running" && "Entrenando..."}
                  {currentJob.status === "completed" && "✓ Completado"}
                  {currentJob.status === "failed" && "✗ Error"}
                  {currentJob.status === "cancelled" && "Cancelado"}
                </Text>
              </View>

              {currentJob.status === "running" && (
                <>
                  <View
                    style={{
                      height: 8,
                      backgroundColor: colors.border,
                      borderRadius: 4,
                      overflow: "hidden",
                      marginBottom: 8,
                    }}
                  >
                    <View
                      style={{
                        height: "100%",
                        width: `${(currentJob.progress || 0) * 100}%`,
                        backgroundColor: colors.accent,
                      }}
                    />
                  </View>
                  <ActivityIndicator color={colors.accent} size="small" />
                </>
              )}

              {currentJob.error && (
                <Text style={{ color: colors.danger, fontSize: 12, marginTop: 8 }}>
                  {currentJob.error}
                </Text>
              )}
            </View>
          </View>
        )}

        {/* LoRAs list */}
        <View style={{ ...shared.section, marginTop: 16 }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <Text style={shared.h2}>📚 LoRAs entrenados</Text>
            <Pressable onPress={fetchLoRAs}>
              <Text style={{ color: colors.accent, fontSize: 14 }}>🔄 Actualizar</Text>
            </Pressable>
          </View>

          {loras.length === 0 ? (
            <Text style={{ color: colors.textDim, marginTop: 12, fontSize: 14 }}>
              No hay LoRAs entrenados aún.
            </Text>
          ) : (
            <View style={{ marginTop: 12, gap: 8 }}>
              {loras.map((lora, idx) => (
                <View
                  key={idx}
                  style={{
                    padding: 12,
                    backgroundColor: colors.surface,
                    borderRadius: 8,
                    borderWidth: 1,
                    borderColor: colors.border,
                  }}
                >
                  <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                    <View style={{ flex: 1 }}>
                      <Text style={{ color: colors.text, fontWeight: "600", marginBottom: 4 }}>
                        {lora.name}
                      </Text>
                      <Text style={{ color: colors.textDim, fontSize: 12 }}>
                        {lora.size_mb.toFixed(1)} MB
                      </Text>
                    </View>
                    <Pressable onPress={() => handleDeleteLoRA(lora.name)}>
                      <Text style={{ color: colors.danger, fontSize: 24 }}>🗑️</Text>
                    </Pressable>
                  </View>
                </View>
              ))}
            </View>
          )}
        </View>
      </View>
    </ScrollView>
  );
}
