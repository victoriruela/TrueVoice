import { Tabs } from "expo-router";
import { useEffect, Component, ReactNode } from "react";
import { View, Text, ScrollView } from "react-native";
import { useConfigStore } from "../src/stores/useConfigStore";
import { cleanupTemp } from "../src/api";

class ErrorBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null };
  static getDerivedStateFromError(e: any) {
    return { error: String(e?.message || e) };
  }
  render() {
    if (this.state.error) {
      return (
        <ScrollView style={{ flex: 1, backgroundColor: "#0f0f23", padding: 16 }}>
          <Text style={{ color: "#ef5350", fontSize: 16, fontWeight: "700", marginBottom: 8 }}>
            ❌ Error en esta pantalla
          </Text>
          <Text style={{ color: "#e0e0e0", fontFamily: "monospace", fontSize: 12 }}>
            {this.state.error}
          </Text>
        </ScrollView>
      );
    }
    return this.props.children;
  }
}

export default function Layout() {
  const fetchConfig = useConfigStore((s) => s.fetch);

  useEffect(() => {
    fetchConfig();
    cleanupTemp().catch(() => {});
  }, []);

  return (
    <ErrorBoundary>
      <Tabs
        screenOptions={{
          headerStyle: { backgroundColor: "#1a1b2e" },
          headerTintColor: "#e0e0e0",
          tabBarStyle: { backgroundColor: "#1a1a2e", borderTopColor: "#2a2a4a" },
          tabBarActiveTintColor: "#64b5f6",
          tabBarInactiveTintColor: "#889",
        }}
      >
        <Tabs.Screen
          name="index"
          options={{ title: "Narración de Carrera", tabBarLabel: "Carrera" }}
        />
        <Tabs.Screen
          name="generar"
          options={{ title: "Generar Audio", tabBarLabel: "Generar" }}
        />
        <Tabs.Screen
          name="carrera"
          options={{ href: null }}
        />
        <Tabs.Screen
          name="race"
          options={{ href: null }}
        />
        <Tabs.Screen
          name="generate"
          options={{ href: null }}
        />
        <Tabs.Screen
          name="caarrera"
          options={{ href: null }}
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
    </ErrorBoundary>
  );
}

