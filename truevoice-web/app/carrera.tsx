import React, { useEffect, useState, useRef, useCallback, Component, ReactNode } from "react";
import { View, Text, TextInput, ScrollView, Pressable, ActivityIndicator } from "react-native";
import { shared, colors } from "../src/theme";
import { useRaceStore } from "../src/stores/useRaceStore";
import { useConfigStore } from "../src/stores/useConfigStore";
import {
  getProgress,
  generateAudio,
  confirmSave,
  getAudioUrl,
  listOutputs,
  deleteOutputs,
  raceExportCSV,
  getContextState,
} from "../src/api";

const EVENT_TYPE_LABELS: Record<number, string> = {
  0: "Evento Manual",
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

function sanitizeFilename(text: string): string {
  return text
    .replace(/[^\w\s\-]/g, "")
    .replace(/\s+/g, "_")
    .slice(0, 60);
}

function formatElapsed(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return h > 0
    ? `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
    : `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/* ── CSV export name dedup helpers ─────────────────────────────────── */
const EXPORT_NAMES_KEY = "truevoice-race-export-names-v1";

function parseNameIndex(name: string): { base: string; index: number | null } {
  const trimmed = name.trim();
  const match = trimmed.match(/^(.*?)(?:\s*\((\d+)\))?$/);
  if (!match) return { base: trimmed, index: null };
  const base = (match[1] || trimmed).trim();
  const idx = match[2] ? Number(match[2]) : null;
  return { base, index: Number.isFinite(idx) ? idx : null };
}

function loadExportNames(): string[] {
  if (typeof window === "undefined" || !window.localStorage) return [];
  try {
    const raw = window.localStorage.getItem(EXPORT_NAMES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((s: any) => typeof s === "string") : [];
  } catch {
    return [];
  }
}

function saveExportName(name: string) {
  if (typeof window === "undefined" || !window.localStorage) return;
  const list = loadExportNames();
  list.push(name);
  try {
    window.localStorage.setItem(EXPORT_NAMES_KEY, JSON.stringify(list.slice(-500)));
  } catch {}
}

function deduplicateName(desired: string, existing: string[]): string {
  const d = desired.trim();
  if (!d) return "sesion";
  const usedSet = new Set(existing.map((n) => n.toLowerCase()));
  if (!usedSet.has(d.toLowerCase())) return d;
  const parsed = parseNameIndex(d);
  const baseLower = parsed.base.toLowerCase();
  let maxIdx = -1;
  for (const e of existing) {
    const ep = parseNameIndex(e);
    if (ep.base.toLowerCase() === baseLower) {
      maxIdx = ep.index === null ? Math.max(maxIdx, 0) : Math.max(maxIdx, ep.index);
    }
  }
  return `${parsed.base} (${Math.max(1, maxIdx + 1)})`;
}

/* ── CSV parser ────────────────────────────────────────────────────── */
function parseCSV(text: string): string[][] {
  const rows: string[][] = [];
  let fields: string[] = [];
  let field = "";
  let inQuote = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"') {
      if (inQuote && text[i + 1] === '"') {
        field += '"';
        i++;
      } else {
        inQuote = !inQuote;
      }
    } else if (!inQuote && ch === ",") {
      fields.push(field);
      field = "";
    } else if (!inQuote && (ch === "\n" || ch === "\r")) {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      fields.push(field);
      if (fields.some((f) => f.trim() !== "")) rows.push(fields);
      fields = [];
      field = "";
    } else {
      field += ch;
    }
  }
  if (field.length > 0 || fields.length > 0) {
    fields.push(field);
    if (fields.some((f) => f.trim() !== "")) rows.push(fields);
  }
  return rows;
}

/* ── Error boundary ────────────────────────────────────────────────── */
class RaceErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };
  static getDerivedStateFromError(e: Error) {
    return { error: e };
  }
  render() {
    if (this.state.error) {
      return (
        <View style={{ flex: 1, backgroundColor: "#0f0f23", padding: 16 }}>
          <Text style={{ color: "#ef5350", fontSize: 16, fontWeight: "700", marginBottom: 8 }}>
            Error en la pantalla de Carrera
          </Text>
          <Text style={{ color: "#e0e0e0", fontSize: 13, marginBottom: 12 }}>
            {this.state.error.message}
          </Text>
          <Text style={{ color: "#aaa", fontSize: 11, fontFamily: "monospace" }}>
            {this.state.error.stack}
          </Text>
        </View>
      );
    }
    return this.props.children;
  }
}

