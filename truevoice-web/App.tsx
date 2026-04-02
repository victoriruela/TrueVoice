import React, { useEffect, useState } from "react";
import { StatusBar } from "expo-status-bar";
import { Pressable, SafeAreaView, ScrollView, Text, View } from "react-native";
import GenerateScreen from "./app/index";
import RaceScreen from "./app/race";
import OutputsScreen from "./app/outputs";
import VoicesScreen from "./app/voices";
import SettingsScreen from "./app/settings";
import { cancelAllGenerations, cleanupTemp } from "./src/api";
import { useConfigStore } from "./src/stores/useConfigStore";
import { useGenerationStore } from "./src/stores/useGenerationStore";
import { colors } from "./src/theme";

type TabKey = "generate" | "race" | "outputs" | "voices" | "settings";

const TABS: Array<{ key: TabKey; title: string }> = [
  { key: "generate", title: "Generar" },
  { key: "race", title: "Carrera" },
  { key: "outputs", title: "Audios" },
  { key: "voices", title: "Voces" },
  { key: "settings", title: "Config" },
];

function ScreenContent({ tab }: { tab: TabKey }) {
  switch (tab) {
    case "race":
      return <RaceScreen />;
    case "outputs":
      return <OutputsScreen />;
    case "voices":
      return <VoicesScreen />;
    case "settings":
      return <SettingsScreen />;
    case "generate":
    default:
      return <GenerateScreen />;
  }
}

export default function App() {
  const fetchConfig = useConfigStore((s) => s.fetch);
  const cancelAllInFlight = useGenerationStore((s) => s.cancelAllInFlight);
  const [tab, setTab] = useState<TabKey>("generate");

  useEffect(() => {
    fetchConfig();
    cleanupTemp().catch(() => {});
    // Best-effort cleanup in case browser skipped beforeunload handlers.
    cancelAllGenerations().catch(() => {});
  }, [fetchConfig]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const stopAll = () => {
      // Keepalive fetch is more reliable than async XHR during unload.
      try {
        fetch(`${window.location.origin}/cancel_all`, {
          method: "POST",
          keepalive: true,
        }).catch(() => {});
      } catch {
        // no-op
      }
      cancelAllInFlight().catch(() => {});
    };

    window.addEventListener("beforeunload", stopAll);
    window.addEventListener("pagehide", stopAll);

    return () => {
      window.removeEventListener("beforeunload", stopAll);
      window.removeEventListener("pagehide", stopAll);
    };
  }, [cancelAllInFlight]);

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
        <ScreenContent tab={tab} />
      </View>
    </SafeAreaView>
  );
}
