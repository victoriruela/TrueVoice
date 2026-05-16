import React, { useEffect, useCallback, useLayoutEffect } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { colors, shared } from "../src/theme";
import { useContextStore } from "../src/stores/useContextStore";

let contextScrollMemory = 0;

export default function ContextoScreen() {
  const {
    contexts,
    inUseName,
    draftIntroText,
    draftEventsText,
    loading,
    error,
    fetchAll,
    loadByName,
    saveDraftAs,
    deleteByName,
    setDraftIntroText,
    setDraftEventsText,
  } = useContextStore();

  useEffect(() => {
    if (!draftIntroText && !draftEventsText) fetchAll();
  }, []);

  const onSave = useCallback(async () => {
    if (typeof window === "undefined") return;
    const name = window.prompt("Nombre del contexto:", "");
    if (!name || !name.trim()) return;
    await saveDraftAs(name.trim());
  }, [saveDraftAs]);

  const onLoad = useCallback(
    async (name: string) => {
      await loadByName(name);
    },
    [loadByName],
  );

  const onDelete = async (name: string) => {
    if (typeof window !== "undefined") {
      const ok = window.confirm(`Eliminar el contexto '${name}'?`);
      if (!ok) {
        return;
      }
    }
    await deleteByName(name);
  };

  const introRef = React.useRef<any>(null);
  const eventsRef = React.useRef<any>(null);
  const scrollRef = React.useRef<any>(null);

  // Restore scroll AFTER resize effects have painted (setTimeout > rAF)
  useEffect(() => {
    const id = setTimeout(() => {
      if (contextScrollMemory > 0) {
        scrollRef.current?.scrollTo?.({ y: contextScrollMemory, animated: false });
      }
    }, 80);
    return () => clearTimeout(id);
  }, []);

  const onScroll = useCallback((e: any) => {
    contextScrollMemory = e?.nativeEvent?.contentOffset?.y ?? 0;
  }, []);

  const resizeEl = useCallback((el: any) => {
    if (!el || !el.style) return;
    el.style.overflow = "hidden";
    el.style.overflowY = "hidden";
    el.style.height = "auto";
    el.style.height = `${Math.max(120, el.scrollHeight)}px`;
  }, []);

  const resizeWithoutMovingScroll = useCallback((ref: React.RefObject<any>) => {
    const el = ref.current?._node ?? ref.current;
    const currentY = contextScrollMemory;
    resizeEl(el);
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo?.({ y: currentY, animated: false });
      contextScrollMemory = currentY;
    });
  }, [resizeEl]);

  // Resize before paint to avoid visible scroll flash while typing.
  useLayoutEffect(() => {
    resizeWithoutMovingScroll(introRef);
  }, [draftIntroText, resizeWithoutMovingScroll]);

  useLayoutEffect(() => {
    resizeWithoutMovingScroll(eventsRef);
  }, [draftEventsText, resizeWithoutMovingScroll]);

  return (
    <ScrollView ref={scrollRef} style={shared.screen} onScroll={onScroll} scrollEventThrottle={16}>
      <Text style={shared.title}>📝 Contexto</Text>

      <View style={shared.card}>
        <Text style={shared.label}>Editar contexto</Text>

        <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: 12 }}>
          {inUseName ? `En uso: ${inUseName}` : "Sin contexto cargado"}
        </Text>

        <Text style={shared.label}>Introducción</Text>
        <TextInput
          ref={introRef}
          multiline
          style={[shared.textArea, { minHeight: 120, overflow: "hidden" }]}
          placeholder="Texto de introducción..."
          placeholderTextColor={colors.textDim}
          value={draftIntroText}
          onChangeText={(text) => {
            setDraftIntroText(text);
          }}
          scrollEnabled={false}
        />

        <Text style={[shared.label, { marginTop: 12 }]}>Eventos</Text>
        <TextInput
          ref={eventsRef}
          multiline
          style={[shared.textArea, { minHeight: 120, overflow: "hidden" }]}
          placeholder="Texto para eventos..."
          placeholderTextColor={colors.textDim}
          value={draftEventsText}
          onChangeText={(text) => {
            setDraftEventsText(text);
          }}
          scrollEnabled={false}
        />

        <View style={[shared.row, { marginTop: 12, gap: 8 }]}>
          <Pressable style={[shared.button, { flex: 1 }]} onPress={onSave}>
            <Text style={shared.buttonText}>Guardar</Text>
          </Pressable>
          <Pressable style={[shared.buttonSecondary, { flex: 1 }]} onPress={fetchAll}>
            <Text style={[shared.buttonText, { color: colors.text }]}>Recargar</Text>
          </Pressable>
        </View>

        {error ? <Text style={{ color: colors.error, marginTop: 10 }}>{error}</Text> : null}
      </View>

      <View style={shared.card}>
        <Text style={shared.label}>Contextos guardados</Text>

        {loading && (
          <ActivityIndicator color={colors.primary} style={{ marginVertical: 16 }} />
        )}

        {!loading && contexts.length === 0 && (
          <Text style={{ color: colors.textDim }}>No hay contextos guardados.</Text>
        )}

        {!loading &&
          contexts.map((item) => (
            <View
              key={item.name}
              style={{
                borderWidth: 1,
                borderColor: item.name === inUseName ? colors.primary : colors.border,
                borderRadius: 8,
                padding: 12,
                marginBottom: 10,
                backgroundColor: colors.surfaceLight,
              }}
            >
              <Text style={{ color: colors.text, fontWeight: "700" }}>{item.name}</Text>
              <Text style={{ color: colors.textDim, marginTop: 2 }}>
                Creado: {item.created_at || "-"}
              </Text>
              <View style={[shared.row, { marginTop: 8, gap: 8 }]}>
                <Pressable
                  style={[shared.buttonSecondary, { flex: 1 }]}
                  onPress={() => onLoad(item.name)}
                >
                  <Text style={[shared.buttonText, { color: colors.text }]}>Cargar</Text>
                </Pressable>
                <Pressable
                  style={[shared.buttonDanger, { flex: 1 }]}
                  onPress={() => onDelete(item.name)}
                >
                  <Text style={shared.buttonText}>Eliminar</Text>
                </Pressable>
              </View>
            </View>
          ))}
      </View>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}
