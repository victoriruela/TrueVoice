import React, { useEffect, useRef, useCallback, useState, useMemo } from "react";
import {
  View,
  Text,
  ScrollView,
  Pressable,
  ActivityIndicator,
  TextInput,
} from "react-native";
import { shared, colors } from "../src/theme";
import { useVoiceStore } from "../src/stores/useVoiceStore";
import { useConfigStore, type NarratorConfig } from "../src/stores/useConfigStore";

const SLOTS = [1, 2, 3, 4];

export default function VoicesScreen() {
  const { voices, loading, fetch, upload, remove } = useVoiceStore();
  const selectedVoice = useConfigStore((s) => s.config.selected_voice);
  const narrators = useConfigStore((s) => s.config.narrators || []);
  const patchConfig = useConfigStore((s) => s.patch);
  const fetchNarrators = useConfigStore((s) => s.fetchNarrators);
  const addNarrator = useConfigStore((s) => s.addNarrator);
  const deleteNarrator = useConfigStore((s) => s.deleteNarrator);
  const setPrincipalNarrator = useConfigStore((s) => s.setPrincipalNarrator);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [showAddForm, setShowAddForm] = useState(false);
  const [formName, setFormName] = useState("");
  const [formKey, setFormKey] = useState("");
  const [formVoice, setFormVoice] = useState("");
  const [formSlot, setFormSlot] = useState(1);
  const [formPrincipal, setFormPrincipal] = useState(false);

  useEffect(() => {
    fetch();
    fetchNarrators();
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

  const voiceOptions = useMemo(
    () => voices.map((v) => ({ value: v.name, label: v.alias || v.name })),
    [voices],
  );

  const resetForm = () => {
    setFormName("");
    setFormKey("");
    setFormVoice("");
    setFormSlot(1);
    setFormPrincipal(false);
    setShowAddForm(false);
  };

  const handleSaveNarrator = async () => {
    const trimmedKey = formKey.trim().replace(/\s+/g, "_").toLowerCase();
    if (!trimmedKey || !formName.trim() || !formVoice) {
      window.alert("Completa nombre, clave y voz");
      return;
    }
    const narrator: NarratorConfig = {
      key: trimmedKey,
      name: formName.trim(),
      voice: formVoice,
      speaker_slot: formSlot,
      is_principal: formPrincipal,
    };
    await addNarrator(narrator);
    resetForm();
  };

  const handleDeleteNarrator = async (key: string, name: string) => {
    if (window.confirm(`¿Eliminar narrador "${name}"?`)) {
      await deleteNarrator(key);
    }
  };

  return (
    <ScrollView style={shared.screen}>
      <Text style={shared.title}>🎙️ Voces</Text>

      {/* ── Narradores ─────────────────────────────────────────────── */}
      <View style={shared.card}>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <Text style={{ color: colors.text, fontSize: 16, fontWeight: "700" }}>
            Narradores
          </Text>
          <Pressable
            onPress={() => setShowAddForm((v) => !v)}
            style={[shared.buttonSecondary, { marginBottom: 0, paddingVertical: 6, paddingHorizontal: 12 }]}
          >
            <Text style={{ color: colors.primary, fontSize: 13, fontWeight: "600" }}>
              {showAddForm ? "Cancelar" : "+ Añadir narrador"}
            </Text>
          </Pressable>
        </View>

        <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 12 }}>
          El narrador principal se usa cuando no se especifica narrador. En textos multi-speaker, usa
          {" "}<Text style={{ color: colors.accent }}>[clave]: texto</Text>.
        </Text>

        {showAddForm && (
          <View style={{ backgroundColor: colors.surfaceLight, padding: 12, borderRadius: 6, marginBottom: 12 }}>
            <Text style={shared.label}>Nombre</Text>
            <TextInput
              style={shared.input}
              value={formName}
              onChangeText={setFormName}
              placeholder="ej: Carlos"
              placeholderTextColor={colors.textDim}
            />

            <Text style={shared.label}>Clave (sin espacios)</Text>
            <TextInput
              style={shared.input}
              value={formKey}
              onChangeText={setFormKey}
              placeholder="ej: carlos"
              placeholderTextColor={colors.textDim}
              autoCapitalize="none"
            />

            <Text style={shared.label}>Voz</Text>
            <select
              value={formVoice}
              onChange={(e) => setFormVoice((e.target as HTMLSelectElement).value)}
              style={{
                backgroundColor: colors.surfaceLight,
                color: colors.text,
                border: `1px solid ${colors.border}`,
                borderRadius: 6,
                padding: 8,
                marginBottom: 8,
                fontSize: 14,
              }}
            >
              <option value="">— Selecciona una voz —</option>
              {voiceOptions.map((v) => (
                <option key={v.value} value={v.value}>{v.label}</option>
              ))}
            </select>

            <Text style={shared.label}>Slot (Speaker N)</Text>
            <View style={{ flexDirection: "row", gap: 8, marginBottom: 8 }}>
              {SLOTS.map((s) => (
                <Pressable
                  key={s}
                  onPress={() => setFormSlot(s)}
                  style={{
                    backgroundColor: formSlot === s ? colors.primary : colors.surface,
                    borderWidth: 1,
                    borderColor: formSlot === s ? colors.primary : colors.border,
                    borderRadius: 6,
                    paddingHorizontal: 14,
                    paddingVertical: 6,
                  }}
                >
                  <Text style={{ color: formSlot === s ? "#fff" : colors.text, fontWeight: "600" }}>{s}</Text>
                </Pressable>
              ))}
            </View>

            <Pressable
              onPress={() => setFormPrincipal((v) => !v)}
              style={{ flexDirection: "row", alignItems: "center", marginBottom: 12 }}
            >
              <View
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: 4,
                  borderWidth: 1,
                  borderColor: colors.border,
                  backgroundColor: formPrincipal ? colors.primary : "transparent",
                  marginRight: 8,
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {formPrincipal && <Text style={{ color: "#fff", fontSize: 12 }}>✓</Text>}
              </View>
              <Text style={{ color: colors.text }}>Narrador principal</Text>
            </Pressable>

            <Pressable onPress={handleSaveNarrator} style={shared.button}>
              <Text style={shared.buttonText}>Guardar narrador</Text>
            </Pressable>
          </View>
        )}

        {narrators.length === 0 ? (
          <Text style={{ color: colors.textDim, fontStyle: "italic", fontSize: 13 }}>
            No hay narradores configurados.
          </Text>
        ) : (
          narrators.map((n) => (
            <View
              key={n.key}
              style={{
                backgroundColor: colors.surfaceLight,
                borderRadius: 6,
                padding: 12,
                marginBottom: 8,
                borderWidth: 1,
                borderColor: n.is_principal ? colors.primary : colors.border,
              }}
            >
              <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                <Text style={{ color: colors.text, fontSize: 15, fontWeight: "700" }}>
                  👤 {n.name}
                </Text>
                <Text style={{ color: colors.accent, fontSize: 12 }}>
                  Slot {n.speaker_slot}
                </Text>
              </View>
              <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 4 }}>
                Clave: <Text style={{ color: colors.text }}>[{n.key}]</Text>  ·  Voz: <Text style={{ color: colors.text }}>{n.voice}</Text>
              </Text>
              <View style={{ flexDirection: "row", gap: 8, marginTop: 8 }}>
                {n.is_principal ? (
                  <View style={{ paddingHorizontal: 8, paddingVertical: 4, backgroundColor: colors.primary, borderRadius: 4 }}>
                    <Text style={{ color: "#fff", fontSize: 11, fontWeight: "700" }}>PRINCIPAL</Text>
                  </View>
                ) : (
                  <Pressable
                    onPress={() => setPrincipalNarrator(n.key)}
                    style={{ paddingHorizontal: 8, paddingVertical: 4, borderWidth: 1, borderColor: colors.border, borderRadius: 4 }}
                  >
                    <Text style={{ color: colors.primary, fontSize: 11, fontWeight: "600" }}>Hacer principal</Text>
                  </Pressable>
                )}
                <Pressable
                  onPress={() => handleDeleteNarrator(n.key, n.name)}
                  style={{ paddingHorizontal: 8, paddingVertical: 4, borderWidth: 1, borderColor: colors.error, borderRadius: 4 }}
                >
                  <Text style={{ color: colors.error, fontSize: 11, fontWeight: "600" }}>Eliminar</Text>
                </Pressable>
              </View>
            </View>
          ))
        )}
      </View>

      {/* ── Upload nueva voz ───────────────────────────────────────── */}
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
