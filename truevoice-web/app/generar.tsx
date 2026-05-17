import React, { useEffect, useState, useMemo, useCallback, useRef } from "react";
import { View, Text, TextInput, ScrollView, Pressable, ActivityIndicator, Modal } from "react-native";
import { shared, colors } from "../src/theme";
import { useConfigStore } from "../src/stores/useConfigStore";
import { useGenerationStore, GenerationTask } from "../src/stores/useGenerationStore";
import { useVoiceStore } from "../src/stores/useVoiceStore";
import { getAudioUrl, listOutputs, deleteOutputs, GenerateRequest, type NarratorConfig } from "../src/api";
import { useRaceStore } from "../src/stores/useRaceStore";

let generateScrollMemory = 0;

function formatElapsed(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return h > 0
    ? `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
    : `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function AudioPlayer({ audioId, directory }: { audioId: string; directory?: string }) {
  const src = useMemo(() => getAudioUrl(audioId, directory), [audioId, directory]);
  return (
    <View style={{ marginVertical: 8 }}>
      {/* @ts-ignore - HTML audio element for web */}
      <audio controls src={src} style={{ width: "100%" }} />
    </View>
  );
}

/* ── Tag insertion bar ─────────────────────────────────────────────── */
function TagBar({ narrators }: { narrators: Pick<NarratorConfig, "key" | "name">[] }) {
  const lastElRef = useRef<HTMLTextAreaElement | null>(null);
  const lastPosRef = useRef({ start: 0, end: 0 });

  useEffect(() => {
    if (typeof document === "undefined") return;
    const onFocus = (e: FocusEvent) => {
      const el = e.target as HTMLTextAreaElement;
      if (el && el.tagName === "TEXTAREA") {
        lastElRef.current = el;
        lastPosRef.current = { start: el.selectionStart ?? 0, end: el.selectionEnd ?? 0 };
      }
    };
    const onSelChange = () => {
      const el = lastElRef.current;
      if (el && document.activeElement === el) {
        lastPosRef.current = { start: el.selectionStart ?? 0, end: el.selectionEnd ?? 0 };
      }
    };
    document.addEventListener("focus", onFocus, true);
    document.addEventListener("selectionchange", onSelChange);
    document.addEventListener("mouseup", onSelChange);
    document.addEventListener("keyup", onSelChange);
    return () => {
      document.removeEventListener("focus", onFocus, true);
      document.removeEventListener("selectionchange", onSelChange);
      document.removeEventListener("mouseup", onSelChange);
      document.removeEventListener("keyup", onSelChange);
    };
  }, []);

  const insertTag = useCallback((tag: string) => {
    const el = lastElRef.current;
    if (!el) return;
    const { start, end } = lastPosRef.current;
    const before = el.value.substring(0, start);
    const after = el.value.substring(end);
    const newValue = before + tag + after;
    const proto = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value");
    if (proto?.set) {
      proto.set.call(el, newValue);
      el.dispatchEvent(new Event("input", { bubbles: true }));
    } else {
      el.value = newValue;
    }
    const newPos = start + tag.length;
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(newPos, newPos);
      lastPosRef.current = { start: newPos, end: newPos };
    });
  }, []);

  return (
    <View
      style={{
        flexDirection: "row",
        flexWrap: "wrap",
        paddingHorizontal: 8,
        paddingVertical: 4,
        backgroundColor: colors.surfaceLight,
        borderBottomWidth: 1,
        borderBottomColor: colors.border,
        gap: 4,
        minHeight: 36,
      }}
    >
      <Pressable
        onPress={() => insertTag("[pause]")}
        style={{
          paddingHorizontal: 10,
          paddingVertical: 4,
          backgroundColor: colors.surface,
          borderRadius: 4,
          borderWidth: 1,
          borderColor: colors.border,
        }}
      >
        <Text style={{ color: colors.textDim, fontSize: 12 }}>⏸ pause</Text>
      </Pressable>
      {narrators.map((n) => (
        <Pressable
          key={n.key}
          onPress={() => insertTag(`[${n.key}]: `)}
          style={{
            paddingHorizontal: 10,
            paddingVertical: 4,
            backgroundColor: colors.surface,
            borderRadius: 4,
            borderWidth: 1,
            borderColor: colors.accent,
          }}
        >
          <Text style={{ color: colors.accent, fontSize: 12 }}>👤 {n.name}</Text>
        </Pressable>
      ))}
    </View>
  );
}

