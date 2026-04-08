# AGENTS.md - TrueVoice

Contexto obligatorio para cualquier agente que trabaje en este repositorio.

> MANDATO DE MANTENIMIENTO DE DOCUMENTACION (OBLIGATORIO)
>
> Cualquier cambio en implementacion o despliegue debe actualizar este archivo en el mismo commit.
> Secciones minimas a mantener: Mapa de Archivos, API Endpoints, Entorno de Desarrollo, Arquitectura.

---

## REGLAS OBLIGATORIAS DE DESARROLLO

### 1. Workflow de commits

- **Un commit por cambio logico.** No acumular cambios sin commitear.
- **NUNCA eliminar ni sobreescribir archivos fuente que funcionan** sin antes verificar que el reemplazo compila y la app se carga correctamente.
- Todos los archivos fuente del frontend (`truevoice-web/app/*.tsx`, `truevoice-web/src/**`) **DEBEN estar commiteados en git**. No depender de archivos que solo existen en disco.

### 2. Tests obligatorios

- **Es OBLIGATORIO ejecutar tests de integracion y E2E antes de dar por finalizado cualquier cambio.**
- Backend Go: `cd truevoice-go && go test ./...`
- Frontend TypeScript: `cd truevoice-web && node node_modules\typescript\bin\tsc --noEmit`
- Tests E2E de API: `cd truevoice-go && go test ./internal/server -run TestE2E -v`
- Si un test falla, el cambio **NO esta completo**. Corregir antes de continuar.

### 3. Build y verificacion visual

Despues de cambios frontend:
```bash
cd truevoice-web
node node_modules\.bin\expo.cmd export --platform web
# Copiar dist/ a truevoice-go/internal/server/webdist/
cd ..\truevoice-go
go build ./...
go run .\cmd\truevoice
# Verificar visualmente TODAS las pestañas en http://localhost:8000/app
```

### 4. Arquitectura del frontend — NO MODIFICAR

- El frontend usa **App.tsx con sistema de pestañas manual** (TabKey, TABS array, display flex/none).
- **NO usar Expo Router** (`app/_layout.tsx` es vestigial, no se usa en produccion).
- `index.ts` importa `App.tsx` via `registerRootComponent(App)`.
- Cada pantalla se importa directamente en App.tsx desde `./app/<nombre>`.

### 5. Lectura de AGENTS.md por directorio

Antes de modificar codigo en un subdirectorio, **leer el AGENTS.md de ese directorio** si existe.
Directorios que tienen AGENTS.md propio:
- `truevoice-go/AGENTS.md`
- `truevoice-web/AGENTS.md`

### 6. Release e instalador (obligatorio)

- **Cada vez que se cree una release, es obligatorio regenerar el instalador Windows en `dist/TrueVoiceInstaller.exe`.**
- Comando canonico:
  - `cd dist`
  - `powershell -ExecutionPolicy Bypass -File .\build_installer.ps1`
- El instalador debe:
  - Crear acceso directo de escritorio `TrueVoice.lnk`.
  - Ejecutar bootstrap durante la instalacion.
  - Descargar en instalacion (no en primer arranque) VibeVoice y el modelo `microsoft/VibeVoice-1.5b`.
  - Mostrar progreso/estado de instalacion (instalando, dependencias, descarga de modelo, etc.).

---

## Resumen del Proyecto

TrueVoice es una aplicacion TTS con clonacion de voz basada en VibeVoice.
La aplicacion productiva usa:
- Backend principal en Go (`truevoice-go/cmd/truevoice` + `truevoice-go/internal/*`)
- Frontend Expo Web exportado y embebido en el binario Go (`truevoice-go/internal/server/webdist`)
- Sidecar Python de VibeVoice solo para inferencia (`vibevoice_app.py`, `inference_wrapper.py`, `patches.py`, `VibeVoice/`)

Se elimino el backend Python/Streamlit legado.

## Arquitectura

```text
Browser
  |
Go HTTP Server (:8000)  <- truevoice-go/cmd/truevoice/main.go
  |  API + static web embed
  |
  +- internal/generation  -> bootstrap runtime Python + subprocess vibevoice_app.py
  +- internal/race        -> parser XML rFactor2 + export Excel/CSV
  |                        + prompts de intro/eventos usando contexto narrativo en uso
  +- internal/voices      -> resolucion de voces
  +- internal/config      -> persistencia frontend_config.json
  +- internal/contexts    -> plantillas de contexto para narracion

Python sidecar:
  vibevoice_app.py -> inference_wrapper.py -> VibeVoice model (HuggingFace)
```

## Mapa de Archivos

