import React, { useEffect, useState } from "react";
import { StatusBar } from "expo-status-bar";
import { Pressable, SafeAreaView, ScrollView, Text, View } from "react-native";
import GenerateScreen from "./app/generar";
import RaceScreen from "./app/carrera";
import ContextoScreen from "./app/contexto";
import OutputsScreen from "./app/outputs";
import VoicesScreen from "./app/voices";
import SettingsScreen from "./app/settings";
import { cleanupTemp } from "./src/api";
import { useConfigStore } from "./src/stores/useConfigStore";
import { colors } from "./src/theme";

type TabKey = "generate" | "race" | "context" | "outputs" | "voices" | "settings";

const TABS: Array<{ key: TabKey; title: string }> = [
  { key: "race", title: "Carrera" },
  { key: "generate", title: "Generar" },
  { key: "context", title: "Contexto" },
  { key: "outputs", title: "Audios" },
  { key: "voices", title: "Voces" },
  { key: "settings", title: "Config" },
];

function AllScreens({ tab }: { tab: TabKey }) {
  return (
    <View style={{ flex: 1 }}>
      {tab === "race" && <RaceScreen />}
      {tab === "generate" && <GenerateScreen />}
      {tab === "context" && <ContextoScreen />}
      {tab === "outputs" && <OutputsScreen />}
      {tab === "voices" && <VoicesScreen />}
      {tab === "settings" && <SettingsScreen />}
    </View>
  );
}

export default function App() {
  const fetchConfig = useConfigStore((s) => s.fetch);
  const [tab, setTab] = useState<TabKey>("race");

  useEffect(() => {
    fetchConfig();
    cleanupTemp().catch(() => {});
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    let sent = false;

    const stopAll = () => {
      if (sent) {
        return;
      }
      sent = true;
      try {
        const endpoint = `${window.location.origin}/cancel_all`;
        if (navigator.sendBeacon) {
          navigator.sendBeacon(endpoint, new Blob([], { type: "text/plain" }));
        } else {
          fetch(endpoint, {
            method: "POST",
            keepalive: true,
          }).catch(() => {});
        }
      } catch {
        // no-op
      }
    };

    window.addEventListener("beforeunload", stopAll);

    return () => {
      window.removeEventListener("beforeunload", stopAll);
    };
  }, []);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
      <StatusBar style="light" />
      <View
        style={{
          backgroundColor: colors.surface,
          borderBottomWidth: 1,
          borderBottomColor: colors.border,
          paddingHorizontal: 16,
          paddingTop: 16,
          paddingBottom: 12,
        }}
      >
        <Text style={{ color: colors.text, fontSize: 22, fontWeight: "700" }}>
          TrueVoice
        </Text>
        <Text style={{ color: colors.textDim, marginTop: 4 }}>
          Sintesis de voz, gestion de voces y narracion de carrera
        </Text>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{
          paddingHorizontal: 12,
          paddingVertical: 10,
          gap: 8,
          backgroundColor: colors.surface,
          borderBottomWidth: 1,
          borderBottomColor: colors.border,
        }}
        style={{ flexGrow: 0 }}
      >
        {TABS.map((item) => {
          const active = item.key === tab;
          return (
            <Pressable
              key={item.key}
              onPress={() => setTab(item.key)}
              style={{
                paddingHorizontal: 14,
                paddingVertical: 8,
                borderRadius: 999,
                backgroundColor: active ? colors.primary : colors.surfaceLight,
                borderWidth: 1,
                borderColor: active ? colors.primary : colors.border,
              }}
            >
              <Text style={{ color: active ? "#ffffff" : colors.text, fontWeight: "600" }}>
                {item.title}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>

      <View style={{ flex: 1 }}>
        <AllScreens tab={tab} />
      </View>
    </SafeAreaView>
  );
}
