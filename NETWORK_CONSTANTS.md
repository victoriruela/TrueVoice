# Network Constants

| Constante | Valor | Fuente |
|-----------|-------|--------|
| HTTP server host | `0.0.0.0` | `truevoice-go/cmd/truevoice/main.go` |
| HTTP server port | `8000` | `truevoice-go/cmd/truevoice/main.go` |
| UI path embebido | `/app` | `truevoice-go/internal/server/*` |
| Ollama API base URL | `http://localhost:11434` | Configurable en `frontend_config.json` |

## Rutas de Runtime

| Elemento | Ruta | Fuente |
|----------|------|--------|
| Project root | raiz del repositorio | `truevoice-go/internal/generation/generation.go` |
| Voces custom | `./voices` | estructura del proyecto |
| Outputs finales | `./api_outputs` | estructura del proyecto |
| Outputs temporales | `./temp_outputs` | estructura del proyecto |
| Sesiones carrera | `./race_sessions` | estructura del proyecto |
| Config frontend | `./frontend_config.json` | estructura del proyecto |
| Cache HuggingFace | `%APPDATA%/TrueVoice/runtime/models/huggingface` | `bootstrap.go` |

## File Browser

En Windows, el backend lista unidades `A:\` a `Z:\`.
En Linux, el backend lista directorios de `/mnt` y, si no existen, usa `/`.
