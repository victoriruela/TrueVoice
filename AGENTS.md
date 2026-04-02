# AGENTS.md - TrueVoice

Contexto completo para cualquier agente IA que trabaje en este proyecto. **Lee este archivo antes de hacer cambios.**

> **MANDATO DE MANTENIMIENTO DE DOCUMENTACIÓN — OBLIGATORIO PARA TODOS LOS AGENTES**
>
> Cualquier agente que modifique la **implementación** (endpoints API, pipeline de síntesis, parsers, modelos de voz)
> o la **infraestructura / despliegue** (Docker, scripts de release, variables de entorno)
> **debe** actualizar este archivo en el mismo commit que introduce el cambio. Secciones a mantener:
> - `Mapa de Archivos` — añadir / renombrar / eliminar entradas cuando cambien los archivos
> - `API Endpoints` — reflejar cualquier ruta nueva, modificada o eliminada
> - `Despliegue Docker` — reflejar cambios en topología, scripts, variables de entorno
> - `Entorno de Desarrollo` — reflejar cambios en comandos de arranque o servicios Docker
> - `Arquitectura` / `Flujo de Datos` — reflejar cambios estructurales en el pipeline
>
> La documentación desactualizada se trata como un bug.

## Resumen del Proyecto

TrueVoice es una aplicación completa de síntesis de voz con clonación (TTS) basada en [Microsoft VibeVoice](https://github.com/microsoft/VibeVoice). Permite generar audio de alta calidad a partir de texto clonando la voz de un hablante a partir de un archivo WAV de referencia. Incluye un módulo de narración de carreras rFactor2 que parsea archivos XML de resultados, genera textos con IA (Ollama) y sintetiza el audio por evento.

## Arquitectura

**Estado de migración (actual):**
- Backend principal en Go: `truevoice-go/cmd/truevoice` + `truevoice-go/internal/*`
- Frontend objetivo: Expo Web (`truevoice-web`), exportado a web y servido como estático embebido en el binario Go
- Sidecar Python de VibeVoice: bootstrap on-demand vía `GET /setup/status` y `POST /setup/bootstrap`
- Backend Python/Streamlit (`api_server.py`, `frontend.py`) permanece como legado durante transición

```
User (Browser)
    |
Go HTTP Server (:8000)           ← truevoice-go/cmd/truevoice/main.go
    |  API + static web embed (single binary)
    |
    ├── Generation Manager        ← truevoice-go/internal/generation/*
    │     Bootstrap Python runtime + subprocess vibevoice_app.py
    │
    ├── Race Parser               ← truevoice-go/internal/race/*
    │     Parseo XML rFactor2 + sesiones + export XLSX
    │
    ├── Voices / Config           ← truevoice-go/internal/voices + internal/config
    │
    ├── Inference Wrapper         ← inference_wrapper.py (invocado como subprocess)
    │     VoiceMapper + VibeVoice model (HuggingFace)
    │     Directorio de voces → voices/
    |
    ├── Race Parser               ← race_parser.py
    │     Parseo XML rFactor2 → RaceHeader + RaceEvent
    |
    └── Ollama (dependencia externa, opcional)
          Generación de textos de narración de carrera
          http://host.docker.internal:11434 (Docker) | http://localhost:11434 (local)
```

**Arranque nominal**:
- Local: `python launcher.py` (arranca API + Frontend) ó dos terminales separadas.
- Docker: `docker compose up --build` (auto-arranca ambos servicios; Ollama corre en el host).

**Startup sequence**: La API espera a estar `healthy` antes de que el frontend se inicie
(`condition: service_healthy` en `docker-compose.yml`).

## Mapa de Archivos

```
TrueVoice/
├── truevoice-go/               # Backend Go (cmd/truevoice + internal/*); API principal en migración
│   ├── cmd/truevoice/main.go   # Entry point del binario único en Go
│   └── internal/
│       ├── server/             # Router HTTP + static embed (webdist exportado desde truevoice-web)
│       ├── generation/         # Generate/progress/cancel + bootstrap sidecar Python
│       ├── race/               # Parser carrera + sesiones + Excel
│       ├── voices/             # Gestión/resolución de voces
│       └── config/             # Persistencia frontend_config.json
├── truevoice-web/              # Frontend Expo (web-only) con Zustand; export web -> truevoice-go/internal/server/webdist/
├── api_server.py               # FastAPI REST API; endpoints de generación, voces, progreso
├── frontend.py                 # Streamlit UI; configuración, generación, narración de carrera
├── inference_wrapper.py        # Wrapper de inferencia VibeVoice (ejecutado como subprocess)
├── vibevoice_app.py            # CLI de VibeVoice; clonación desde YouTube, archivos locales
├── race_parser.py              # Parser XML rFactor2; extrae RaceHeader + RaceEvent (3 tipos)
├── patches.py                  # Parches de compatibilidad aplicados antes de importar vibevoice
├── launcher.py                 # Lanzador automático (API + Frontend + abre navegador)
├── installer.py                # Script de instalación de dependencias
├── frontend_config.json        # Configuración persistente del frontend (voz, carpetas, Ollama)
├── generate_drives.ps1         # Genera docker-compose.override.yml con los discos Windows montados
├── Dockerfile.api              # Imagen Docker del backend (Python 3.11, torch CPU, ffmpeg)
├── Dockerfile.frontend         # Imagen Docker del frontend (Python 3.11, streamlit)
├── docker-compose.yml          # Orquestación: servicios api + frontend; volúmenes persistentes
├── docker-compose.override.yml # AUTO-GENERADO por generate_drives.ps1 — NO editar manualmente
├── VibeVoice/                  # Subpaquete Microsoft VibeVoice (instalado con pip install -e)
│   └── vibevoice/              # Paquete Python principal de VibeVoice
├── voices/                     # Archivos WAV de referencia para clonación de voz
├── api_outputs/                # Audios generados (persistidos entre reinicios vía volumen Docker)
├── temp_outputs/               # Archivos temporales durante generación (se limpian periódicamente)
├── race_sessions/              # Sesiones de narración guardadas (JSON + Excel por carrera)
├── archivos_ejemplo/           # Archivos XML de ejemplo para pruebas del race parser
├── AGENTS.md                   # ESTE ARCHIVO — contexto completo para agentes IA
├── SUBAGENTS.md                # Flujo operativo Asana + subagentes (paralelizacion)
├── GIT.md                      # Flujo git, convenciones de commits, procedimiento de release
├── ASANA.md                    # Integración Asana MCP
├── CONSTANTS.md                # Índice de archivos de constantes por dominio
└── README.md                   # Documentación de usuario (español)
```

## Dependencias

```
# API / Inferencia
fastapi                  # API REST
uvicorn                  # ASGI runner
python-multipart         # File upload
torch / torchaudio       # PyTorch (CPU-only en Docker)
transformers             # HuggingFace transformers (VibeVoice model)
accelerate               # HuggingFace accelerate (model loading)
huggingface_hub          # Descarga de modelos HuggingFace
soundfile                # Lectura/escritura de audio WAV
scipy                    # Procesamiento de señal
numpy<2                  # Compatibilidad binaria con torch/torchaudio CPU usados por VibeVoice
yt-dlp                   # Extracción de audio desde YouTube
moviepy                  # Procesamiento de vídeo
pydantic                 # Validación de datos (via FastAPI)
requests                 # HTTP (frontend → API, frontend → Ollama)
openpyxl                 # Exportación Excel de narración de carrera

# Frontend
streamlit                # UI web interactiva
```

**Dependencia del sistema**: [FFmpeg](https://ffmpeg.org/) instalado y en el PATH (requerido para procesamiento
de audio/vídeo). Pre-instalado en el contenedor Docker de la API.

**Python**: 3.11 (especificado en Dockerfiles).

## Variables de Entorno

| Variable | Defecto | Propósito |
|----------|---------|---------|
| `API_URL` | `http://localhost:8000` | URL de la API para el frontend (Python server-side) |
| `CONFIG_DIR` | directorio del script | Directorio donde reside `frontend_config.json` |
| `HF_HOME` | `~/.cache/huggingface` | Caché de modelos HuggingFace |
| `TRANSFORMERS_CACHE` | `$HF_HOME/transformers` | Caché de transformers |
| `MKL_NUM_THREADS` | `0` (auto) | Hilos MKL (0 = automático) |
| `OPENBLAS_NUM_THREADS` | `0` (auto) | Hilos OpenBLAS |
| `NUMEXPR_NUM_THREADS` | `0` (auto) | Hilos NumExpr |
| `TOKENIZERS_PARALLELISM` | `true` | Paralelismo en tokenizers HuggingFace |

En Docker el frontend apunta a `http://api:8000` (nombre de servicio Docker) en lugar de `localhost`.

## API Endpoints

### Estado y voces

#### `GET /`
Health check. Devuelve `{"status": "ok", "service": "TrueVoice API", "version": "2.0.0"}` en el backend Go.

#### `GET /models`
Lista modelos disponibles para síntesis.
Devuelve array de `ModelInfo {id, name, size}`.

#### `GET /voices`
Lista las voces disponibles en el directorio configurado.
Query param opcional: `directory` (ruta absoluta al directorio de voces alternativo).
Devuelve array de `VoiceInfo {name, filename, alias}`.

#### `POST /voices/upload`
Sube un nuevo archivo de voz WAV. Multipart form: `audio_file` (UploadFile), `voice_name` (Form string).
El archivo se guarda en `voices/{name}.wav`.

#### `DELETE /voices/{name}`
Elimina una voz personalizada de `voices/`. No puede eliminar voces del directorio interno de VibeVoice.

### Generación de audio

#### `POST /generate`
Genera audio a partir de texto. Body JSON (`GenerateRequest`):
- `text` (requerido): texto a sintetizar
- `voice_name`: nombre de voz o ruta absoluta al WAV (default: `"Alice"`)
- `custom_output_name`: nombre del archivo de salida (sin extensión)
- `output_directory`: directorio de salida personalizado
- `audio_id_hint`: sugerencia de ID para rastreo de progreso
- `model`: modelo HuggingFace (default: `"microsoft/VibeVoice-1.5b"`)
- `output_format`: `"wav"`, `"mp3"`, `"flac"`, `"ogg"` (default: `"wav"`)
- `cfg_scale`: 0.5–5.0 (default: `2.0`)
- `ddpm_steps`: 1–200 (default: `30`)
- `disable_prefill`: boolean — desactiva clonación de voz

La generación se ejecuta como subprocess (`vibevoice_app.py`). El progreso se escribe en `PROGRESS_STORE`.
Devuelve `GenerateResponse {success, message, audio_id, filename, is_temp}`.

#### `GET /audio/{audio_id}`
Descarga el archivo de audio generado por su ID. Busca en `temp_outputs/` y `api_outputs/`.

#### `GET /progress/{progress_id}`
Consulta el progreso de una generación activa. Devuelve `{total, current, status, error?, start_time, last_update}`.

#### `POST /cancel/{progress_id}`
Cancela una generación en curso enviando SIGTERM al subprocess activo.

#### `POST /cancel_all`
Cancela todas las generaciones en curso. Devuelve `{cancelled}` con el número de procesos cancelados.

#### `POST /confirm_save`
Mueve un archivo de `temp_outputs/` a `api_outputs/` (o a `output_directory` si se especifica).
Body: `SaveRequest {audio_id, output_directory?}`.

#### `GET /setup/status`
Estado del sidecar Python (bootstrap/runtime).
Devuelve `{running, ready, stage, error, last_update, python_path, runtime_path}`.

#### `POST /setup/bootstrap`
Fuerza bootstrap del runtime Python para VibeVoice (primer arranque o recuperación).
Devuelve `{status, python_path, runtime_path}`.

### Mantenimiento

#### `GET /outputs`
Lista los archivos generados en `api_outputs/`. Devuelve array de `OutputFileInfo`.

#### `DELETE /outputs/delete`
Elimina archivos de `api_outputs/` por lista de nombres.
Soporta `filenames[]` por query y/o body JSON.

#### `POST /cleanup_temp`
Elimina todos los archivos de `temp_outputs/` con más de 1 hora de antigüedad.

## Pipeline de Síntesis de Voz

### Flujo `POST /generate`

1. Resolución de voz: `_resolve_voice(voice_name, directory)` → ruta absoluta WAV
2. Validación del formato de salida (`wav | mp3 | flac | ogg`)
3. Inicialización de entrada en `PROGRESS_STORE` con estado `"starting"`
4. Construcción del comando subprocess:
   `python vibevoice_app.py --text ... --voice-name <ruta_absoluta> --model ... --output ... --cfg-scale ... --ddpm-steps ...`
  Nota: el formato final se infiere por la extensión de `--output` (`.wav`, `.mp3`, `.flac`, `.ogg`); no existe flag `--output-format` en el CLI.
5. Ejecución como subprocess con captura de stdout/stderr en tiempo real
6. El progreso se parsea de la salida del subprocess y se actualiza en `PROGRESS_STORE`
7. En éxito: archivo escrito en `temp_outputs/`, estado `"done"`
8. El cliente llama a `POST /save/{audio_id}` para moverlo al destino final

### Inferencia (`inference_wrapper.py`)

Ejecutado como proceso independiente por `vibevoice_app.py`:
1. Configura `PYTHONPATH` para encontrar el paquete `vibevoice` en `VibeVoice/`
  y añade la raíz del proyecto a `sys.path` para importar módulos locales (ej. `patches.py`)
2. Aplica parches de compatibilidad (`patches.py`) antes de importar VibeVoice
3. Instancia `VoiceMapper` — mapea nombres de voz a rutas WAV en `voices/`
4. Carga el modelo VibeVoice desde HuggingFace (caché en `HF_HOME`)
5. Sintetiza el audio usando el WAV de referencia para clonar la voz
6. Escribe el archivo de salida en el formato especificado

### Resolución de voces (`_resolve_voice`)

Prioridad de búsqueda:
1. Ruta absoluta existente → devuelve directamente
2. Coincidencia en `DEFAULT_VOICES` (tabla de alias) → busca en directorio custom, luego `voices/`, luego `VibeVoice/demo/voices/`
3. Fichero `{name}.wav` en el directorio de voces activo
4. Coincidencia exacta de stem (case-insensitive) entre todos los WAV del directorio
5. Coincidencia parcial de stem

**Voces por defecto integradas** (de `VibeVoice/demo/voices/`):
`Alice`, `Carter`, `Frank`, `Mary`, `Maya`, `Samuel`, `Anchen`, `Bowen`, `Xinran`

## Race Parser (`race_parser.py`)

Parsea archivos XML de resultados de carrera rFactor2 y extrae tres tipos de eventos:

### Tipos de evento

| Tipo | Significado | Fuente |
|------|-------------|--------|
| 1 | Adelantamiento | Inferido de cambios de posición entre vueltas |
| 2 | Choque entre pilotos | `<Incident>` con "another vehicle", deduplicado |
| 3 | Choque contra el muro | `<Incident>` con "Wing", deduplicado |

### Deduplicación

- Choques con el mismo timestamp y pilotos implicados → se registra solo una vez
- Dos eventos del mismo tipo e implicados con menos de **7 segundos** de diferencia → solo se conserva el primero

### Estructuras de datos

- `RaceHeader`: `track_event`, `track_length` (metros), `race_laps`, `num_drivers`, `grid_order[]`, `intro_text`
- `RaceEvent`: `lap`, `timestamp`, `event_type`, `summary`, `description` (rellena la IA)
- `RaceSession`: `intro_text`, `intro_audio`, `header`, `events[]`, `event_audios{}`,
  `hidden_event_indices[]`, `selected_event_indices[]`

## Módulo de Narración de Carrera (Frontend)

### Flujo de trabajo completo

1. **Parseo XML** → `race_parser.py` extrae header + eventos
2. **Generación de intro con Ollama** → prompt al LLM estilo comentarista F1
3. **Generación de descripciones por evento** → una llamada Ollama por evento; editable manualmente
4. **Síntesis de audio** → `POST /generate` por texto (intro + cada evento)
5. **Guardado de sesión** → JSON en `race_sessions/` + Excel (.xlsx) con columnas:
   Vuelta, Timestamp, Tipo, Resumen, Descripción IA, Audio
6. **Edición de eventos en frontend Expo**:
  - Generación individual de texto IA por evento
  - Generación individual de audio por evento
  - Inserción de eventos intermedios
  - Ocultar/mostrar eventos
  - Selección múltiple + borrado masivo
  - Autosave de estado de ocultos/selección cuando hay sesión activa

### Configuración persistente (`frontend_config.json`)

Se lee y escribe en cada operación relevante del frontend. Contiene: URL Ollama, modelo Ollama,
carpeta de salida de audios, carpeta de textos, voz activa, tareas de generación en curso, etc.

## Flujo de Datos Docker

```
Frontend (truevoice-frontend :8501)
    │  API_URL = http://api:8000
    ▼
API (truevoice-api :8000)
    │  subprocess: python vibevoice_app.py
    ▼
inference_wrapper.py (mismo contenedor)
    │  torch CPU + HuggingFace model
    ▼
HuggingFace cache  ←→  volume: hf_cache → /root/.cache/huggingface

Frontend ──► host.docker.internal:11434 (Ollama, corre en el host)
```

### Volúmenes Docker

| Mount | Propósito |
|-------|---------|
| `hf_cache` → `/root/.cache/huggingface` | Caché modelos HuggingFace (no re-descarga en restart) |
| `./voices` → `/app/voices` | Voces personalizadas (persistidas) |
| `./api_outputs` → `/app/api_outputs` | Audios generados (persistidos) |
| `./temp_outputs` → `/app/temp_outputs` | Archivos temporales de generación |
| `./race_sessions` → `/app/race_sessions` | Sesiones de narración guardadas |
| `./frontend_config.json` → `/app/frontend_config.json` | Config del frontend |
| `c:/` → `/mnt/c` (override) | Acceso al sistema de archivos Windows (browser de carpetas) |

## Asana MCP Integration

Ver [`ASANA.md`](ASANA.md) para detalles completos.
Ver [`SUBAGENTS.md`](SUBAGENTS.md) para el protocolo de paralelización con subagentes.

### Proyecto canónico

El proyecto Asana para este repositorio es **"TrueVoice"**
(GID: `1213903547619538`, workspace: `1213846793386214`).
**Usar siempre este proyecto.** Nunca crear un segundo proyecto.

### Estructura del board

El proyecto usa **Board layout** con cuatro secciones fijas:

| Sección | Significado |
|---------|-------------|
| `Pending` | Tarea creada, no iniciada |
| `In Progress` | Asignada a un subagente, en trabajo activo |
| `In Hold` | Bloqueada o en espera de revisión |
| `Done` | Mergeada y verificada |

### Protocolo de fallo MCP — OBLIGATORIO

El token expira cada hora y el IDE lo cachea. Cuando cualquier `mcp_asana-mcp_*` falle con `invalid_token`:

```
Paso 1 — Refrescar y re-inyectar el token:
    python "$env:USERPROFILE\.claude\asana-mcp\scripts\asana_mcp.py" auth
    python "$env:USERPROFILE\.claude\asana-mcp\scripts\asana_mcp.py" update-mcp

Paso 2 — Reintentar la herramienta MCP inmediatamente.

Paso 3 — Si sigue fallando: PARAR y pedir al usuario que reinicie el IDE.
```

**NUNCA** crear scripts Python alternativos que llamen a la API de Asana directamente.

## Constantes

Todos los valores hardcodeados (puertos, rutas, modelos, parámetros de síntesis, config Asana)
están documentados en [`CONSTANTS.md`](CONSTANTS.md). Consultar ese archivo al trabajar con valores
de configuración específicos.

## Patrones Clave

**Generación como subprocess**: la síntesis de voz se ejecuta en un subprocess independiente
(`vibevoice_app.py`) para aislar el proceso PyTorch del worker FastAPI. El progreso se captura
parseando stdout del subprocess y se almacena en `PROGRESS_STORE` (dict en memoria).

**Resolución de voces en dos pasos**: `api_server.py._resolve_voice()` resuelve el nombre a una
ruta WAV absoluta antes de pasarla al subprocess. El subprocess recibe siempre ruta absoluta, nunca alias.

**Voces Windows desde Docker**: `docker-compose.override.yml` (generado por `generate_drives.ps1`)
monta `c:/` en `/mnt/c`. El frontend convierte rutas de contenedor a rutas Windows con
`container_to_windows_path()`.

**Configuración persistente del frontend**: toda la config del usuario se guarda en
`frontend_config.json` y se recarga en cada sesión de Streamlit.

**Race parser deduplicación**: los incidentes XML duplicados (mismo timestamp ± 7s, mismo piloto)
se filtran en `race_parser.py` antes de llegar al frontend.

## Idioma

La interfaz de usuario y toda la narración de carrera generada por IA está en **español (Castellano)**.
Los prompts de Ollama instruyen explícitamente al LLM a responder en español.

## Entorno de Desarrollo

### Inicio rápido (local, sin Docker)

```bash
# Instalar dependencias
pip install -r requirements.txt
pip install -e ./VibeVoice

# Terminal 1 — API
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000

# Terminal 2 — Frontend
streamlit run frontend.py

# O usar el lanzador automático
python launcher.py

# Exportar frontend web para incrustarlo en el binario Go
cd truevoice-web
node .\node_modules\expo\bin\cli export --platform web
# Copiar dist/ a truevoice-go/internal/server/webdist/
```

### Inicio con Docker

```bash
# Generar override de discos Windows (solo Windows, una vez o cuando cambien los discos)
powershell -ExecutionPolicy Bypass -NoProfile -File generate_drives.ps1

# Construir y arrancar
docker compose up --build

# Solo la API
docker compose up api
```

### Servicios

| Servicio | URL | Comando local |
|---------|-----|---------------|
| API Backend | http://localhost:8000 | `uvicorn api_server:app --port 8000` |
| UI embebida Go | http://localhost:8000/app | `truevoice-go\\truevoice.exe` |
| Frontend legado | http://localhost:8501 | `streamlit run frontend.py` |
| API Docs (Swagger) | http://localhost:8000/docs | automático con FastAPI |
| Ollama (externo) | http://localhost:11434 | `ollama serve` (host) |

### Sin tests automatizados (a fecha de hoy)

TrueVoice **no tiene suite de tests implementada**. Al añadir tests:
- `pytest` + `pytest-mock` + `httpx` como dependencias de desarrollo
- Tests unitarios para `race_parser.py` (puro Python, sin dependencias externas)
- Tests de integración para endpoints FastAPI con `httpx.TestClient`

## Docker

### Arquitectura de contenedores

```
┌──────────────────────┐    ┌─────────────────────┐
│  Frontend            │───▶│  API                │
│  truevoice-frontend  │    │  truevoice-api       │
│  :8501               │    │  :8000              │
└──────────────────────┘    └─────────────────────┘
         │                            │
         └──── host.docker.internal ──┘
                    :11434 (Ollama)
```

### Archivos Docker

| Archivo | Propósito |
|---------|---------|
| `Dockerfile.api` | Python 3.11, torch CPU, ffmpeg, VibeVoice, deps ML |
| `Dockerfile.frontend` | Python 3.11, streamlit, requests, openpyxl |
| `docker-compose.yml` | Orquestación principal; volúmenes; health check API |
| `docker-compose.override.yml` | Montaje discos Windows (auto-generado — no editar) |
| `generate_drives.ps1` | Genera el override con los discos detectados |

### Notas operacionales

- El modelo VibeVoice se descarga de HuggingFace la primera vez. Puede tardar varios minutos.
  El volumen `hf_cache` lo persiste entre reinicios.
- `temp_outputs/` se limpia automáticamente vía `POST /cleanup_temp` (archivos > 1 hora).
  El frontend llama a este endpoint al arrancar.
- `docker-compose.override.yml` se regenera al ejecutar `generate_drives.ps1`.
  Nunca editar manualmente — los cambios se sobreescriben.
- Ollama corre fuera de Docker en el host. El contenedor accede via `host.docker.internal:11434`.

## Metodología de Desarrollo

Ver [`GIT.md`](GIT.md) para el flujo completo de commits, branching y procedimiento de release.

| Rama | Significado |
|------|------------|
| `main` | Código estable y desplegado |
| `develop` | Integración de features antes de release |
| `feat/<nombre>` | Nueva funcionalidad |
| `fix/<nombre>` | Corrección de bug |
