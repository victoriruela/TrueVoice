# TrueVoice

TrueVoice es una aplicacion TTS con clonacion de voz basada en VibeVoice.
La arquitectura productiva es un backend Go unico que sirve la UI web embebida y ejecuta un sidecar Python solo para inferencia.

## Arquitectura Actual

- Backend/API/UI: Go en `truevoice-go/cmd/truevoice`
- Frontend fuente: Expo Web en `truevoice-web` (exportado a `truevoice-go/internal/server/webdist`)
- Sidecar Python de inferencia: `vibevoice_app.py`, `inference_wrapper.py`, `patches.py`, `VibeVoice/`
- Ollama: servicio externo opcional para textos de narracion

## Requisitos

- Go 1.23+
- Node.js 20+ (para exportar web de Expo)
- Python 3.11+ (solo sidecar VibeVoice)
- FFmpeg
- (Opcional) Ollama en `http://localhost:11434`

## Desarrollo Local

1. Exportar frontend web (solo si cambias `truevoice-web`):

```bash
cd truevoice-web
node .\node_modules\expo\bin\cli export --platform web
# Copiar dist/ a truevoice-go/internal/server/webdist/
```

2. Ejecutar servidor Go:

```bash
cd ..\truevoice-go
go run .\cmd\truevoice
```

3. Abrir la app:

- UI: `http://localhost:8000/app`
- Health: `http://localhost:8000/`

## API Principal

- `GET /`
- `GET /models`
- `GET /voices`
- `POST /voices/upload`
- `DELETE /voices/{name}`
- `POST /generate`
- `GET /audio/{audio_id}`
- `GET /progress/{progress_id}`
- `POST /cancel/{progress_id}`
- `POST /cancel_all`
- `POST /confirm_save`
- `POST /race/excel?name=<nombre>`
- `GET /outputs`
- `DELETE /outputs/delete`
- `POST /cleanup_temp`
- `GET /setup/status`
- `POST /setup/bootstrap`

## Sidecar VibeVoice (CLI)

Puedes ejecutar directamente el CLI:

```bash
python vibevoice_app.py --list-voices
python vibevoice_app.py --text "Hola" --voice-name Alice --output salida.wav
```

## Referencias

- `AGENTS.md` para arquitectura y reglas del repo
- `GIT.md` para flujo de ramas, RC y releases
- `ASANA.md` y `SUBAGENTS.md` para operativa Asana
