import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  ScrollView,
  Pressable,
  ActivityIndicator,
} from "react-native";
import { shared, colors } from "../src/theme";
import { useRaceStore } from "../src/stores/useRaceStore";
import { useConfigStore } from "../src/stores/useConfigStore";
import { generateAudio, confirmSave, getAudioUrl } from "../src/api";

const EVENT_TYPE_LABELS: Record<number, string> = {
  1: "Adelantamiento",
  2: "Choque entre pilotos",
  3: "Choque contra muro",
  4: "Penalización",
  5: "Entrada a boxes",
};

function formatTimestamp(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function sanitizeFilename(s: string): string {
  return s.replace(/[^\w\s\-]/g, "").replace(/\s+/g, "_").slice(0, 60);
}

function formatElapsed(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (h > 0) {
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function RaceScreen() {
  const store = useRaceStore();
  const config = useConfigStore((s) => s.config);
  const patchConfig = useConfigStore((s) => s.patch);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [sessionName, setSessionName] = useState("");
  const [generatingAll, setGeneratingAll] = useState(false);
  const [genProgress, setGenProgress] = useState({ done: 0, total: 0 });
  const [batchStartedAt, setBatchStartedAt] = useState<number | null>(null);
  const [batchElapsedSec, setBatchElapsedSec] = useState(0);
  const [currentBatchItem, setCurrentBatchItem] = useState("");
  const [eventAudioDurations, setEventAudioDurations] = useState<Record<number, number>>({});
  const [showHiddenEvents, setShowHiddenEvents] = useState(false);
  const [generatingIntroAudio, setGeneratingIntroAudio] = useState(false);
  const [generatingEventText, setGeneratingEventText] = useState<Record<number, boolean>>({});
  const [generatingEventAudio, setGeneratingEventAudio] = useState<Record<number, boolean>>({});

  useEffect(() => {
    store.fetchSessions();
    if (config.last_race_session) {
      store.loadSession(config.last_race_session);
      setSessionName(config.last_race_session);
    }
  }, []);

  const handleFileSelect = useCallback(async (e: any) => {
    const file = e.target?.files?.[0];
    if (!file) return;
    await store.parseXml(file);
  }, []);

  const generateAudioForText = useCallback(
    async (text: string, filename: string): Promise<string | null> => {
      try {
        const { data } = await generateAudio({
          text,
          voice_name: config.selected_voice,
          model: config.selected_model,
          output_format: config.output_format,
          cfg_scale: config.cfg_scale,
          ddpm_steps: config.ddpm_steps,
          disable_prefill: config.disable_prefill,
          custom_output_name: filename,
          output_directory: config.output_directory || undefined,
        });
        if (data.success && data.audio_id) {
          await confirmSave(data.audio_id, config.output_directory || undefined);
          return data.audio_id;
        }
      } catch {}
      return null;
    },
    [config],
  );

  const generateAllAudios = useCallback(async () => {
    setGeneratingAll(true);
    setBatchStartedAt(Date.now());
    setCurrentBatchItem("Intro de carrera");
    const total = (store.introText ? 1 : 0) + store.events.length;
    let done = 0;
    setGenProgress({ done: 0, total });

    // Intro
    if (store.introText) {
      const stepStart = Date.now();
      const id = await generateAudioForText(store.introText, "intro_carrera");
      if (id) store.setIntroAudio(id);
      setEventAudioDurations((s) => ({ ...s, [-1]: Math.floor((Date.now() - stepStart) / 1000) }));
      done++;
      setGenProgress({ done, total });
    }

    // Events
    for (let i = 0; i < store.events.length; i++) {
      const ev = store.events[i];
      setCurrentBatchItem(`Evento V${ev.lap} · ${ev.summary.slice(0, 36)}`);
      const desc = ev.description || ev.summary;
      if (!desc) continue;
      const fname = sanitizeFilename(
        `${ev.lap}_${formatTimestamp(ev.timestamp).replace(/:/g, "-")}_${ev.summary.slice(0, 40)}`,
      );
      const stepStart = Date.now();
      const id = await generateAudioForText(desc, fname);
      if (id) store.setEventAudio(i, id);
      setEventAudioDurations((s) => ({ ...s, [i]: Math.floor((Date.now() - stepStart) / 1000) }));
      done++;
      setGenProgress({ done, total });
    }
    setGeneratingAll(false);
    setCurrentBatchItem("");
    setBatchStartedAt(null);
  }, [store, generateAudioForText]);

  useEffect(() => {
    if (!generatingAll || !batchStartedAt) {
      return;
    }
    const timer = setInterval(() => {
      setBatchElapsedSec(Math.max(0, Math.floor((Date.now() - batchStartedAt) / 1000)));
    }, 1000);
    return () => clearInterval(timer);
  }, [generatingAll, batchStartedAt]);

  const handleSave = useCallback(async () => {
    const name = sessionName.trim() || store.header?.track_event || "sesion";
    await store.saveSession(name);
    patchConfig({ last_race_session: name });
  }, [sessionName, store, patchConfig]);

  const handleGenerateIntroAudio = useCallback(async () => {
    if (!store.introText?.trim()) return;
    setGeneratingIntroAudio(true);
    try {
      const id = await generateAudioForText(store.introText, "intro_carrera");
      if (id) store.setIntroAudio(id);
    } finally {
      setGeneratingIntroAudio(false);
    }
  }, [store, generateAudioForText]);

  const handleGenerateEventText = useCallback(
    async (index: number) => {
      setGeneratingEventText((s) => ({ ...s, [index]: true }));
      try {
        await store.generateDescriptionForEvent(index);
      } finally {
        setGeneratingEventText((s) => ({ ...s, [index]: false }));
      }
    },
    [store],
  );

  const handleGenerateEventAudio = useCallback(
    async (index: number) => {
      const ev = store.events[index];
      if (!ev) return;
      const text = (ev.description || ev.summary || "").trim();
      if (!text) return;

      setGeneratingEventAudio((s) => ({ ...s, [index]: true }));
      try {
        const fname = sanitizeFilename(
          `${ev.lap}_${formatTimestamp(ev.timestamp).replace(/:/g, "-")}_${ev.summary.slice(0, 40)}`,
        );
        const id = await generateAudioForText(text, fname);
        if (id) store.setEventAudio(index, id);
      } finally {
        setGeneratingEventAudio((s) => ({ ...s, [index]: false }));
      }
    },
    [store, generateAudioForText],
  );

  return (
    <ScrollView style={shared.screen}>
      <Text style={shared.title}>📝 Narración de Carrera</Text>

      {/* Session selector */}
      <View style={shared.card}>
        <Text style={shared.label}>Sesión</Text>
        <View style={shared.row}>
          <Pressable
            style={[shared.buttonSecondary, { flex: 1 }]}
            onPress={() => store.newSession()}
          >
            <Text style={[shared.buttonText, { color: colors.text }]}>Nueva</Text>
          </Pressable>
          {store.sessions.map((s) => (
            <Pressable
              key={s.name}
              style={[
                shared.buttonSecondary,
                { flex: 1 },
                store.currentSession === s.name && { borderColor: colors.primary },
              ]}
              onPress={() => {
                store.loadSession(s.name);
                setSessionName(s.name);
              }}
            >
              <Text
                style={[shared.buttonText, { color: colors.text }]}
                numberOfLines={1}
              >
                {s.name}
              </Text>
            </Pressable>
          ))}
        </View>
      </View>

      {/* XML upload */}
      <View style={shared.card}>
        <Text style={shared.label}>Archivo XML (rFactor2)</Text>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xml"
          onChange={handleFileSelect}
          style={{ color: colors.text, marginBottom: 8 }}
        />
      </View>

      {store.loading && (
        <ActivityIndicator size="large" color={colors.primary} style={{ marginVertical: 16 }} />
      )}
      {store.error && (
        <Text style={{ color: colors.error, marginBottom: 12 }}>{store.error}</Text>
      )}

      {/* Header info */}
      {store.header && (
        <View style={shared.card}>
          <Text style={[shared.title, { fontSize: 16 }]}>
            {store.header.track_event}
          </Text>
          <Text style={{ color: colors.textDim }}>
            {store.header.race_laps} vueltas · {store.header.num_drivers} pilotos ·{" "}
            {store.header.track_length.toFixed(0)}m
          </Text>
          <Text style={{ color: colors.textDim, marginTop: 4 }}>
            Parrilla: {store.header.grid_order.join(", ")}
          </Text>
        </View>
      )}

      {/* Intro */}
      {store.header && (
        <View style={shared.card}>
          <Text style={shared.label}>Texto de Introducción</Text>
          <TextInput
            style={shared.textArea}
            value={store.introText}
            onChangeText={store.setIntroText}
            multiline
            placeholder="Genera o escribe el texto de introducción..."
            placeholderTextColor={colors.textDim}
          />
          <View style={shared.row}>
            <Pressable style={[shared.button, { flex: 1 }]} onPress={store.generateIntro}>
              <Text style={shared.buttonText}>Generar intro con IA</Text>
            </Pressable>
            <Pressable
              style={[shared.buttonSecondary, { flex: 1 }]}
              onPress={handleGenerateIntroAudio}
              disabled={generatingIntroAudio || !store.introText?.trim()}
            >
              <Text style={[shared.buttonText, { color: colors.text }]}>
                {generatingIntroAudio ? "Generando audio..." : "Generar audio intro"}
              </Text>
            </Pressable>
            {store.introAudio ? (
              <View style={{ flex: 1 }}>
                <audio controls src={getAudioUrl(store.introAudio)} style={{ width: "100%" }} />
              </View>
            ) : null}
          </View>
        </View>
      )}

      {/* Event descriptions */}
      {store.events.length > 0 && (
        <View style={shared.card}>
          <View style={[shared.row, { justifyContent: "space-between", marginBottom: 8 }]}>
            <Text style={shared.label}>
              Eventos visibles ({store.events.filter((_, idx) => !store.hiddenEventIndices.has(idx)).length}/{store.events.length})
            </Text>
            <Pressable style={shared.button} onPress={store.generateDescriptions}>
              <Text style={shared.buttonText}>Generar descripciones IA</Text>
            </Pressable>
          </View>
          <View style={[shared.row, { flexWrap: "wrap", marginBottom: 10 }]}> 
            <Pressable style={shared.buttonSecondary} onPress={store.selectAllEvents}>
              <Text style={[shared.buttonText, { color: colors.text }]}>Seleccionar visibles</Text>
            </Pressable>
            <Pressable style={shared.buttonSecondary} onPress={store.clearEventSelection}>
              <Text style={[shared.buttonText, { color: colors.text }]}>Limpiar seleccion</Text>
            </Pressable>
            <Pressable
              style={[shared.buttonSecondary, { borderColor: colors.error }]}
              onPress={async () => {
                if (!store.selectedEventIndices.size) return;
                if (!window.confirm(`Eliminar ${store.selectedEventIndices.size} eventos seleccionados?`)) return;
                await store.deleteSelectedEvents();
              }}
              disabled={!store.selectedEventIndices.size}
            >
              <Text style={[shared.buttonText, { color: colors.error }]}>Borrar seleccionados ({store.selectedEventIndices.size})</Text>
            </Pressable>
            <Pressable style={shared.buttonSecondary} onPress={() => setShowHiddenEvents((v) => !v)}>
              <Text style={[shared.buttonText, { color: colors.text }]}>
                {showHiddenEvents ? "Ocultar filas ocultas" : `Mostrar ocultos (${store.hiddenEventIndices.size})`}
              </Text>
            </Pressable>
          </View>
          {store.events.map((ev, i) => (
            (!store.hiddenEventIndices.has(i) || showHiddenEvents) ? (
            <View
              key={i}
              style={{
                borderBottomWidth: 1,
                borderBottomColor: colors.border,
                paddingVertical: 8,
                opacity: store.hiddenEventIndices.has(i) ? 0.55 : 1,
              }}
            >
              <View style={shared.row}>
                <Pressable
                  onPress={() => store.toggleEventSelected(i)}
                  style={{ marginRight: 6 }}
                >
                  <Text style={{ color: colors.text }}>
                    {store.selectedEventIndices.has(i) ? "☑" : "☐"}
                  </Text>
                </Pressable>
                <Text style={{ color: colors.primary, fontWeight: "600", width: 50 }}>
                  V{ev.lap}
                </Text>
                <Text style={{ color: colors.textDim, width: 70 }}>
                  {formatTimestamp(ev.timestamp)}
                </Text>
                <Text style={{ color: colors.accent, flex: 1 }}>
                  {EVENT_TYPE_LABELS[ev.event_type] || `Tipo ${ev.event_type}`}
                </Text>
                {store.hiddenEventIndices.has(i) && (
                  <Text style={{ color: colors.textDim, fontSize: 12 }}>[Oculto]</Text>
                )}
              </View>
              <Text style={{ color: colors.text, marginVertical: 4 }}>{ev.summary}</Text>
              <TextInput
                style={[shared.input, { fontSize: 13 }]}
                value={ev.description}
                onChangeText={(v) => store.updateEventDescription(i, v)}
                placeholder="Descripción IA..."
                placeholderTextColor={colors.textDim}
              />

              <View style={[shared.row, { flexWrap: "wrap", marginBottom: 8 }]}>
                <Pressable
                  style={shared.buttonSecondary}
                  onPress={() => handleGenerateEventText(i)}
                  disabled={!!generatingEventText[i]}
                >
                  <Text style={[shared.buttonText, { color: colors.text }]}>
                    {generatingEventText[i] ? "Generando texto..." : "Generar texto"}
                  </Text>
                </Pressable>
                <Pressable
                  style={shared.buttonSecondary}
                  onPress={() => handleGenerateEventAudio(i)}
                  disabled={!!generatingEventAudio[i] || !(ev.description || ev.summary)}
                >
                  <Text style={[shared.buttonText, { color: colors.text }]}>
                    {generatingEventAudio[i] ? "Generando audio..." : "Generar audio"}
                  </Text>
                </Pressable>
                <Pressable
                  style={shared.buttonSecondary}
                  onPress={() => store.insertEventAfter(i)}
                >
                  <Text style={[shared.buttonText, { color: colors.text }]}>Insertar evento debajo</Text>
                </Pressable>
                <Pressable
                  style={shared.buttonSecondary}
                  onPress={async () => {
                    await store.toggleEventHidden(i);
                  }}
                >
                  <Text style={[shared.buttonText, { color: colors.text }]}> 
                    {store.hiddenEventIndices.has(i) ? "Mostrar" : "Ocultar"}
                  </Text>
                </Pressable>
                <Pressable
                  style={[shared.buttonSecondary, { borderColor: colors.error }]}
                  onPress={async () => {
                    if (!window.confirm("Eliminar este evento?")) return;
                    await store.deleteEvent(i);
                  }}
                >
                  <Text style={[shared.buttonText, { color: colors.error }]}>Borrar</Text>
                </Pressable>
              </View>

              {eventAudioDurations[i] !== undefined && (
                <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 6 }}>
                  Ultimo audio generado en {formatElapsed(eventAudioDurations[i])}
                </Text>
              )}

              {store.eventAudios[String(i)] && (
                <audio
                  controls
                  src={getAudioUrl(store.eventAudios[String(i)])}
                  style={{ width: "100%" }}
                />
              )}
            </View>
            ) : null
          ))}
        </View>
      )}

      {/* Actions */}
      {store.header && (
        <View style={shared.card}>
          {generatingAll ? (
            <View>
              <Text style={{ color: colors.text, marginBottom: 8 }}>
                Generando audios... {genProgress.done}/{genProgress.total} · {formatElapsed(batchElapsedSec)}
              </Text>
              {currentBatchItem ? (
                <Text style={{ color: colors.textDim, marginBottom: 8 }}>
                  En curso: {currentBatchItem}
                </Text>
              ) : null}
              <View
                style={{
                  height: 8,
                  backgroundColor: colors.surfaceLight,
                  borderRadius: 4,
                }}
              >
                <View
                  style={{
                    width: `${genProgress.total > 0 ? (genProgress.done / genProgress.total) * 100 : 0}%`,
                    height: 8,
                    backgroundColor: colors.primary,
                    borderRadius: 4,
                  }}
                />
              </View>
            </View>
          ) : (
            <Pressable style={shared.button} onPress={generateAllAudios}>
              <Text style={shared.buttonText}>Generar todos los audios</Text>
            </Pressable>
          )}

          <View style={shared.divider} />

          <View style={shared.row}>
            <TextInput
              style={[shared.input, { flex: 1 }]}
              value={sessionName}
              onChangeText={setSessionName}
              placeholder="Nombre de sesión..."
              placeholderTextColor={colors.textDim}
            />
            <Pressable style={[shared.button, { backgroundColor: colors.success }]} onPress={handleSave}>
              <Text style={shared.buttonText}>Guardar sesión</Text>
            </Pressable>
          </View>
        </View>
      )}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}
