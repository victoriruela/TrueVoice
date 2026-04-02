import React, { useEffect, useCallback, useState } from "react";
import { View, Text, TextInput, ScrollView, Pressable, ActivityIndicator } from "react-native";
import { shared, colors } from "../src/theme";
import { useConfigStore } from "../src/stores/useConfigStore";
import { useGenerationStore, GenerationTask } from "../src/stores/useGenerationStore";
import { useVoiceStore } from "../src/stores/useVoiceStore";
import { getAudioUrl } from "../src/api";

function formatElapsed(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (h > 0) {
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function AudioPlayer({ audioId, directory }: { audioId: string; directory?: string }) {
  const url = getAudioUrl(audioId, directory);
  return (
    <View style={{ marginVertical: 8 }}>
      {/* On web, use HTML audio element */}
      <audio controls src={url} style={{ width: "100%" }} />
    </View>
  );
}

function TaskCard({ task }: { task: GenerationTask }) {
  const config = useConfigStore((s) => s.config);
  const { updateTask, generate, save, removeTask } = useGenerationStore();
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (task.status !== "generating") {
      return;
    }
    const timer = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [task.status]);

  const onGenerate = useCallback(() => {
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

  const pct =
    task.progress && task.progress.total > 0
      ? Math.round((task.progress.current / task.progress.total) * 100)
      : 0;

  const startMs = task.progress?.start_time
    ? task.progress.start_time * 1000
    : task.startedAt || nowMs;
  const elapsed = Math.max(0, Math.floor((nowMs - startMs) / 1000));

  return (
    <View style={shared.card}>
      <View style={[shared.row, { justifyContent: "space-between", marginBottom: 8 }]}>
        <TextInput
          style={[shared.input, { flex: 1, fontWeight: "600" }]}
          value={task.customName}
          onChangeText={(v) => updateTask(task.id, { customName: v })}
          placeholder="Nombre del audio"
          placeholderTextColor={colors.textDim}
        />
        <Pressable onPress={() => removeTask(task.id)} style={{ padding: 8 }}>
          <Text style={{ color: colors.error, fontSize: 18 }}>✕</Text>
        </Pressable>
      </View>

      <TextInput
        style={shared.textArea}
        value={task.text}
        onChangeText={(v) => updateTask(task.id, { text: v })}
        placeholder="Escribe el texto a sintetizar..."
        placeholderTextColor={colors.textDim}
        multiline
      />

      {task.status === "generating" && (
        <View style={[shared.row, { marginBottom: 8 }]}>
          <ActivityIndicator color={colors.primary} />
          <Text style={{ color: colors.textDim }}>
            Generando... {pct > 0 ? `${pct}%` : ""} · {formatElapsed(elapsed)}
          </Text>
          {task.progress && (
            <View
              style={{
                flex: 1,
                height: 6,
                backgroundColor: colors.surfaceLight,
                borderRadius: 3,
                marginLeft: 8,
              }}
            >
              <View
                style={{
                  width: `${pct}%`,
                  height: 6,
                  backgroundColor: colors.primary,
                  borderRadius: 3,
                }}
              />
            </View>
          )}
        </View>
      )}

      {task.error && (
        <Text style={{ color: colors.error, marginBottom: 8 }}>{task.error}</Text>
      )}

      {task.result?.audio_id && (
        <AudioPlayer audioId={task.result.audio_id} />
      )}

      <View style={shared.row}>
        <Pressable
          style={[shared.button, { flex: 1, opacity: task.status === "generating" ? 0.5 : 1 }]}
          onPress={onGenerate}
          disabled={task.status === "generating" || !task.text.trim()}
        >
          <Text style={shared.buttonText}>
            {task.status === "generating" ? "Generando..." : "Generar"}
          </Text>
        </Pressable>

        {task.result?.is_temp && task.status === "done" && (
          <Pressable
            style={[shared.button, { flex: 1, backgroundColor: colors.success }]}
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
  const { tasks, addTask } = useGenerationStore();
  const fetchVoices = useVoiceStore((s) => s.fetch);
  const config = useConfigStore((s) => s.config);

  useEffect(() => {
    fetchVoices(config.voice_directory || undefined);
  }, [config.voice_directory]);

  return (
    <ScrollView style={shared.screen}>
      <Text style={shared.title}>🗣️ Generar Audio</Text>

      {tasks.map((t) => (
        <TaskCard key={t.id} task={t} />
      ))}

      <Pressable style={shared.buttonSecondary} onPress={() => addTask()}>
        <Text style={[shared.buttonText, { color: colors.primary }]}>+ Añadir tarea</Text>
      </Pressable>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}
