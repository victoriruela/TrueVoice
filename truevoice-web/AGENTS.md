# AGENTS.md - truevoice-web (Frontend Expo Web)

## Arquitectura critica — NO MODIFICAR

- **App.tsx** es el entry point. Usa un sistema de **pestañas manual** (`TabKey`, `TABS` array, `display: flex/none`).
- **NO usar Expo Router.** `app/_layout.tsx` es vestigial y no se usa en produccion.
- `index.ts` importa `App.tsx` via `registerRootComponent(App)`.
- Cada pantalla se importa directamente en `App.tsx` desde `./app/<nombre>`.

## Estructura

```text
truevoice-web/
+- App.tsx                  # Entry point. Sistema de tabs manual (TabKey, TABS[])
+- index.ts                 # registerRootComponent(App) — NO CAMBIAR
+- app.json                 # Config Expo
+- tsconfig.json
+- package.json
+- app/
|  +- _layout.tsx           # VESTIGIAL — NO usar. Expo Router no esta activo.
|  +- index.tsx             # VESTIGIAL — solo usado por Expo Router, ignorar.
|  +- carrera.tsx           # 📝 Narracion de Carrera (sesiones, XML, CSV, eventos, audio)
|  +- generar.tsx           # 🗣️ Generar Audio (tareas TTS, progreso, audio player)
|  +- contexto.tsx          # 📋 Contexto (plantillas de contexto para narracion)
|  +- outputs.tsx           # 🔊 Audios Generados (listado, player, download, delete)
|  +- voices.tsx            # 🎤 Voces (listar, upload, delete)
|  +- settings.tsx          # ⚙️ Config (modelo, voz, directorio, Ollama)
+- src/
   +- api.ts                # Cliente HTTP axios. Todas las llamadas al backend.
   +- theme.ts              # colors + shared StyleSheet
   +- stores/
      +- useConfigStore.ts
      +- useGenerationStore.ts
      +- useOutputStore.ts
      +- useRaceStore.ts
      +- useVoiceStore.ts
      +- useContextStore.ts
```

## Reglas

1. **TypeScript check obligatorio:** `node node_modules\typescript\bin\tsc --noEmit`
2. **Build:** `node node_modules\.bin\expo.cmd export --platform web`
3. **Copiar dist/ a `truevoice-go/internal/server/webdist/`** despues de build.
4. **TODOS los .tsx de app/ DEBEN estar commiteados en git.** No depender de archivos solo en disco.
5. **Usar `<audio>` y `<input type="file">` HTML** en vez de componentes RN — esto es web-only.
6. **Zustand stores** persisten en localStorage. Respetar la key de persistencia.
7. **Theme compartido:** usar `colors` y `shared` de `src/theme.ts`. No crear estilos inline sin necesidad.

## Como añadir una nueva pestaña

1. Crear `app/nueva.tsx` con `export default function NuevaScreen()`.
2. En `App.tsx`:
   - Importar: `import NuevaScreen from "./app/nueva";`
   - Añadir a `TabKey`: `"nueva"`
   - Añadir a `TABS[]`: `{ key: "nueva", title: "Nueva" }`
   - En `AllScreens`, añadir `<View>` con display condicional
3. Si necesita API, añadir funciones en `src/api.ts`.
4. Si necesita estado, crear `src/stores/useNuevaStore.ts` con Zustand.
5. Verificar: `tsc --noEmit`, build, verificar visualmente.

## Prohibiciones

- **NO activar Expo Router como sistema de navegacion.**
- **NO borrar App.tsx ni cambiar index.ts** (a menos que se migre toda la arquitectura).
- **NO crear archivos .tsx fuera de `app/`** para pantallas.
- **NO usar `useEffect` con funciones del store como dependencia** (crea loops infinitos con Zustand).
