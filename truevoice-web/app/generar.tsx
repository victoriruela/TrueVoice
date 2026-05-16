import React, { useEffect, useState, useMemo, useCallback, useRef } from "react";
import { View, Text, TextInput, ScrollView, Pressable, ActivityIndicator } from "react-native";
import { shared, colors } from "../src/theme";
import { useConfigStore } from "../src/stores/useConfigStore";
import { useGenerationStore, GenerationTask } from "../src/stores/useGenerationStore";
import { useVoiceStore } from "../src/stores/useVoiceStore";
import { getAudioUrl, listOutputs, deleteOutputs, GenerateRequest } from "../src/api";
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
  );
}
