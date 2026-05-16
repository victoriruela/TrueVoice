import React, { useEffect, useCallback, useMemo, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  Pressable,
  ActivityIndicator,
} from "react-native";
import { shared, colors } from "../src/theme";
import { useOutputStore } from "../src/stores/useOutputStore";
import { useConfigStore } from "../src/stores/useConfigStore";
import { useRaceStore } from "../src/stores/useRaceStore";
import { getAudioUrl, deleteOutputs } from "../src/api";

let outputsScrollMemory = 0;

function formatCreatedAt(unixSeconds: number): string {
  if (!Number.isFinite(unixSeconds)) {
    return "Fecha desconocida";
  }
  return new Date(unixSeconds * 1000).toLocaleString("es-ES", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function OutputsScreen() {
  const { outputs, loading, fetch } = useOutputStore();
  const outputDirectory = useConfigStore((s) => s.config.output_directory);
  const removeAudioRefs = useRaceStore((s) => s.removeAudioReferencesByIds);
  const scrollRef = React.useRef<any>(null);
  const [selectedAudioIds, setSelectedAudioIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetch(outputDirectory || undefined);
  }, [fetch, outputDirectory]);

  useEffect(() => {
    const validIds = new Set(outputs.map((o) => o.id));
    setSelectedAudioIds((prev) => {
      const next = new Set<string>();
      prev.forEach((id) => {
        if (validIds.has(id)) {
          next.add(id);
        }
      });
      if (next.size === prev.size) {
        return prev;
      }
      return next;
    });
  }, [outputs]);

  useEffect(() => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo?.({ y: outputsScrollMemory, animated: false });
    });
  }, []);

  const onScroll = useCallback((e: any) => {
    const y = e?.nativeEvent?.contentOffset?.y ?? 0;
    outputsScrollMemory = y;
  }, []);

  const handleDelete = useCallback(
    async (filename: string, audioId: string) => {
      if (window.confirm(`¿Eliminar ${filename}?`)) {
        await deleteOutputs([filename], outputDirectory || undefined);
        removeAudioRefs([audioId]);
        await fetch(outputDirectory || undefined);
      }
    },
    [fetch, outputDirectory, removeAudioRefs],
  );

  const selectedCount = selectedAudioIds.size;
  const allSelected = useMemo(
    () => outputs.length > 0 && selectedAudioIds.size === outputs.length,
    [outputs.length, selectedAudioIds],
  );

  const toggleSelected = useCallback((audioId: string) => {
    setSelectedAudioIds((prev) => {
      const next = new Set(prev);
      if (next.has(audioId)) {
        next.delete(audioId);
      } else {
        next.add(audioId);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedAudioIds(new Set(outputs.map((o) => o.id)));
  }, [outputs]);

  const clearSelection = useCallback(() => {
    setSelectedAudioIds(new Set());
  }, []);

  const deleteSelected = useCallback(async () => {
    if (selectedAudioIds.size === 0) return;
    const selected = outputs.filter((o) => selectedAudioIds.has(o.id));
    if (selected.length === 0) return;
    if (!window.confirm(`¿Eliminar ${selected.length} audio(s) seleccionado(s)?`)) return;

    // Delete one by one: this path is proven reliable on Windows file locks and backend parsing.
    for (const item of selected) {
      await deleteOutputs([item.filename], outputDirectory || undefined);
    }

    removeAudioRefs(selected.map((o) => o.id));
    setSelectedAudioIds(new Set());
    await fetch(outputDirectory || undefined);
  }, [selectedAudioIds, outputs, outputDirectory, removeAudioRefs, fetch]);

  return (
    <ScrollView ref={scrollRef} style={shared.screen} onScroll={onScroll} scrollEventThrottle={16}>
      <Text style={shared.title}>🔊 Audios Generados</Text>

      <Pressable
        style={[shared.buttonSecondary, { marginBottom: 16, alignSelf: "flex-start", minWidth: 130 }]}
        onPress={() => fetch(outputDirectory || undefined)}
      >
        <Text style={[shared.buttonText, { color: colors.text }]}>Refrescar</Text>
      </Pressable>

      {outputs.length > 0 && (
        <View style={[shared.row, { marginBottom: 12, flexWrap: "wrap", gap: 8 }]}>
          {!allSelected && (
            <Pressable style={shared.buttonSecondary} onPress={selectAll}>
              <Text style={[shared.buttonText, { color: colors.text }]}>✓ Seleccionar todo</Text>
            </Pressable>
          )}
          {selectedCount > 0 && (
            <Pressable style={shared.buttonSecondary} onPress={clearSelection}>
              <Text style={[shared.buttonText, { color: colors.textDim }]}>Limpiar selección</Text>
            </Pressable>
          )}
          {selectedCount > 0 && (
            <Pressable style={[shared.buttonSecondary, { borderColor: colors.error }]} onPress={deleteSelected}>
              <Text style={[shared.buttonText, { color: colors.error }]}>
                🗑️ Borrar seleccionados ({selectedCount})
              </Text>
            </Pressable>
          )}
        </View>
      )}

      {loading && (
        <ActivityIndicator size="large" color={colors.primary} style={{ marginVertical: 16 }} />
      )}

      {outputs.length === 0 && !loading && (
        <Text style={{ color: colors.textDim, textAlign: "center", marginTop: 32 }}>
          No hay audios generados todavía.
        </Text>
      )}

      {outputs.map((f) => (
        <View
          key={f.id}
          style={[
            shared.card,
            selectedAudioIds.has(f.id) && { borderColor: colors.primary, borderWidth: 1 },
          ]}
        >
          <View style={[shared.row, { justifyContent: "space-between", marginBottom: 6 }]}>
            <Pressable onPress={() => toggleSelected(f.id)} style={{ marginRight: 8 }}>
              <Text style={{ color: colors.text, fontSize: 16 }}>{selectedAudioIds.has(f.id) ? "☑" : "☐"}</Text>
            </Pressable>
            <View style={{ flex: 1 }}>
              <Text style={{ color: colors.text, fontWeight: "600" }} numberOfLines={1}>
                {f.filename}
              </Text>
              <Text style={{ color: colors.textDim, fontSize: 12, marginTop: 2 }}>
                Creado: {formatCreatedAt(f.created)}
              </Text>
            </View>
            <Text style={{ color: colors.textDim, fontSize: 12, marginLeft: 8 }}>
              {(f.size / 1024 / 1024).toFixed(2)} MB
            </Text>
          </View>

          <audio
            controls
            src={getAudioUrl(f.id, outputDirectory || undefined)}
            style={{ width: "100%", marginBottom: 8 }}
          />

          <View style={[shared.row, { justifyContent: "flex-end" }]}>
            <Pressable
              style={[shared.buttonSecondary]}
              onPress={() => {
                const a = document.createElement("a");
                a.href = getAudioUrl(f.id, outputDirectory || undefined);
                a.download = f.filename;
                a.click();
              }}
            >
              <Text style={[shared.buttonText, { color: colors.text }]}>Descargar</Text>
            </Pressable>
            <Pressable
              style={[shared.buttonSecondary, { borderColor: colors.error }]}
              onPress={() => handleDelete(f.filename, f.id)}
            >
              <Text style={[shared.buttonText, { color: colors.error }]}>Eliminar</Text>
            </Pressable>
          </View>
        </View>
      ))}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}
