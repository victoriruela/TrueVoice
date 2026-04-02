import React, { useEffect, useRef, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  Pressable,
  ActivityIndicator,
} from "react-native";
import { shared, colors } from "../src/theme";
import { useVoiceStore } from "../src/stores/useVoiceStore";
import { useConfigStore } from "../src/stores/useConfigStore";

export default function VoicesScreen() {
  const { voices, loading, fetch, upload, remove } = useVoiceStore();
  const selectedVoice = useConfigStore((s) => s.config.selected_voice);
  const patchConfig = useConfigStore((s) => s.patch);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch();
  }, []);

  const handleUpload = useCallback(
    async (e: any) => {
      const file = e.target?.files?.[0];
      if (!file) return;
      const name = file.name.replace(/\.wav$/i, "");
      await upload(name, file);
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    [upload],
  );

  const handleSelect = useCallback(
    (name: string) => {
      patchConfig({ selected_voice: name });
    },
    [patchConfig],
  );

  const handleDelete = useCallback(
    async (name: string) => {
      if (window.confirm(`¿Eliminar la voz "${name}"?`)) {
        await remove(name);
        if (selectedVoice === name) patchConfig({ selected_voice: "Alice" });
      }
    },
    [remove, selectedVoice, patchConfig],
  );

  return (
    <ScrollView style={shared.screen}>
      <Text style={shared.title}>🎙️ Voces</Text>

      {/* Upload */}
      <View style={shared.card}>
        <Text style={shared.label}>Subir nueva voz (.wav)</Text>
        <input
          ref={fileInputRef}
          type="file"
          accept=".wav"
          onChange={handleUpload}
          style={{ color: colors.text, marginBottom: 8 }}
        />
      </View>

      {loading && (
        <ActivityIndicator size="large" color={colors.primary} style={{ marginVertical: 16 }} />
      )}

      {/* Voice grid */}
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 12 }}>
        {voices.map((v) => {
          const isSelected = selectedVoice === v.name;
          return (
            <Pressable
              key={v.name}
              onPress={() => handleSelect(v.name)}
              style={[
                shared.card,
                {
                  width: 180,
                  borderColor: isSelected ? colors.primary : colors.border,
                  borderWidth: isSelected ? 2 : 1,
                },
              ]}
            >
              <Text
                style={{
                  color: isSelected ? colors.primary : colors.text,
                  fontWeight: "600",
                  fontSize: 15,
                  marginBottom: 4,
                }}
              >
                {v.alias || v.name}
              </Text>
              <Text style={{ color: colors.textDim, fontSize: 12 }}>{v.filename}</Text>

              {/* Only show delete for custom voices (not built-in) */}
              {v.filename.startsWith("voices/") || !v.filename.includes("/") ? (
                <Pressable
                  onPress={(e) => {
                    e.stopPropagation();
                    handleDelete(v.name);
                  }}
                  style={{ marginTop: 8 }}
                >
                  <Text style={{ color: colors.error, fontSize: 12 }}>Eliminar</Text>
                </Pressable>
              ) : null}
            </Pressable>
          );
        })}
      </View>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}
