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
import { getAudioUrl, deleteOutputs } from "../src/api";

export default function OutputsScreen() {
  const { outputs, loading, fetch } = useOutputStore();

  useEffect(() => {
    fetch();
  }, []);

  const handleDelete = useCallback(
    async (filename: string) => {
      if (window.confirm(`¿Eliminar ${filename}?`)) {
        await deleteOutputs([filename]);
        await fetch();
      }
    },
    [fetch],
  );

  return (
    <ScrollView style={shared.screen}>
      <Text style={shared.title}>🔊 Audios Generados</Text>

      <Pressable style={[shared.buttonSecondary, { marginBottom: 16 }]} onPress={() => fetch()}>
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
            <Text style={{ color: colors.text, fontWeight: "600", flex: 1 }} numberOfLines={1}>
              {f.filename}
            </Text>
            <Text style={{ color: colors.textDim, fontSize: 12, marginLeft: 8 }}>
              {(f.size / 1024 / 1024).toFixed(2)} MB
            </Text>
          </View>

          <audio controls src={getAudioUrl(f.id)} style={{ width: "100%", marginBottom: 8 }} />

          <View style={[shared.row, { justifyContent: "flex-end" }]}>
            <Pressable
              style={[shared.buttonSecondary]}
              onPress={() => {
                const a = document.createElement("a");
                a.href = getAudioUrl(f.id);
                a.download = f.filename;
                a.click();
              }}
            >
              <Text style={[shared.buttonText, { color: colors.text }]}>Descargar</Text>
            </Pressable>
            <Pressable
              style={[shared.buttonSecondary, { borderColor: colors.error }]}
              onPress={() => handleDelete(f.filename)}
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
