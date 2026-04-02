# Network Constants

| Constante | Valor | Fuente |
|-----------|-------|--------|
| FastAPI host | `0.0.0.0` | `Dockerfile.api` CMD (Uvicorn) |
| FastAPI port | `8000` | `Dockerfile.api` CMD + `docker-compose.yml` |
| Streamlit port | `8501` | `Dockerfile.frontend` CMD |
| Ollama API base URL (local) | `http://localhost:11434` | `frontend.py` config default |
| Ollama API base URL (Docker) | `http://host.docker.internal:11434` | `docker-compose.yml` `extra_hosts` |
| Frontend → API (local) | `http://localhost:8000` | `frontend.py` env `API_URL` default |
| Frontend → API (Docker) | `http://api:8000` | `docker-compose.yml` env `API_URL` |

## Rutas de Directorios (dentro del contenedor)

| Variable | Ruta contenedor | Declarada en |
|----------|----------------|--------------|
| `PROJECT_ROOT` | `/app` | `api_server.py:37` (WORKDIR Dockerfile) |
| `DEFAULT_VOICES_DIR` | `/app/voices` | `api_server.py:40` |
| `VIBEVOICE_VOICES_DIR` | `/app/VibeVoice/demo/voices` | `api_server.py:41` |
| `OUTPUTS_DIR` | `/app/api_outputs` | `api_server.py:42` |
| `TEMP_DIR` | `/app/temp_outputs` | `api_server.py:43` |
| Race sessions | `/app/race_sessions` | `docker-compose.yml` volume |
| HuggingFace cache | `/root/.cache/huggingface` | `docker-compose.yml` env `HF_HOME` |
| Frontend config | `/app/frontend_config.json` | `docker-compose.yml` volume |

## Docker Networking

Cuando se ejecuta mediante `docker compose`, los servicios se comunican usando nombres DNS de servicio:

| Conexión | URL | Variable de entorno |
|----------|-----|---------------------|
| Frontend → API | `http://api:8000` | `API_URL` |
| Contenedor → Ollama (host) | `http://host.docker.internal:11434` | URL en `frontend_config.json` |

## Montaje de Discos Windows (Override)

El archivo `docker-compose.override.yml` (generado por `generate_drives.ps1`) monta los discos
Windows detectados en ambos contenedores:

| Disco (host) | Mount (contenedor) |
|--------------|-------------------|
| `C:\` | `/mnt/c` |
| `D:\` | `/mnt/d` (si existe) |
| ... | ... |

La función `container_to_windows_path()` en `frontend.py` convierte `/mnt/c/...` → `C:\...`
para mostrar rutas legibles al usuario.