/* ── Main CarreraScreen inner ──────────────────────────────────────── */
function CarreraContent() {
  const store = useRaceStore();
  const config = useConfigStore((s) => s.config);
  const YELLOW = "#ffd54f";

  const xmlInputRef = useRef<any>(null);
  const csvInputRef = useRef<any>(null);

  const [batchElapsed, setBatchElapsed] = useState(0);
  const [itemElapsed, setItemElapsed] = useState(0);
  const [eventGenTimes, setEventGenTimes] = useState<Record<number, number>>({});
  const [showHidden, setShowHidden] = useState(false);
  const [generatingIntroAudio, setGeneratingIntroAudio] = useState(false);
  const [generatingTextForEvent, setGeneratingTextForEvent] = useState<Record<number, boolean>>({});
  const [generatingAudioForEvent, setGeneratingAudioForEvent] = useState<Record<number, boolean>>({});
  const [generatingSelectedTexts, setGeneratingSelectedTexts] = useState(false);
  const [missingAudios, setMissingAudios] = useState<Set<string>>(new Set());
  const introTextareaRef = useRef<any>(null);
  const [contextInUseName, setContextInUseName] = useState("-");
  const [contextStateLoading, setContextStateLoading] = useState(false);
  const [contextStateError, setContextStateError] = useState("");

  // Edit event modal state
  const [editEventIndex, setEditEventIndex] = useState<number | null>(null);
  const [editTimestamp, setEditTimestamp] = useState("");
  const [editSummary, setEditSummary] = useState("");

  const refreshContextInUse = useCallback(async () => {
    setContextStateLoading(true);
    setContextStateError("");
    try {
      const { data } = await getContextState();
      setContextInUseName(data.in_use_name?.trim() || "(sin contexto cargado)");
    } catch {
      setContextStateError("No se pudo leer el contexto en uso");
      setContextInUseName("-");
    } finally {
      setContextStateLoading(false);
    }
  }, []);

  // Auto-resize intro textarea
  const autoResizeIntro = useCallback(() => {
    const el = introTextareaRef.current?._node ?? introTextareaRef.current;
    if (el && el.style) {
      el.style.height = "auto";
      el.style.height = `${Math.max(80, el.scrollHeight)}px`;
    }
  }, []);

  useEffect(() => {
    requestAnimationFrame(autoResizeIntro);
  }, [store.introText, autoResizeIntro]);

  const handleIntroTextChange = useCallback(
    (text: string) => {
      store.setIntroText(text);
      requestAnimationFrame(autoResizeIntro);
    },
    [store, autoResizeIntro],
  );

  // Initial load
  useEffect(() => {
    store.fetchSessions();
    if (!store.header && store.events.length === 0 && config.last_race_session) {
      store.loadSession(config.last_race_session);
    }
    refreshContextInUse();
  }, []);

  // Track missing audios
  // DISABLED: This was causing React error #185 (infinite updateDepth)
  // useEffect(() => {
  //   const allAudios = [
  //     ...(store.introAudio ? [store.introAudio] : []),
  //     ...Object.values(store.eventAudios),
  //   ].filter(Boolean);
  //   setMissingAudios((prev) => {
  //     const next = new Set(prev);
  //     for (const a of allAudios) next.delete(a);
  //     return next;
  //   });
  // }, [store.introAudio, store.eventAudios]);

  // XML file handler
  const handleXmlFile = useCallback(
    async (e: any) => {
      const file = e.target?.files?.[0];
      if (file) await store.parseXml(file);
    },
    [],
  );

  // Wait for generation progress to complete
  const waitForProgress = useCallback(async (audioId: string): Promise<boolean> => {
    const maxAttempts = Math.ceil(100);
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((r) => setTimeout(r, 3000));
      try {
        const { data } = await getProgress(audioId);
        if (data.status === "done") return true;
        if (data.status === "error" || data.status === "cancelled") return false;
      } catch {}
    }
    return false;
  }, []);

  // Generate a single audio
  const generateSingleAudio = useCallback(
    async (text: string, outputName: string, label: string): Promise<string | null> => {
      if (!config.output_directory?.trim()) {
        window.alert("Debes seleccionar primero una carpeta de salida en la pestaña Config.");
        return null;
      }
      store.setCurrentAudioGeneration(label, Date.now());
      try {
        const { data } = await generateAudio({
          text,
          voice_name: config.selected_voice,
          model: config.selected_model,
          output_format: config.output_format,
          cfg_scale: config.cfg_scale,
          ddpm_steps: config.ddpm_steps,
          disable_prefill: config.disable_prefill,
          custom_output_name: outputName,
          output_directory: config.output_directory || undefined,
        });
        if (data.success && data.audio_id) {
          if (!(await waitForProgress(data.audio_id))) return null;
          const saveResp = await confirmSave(data.audio_id, config.output_directory || undefined);
          await new Promise((r) => setTimeout(r, 500));
          return saveResp.data.audio_id || data.audio_id;
        }
      } catch {
      } finally {
        store.setCurrentAudioGeneration("", null);
      }
      return null;
    },
    [config, waitForProgress, store],
  );

  // Batch generate audios for selected events
  const handleBatchGenerateAudios = useCallback(async () => {
    const indices = Array.from(store.selectedEventIndices)
      .filter((i) => i >= 0 && i < store.events.length)
      .sort((a, b) => a - b);
    if (indices.length === 0) return;

    store.setBatchProgress({
      batchGenerating: true,
      batchDone: 0,
      batchTotal: indices.length,
      batchCurrentItem: "Preparando selección",
      batchStartedAt: Date.now(),
    });

    const total = indices.length;
    let done = 0;

    for (const idx of indices) {
      const ev = store.events[idx];
      if (!ev) continue;

      store.setBatchProgress({
        batchCurrentItem: `Evento V${ev.lap} · ${ev.summary.slice(0, 36)}`,
      });

      const desc = ev.description || "";
      if (!desc.trim()) {
        done++;
        store.setBatchProgress({ batchDone: done, batchTotal: total });
        continue;
      }

      const outName = sanitizeFilename(
        `${ev.lap}_${formatTimestamp(ev.timestamp).replace(/:/g, "-")}_${ev.summary.slice(0, 40)}`,
      );
      const t0 = Date.now();
      const audioId = await generateSingleAudio(desc, outName, `Evento ${idx + 1}`);
      if (audioId) store.setEventAudio(idx, audioId);
      setEventGenTimes((prev) => ({ ...prev, [idx]: Math.floor((Date.now() - t0) / 1000) }));
      done++;
      store.setBatchProgress({ batchDone: done, batchTotal: total });
    }

    store.clearBatchProgress();
  }, [store, generateSingleAudio]);

  // Batch elapsed timer
  useEffect(() => {
    if (!store.batchGenerating || !store.batchStartedAt) return;
    setBatchElapsed(Math.max(0, Math.floor((Date.now() - store.batchStartedAt) / 1000)));
    const timer = setInterval(() => {
      setBatchElapsed(Math.max(0, Math.floor((Date.now() - store.batchStartedAt!) / 1000)));
    }, 1000);
    return () => clearInterval(timer);
  }, [store.batchGenerating, store.batchStartedAt]);

  // Current item elapsed timer
  useEffect(() => {
    if (!store.currentAudioStartedAt) return;
    const timer = setInterval(() => {
      setItemElapsed(Math.max(0, Math.floor((Date.now() - store.currentAudioStartedAt!) / 1000)));
    }, 1000);
    return () => clearInterval(timer);
  }, [store.currentAudioStartedAt]);

  // CSV import handler
  const handleCSVImport = useCallback(
    async (e: any) => {
      const file = e.target?.files?.[0];
      if (!file) return;
      const csvText = await file.text();
      const rows = parseCSV(csvText);
      if (rows.length < 2) return;

      const events: any[] = [];
      const eventAudios: Record<string, string> = {};
      let introText = "";
      let introAudio = "";
      let eventIdx = 0;

      for (let i = 1; i < rows.length; i++) {
        const [col0, col1, col2, col3, col4, col5] = rows[i];

        if (
          (col2 || "").trim().toLowerCase() === "introducción" ||
          (col2 || "").trim().toLowerCase() === "introduccion"
        ) {
          introText = col4 ?? "";
          introAudio = (col5 ?? "").trim();
          continue;
        }

        const lap = parseInt(col0, 10) || 0;
        const timeParts = (col1 || "00:00:00").split(":").map(Number);
        const timestamp = 3600 * (timeParts[0] || 0) + 60 * (timeParts[1] || 0) + (timeParts[2] || 0);

        const typeMap: Record<string, number> = {
          "Evento Manual": 0,
          Adelantamiento: 1,
          "Choque entre pilotos": 2,
          "Choque contra muro": 3,
          Penalización: 4,
          "Entrada a boxes": 5,
        };

        events.push({
          lap,
          timestamp,
          event_type: typeMap[col2?.trim()] ?? 0,
          summary: col3 ?? "",
          description: col4 ?? "",
        });

        if (col5?.trim()) {
          eventAudios[String(eventIdx)] = col5.trim();
        }
        eventIdx++;
      }

      store.loadFromCSV(events, eventAudios, introText, introAudio);

      // Check which audios actually exist
      const allAudios = [...(introAudio ? [introAudio] : []), ...Object.values(eventAudios)].filter(Boolean);
      if (allAudios.length > 0) {
        try {
          const { data } = await listOutputs(config.output_directory || undefined);
          const existingIds = new Set(data.map((o) => o.id));
          setMissingAudios(new Set(allAudios.filter((a) => !existingIds.has(a))));
        } catch {
          setMissingAudios(new Set());
        }
      } else {
        setMissingAudios(new Set());
      }

      if (csvInputRef.current) csvInputRef.current.value = "";
    },
    [store],
  );

  // CSV export
  const handleCSVExport = useCallback(async () => {
    if (!store.header) {
      window.alert("Primero carga un XML de carrera antes de guardar textos.");
      return;
    }

    const baseName = (store.currentSession || store.header.track_event || "sesion").trim() || "sesion";
    const previousNames = loadExportNames();
    const finalName = deduplicateName(baseName, [
      ...store.sessions.map((s) => s.name),
      ...previousNames,
    ]);

    const { data } = await raceExportCSV(finalName, {
      intro_text: store.introText,
      intro_audio: store.introAudio,
      header: store.header,
      events: store.events,
      event_audios: store.eventAudios,
      hidden_event_indices: Array.from(store.hiddenEventIndices),
      selected_event_indices: Array.from(store.selectedEventIndices),
    });

    const blob = new Blob([data], { type: "text/csv; charset=utf-8" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${finalName}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    saveExportName(finalName);
  }, [store]);

  // Generate intro audio
  const handleGenerateIntroAudio = useCallback(async () => {
    if (!store.introText?.trim()) return;
    setGeneratingIntroAudio(true);
    try {
      const outName = sanitizeFilename(store.header?.track_event || "carrera");
      const audioId = await generateSingleAudio(store.introText, `0_Intro_${outName}`, "Intro de carrera");
      if (audioId) {
        store.setIntroAudio(audioId);
        setMissingAudios((prev) => {
          if (!prev.has(audioId)) return prev;
          const next = new Set(prev);
          next.delete(audioId);
          return next;
        });
      }
    } finally {
      setGeneratingIntroAudio(false);
    }
  }, [store, generateSingleAudio]);

  // Generate intro text via AI
  const handleGenerateIntroText = useCallback(async () => {
    await store.generateIntro();
    requestAnimationFrame(() => {
      requestAnimationFrame(autoResizeIntro);
    });
  }, [store, autoResizeIntro]);

  // Generate text for single event
  const handleGenerateEventText = useCallback(
    async (idx: number) => {
      setGeneratingTextForEvent((prev) => ({ ...prev, [idx]: true }));
      try {
        await store.generateDescriptionForEvent(idx);
      } finally {
        setGeneratingTextForEvent((prev) => ({ ...prev, [idx]: false }));
      }
    },
    [store],
  );

  // Batch generate texts for selected events
  const handleBatchGenerateTexts = useCallback(async () => {
    const indices = Array.from(store.selectedEventIndices)
      .filter((i) => i >= 0 && i < store.events.length)
      .sort((a, b) => a - b);
    if (indices.length === 0) return;
    setGeneratingSelectedTexts(true);
    try {
      for (const idx of indices) {
        setGeneratingTextForEvent((prev) => ({ ...prev, [idx]: true }));
        try {
          await store.generateDescriptionForEvent(idx);
        } finally {
          setGeneratingTextForEvent((prev) => ({ ...prev, [idx]: false }));
        }
      }
    } finally {
      setGeneratingSelectedTexts(false);
    }
  }, [store]);

  // Generate audio for single event
  const handleGenerateEventAudio = useCallback(
    async (idx: number) => {
      const ev = store.events[idx];
      if (!ev) return;
      const desc = (ev.description || "").trim();
      if (!desc) {
        window.alert("Escribe primero el texto en el cuadro de descripción del evento.");
        return;
      }
      setGeneratingAudioForEvent((prev) => ({ ...prev, [idx]: true }));
      try {
        const outName = sanitizeFilename(
          `${ev.lap}_${formatTimestamp(ev.timestamp).replace(/:/g, "-")}_${ev.summary.slice(0, 40)}`,
        );
        const audioId = await generateSingleAudio(desc, outName, `Evento ${idx + 1}`);
        if (audioId) store.setEventAudio(idx, audioId);
      } finally {
        setGeneratingAudioForEvent((prev) => ({ ...prev, [idx]: false }));
      }
    },
    [store, generateSingleAudio],
  );

  // Delete intro audio
  const handleDeleteIntroAudio = useCallback(async () => {
    if (!store.introAudio) return;
    if (!window.confirm("¿Eliminar el audio de la intro?")) return;
    const { data } = await listOutputs(config.output_directory || undefined);
    const found = data.find((o) => o.id === store.introAudio);
    if (found) await deleteOutputs([found.filename], config.output_directory || undefined);
    store.removeAudioReferencesByIds([store.introAudio]);
  }, [store, config.output_directory]);

  // Delete event audio
  const handleDeleteEventAudio = useCallback(
    async (idx: number) => {
      const audioId = store.eventAudios[String(idx)];
      if (!audioId) return;
      if (!window.confirm("¿Eliminar el audio de este evento?")) return;
      const { data } = await listOutputs(config.output_directory || undefined);
      const found = data.find((o) => o.id === audioId);
      if (found) await deleteOutputs([found.filename], config.output_directory || undefined);
      store.removeAudioReferencesByIds([audioId]);
    },
    [store, config.output_directory],
  );

  return (
    <View style={{ flex: 1 }}>
      <ScrollView style={shared.screen} contentContainerStyle={{ paddingBottom: 120 }}>
        <Text style={shared.title}>📝 Narración de Carrera</Text>

        {/* ── Context in use ───────────────────────────────────────── */}
        <View style={shared.card}>
          <Text style={shared.label}>Contexto en uso para generar textos</Text>
          <Text style={{ color: colors.text, fontWeight: "700", marginTop: 4 }}>
            {contextStateLoading ? "Cargando..." : contextInUseName}
          </Text>
          {contextStateError ? (
            <Text style={{ color: colors.error, marginTop: 6 }}>{contextStateError}</Text>
          ) : null}
          <View style={[shared.row, { marginTop: 10 }]}>
            <Pressable style={shared.buttonSecondary} onPress={refreshContextInUse}>
              <Text style={[shared.buttonText, { color: colors.text }]}>Refrescar contexto</Text>
            </Pressable>
          </View>
        </View>

        {/* ── Session management ─────────────────────────────────────── */}
        <View style={shared.card}>
          <Text style={shared.label}>Sesión</Text>
          <View style={shared.row}>
            <Pressable style={[shared.buttonSecondary, { flex: 1 }]} onPress={() => store.newSession()}>
              <Text style={[shared.buttonText, { color: colors.text }]}>Nueva</Text>
            </Pressable>
            <Pressable style={[shared.buttonSecondary, { flex: 1 }]} onPress={() => csvInputRef.current?.click()}>
              <Text style={[shared.buttonText, { color: colors.text }]}>Cargar CSV</Text>
            </Pressable>
            {/* @ts-ignore - HTML input element for web */}
            <input
              ref={csvInputRef}
              type="file"
              accept=".csv"
              onChange={handleCSVImport}
              style={{ display: "none" }}
            />
            {store.sessions.map((sess) => (
              <Pressable
                key={sess.name}
                style={[
                  shared.buttonSecondary,
                  { flex: 1 },
                  store.currentSession === sess.name && { borderColor: colors.primary },
                ]}
                onPress={() => store.loadSession(sess.name)}
              >
                <Text style={[shared.buttonText, { color: colors.text }]} numberOfLines={1}>
                  {sess.name}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        {/* ── XML upload ────────────────────────────────────────────── */}
        <View style={shared.card}>
          <Text style={shared.label}>Archivo XML (rFactor2)</Text>
          {/* @ts-ignore - HTML input element for web */}
          <input
            ref={xmlInputRef}
            type="file"
            accept=".xml"
            onChange={handleXmlFile}
            style={{ color: colors.text, marginBottom: 8 }}
          />
        </View>

        {/* ── Loading / error ───────────────────────────────────────── */}
        {store.loading && <ActivityIndicator size="large" color={colors.primary} style={{ marginVertical: 16 }} />}
        {store.error && <Text style={{ color: colors.error, marginBottom: 12 }}>{store.error}</Text>}

        {/* ── Header card ───────────────────────────────────────────── */}
        {store.header && (
          <View style={shared.card}>
            <Text style={[shared.title, { fontSize: 16 }]}>{store.header.track_event}</Text>
            <Text style={{ color: colors.textDim }}>
              {store.header.race_laps} vueltas · {store.header.num_drivers} pilotos ·{" "}
              {store.header.track_length.toFixed(0)}m
            </Text>
            <Text style={{ color: colors.textDim, marginTop: 4 }}>
              Parrilla: {(store.header.grid_order ?? []).map((name, i) => `${i + 1}. ${name}`).join(", ")}
            </Text>
          </View>
        )}

        {/* ── Intro text card ───────────────────────────────────────── */}
        {store.header && (
          <View style={shared.card}>
            <Text style={shared.label}>Texto de Introducción</Text>
            <TextInput
              ref={introTextareaRef}
              style={shared.textArea}
              value={store.introText}
              onChangeText={handleIntroTextChange}
              multiline
              scrollEnabled={false}
              placeholder="Genera o escribe el texto de introducción..."
              placeholderTextColor={colors.textDim}
            />
            <Pressable style={[shared.button, { alignSelf: "flex-start" }]} onPress={handleGenerateIntroText}>
              <Text style={shared.buttonText}>Generar intro con IA</Text>
            </Pressable>

            <View style={shared.row}>
              <Pressable
                style={shared.buttonSecondary}
                onPress={handleGenerateIntroAudio}
                disabled={generatingIntroAudio || !store.introText?.trim()}
              >
                <Text style={[shared.buttonText, { color: colors.text }]}>
                  {generatingIntroAudio ? "Generando audio..." : "Generar audio intro"}
                </Text>
              </Pressable>

              {store.introAudio ? (
                missingAudios.has(store.introAudio) ? (
                  <Text style={{ color: colors.error, fontSize: 13, marginTop: 4 }}>
                    Audio {store.introAudio} no existe
                  </Text>
                ) : (
                  <View style={{ flex: 1 }}>
                    <View style={[shared.row, { alignItems: "center", flexWrap: "nowrap" }]}>
                      {/* @ts-ignore - HTML audio element for web */}
                      <audio
                        controls
                        src={getAudioUrl(store.introAudio, config.output_directory || undefined)}
                        style={{ width: 340, maxWidth: "52%" }}
                      />
                      <View style={{ flex: 1, marginLeft: 8 }}>
                        <Text style={{ color: colors.textDim, fontSize: 12 }} numberOfLines={1}>
                          {store.introAudio}
                        </Text>
                        <Pressable
                          style={[
                            shared.buttonSecondary,
                            {
                              borderColor: colors.error,
                              marginTop: 6,
                              alignSelf: "flex-start",
                              paddingVertical: 6,
                              paddingHorizontal: 10,
                            },
                          ]}
                          onPress={handleDeleteIntroAudio}
                        >
                          <Text style={[shared.buttonText, { color: colors.error }]}>Eliminar audio</Text>
                        </Pressable>
                      </View>
                    </View>
                  </View>
                )
              ) : null}
            </View>

            {generatingIntroAudio && (
              <Text style={{ color: colors.textDim, marginTop: 8 }}>
                <Text style={{ color: YELLOW, fontWeight: "700" }}>Generando audio intro...</Text>{" "}
                <Text style={{ color: YELLOW, fontWeight: "700" }}>{formatElapsed(itemElapsed)}</Text>
              </Text>
            )}
            {!generatingIntroAudio &&
              store.currentAudioItem === "Intro de carrera" &&
              store.currentAudioStartedAt && (
                <Text style={{ color: colors.textDim, marginTop: 8 }}>
                  <Text style={{ color: YELLOW, fontWeight: "700" }}>Generando audio intro...</Text>{" "}
                  <Text style={{ color: YELLOW, fontWeight: "700" }}>{formatElapsed(itemElapsed)}</Text>
                </Text>
              )}
          </View>
        )}

        {/* ── Events card ───────────────────────────────────────────── */}
        {store.events.length > 0 && (
          <View style={shared.card}>
            <View style={[shared.row, { justifyContent: "space-between", marginBottom: 8 }]}>
              <Text style={shared.label}>
                Eventos visibles ({store.events.filter((_, i) => !store.hiddenEventIndices.has(i)).length}/
                {store.events.length})
              </Text>
            </View>

            {/* Toolbar */}
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
                  if (
                    store.selectedEventIndices.size &&
                    window.confirm(`Eliminar ${store.selectedEventIndices.size} eventos seleccionados?`)
                  ) {
                    await store.deleteSelectedEvents();
                  }
                }}
                disabled={!store.selectedEventIndices.size}
              >
                <Text style={[shared.buttonText, { color: colors.error }]}>
                  Borrar seleccionados ({store.selectedEventIndices.size})
                </Text>
              </Pressable>
              <Pressable style={shared.buttonSecondary} onPress={() => setShowHidden((v) => !v)}>
                <Text style={[shared.buttonText, { color: colors.text }]}>
                  {showHidden ? "Ocultar filas ocultas" : `Mostrar ocultos (${store.hiddenEventIndices.size})`}
                </Text>
              </Pressable>
              <Pressable
                style={[
                  shared.button,
                  { backgroundColor: colors.accent, opacity: store.selectedEventIndices.size ? 1 : 0.5 },
                ]}
                onPress={handleBatchGenerateTexts}
                disabled={generatingSelectedTexts || store.batchGenerating || store.selectedEventIndices.size === 0}
              >
                <Text style={shared.buttonText}>
                  Generar descripciones IA seleccionados ({store.selectedEventIndices.size})
                </Text>
              </Pressable>
              <Pressable
                style={[shared.button, { opacity: store.selectedEventIndices.size ? 1 : 0.5 }]}
                onPress={handleBatchGenerateAudios}
                disabled={store.batchGenerating || store.selectedEventIndices.size === 0}
              >
                <Text style={shared.buttonText}>
                  Generar audios de seleccionados ({store.selectedEventIndices.size})
                </Text>
              </Pressable>
            </View>

            {/* Batch progress */}
            {store.batchGenerating && (
              <View style={{ marginBottom: 10 }}>
                <Text style={{ color: YELLOW, fontWeight: "700", marginBottom: 6 }}>
                  Generando seleccionados... {store.batchDone}/{store.batchTotal} · {formatElapsed(batchElapsed)}
                </Text>
                {store.batchCurrentItem ? (
                  <Text style={{ color: YELLOW, fontWeight: "700", marginBottom: 6 }}>
                    En curso: {store.batchCurrentItem}
                  </Text>
                ) : null}
                {store.currentAudioItem ? (
                  <Text style={{ color: YELLOW, fontWeight: "700", marginBottom: 6 }}>
                    Tiempo actual ({store.currentAudioItem}): {formatElapsed(itemElapsed)}
                  </Text>
                ) : null}
                <View style={{ height: 8, backgroundColor: colors.surfaceLight, borderRadius: 4 }}>
                  <View
                    style={{
                      width: `${store.batchTotal > 0 ? (store.batchDone / store.batchTotal) * 100 : 0}%`,
                      height: 8,
                      backgroundColor: colors.primary,
                      borderRadius: 4,
                    }}
                  />
                </View>
              </View>
            )}

            {/* Event list */}
            {store.events.map((ev, idx) =>
              !store.hiddenEventIndices.has(idx) || showHidden ? (
                <View
                  key={idx}
                  style={{
                    borderBottomWidth: 1,
                    borderBottomColor: colors.border,
                    paddingVertical: 8,
                    opacity: store.hiddenEventIndices.has(idx) ? 0.55 : 1,
                  }}
                >
                  {/* Event header row */}
                  <View style={shared.row}>
                    <Pressable onPress={() => store.toggleEventSelected(idx)} style={{ marginRight: 6 }}>
                      <Text style={{ color: colors.text }}>
                        {store.selectedEventIndices.has(idx) ? "☑" : "☐"}
                      </Text>
                    </Pressable>
                    <Text style={{ color: colors.primary, fontWeight: "600", width: 50 }}>V{ev.lap}</Text>
                    <Text style={{ color: colors.textDim, width: 70 }}>{formatTimestamp(ev.timestamp)}</Text>
                    <Text style={{ color: colors.accent, flex: 1 }}>
                      {EVENT_TYPE_LABELS[ev.event_type] || `Tipo ${ev.event_type}`}
                    </Text>
                    {store.hiddenEventIndices.has(idx) && (
                      <Text style={{ color: colors.textDim, fontSize: 12 }}>[Oculto]</Text>
                    )}
                  </View>

                  {/* Summary */}
                  <Text style={{ color: colors.text, marginVertical: 4 }}>{ev.summary}</Text>

                  {/* Description input */}
                  <TextInput
                    style={[shared.input, { fontSize: 13 }]}
                    value={ev.description}
                    onChangeText={(t) => store.updateEventDescription(idx, t)}
                    placeholder="Descripción IA..."
                    placeholderTextColor={colors.textDim}
                  />

                  {/* Action buttons */}
                  <View style={[shared.row, { flexWrap: "wrap", marginBottom: 8 }]}>
                    <Pressable
                      style={shared.buttonSecondary}
                      onPress={() => handleGenerateEventText(idx)}
                      disabled={!!generatingTextForEvent[idx]}
                    >
                      <Text style={[shared.buttonText, { color: colors.text }]}>
                        {generatingTextForEvent[idx] ? "Generando texto..." : "Generar texto"}
                      </Text>
                    </Pressable>
                    <Pressable
                      style={shared.buttonSecondary}
                      onPress={() => handleGenerateEventAudio(idx)}
                      disabled={!!generatingAudioForEvent[idx] || !(ev.description || ev.summary)}
                    >
                      <Text style={[shared.buttonText, { color: colors.text }]}>
                        {generatingAudioForEvent[idx] ? "Generando audio..." : "Generar audio"}
                      </Text>
                    </Pressable>
                    <Pressable
                      style={shared.buttonSecondary}
                      onPress={() => {
                        store.insertEventAfter(idx);
                        const newIdx = idx + 1;
                        setEditEventIndex(newIdx);
                        const newEv = store.events[newIdx];
                        if (newEv) {
                          const h2 = Math.floor(newEv.timestamp / 3600);
                          const m2 = Math.floor((newEv.timestamp % 3600) / 60);
                          const s2 = newEv.timestamp % 60;
                          setEditTimestamp(
                            `${String(h2).padStart(2, "0")}:${String(m2).padStart(2, "0")}:${String(s2).padStart(2, "0")}`,
                          );
                          setEditSummary(newEv.summary);
                        }
                      }}
                    >
                      <Text style={[shared.buttonText, { color: colors.text }]}>Insertar evento debajo</Text>
                    </Pressable>
                    <Pressable
                      style={shared.buttonSecondary}
                      onPress={async () => {
                        await store.toggleEventHidden(idx);
                      }}
                    >
                      <Text style={[shared.buttonText, { color: colors.text }]}>
                        {store.hiddenEventIndices.has(idx) ? "Mostrar" : "Ocultar"}
                      </Text>
                    </Pressable>
                    <Pressable
                      style={[shared.buttonSecondary, { borderColor: colors.error }]}
                      onPress={async () => {
                        if (window.confirm("Eliminar este evento?")) await store.deleteEvent(idx);
                      }}
                    >
                      <Text style={[shared.buttonText, { color: colors.error }]}>Borrar</Text>
                    </Pressable>
                  </View>

                  {/* Gen time info */}
                  {eventGenTimes[idx] !== undefined && (
                    <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 6 }}>
                      Ultimo audio generado en {formatElapsed(eventGenTimes[idx])}
                    </Text>
                  )}

                  {/* Generating audio indicator */}
                  {generatingAudioForEvent[idx] && (
                    <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 6 }}>
                      <Text style={{ color: YELLOW, fontWeight: "700" }}>Generando audio...</Text>{" "}
                      <Text style={{ color: YELLOW, fontWeight: "700" }}>{formatElapsed(itemElapsed)}</Text>
                    </Text>
                  )}
                  {!generatingAudioForEvent[idx] &&
                    store.currentAudioItem === `Evento ${idx + 1}` &&
                    store.currentAudioStartedAt && (
                      <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 6 }}>
                        <Text style={{ color: YELLOW, fontWeight: "700" }}>Generando audio...</Text>{" "}
                        <Text style={{ color: YELLOW, fontWeight: "700" }}>{formatElapsed(itemElapsed)}</Text>
                      </Text>
                    )}

                  {/* Audio player */}
                  {store.eventAudios[String(idx)] &&
                    (missingAudios.has(store.eventAudios[String(idx)]) ? (
                      <Text style={{ color: colors.error, fontSize: 13, marginTop: 4 }}>
                        Audio {store.eventAudios[String(idx)]} no existe
                      </Text>
                    ) : (
                      <View>
                        <View style={[shared.row, { alignItems: "center", flexWrap: "nowrap" }]}>
                          {/* @ts-ignore - HTML audio element for web */}
                          <audio
                            controls
                            src={getAudioUrl(store.eventAudios[String(idx)], config.output_directory || undefined)}
                            style={{ width: 340, maxWidth: "52%" }}
                          />
                          <View style={{ flex: 1, marginLeft: 8 }}>
                            <Text style={{ color: colors.textDim, fontSize: 12 }} numberOfLines={1}>
                              {store.eventAudios[String(idx)]}
                            </Text>
                            <Pressable
                              style={[
                                shared.buttonSecondary,
                                {
                                  borderColor: colors.error,
                                  marginTop: 6,
                                  alignSelf: "flex-start",
                                  paddingVertical: 6,
                                  paddingHorizontal: 10,
                                },
                              ]}
                              onPress={() => handleDeleteEventAudio(idx)}
                            >
                              <Text style={[shared.buttonText, { color: colors.error }]}>Eliminar audio</Text>
                            </Pressable>
                          </View>
                        </View>
                      </View>
                    ))}
                </View>
              ) : null,
            )}
          </View>
        )}

        <View style={{ height: 16 }} />
      </ScrollView>

      {/* ── Floating CSV save button ──────────────────────────────── */}
      <View style={{ position: "absolute", right: 16, bottom: 16 }}>
        <Pressable
          style={[
            shared.button,
            { backgroundColor: colors.success, minWidth: 180, opacity: store.header ? 1 : 0.5 },
          ]}
          onPress={handleCSVExport}
          disabled={!store.header}
        >
          <Text style={shared.buttonText}>Guardar CSV</Text>
        </Pressable>
      </View>

      {/* ── Edit event modal ──────────────────────────────────────── */}
      {editEventIndex !== null && (
        <View
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.7)",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 1000,
          }}
          // @ts-ignore
          onPress={() => setEditEventIndex(null)}
        >
          <View
            style={{
              backgroundColor: colors.surface,
              borderRadius: 8,
              padding: 20,
              maxWidth: "90%",
              width: 500,
              borderColor: colors.border,
              borderWidth: 1,
            }}
            // @ts-ignore
            onPress={(e: any) => e.stopPropagation()}
          >
            <Text style={[shared.label, { marginBottom: 16 }]}>Editar Evento Manual</Text>

            <Text style={[shared.label, { marginBottom: 4 }]}>Timestamp (HH:MM:SS)</Text>
            <TextInput
              value={editTimestamp}
              onChangeText={setEditTimestamp}
              placeholder="00:00:00"
              placeholderTextColor={colors.textDim}
              style={{
                backgroundColor: colors.bg,
                color: colors.text,
                borderColor: colors.border,
                borderWidth: 1,
                borderRadius: 4,
                padding: 8,
                marginBottom: 16,
                fontFamily: "monospace",
              }}
            />

            <Text style={[shared.label, { marginBottom: 4 }]}>Resumen del Evento</Text>
            <TextInput
              value={editSummary}
              onChangeText={setEditSummary}
              placeholder="Descripción del evento"
              placeholderTextColor={colors.textDim}
              multiline
              numberOfLines={3}
              style={{
                backgroundColor: colors.bg,
                color: colors.text,
                borderColor: colors.border,
                borderWidth: 1,
                borderRadius: 4,
                padding: 8,
                marginBottom: 16,
                textAlignVertical: "top",
              }}
            />

            <View style={[shared.row, { justifyContent: "flex-end", gap: 8 }]}>
              <Pressable style={shared.buttonSecondary} onPress={() => setEditEventIndex(null)}>
                <Text style={[shared.buttonText, { color: colors.text }]}>Cancelar</Text>
              </Pressable>
              <Pressable
                style={shared.button}
                onPress={() => {
                  if (editEventIndex !== null) {
                    const parts = editTimestamp.split(":");
                    const ts =
                      3600 * parseInt(parts[0] || "0", 10) +
                      60 * parseInt(parts[1] || "0", 10) +
                      parseInt(parts[2] || "0", 10);
                    const updated = [...store.events];
                    if (updated[editEventIndex]) {
                      updated[editEventIndex] = {
                        ...updated[editEventIndex],
                        timestamp: ts,
                        summary: editSummary,
                      };
                      store.setEvents(updated);
                    }
                    setEditEventIndex(null);
                  }
                }}
              >
                <Text style={shared.buttonText}>Guardar</Text>
              </Pressable>
            </View>
          </View>
        </View>
      )}
    </View>
  );
}

export default function CarreraScreen() {
  return (
    <RaceErrorBoundary>
      <CarreraContent />
    </RaceErrorBoundary>
  );
}
