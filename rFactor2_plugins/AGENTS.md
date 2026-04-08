# AGENTS.md — rFactor2_plugins

## Propósito

Plugin C++ (DLL) para rFactor 2 que captura eventos de carrera en tiempo real
y genera un JSON importable por el backend Go de TrueVoice.

## Estructura

```
rFactor2_plugins/
├── CMakeLists.txt              # Build system (CMake → Visual Studio)
├── README.md                   # Instrucciones de compilación e instalación
├── include/
│   ├── InternalsPlugin.hpp     # SDK header rF2 V07 (NO modificar)
│   └── PluginObjects.hpp       # Base class del SDK (NO modificar)
└── src/
    ├── TrueVoicePlugin.h/cpp   # Entry point DLL + callbacks rF2
    ├── EventDetector.h/cpp     # Lógica de detección de eventos
    └── JsonWriter.h/cpp        # Serialización JSON sin deps externas
```

## Reglas

1. **NO modificar los headers del SDK** en `include/` — provienen del repositorio oficial.
2. Los umbrales de detección son constantes en `EventDetector.h` — ajustar ahí si es necesario.
3. El JSON de salida debe ser compatible con `ParsePluginJSON()` en `truevoice-go/internal/race/plugin_parser.go`.
4. Compilar siempre como **x64** (rFactor 2 moderno es 64-bit).
5. Usar `#pragma pack(push, 4)` en todas las estructuras compartidas con rF2.

## Build

```powershell
mkdir build; cd build
cmake .. -G "Visual Studio 17 2022" -A x64
cmake --build . --config Release
```

## Tipos de evento

`collision_vehicle`, `collision_wall`, `off_track`, `proximity`,
`overtake`, `penalty`, `pit_entry`, `fastest_lap`
