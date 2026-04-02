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

export default function RaceScreen() {
  const store = useRaceStore();
  const config = useConfigStore((s) => s.config);
  const patchConfig = useConfigStore((s) => s.patch);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [sessionName, setSessionName] = useState("");
  const [generatingAll, setGeneratingAll] = useState(false);
  const [genProgress, setGenProgress] = useState({ done: 0, total: 0 });

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
    const total = (store.introText ? 1 : 0) + store.events.length;
    let done = 0;
    setGenProgress({ done: 0, total });

    // Intro
    if (store.introText) {
      const id = await generateAudioForText(store.introText, "intro_carrera");
      if (id) store.setIntroAudio(id);
      done++;
      setGenProgress({ done, total });
    }

    // Events
    for (let i = 0; i < store.events.length; i++) {
      const ev = store.events[i];
      const desc = ev.description || ev.summary;
      if (!desc) continue;
      const fname = sanitizeFilename(
        `${ev.lap}_${formatTimestamp(ev.timestamp).replace(/:/g, "-")}_${ev.summary.slice(0, 40)}`,
      );
      const id = await generateAudioForText(desc, fname);
      if (id) store.setEventAudio(i, id);
      done++;
      setGenProgress({ done, total });
    }
    setGeneratingAll(false);
  }, [store, generateAudioForText]);

  const handleSave = useCallback(async () => {
    const name = sessionName.trim() || store.header?.track_event || "sesion";
    await store.saveSession(name);
    patchConfig({ last_race_session: name });
  }, [sessionName, store, patchConfig]);

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
            <Text style={shared.label}>Eventos ({store.events.length})</Text>
            <Pressable style={shared.button} onPress={store.generateDescriptions}>
              <Text style={shared.buttonText}>Generar descripciones IA</Text>
            </Pressable>
          </View>
          {store.events.map((ev, i) => (
            <View
              key={i}
              style={{
                borderBottomWidth: 1,
                borderBottomColor: colors.border,
                paddingVertical: 8,
              }}
            >
              <View style={shared.row}>
                <Text style={{ color: colors.primary, fontWeight: "600", width: 50 }}>
                  V{ev.lap}
                </Text>
                <Text style={{ color: colors.textDim, width: 70 }}>
                  {formatTimestamp(ev.timestamp)}
                </Text>
                <Text style={{ color: colors.accent, flex: 1 }}>
                  {EVENT_TYPE_LABELS[ev.event_type] || `Tipo ${ev.event_type}`}
                </Text>
              </View>
              <Text style={{ color: colors.text, marginVertical: 4 }}>{ev.summary}</Text>
              <TextInput
                style={[shared.input, { fontSize: 13 }]}
                value={ev.description}
                onChangeText={(v) => store.updateEventDescription(i, v)}
                placeholder="Descripción IA..."
                placeholderTextColor={colors.textDim}
              />
              {store.eventAudios[String(i)] && (
                <audio
                  controls
                  src={getAudioUrl(store.eventAudios[String(i)])}
                  style={{ width: "100%" }}
                />
              )}
            </View>
          ))}
        </View>
      )}

      {/* Actions */}
      {store.header && (
        <View style={shared.card}>
          {generatingAll ? (
            <View>
              <Text style={{ color: colors.text, marginBottom: 8 }}>
                Generando audios... {genProgress.done}/{genProgress.total}
              </Text>
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