function TaskCard({
  task,
  isSelected,
  onToggleSelect,
}: {
  task: GenerationTask;
  isSelected: boolean;
  onToggleSelect: () => void;
}) {
  const config = useConfigStore((s) => s.config);
  const { updateTask, generate, save, removeTask } = useGenerationStore();
  const removeAudioReferencesByIds = useRaceStore((s) => s.removeAudioReferencesByIds);
  const [now, setNow] = useState(() => Date.now());
  const [showFormatHint, setShowFormatHint] = useState(false);
  const textAreaRef = useRef<any>(null);

  const getScrollParent = useCallback((el: any): any => {
    if (!el || typeof window === "undefined") return null;
    let p = el.parentElement;
    while (p) {
      const style = window.getComputedStyle(p);
      const overflowY = style?.overflowY || "";
      if ((overflowY === "auto" || overflowY === "scroll") && p.scrollHeight > p.clientHeight) {
        return p;
      }
      p = p.parentElement;
    }
    return null;
  }, []);

  const centerTypingLine = useCallback(() => {
    const el = textAreaRef.current?._node ?? textAreaRef.current;
    if (!el || typeof window === "undefined") return;
    const parent = getScrollParent(el);
    if (!parent) return;
    const rect = el.getBoundingClientRect();
    const parentRect = parent.getBoundingClientRect();
    const lineHeight = 24;
    const caretY = rect.bottom - lineHeight;
    const caretYInParent = caretY - parentRect.top + parent.scrollTop;
    const targetTop = Math.max(0, caretYInParent - parent.clientHeight * 0.5);
    parent.scrollTop = targetTop;
  }, [getScrollParent]);

  useEffect(() => {
    if (task.status !== "generating") return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [task.status]);

  const handleGenerate = useCallback(() => {
    generate(task.id, {
      voice_name: config.selected_voice,
      model: config.selected_model,
      output_format: config.output_format,
      cfg_scale: config.cfg_scale,
      ddpm_steps: config.ddpm_steps,
      disable_prefill: config.disable_prefill,
      output_directory: config.output_directory || undefined,
    });
  }, [task.id, config]);

  const handleDeleteAudio = useCallback(async () => {
    const audioId = task.result?.audio_id;
    if (!audioId) return;
    const dir = config.output_directory || undefined;
    let filename = task.result?.filename || "";
    if (!filename) {
      const { data } = await listOutputs(dir);
      const found = data.find((o) => o.id === audioId);
      filename = found?.filename || "";
    }
    if (filename) {
      if (window.confirm(`¿Eliminar ${filename}?`)) {
        await deleteOutputs([filename], dir);
        removeAudioReferencesByIds([audioId]);
        updateTask(task.id, { result: null, progress: null, status: "idle", error: null });
      }
    } else {
      window.alert("No se pudo localizar el archivo para eliminar.");
    }
  }, [task.id, task.result, config.output_directory, updateTask, removeAudioReferencesByIds]);

  const pct =
    task.progress && task.progress.total > 0
      ? Math.round((task.progress.current / task.progress.total) * 100)
      : 0;

  const startTime = task.progress?.start_time
    ? 1000 * task.progress.start_time
    : task.startedAt || now;
  const elapsed = Math.max(0, Math.floor((now - startTime) / 1000));

  const autoResizeTaskTextArea = useCallback(() => {
    const el = textAreaRef.current?._node ?? textAreaRef.current;
    if (!el || !el.style) return;
    el.style.overflow = "hidden";
    el.style.overflowY = "hidden";
    el.style.height = "auto";
    el.style.height = `${Math.max(120, el.scrollHeight)}px`;
    centerTypingLine();
  }, [centerTypingLine]);

  useEffect(() => {
    requestAnimationFrame(autoResizeTaskTextArea);
  }, [task.text, autoResizeTaskTextArea]);

  return (
    <View style={[shared.card, { backgroundColor: isSelected ? colors.surfaceLight : colors.surface }]}>
      <View style={[shared.row, { justifyContent: "space-between", marginBottom: 8 }]}>
        <Pressable onPress={onToggleSelect} style={{ padding: 8, marginRight: 8 }}>
          <Text style={{ fontSize: 20 }}>{isSelected ? "☑️" : "☐"}</Text>
        </Pressable>
        <TextInput
          style={[shared.input, { flex: 1, fontWeight: "600" }]}
          value={task.customName}
          onChangeText={(t) => updateTask(task.id, { customName: t })}
          placeholder="Nombre del audio"
          placeholderTextColor={colors.textDim}
        />
        <Pressable onPress={() => removeTask(task.id)} style={{ padding: 8 }}>
          <Text style={{ color: colors.error, fontSize: 18 }}>✕</Text>
        </Pressable>
      </View>

      <View style={{ flexDirection: "row", alignItems: "center", marginBottom: 4 }}>
        <Text style={[shared.label, { marginBottom: 0, flex: 1 }]}>Texto a sintetizar</Text>
        <Pressable
          onPress={() => setShowFormatHint(true)}
          style={{
            width: 22,
            height: 22,
            borderRadius: 11,
            borderWidth: 1,
            borderColor: colors.primary,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Text style={{ color: colors.primary, fontSize: 12, fontWeight: "700" }}>i</Text>
        </Pressable>
      </View>

      <TextInput
        ref={textAreaRef}
        style={[shared.textArea, { minHeight: 120, overflow: "hidden" }]}
        value={task.text}
        onChangeText={(t) => {
          updateTask(task.id, { text: t });
        }}
        placeholder="Escribe el texto a sintetizar..."
        placeholderTextColor={colors.textDim}
        multiline
        scrollEnabled={false}
      />

      <Modal
        visible={showFormatHint}
        transparent
        animationType="fade"
        onRequestClose={() => setShowFormatHint(false)}
      >
        <View
          style={{
            flex: 1,
            backgroundColor: "rgba(0,0,0,0.6)",
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
              maxWidth: 520,
              width: "100%",
            }}
          >
            <Text style={{ color: colors.text, fontSize: 16, fontWeight: "700", marginBottom: 8 }}>
              Formato multi-speaker
            </Text>
            <Text style={{ color: colors.textDim, fontSize: 13, marginBottom: 8 }}>
              Para narraciones con varias voces, usa el formato:
            </Text>
            <View
              style={{
                backgroundColor: colors.surfaceLight,
                padding: 12,
                borderRadius: 6,
                marginBottom: 12,
              }}
            >
              <Text style={{ color: colors.text, fontFamily: "monospace", fontSize: 13 }}>
                Speaker 1: Buenos días a todos{"\n"}
                Speaker 2: Y bienvenidos al Gran Premio de Japón
              </Text>
            </View>
            <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 4 }}>
              También puedes usar <Text style={{ color: colors.accent }}>[clave]:</Text> con las claves de los narradores configurados en Voces.
            </Text>
            <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 4 }}>
              Etiqueta <Text style={{ color: colors.accent }}>[pause:1000]</Text> para insertar 1 segundo de silencio.
            </Text>
            <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 16 }}>
              Los textos largos se dividen automáticamente en bloques (configurable en Ajustes).
            </Text>

            <View style={{ flexDirection: "row", gap: 8, justifyContent: "flex-end" }}>
              <Pressable
                onPress={() => {
                  const example =
                    "Speaker 1: Buenos días a todos.\nSpeaker 2: Y bienvenidos al Gran Premio de Japón.";
                  updateTask(task.id, { text: example });
                  setShowFormatHint(false);
                }}
                style={[shared.buttonSecondary, { marginBottom: 0 }]}
              >
                <Text style={[shared.buttonText, { color: colors.primary }]}>Insertar ejemplo</Text>
              </Pressable>
              <Pressable
                onPress={() => setShowFormatHint(false)}
                style={[shared.button, { marginBottom: 0 }]}
              >
                <Text style={shared.buttonText}>Cerrar</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>

      {task.status === "generating" && (
        <View style={[shared.row, { marginBottom: 8 }]}>
          <ActivityIndicator color={colors.primary} />
          <Text style={{ color: colors.textDim }}>
            Generando... {pct > 0 ? `${pct}%` : ""} · {formatElapsed(elapsed)}
          </Text>
          {task.progress && (
            <View style={{ flex: 1, height: 6, backgroundColor: colors.surfaceLight, borderRadius: 3, marginLeft: 8 }}>
              <View style={{ width: `${pct}%`, height: 6, backgroundColor: colors.primary, borderRadius: 3 }} />
            </View>
          )}
        </View>
      )}

      {task.error && (
        <Text style={{ color: colors.error, marginBottom: 8 }}>{task.error}</Text>
      )}

      {task.result?.audio_id && (
        <AudioPlayer audioId={task.result.audio_id} directory={config.output_directory || undefined} />
      )}

      <View style={shared.row}>
        <Pressable
          style={[
            shared.button,
            {
              opacity: task.status === "generating" ? 0.5 : 1,
              minWidth: 120,
              alignSelf: "flex-start",
            },
          ]}
          onPress={handleGenerate}
          disabled={task.status === "generating" || !task.text.trim()}
        >
          <Text style={shared.buttonText}>
            {task.status === "generating" ? "Generando..." : "Generar"}
          </Text>
        </Pressable>

        {task.result?.audio_id && task.status === "done" && (
          <Pressable
            style={[shared.buttonSecondary, { borderColor: colors.error }]}
            onPress={handleDeleteAudio}
          >
            <Text style={[shared.buttonText, { color: colors.error }]}>Eliminar audio</Text>
          </Pressable>
        )}

        {task.result?.is_temp && task.status === "done" && (
          <Pressable
            style={[shared.button, { backgroundColor: colors.success, minWidth: 120 }]}
            onPress={() => save(task.id, config.output_directory || undefined)}
          >
            <Text style={shared.buttonText}>Guardar</Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}

export default function GenerateScreen() {
  const {
    tasks,
    addTask,
    selectedTaskIds,
    toggleTaskSelection,
    removeSelectedTasks,
    clearSelection,
    selectAllTasks,
  } = useGenerationStore();
  const fetchVoices = useVoiceStore((s) => s.fetch);
  const config = useConfigStore((s) => s.config);
  const scrollRef = useRef<any>(null);

  useEffect(() => {
    fetchVoices(config.voice_directory || undefined);
  }, [config.voice_directory]);

  useEffect(() => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo?.({ y: generateScrollMemory, animated: false });
    });
  }, []);

  const onScroll = useCallback((e: any) => {
    const y = e?.nativeEvent?.contentOffset?.y ?? 0;
    generateScrollMemory = y;
  }, []);

  return (
    <View style={{ flex: 1 }}>
      <TagBar narrators={config.narrators || []} />
      <ScrollView ref={scrollRef} style={shared.screen} onScroll={onScroll} scrollEventThrottle={16}>
      <Text style={shared.title}>🗣️ Generar Audio</Text>

      {tasks.map((task) => (
        <TaskCard
          key={task.id}
          task={task}
          isSelected={selectedTaskIds.includes(task.id)}
          onToggleSelect={() => toggleTaskSelection(task.id)}
        />
      ))}

      <Pressable style={[shared.buttonSecondary, { alignSelf: "flex-start", minWidth: 170 }]} onPress={() => addTask()}>
        <Text style={[shared.buttonText, { color: colors.primary }]}>+ Añadir tarea</Text>
      </Pressable>

      {tasks.length > 0 && selectedTaskIds.length < tasks.length && (
        <Pressable style={[shared.buttonSecondary, { alignSelf: "flex-start", minWidth: 170 }]} onPress={selectAllTasks}>
          <Text style={[shared.buttonText, { color: colors.primary }]}>✓ Seleccionar todo</Text>
        </Pressable>
      )}

      {selectedTaskIds.length > 0 && (
        <View style={{ marginTop: 12, gap: 8 }}>
          <Pressable
            style={[shared.button, { backgroundColor: colors.error, alignSelf: "flex-start", minWidth: 220 }]}
            onPress={removeSelectedTasks}
          >
            <Text style={shared.buttonText}>
              🗑️ Borrar {selectedTaskIds.length} seleccionado{selectedTaskIds.length > 1 ? "s" : ""}
            </Text>
          </Pressable>
          <Pressable style={[shared.buttonSecondary, { alignSelf: "flex-start", minWidth: 180 }]} onPress={clearSelection}>
            <Text style={[shared.buttonText, { color: colors.textDim }]}>Deseleccionar todo</Text>
          </Pressable>
        </View>
      )}

      <View style={{ height: 40 }} />
    </ScrollView>
    </View>
  );
}
