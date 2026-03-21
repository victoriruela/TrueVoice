# TrueVoice — Generador de Audio con Clonación de Voz

Aplicación completa para generar audio a partir de texto usando
[VibeVoice de Microsoft](https://github.com/microsoft/VibeVoice), con soporte
para clonación de voz desde archivos de audio, vídeo o YouTube.

Incluye **interfaz web (Streamlit)**, **API REST (FastAPI)** y **CLI** (línea de comandos).

## Arquitectura

Dependencias principales:

| Paquete | Uso |
|---------|-----|
| `torch`, `torchaudio` | Motor de inferencia |
| `transformers`, `accelerate` | Carga del modelo VibeVoice |
| `soundfile` | Procesamiento de audio |
| `fastapi`, `uvicorn` | API REST |
| `streamlit` | Interfaz web |
| `requests` | Comunicación frontend → API |
| `yt-dlp` | Descarga de audio desde YouTube |

| Servicio | URL |
|----------|-----|
| Frontend Streamlit | `http://localhost:8501` |
| API REST (docs interactivos) | `http://localhost:8000/docs` |

### Funcionalidades de la interfaz web

- **Generar audio**: escribe un texto, elige una voz y ajusta los parámetros.
- **Reproductor integrado**: escucha el audio generado directamente en el navegador.
- **Descargar audio**: botón de descarga en el formato elegido.
- **Gestionar voces**: ver, subir y eliminar voces personalizadas.
- **Panel de configuración** (sidebar): modelo, formato, CFG Scale, DDPM Steps.

## Uso — CLI (línea de comandos)

### Ver voces disponibles

- ✅ Conversión de texto a audio (TTS) con clonación de voz
- ✅ Interfaz web con Streamlit
- ✅ API REST con FastAPI (documentación interactiva en `/docs`)
- ✅ CLI completo para uso por terminal
- ✅ Clonación de voz desde archivos de audio o vídeo locales
- ✅ Extracción de voz desde vídeos de YouTube por fragmento de tiempo
- ✅ Salida en múltiples formatos: WAV, MP3, FLAC, OGG
- ✅ Parámetros ajustables de calidad (CFG Scale, DDPM Steps)
- ✅ Gestión de voces (listar, subir, eliminar) desde la web
- ✅ Soporte para GPU (CUDA) y CPU
- ✅ Clonación automática del repositorio de VibeVoice

## Instalación

### Extraer voz desde YouTube
Puedes crear un preset de voz directamente desde un fragmento de un vídeo de
YouTube indicando la URL, el tiempo de inicio y el tiempo de fin en formato
`HH:MM:SS`:

```bash
python vibevoice_app.py --youtube-voice "https://www.youtube.com/watch?v=VIDEO_ID" --start 00:01:30 --end 00:02:00 --voice-name MiVoz
```

## Instalación

### 2. Instalar dependencias

bash pip install -r requirements.txt

### 3. Primera ejecución

**Terminal 2 — Levantar el Frontend:**

La primera vez que se ejecute la aplicación se realizará automáticamente:

1. Clonación del repositorio de VibeVoice
2. Instalación del paquete `vibevoice`
3. Descarga del modelo (~6 GB para `VibeVoice-1.5b`)

## Uso — Interfaz Web (recomendado)

Se necesitan **dos terminales**:

**Terminal 1 — Levantar la API REST:**

bash python vibevoice_app.py --list-voices

### Ver voces disponibles

Voces incluidas en el repositorio:

| Alias         | Archivo real          |
|---------------|-----------------------|
| `Alice`       | `en-Alice_woman`      |
| `Carter`      | `en-Carter_man`       |
| `Frank`       | `en-Frank_man`        |
| `Mary`        | `en-Mary_woman_bgm`   |
| `Maya`        | `en-Maya_woman`       |
| `Samuel`      | `in-Samuel_man`       |
| `Anchen`      | `zh-Anchen_man_bgm`   |
| `Bowen`       | `zh-Bowen_man`        |
| `Xinran`      | `zh-Xinran_woman`     |

### Generar audio simple

bash python vibevoice_app.py --text "Hola, esto es una prueba" --output prueba.wav

### Usar una voz específica

### Añadir voz personalizada desde audio

bash python vibevoice_app.py --clone-voice mi_voz.wav --voice-name MiVoz

### Añadir voz desde un vídeo local

bash python vibevoice_app.py --clone-voice video.mp4 --voice-name MiVoz

Formatos de video soportados: `.mp4`, `.avi`, `.mov`, `.mkv`, `.flv`, `.wmv`

python vibevoice_app.py --text "Hola, esto es una prueba" --voice-name MiVoz --output resultado.mp3

### Modo interactivo

bash python vibevoice_app.py --interactive --voice-name Alice

### Sin clonación de voz (más rápido)

bash python vibevoice_app.py --text "Hola" --disable-prefill --output prueba.wav

### Modo interactivo

## Opciones de línea de comandos

| Opción              | Alias | Descripción |
|---------------------|-------|-------------|
| `--text`            | `-t`  | Texto a convertir en audio |
| `--output`          | `-o`  | Archivo de salida (default: `output.wav`). La extensión determina el formato. |
| `--clone-voice`     | `-c`  | Audio/video local de referencia para clonar voz |
| `--youtube-voice`   | `-y`  | URL de YouTube de la que extraer la voz de referencia |
| `--start`           |       | Tiempo de inicio del fragmento en formato `HH:MM:SS` (para `--youtube-voice`) |
| `--end`             |       | Tiempo de fin del fragmento en formato `HH:MM:SS` (para `--youtube-voice`) |
| `--voice-name`      | `-v`  | Nombre de la voz a usar o guardar (default: `Alice`) |
| `--model`           | `-m`  | Modelo a usar (default: `microsoft/VibeVoice-1.5b`) |
| `--disable-prefill` |       | Desactiva clonación de voz (voz genérica, más rápido) |
| `--interactive`     | `-i`  | Modo interactivo para múltiples textos |
| `--list-voices`     | `-l`  | Lista voces disponibles y sale |

### Alta calidad (más lento)
## Modelos disponibles

Estándar 1.5B - recomendado para CPU (default, ~6GB)
--model microsoft/VibeVoice-1.5b
Grande 7B - mayor calidad, requiere GPU (~28GB)
--model microsoft/VibeVoice-7b

> ⚠️ El modelo `Realtime-0.5B` es solo para **streaming** y no es compatible
> con `inference_from_file.py`. No uses ese modelo con esta aplicación.

## Solución de problemas

### El modelo genera 1 token y falla

Asegúrate de estar usando `microsoft/VibeVoice-1.5b` (por defecto), no el
modelo `Realtime-0.5B`.

### La voz no se encuentra

Ejecuta `--list-voices` para ver los nombres exactos disponibles. Puedes usar
los alias cortos (`Alice`, `Maya`...) o el nombre completo del archivo
(`en-Alice_woman`).

### Error al procesar video

## Instala FFmpeg:

bash conda install ffmpeg -c conda-forge

### Advertencia de symlinks en Windows

Activa el **Modo Desarrollador** en Windows:
*Configuración → Actualización y seguridad → Para desarrolladores → Modo de desarrollador*

### Formatos de salida

La extensión del archivo `--output` determina el formato. Se soportan:
**WAV**, **MP3**, **FLAC** y **OGG**.

## Referencias

- [VibeVoice GitHub (Oficial)](https://github.com/microsoft/VibeVoice)
- [VibeVoice GitHub (Comunidad)](https://github.com/vibevoice-community/VibeVoice)
- [VibeVoice en Hugging Face](https://huggingface.co/collections/microsoft/vibevoice)
### Sin clonación de voz (más rápido)

## Voces incluidas

| Alias | Archivo | Idioma |
|-------|---------|--------|
| `Alice` | `en-Alice_woman` | Inglés |
| `Carter` | `en-Carter_man` | Inglés |
| `Frank` | `en-Frank_man` | Inglés |
| `Mary` | `en-Mary_woman_bgm` | Inglés |
| `Maya` | `en-Maya_woman` | Inglés |
| `Samuel` | `in-Samuel_man` | Hindi |
| `Anchen` | `zh-Anchen_man_bgm` | Chino |
| `Bowen` | `zh-Bowen_man` | Chino |
| `Xinran` | `zh-Xinran_woman` | Chino |

Puedes añadir voces propias desde la interfaz web, por CLI o copiando archivos `.wav`
en `VibeVoice/demo/voices/`.

## Opciones CLI completas

| Opción | Alias | Descripción |
|--------|-------|-------------|
| `--text` | `-t` | Texto a convertir en audio |
| `--output` | `-o` | Archivo de salida (extensión = formato). Default: `output.wav` |
| `--clone-voice` | `-c` | Audio/vídeo local para clonar voz |
| `--youtube-voice` | `-y` | URL de YouTube para extraer voz |
| `--start` | | Inicio del fragmento `HH:MM:SS` (con `--youtube-voice`) |
| `--end` | | Fin del fragmento `HH:MM:SS` (con `--youtube-voice`) |
| `--voice-name` | `-v` | Nombre de la voz (default: `Alice`) |
| `--model` | `-m` | Modelo HuggingFace (default: `microsoft/VibeVoice-1.5b`) |
| `--cfg-scale` | | CFG Scale `0.5-5.0` (default: `2.0`) |
| `--ddpm-steps` | | Pasos DDPM `1-200` (default: `30`) |
| `--disable-prefill` | | Desactiva clonación de voz |
| `--interactive` | `-i` | Modo interactivo |
| `--list-voices` | `-l` | Listar voces y salir |

## Endpoints de la API REST

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/` | Estado de la API |
| `GET` | `/voices` | Lista de voces disponibles |
| `GET` | `/models` | Lista de modelos disponibles |
| `POST` | `/generate` | Genera audio a partir de texto (JSON) |
| `GET` | `/audio/{audio_id}` | Descarga un audio generado |
| `POST` | `/voices/upload` | Sube una nueva voz (multipart/form-data) |
| `DELETE` | `/voices/{voice_name}` | Elimina una voz personalizada |

Documentación interactiva (Swagger): `http://localhost:8000/docs`

## Parámetros de calidad

| Parámetro | Qué controla | Rango | Recomendado |
|-----------|-------------|-------|-------------|
| **CFG Scale** | Fidelidad al texto. Más alto = sigue más el texto | 0.5 – 5.0 | 1.5 – 2.5 |
| **DDPM Steps** | Calidad del audio. Más pasos = mejor pero más lento | 1 – 200 | 20 – 50 |

### El modelo genera 1 token y falla

| Escenario | CFG Scale | DDPM Steps | Velocidad |
|-----------|-----------|------------|-----------|
| Prueba rápida | 1.2 | 5 | ⚡ Muy rápido |
| Balance | 1.5 | 20 | 🟢 Rápido |
| Alta calidad | 1.8 | 30 | 🟡 Moderado |
| Producción | 2.0 | 50 | 🔴 Lento |

## Modelos disponibles

| Modelo | Parámetros | Tamaño | Notas |
|--------|-----------|--------|-------|
| `microsoft/VibeVoice-1.5b` | 1.5B | ~6 GB | Recomendado, funciona en CPU |
| `microsoft/VibeVoice-7b` | 7B | ~28 GB | Mayor calidad, requiere GPU |

> ⚠️ El modelo `Realtime-0.5B` es solo para streaming y **no es compatible**
> con esta aplicación.

## Solución de problemas

### No se puede conectar con la API

Asegúrate de que la API está corriendo:
### Advertencia de symlinks en Windows

Activa el **Modo Desarrollador**:
*Configuración → Actualización y seguridad → Para desarrolladores → Modo de desarrollador*

## Formatos de salida

La extensión del archivo `--output` determina el formato automáticamente:

- `.wav` — Sin compresión, máxima calidad
- `.mp3` — Comprimido, compatible universal
- `.flac` — Compresión sin pérdida
- `.ogg` — Compresión abierta

## Consejos para mejor calidad de clonación

- Usa **20-60 segundos** de audio limpio de referencia
- Evita ruido de fondo, música o reverberación
- Una sola persona hablando en el audio
- Audio en buena calidad (sin distorsión, volumen adecuado)

## Referencias

- [VibeVoice — GitHub (Oficial)](https://github.com/microsoft/VibeVoice)
- [VibeVoice — GitHub (Comunidad)](https://github.com/vibevoice-community/VibeVoice)
- [VibeVoice — Hugging Face](https://huggingface.co/collections/microsoft/vibevoice)
- [FastAPI — Documentación](https://fastapi.tiangolo.com/)
- [Streamlit — Documentación](https://docs.streamlit.io/)

@app.post("/generate", response_model=GenerateResponse)
def generate_audio(req: GenerateRequest):
    """Genera audio a partir de texto usando VibeVoice."""
    # Valida la voz
    resolved = _resolve_voice(req.voice_name)
    if resolved is None:
        available = [f.stem for f in VOICES_DIR.glob("*.wav")]
        raise HTTPException(404, f"Voz '{req.voice_name}' no encontrada. Disponibles: {available}")

    # Valida formato
    fmt = req.output_format.lower().lstrip(".")
    if fmt not in ("wav", "mp3", "flac", "ogg"):
        raise HTTPException(400, f"Formato '{fmt}' no soportado. Usa: wav, mp3, flac, ogg")

    # Genera un ID único para este audio
    audio_id = uuid.uuid4().hex[:12]
    output_file = OUTPUTS_DIR / f"{audio_id}.{fmt}"

    # Llama al backend CLI
    cmd = [
        sys.executable, str(PROJECT_ROOT / "vibevoice_app.py"),
        "--text", req.text,
        "--voice-name", req.voice_name,
        "--model", req.model,
        "--output", str(output_file),
        "--cfg-scale", str(req.cfg_scale),
        "--ddpm-steps", str(req.ddpm_steps),
    ]
    if req.disable_prefill:
        cmd.append("--disable-prefill")

    print(f"\n[API] Ejecutando comando:")
    print(f"  {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Timeout: la generación tardó más de 10 minutos")

    # Log stdout y stderr para debug
    if result.stdout:
        print(f"[API] STDOUT:\n{result.stdout[-1000:]}")
    if result.stderr:
        print(f"[API] STDERR:\n{result.stderr[-1000:]}")
    print(f"[API] Return code: {result.returncode}")

    if result.returncode != 0 or not output_file.exists():
        # Combina stdout y stderr para dar más contexto del error
        detail_parts = []
        if result.stderr:
            detail_parts.append(result.stderr[-500:])
        if result.stdout:
            detail_parts.append(result.stdout[-500:])
        detail = "\n".join(detail_parts) if detail_parts else "Error desconocido (sin salida)"
        raise HTTPException(500, f"Error generando audio:\n{detail}")

    return GenerateResponse(
        success=True,
        message="Audio generado correctamente",
        audio_id=audio_id,
        filename=output_file.name,
    )