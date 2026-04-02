import { Tabs } from "expo-router";
import { useEffect } from "react";
import { useConfigStore } from "../src/stores/useConfigStore";
import { cleanupTemp } from "../src/api";

export default function Layout() {
  const fetchConfig = useConfigStore((s) => s.fetch);

  useEffect(() => {
    fetchConfig();
    cleanupTemp().catch(() => {});
  }, []);

  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: "#1a1a2e" },
        headerTintColor: "#e0e0e0",
        tabBarStyle: { backgroundColor: "#1a1a2e", borderTopColor: "#2a2a4a" },
        tabBarActiveTintColor: "#64b5f6",
        tabBarInactiveTintColor: "#888",
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: "Generar Audio", tabBarLabel: "🗣️ Generar" }}
      />
      <Tabs.Screen
        name="race"
        options={{ title: "Narración de Carrera", tabBarLabel: "📝 Carrera" }}
      />
      <Tabs.Screen
        name="outputs"
        options={{ title: "Audios Generados", tabBarLabel: "📂 Audios" }}
      />
      <Tabs.Screen
        name="voices"
        options={{ title: "Gestionar Voces", tabBarLabel: "🎤 Voces" }}
      />
      <Tabs.Screen
        name="settings"
        options={{ title: "Configuración", tabBarLabel: "⚙️ Config" }}
      />
    </Tabs>
  );
}
