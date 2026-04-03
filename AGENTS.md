# AGENTS.md - TrueVoice

Contexto obligatorio para cualquier agente que trabaje en este repositorio.

> MANDATO DE MANTENIMIENTO DE DOCUMENTACION (OBLIGATORIO)
>
> Cualquier cambio en implementacion o despliegue debe actualizar este archivo en el mismo commit.
> Secciones minimas a mantener: Mapa de Archivos, API Endpoints, Entorno de Desarrollo, Arquitectura.

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
  +- internal/race        -> parser XML rFactor2 + export Excel
  +- internal/voices      -> resolucion de voces
  +- internal/config      -> persistencia frontend_config.json

Python sidecar:
  vibevoice_app.py -> inference_wrapper.py -> VibeVoice model (HuggingFace)
```

## Mapa de Archivos

```text
TrueVoice/
+- truevoice-go/
|  +- cmd/truevoice/main.go
|  +- internal/server/
|  +- internal/generation/
|  +- internal/race/
|  +- internal/voices/
|  +- internal/config/
+- truevoice-web/                    # Fuente Expo Web
+- vibevoice_app.py                  # CLI sidecar
+- inference_wrapper.py              # Wrapper de inferencia
+- patches.py                        # Parches de compatibilidad VibeVoice
+- VibeVoice/                        # Paquete VibeVoice
+- frontend_config.json              # Config persistente
+- voices/
+- api_outputs/
+- temp_outputs/
+- race_sessions/
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

## Variables de Entorno

| Variable | Defecto | Proposito |
|----------|---------|-----------|
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

### Race
- POST /race/excel?name=<nombre>

### Mantenimiento
- GET /outputs
- DELETE /outputs/delete
- POST /cleanup_temp

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
