# TrueVoice rFactor 2 Plugin

Plugin DLL para rFactor 2 que captura eventos de carrera en tiempo real y genera un archivo JSON importable por TrueVoice.

## Eventos capturados

| Evento | Tipo JSON | Detección |
|--------|-----------|-----------|
| Choque piloto-piloto | `collision_vehicle` | Impacto + vehículo cercano (<25m) |
| Choque contra muro/valla | `collision_wall` | Impacto sin vehículo cercano |
| Salida de pista | `off_track` | 2+ ruedas en grass/dirt/gravel |
| Proximidad <0.5s | `proximity` | `mTimeBehindNext < 0.5` |
| Adelantamiento | `overtake` | Cambio de `mPlace` entre dos pilotos |
| Sanción | `penalty` | Incremento de `mNumPenalties` |
| Entrada en boxes | `pit_entry` | Transición `mPitState` 3→4 |
| Vuelta rápida | `fastest_lap` | Nuevo `mBestLapTime` global |

Cada evento incluye:
- Timestamp absoluto (`timestamp_et`) y relativo al inicio de carrera (`timestamp_hms` en HH:MM:SS)
- Vuelta actual y distancia en circuito (`lap`, `lap_dist`)
- Coordenadas de posición (`position.x/y/z`)
- **Snapshot de posiciones de TODOS los pilotos** (`driver_positions[]`) para visualización en mapa

## Requisitos para compilar

- **Windows 10/11** (x64)
- **Visual Studio 2019** o posterior (con componente "Desktop development with C++")
- **CMake 3.20+**

## Compilación

```powershell
cd rFactor2_plugins
mkdir build
cd build
cmake .. -G "Visual Studio 17 2022" -A x64
cmake --build . --config Release
```

El resultado es `build\Release\TrueVoicePlugin.dll`.

> Si usas VS 2019, cambia el generador a `"Visual Studio 16 2019"`.

## Instalación en rFactor 2

1. Copia `TrueVoicePlugin.dll` a la carpeta de plugins de rFactor 2:
   ```
   <rFactor 2>\Bin64\Plugins\
   ```
   Típicamente: `C:\Program Files (x86)\Steam\steamapps\common\rFactor 2\Bin64\Plugins\`

2. Inicia rFactor 2. El plugin se activa automáticamente.

3. Al finalizar cada sesión (carrera, clasificación, práctica), el plugin genera:
   ```
  <rFactor 2>\UserData\Log\{timestamp}_{nombre_circuito}_events.json
   ```
  Ejemplo: `20260409_014950_Suzuka_events.json`

4. Importa ese archivo JSON en TrueVoice desde la pestaña **Carrera** > **Importar JSON Plugin**.

## Formato del JSON de salida

```json
{
  "plugin_version": "1.0.0",
  "track_name": "Suzuka",
  "track_length": 5819.8,
  "session_type": "race",
  "race_start_et": 234.69,
  "num_laps": 39,
  "drivers": [
    {"id": 68, "name": "jesusmolero", "vehicle": "RaceF1_26", "grid_pos": 1}
  ],
  "events": [
    {
      "type": "collision_vehicle",
      "timestamp_et": 456.70,
      "timestamp_hms": "00:03:42",
      "lap": 3,
      "lap_dist": 2340.5,
      "drivers_involved": ["PilotoA", "PilotoB"],
      "position": {"x": 120.5, "y": 0.2, "z": -450.1},
      "impact_magnitude": 1523.4,
      "driver_positions": [
        {"name": "PilotoA", "place": 1, "pos": {"x": 120.5, "y": 0.2, "z": -450.1}, "lap_dist": 2340.5, "lap": 3}
      ]
    }
  ]
}
```

## Umbrales configurables (constantes en EventDetector.h)

| Constante | Valor | Descripción |
|-----------|-------|-------------|
| `COLLISION_MAGNITUDE_THRESHOLD` | 200.0 | Magnitud mínima de impacto para registrar colisión |
| `COLLISION_DEDUP_SECONDS` | 5.0 | Segundos entre colisiones del mismo vehículo para dedup |
| `COLLISION_VEHICLE_DISTANCE` | 25.0 | Distancia máxima (metros) para considerar colisión vehículo-vehículo |
| `PROXIMITY_TRIGGER_GAP` | 0.5 | Umbral de gap (segundos) para evento de proximidad |
| `PROXIMITY_RESET_GAP` | 1.0 | Gap (segundos) para resetear estado de proximidad (histéresis) |
| `OVERTAKE_DEDUP_SECONDS` | 10.0 | Cooldown entre adelantamientos del mismo par de pilotos |
| `OFF_TRACK_DEDUP_SECONDS` | 5.0 | Cooldown entre salidas de pista del mismo piloto |
| `OFF_TRACK_MIN_WHEELS` | 2 | Mínimo de ruedas fuera de pista para registrar evento |

## Notas técnicas

- El plugin hereda de `InternalsPluginV07` (versión más reciente del SDK)
- Usa `UpdateScoring` (~5 Hz) para: adelantamientos, sanciones, boxes, vuelta rápida, proximidad
- Usa `UpdateTelemetry` (~50 Hz) para: colisiones y salidas de pista
- Los headers del SDK provienen de [TheIronWolfModding/rF2SharedMemoryMapPlugin](https://github.com/TheIronWolfModding/rF2SharedMemoryMapPlugin) (MIT)
- No tiene dependencias externas — usa únicamente la librería estándar de C++17
- La detección de la **razón del pit stop** es heurística (no hay campo explícito en el SDK)
- El **tipo de sanción** (Drive Through vs Stop/Go) no está disponible en el SDK — solo el contador `mNumPenalties`
