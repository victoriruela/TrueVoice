# LLM & Model Constants

## Modelos VibeVoice (TTS)

| Constante | Valor | Fuente |
|-----------|-------|--------|
| Modelo por defecto | `microsoft/VibeVoice-1.5b` | `api_server.py` `GenerateRequest.model` default |
| Modelo alta calidad | `microsoft/VibeVoice-7b` | Documentado en README |
| CFG Scale (default) | `2.0` | `api_server.py` `GenerateRequest.cfg_scale` default |
| CFG Scale (rango) | `0.5 – 5.0` | `api_server.py` Field constraints |
| DDPM Steps (default) | `30` | `api_server.py` `GenerateRequest.ddpm_steps` default |
| DDPM Steps (rango) | `1 – 200` | `api_server.py` Field constraints |
| Output format (default) | `wav` | `api_server.py` `GenerateRequest.output_format` default |
| Formatos soportados | `wav`, `mp3`, `flac`, `ogg` | `api_server.py` validación en `POST /generate` |
| `disable_prefill` (default) | `False` | `api_server.py` `GenerateRequest.disable_prefill` |

### Notas de rendimiento

- `VibeVoice-1.5b`: Funciona en CPU. Tiempo de generación ~5–30s según longitud del texto y hardware.
- `VibeVoice-7b`: Requiere ~28 GB VRAM. No recomendado para CPU.
- Los modelos se descargan automáticamente de HuggingFace y se cachean en `HF_HOME`.

### Paralelismo CPU en Docker

| Variable de entorno | Valor | Efecto |
|--------------------|-------|--------|
| `MKL_NUM_THREADS` | `0` (auto) | MKL usa todos los cores |
| `OPENBLAS_NUM_THREADS` | `0` (auto) | OpenBLAS usa todos los cores |
| `NUMEXPR_NUM_THREADS` | `0` (auto) | NumExpr usa todos los cores |
| `TOKENIZERS_PARALLELISM` | `true` | Tokenizers HuggingFace en paralelo |

Dentro de `inference_wrapper.py`:
- `torch.set_num_threads(os.cpu_count())` — hilos de cómputo PyTorch
- `torch.set_num_interop_threads(cpu_count // 2)` — hilos inter-operación PyTorch

## Voces por Defecto

| Alias (frontend) | Nombre interno (archivo WAV) | Idioma |
|-----------------|------------------------------|--------|
| `Alice` | `en-Alice_woman` | Inglés |
| `Carter` | `en-Carter_man` | Inglés |
| `Frank` | `en-Frank_man` | Inglés |
| `Mary` | `en-Mary_woman_bgm` | Inglés |
| `Maya` | `en-Maya_woman` | Inglés |
| `Samuel` | `in-Samuel_man` | Inglés (India) |
| `Anchen` | `zh-Anchen_man_bgm` | Chino |
| `Bowen` | `zh-Bowen_man` | Chino |
| `Xinran` | `zh-Xinran_woman` | Chino |

Fuente: `api_server.py` dict `DEFAULT_VOICES`.

## Ollama (Narración de Carrera)

| Constante | Valor | Fuente |
|-----------|-------|--------|
| URL base (local) | `http://localhost:11434` | `frontend.py` config default |
| Modelo (default) | `llama3.2` | `frontend.py` config default |
| Timeout petición modelos | `5s` | `frontend.py` `fetch_ollama_models()` |

El modelo y la URL los configura el usuario desde la interfaz y se persisten en `frontend_config.json`.

## Cleanup de Temporales

| Constante | Valor | Fuente |
|-----------|-------|--------|
| Antigüedad máxima archivos temp | `3600s` (1 hora) | `api_server.py` `POST /cleanup_temp` |