```text
TrueVoice/
+- truevoice-go/
|  +- cmd/truevoice/main.go
|  +- internal/server/              # HTTP router, handlers, static embed
|  +- internal/generation/          # TTS generation + sidecar management
|  +- internal/race/                # Race XML parser, sessions, CSV export
|  +- internal/voices/              # Voice file resolution
|  +- internal/config/              # frontend_config.json persistence
|  +- internal/contexts/            # Context templates for narration
|  +- AGENTS.md                     # Backend-specific rules
+- truevoice-web/                    # Fuente Expo Web
|  +- App.tsx                        # Entry point con sistema de tabs manual
|  +- index.ts                       # registerRootComponent(App)
|  +- app/carrera.tsx                # Pantalla Carrera (narracion)
|  +- app/generar.tsx                # Pantalla Generar (TTS tasks)
|  +- app/contexto.tsx               # Pantalla Contexto (plantillas)
|  +- app/outputs.tsx                # Pantalla Audios
|  +- app/voices.tsx                 # Pantalla Voces
|  +- app/settings.tsx               # Pantalla Config
|  +- src/api.ts                     # Cliente HTTP axios
|  +- src/theme.ts                   # Tema y estilos compartidos
|  +- src/stores/                    # Zustand stores
|  +- AGENTS.md                      # Frontend-specific rules
+- vibevoice_app.py                  # CLI sidecar
+- inference_wrapper.py              # Wrapper de inferencia
+- patches.py                        # Parches de compatibilidad de runtime (VibeVoice/Transformers/Torch)
+- VibeVoice/                        # Paquete VibeVoice
+- frontend_config.json              # Config persistente
+- contexts/                         # Contextos JSON storage
+- voices/
+- api_outputs/
+- temp_outputs/
+- race_sessions/
+- dist/                            # Instalador Windows + debug launcher
- AGENTS.md
- README.md
+- AGENTS.md
+- README.md
+- GIT.md
+- ASANA.md
+- SUBAGENTS.md
+- CONSTANTS.md
```

## Dependencias

Runtime principal:
- Go (backend)
- Python 3.11+ (solo sidecar VibeVoice)
- FFmpeg

Dependencias Python del sidecar:
- torch / torchaudio
- transformers, accelerate, huggingface_hub
- soundfile, scipy, datasets, diffusers, peft, librosa
- VibeVoice editable (`pip install -e ./VibeVoice`)
- En CPU, `inference_wrapper.py` fuerza `attn_implementation="eager"` para evitar el requisito SDPA de Transformers en runtimes con torch antiguo.

## Variables de Entorno

| Variable | Defecto | Proposito |
|----------|---------|-----------|
| TRUEVOICE_RUNTIME_DIR | `<install_dir>/runtime` en instalador; si no, `%LOCALAPPDATA%/TrueVoice/runtime` | Fuerza la ruta del runtime Python/modelos para evitar problemas de perfiles roaming |
| HF_HOME | ~/.cache/huggingface | Cache de modelos |
| TRANSFORMERS_CACHE | $HF_HOME/transformers | Cache transformers |
| MKL_NUM_THREADS | 0 | Paralelismo MKL |
| OPENBLAS_NUM_THREADS | 0 | Paralelismo OpenBLAS |
| NUMEXPR_NUM_THREADS | 0 | Paralelismo NumExpr |
| TOKENIZERS_PARALLELISM | true | Tokenizers HF |

## API Endpoints (Go)

### Estado y setup
- GET /
- GET /setup/status
- POST /setup/bootstrap
- GET /models

### Config
- GET /config
- PUT /config

### Voces
- GET /voices
- POST /voices/upload
- DELETE /voices/{name}

### Generacion
- POST /generate
- GET /audio/{audio_id}
- GET /progress/{progress_id}
- POST /cancel/{progress_id}
- POST /cancel_all
- POST /confirm_save

### Outputs
- GET /outputs
- DELETE /outputs/delete
- POST /cleanup_temp

### Contextos
- GET /contexts
- GET /contexts/state
- GET /contexts/{name}
- POST /contexts/save  # si el nombre ya existe, guarda como "Nombre (1)", "Nombre (2)", etc.
- POST /contexts/load/{name}
- DELETE /contexts/{name}

### Race
- POST /race/parse
- POST /race/intro
- POST /race/descriptions
- GET /race/sessions
- GET /race/sessions/{name}
- POST /race/sessions/{name}
- DELETE /race/sessions/{name}
- POST /race/csv?name=<nombre>
- GET /race/sessions/{name}/csv

### Ollama proxy
- GET /ollama/models
- POST /ollama/generate

### Browse (directory picker)
- GET /browse/drives
- GET /browse/folders

## Pipeline de Sintesis

1. Go recibe POST /generate
2. Resuelve voz (internal/voices)
3. Asegura runtime Python (bootstrap)
4. Ejecuta `vibevoice_app.py` como subprocess
5. Parsea progreso en stdout y actualiza store en memoria
6. Guarda en temp_outputs y confirma/mueve a destino

## Entorno de Desarrollo

### Local

```bash
# 1) Exportar web de Expo (si hubo cambios frontend)
cd truevoice-web
node .\node_modules\expo\bin\cli export --platform web
# copiar dist/ a truevoice-go/internal/server/webdist/

# 2) Ejecutar backend Go
cd ..\truevoice-go
go run .\cmd\truevoice
```

### Build instalador Windows (single EXE)

```bash
cd dist
powershell -ExecutionPolicy Bypass -File .\build_installer.ps1
# Genera: dist/TrueVoiceInstaller.exe
# Incluye debug_launcher.cmd y debug_launcher.ps1
```

Notas de instalacion:
- El instalador crea acceso directo de escritorio (`TrueVoice.lnk`) al launcher.
- Durante la instalacion se ejecuta bootstrap del runtime para descargar dependencias de VibeVoice y el modelo `microsoft/VibeVoice-1.5b`.

Servicios:
- App + API: http://localhost:8000/app
- Health: http://localhost:8000/
- Docs/API test: usar endpoints REST desde cliente HTTP
- Ollama externo: http://localhost:11434

## Asana MCP Integration

Proyecto canonico: TrueVoice (GID `1213903547619538`, workspace `1213846793386214`).

Secciones board:
- Pending
- In Progress
- In Hold
- Done

Si falla MCP con `invalid_token`, seguir el protocolo de AGENTS/ASANA.md (auth -> update-mcp -> reintentar -> reiniciar IDE si persiste).

## Idioma

UI y narracion de carrera en espanol (castellano).
