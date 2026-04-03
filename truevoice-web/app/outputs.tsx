import React, { useEffect, useCallback } from "react";
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

  useEffect(() => {
    fetch(outputDirectory || undefined);
  }, [fetch, outputDirectory]);

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

  return (
    <ScrollView style={shared.screen}>
      <Text style={shared.title}>🔊 Audios Generados</Text>

      <Pressable
        style={[shared.buttonSecondary, { marginBottom: 16 }]}
        onPress={() => fetch(outputDirectory || undefined)}
      >
        <Text style={[shared.buttonText, { color: colors.text }]}>Refrescar</Text>
      </Pressable>

      {loading && (
        <ActivityIndicator size="large" color={colors.primary} style={{ marginVertical: 16 }} />
      )}

      {outputs.length === 0 && !loading && (
        <Text style={{ color: colors.textDim, textAlign: "center", marginTop: 32 }}>
          No hay audios generados todavía.
        </Text>
      )}

      {outputs.map((f) => (
        <View key={f.id} style={shared.card}>
          <View style={[shared.row, { justifyContent: "space-between", marginBottom: 6 }]}>
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
