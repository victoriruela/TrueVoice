# LLM & Model Constants

## Modelos VibeVoice (TTS)

| Constante | Valor | Fuente |
|-----------|-------|--------|
| Modelo por defecto | `microsoft/VibeVoice-1.5b` | `truevoice-go/internal/generation/generation.go` |
| CFG Scale (default) | `2.0` | `truevoice-go/internal/generation/generation.go` |
| DDPM Steps (default) | `30` | `truevoice-go/internal/generation/generation.go` |
| Output format (default) | `wav` | `truevoice-go/internal/generation/generation.go` |
| Formatos soportados | `wav`, `mp3`, `flac`, `ogg` | `truevoice-go/internal/generation/generation.go` |
| `disable_prefill` | `false` por defecto | `truevoice-go/internal/generation/generation.go` |

## Bootstrap Python Sidecar

| Constante | Valor | Fuente |
|-----------|-------|--------|
| Python embebido (Windows) | `3.11.8` | `truevoice-go/internal/generation/bootstrap.go` |
| URL embed Python | `https://www.python.org/ftp/python/3.11.8/python-3.11.8-embed-amd64.zip` | `bootstrap.go` |
| Runtime root (Windows) | `%APPDATA%/TrueVoice/runtime` | `bootstrap.go` |
| Runtime root (fallback) | `./runtime` | `bootstrap.go` |

## Voces por Defecto

Voces por defecto soportadas por el resolvedor de voces: `Alice`, `Carter`, `Frank`, `Mary`, `Maya`, `Samuel`, `Anchen`, `Bowen`, `Xinran`.

Fuente: `truevoice-go/internal/voices/voices.go`.

## Ollama (Narracion de Carrera)

- URL y modelo se configuran en `frontend_config.json`.

## Cleanup de Temporales

El endpoint `POST /cleanup_temp` elimina outputs temporales antiguos (ventana de 1 hora en la implementacion actual).
