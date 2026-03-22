# TrueVoice — Generador de Audio con Clonación de Voz

Aplicación completa para generar audio a partir de texto usando [VibeVoice de Microsoft](https://github.com/microsoft/VibeVoice), con soporte para clonación de voz desde archivos de audio, vídeo o YouTube.

Incluye **interfaz web (Streamlit)**, **API REST (FastAPI)** y **CLI** (línea de comandos).

## 🚀 Características

- ✅ **Conversión de texto a audio (TTS)** con clonación de voz de alta fidelidad.
- ✅ **Interfaz web (Streamlit)** intuitiva para generar audio y gestionar voces.
- ✅ **API REST (FastAPI)** con documentación interactiva en `/docs`.
- ✅ **CLI completo** para uso avanzado por terminal.
- ✅ **Clonación de voz** desde archivos de audio (.wav, .mp3, etc.) o vídeos locales (.mp4, .mkv, etc.).
- ✅ **Extracción de voz desde YouTube** indicando fragmentos de tiempo específicos.
- ✅ **Múltiples formatos de salida**: WAV, MP3, FLAC, OGG.
- ✅ **Ajustes de calidad**: Parámetros CFG Scale y DDPM Steps personalizables.
- ✅ **Soporte para GPU (CUDA)** y CPU.

---

## 🛠️ Instalación

### 1. Requisitos previos
- **Python 3.10 o superior** (se recomienda usar un entorno virtual).
- **FFmpeg** instalado en el sistema (necesario para procesar vídeo y audio).
- **Modo Desarrollador en Windows** (para permitir symlinks):
  *Configuración → Actualización y seguridad → Para desarrolladores → Modo de desarrollador*

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Primera ejecución
La primera vez que uses la aplicación (vía CLI, API o Web), se realizará automáticamente:
1. Descarga del modelo preentrenado (~6 GB para `VibeVoice-1.5b`) desde HuggingFace.
2. Descarga de voces predeterminadas de ejemplo si no existen en la carpeta `voices/`.

---

## 🖥️ Cómo ejecutar la aplicación

### Opción A: Interfaz Web (Recomendado)
Para usar la interfaz web, necesitas ejecutar la API y el Frontend en dos terminales separadas:

**Terminal 1 — API REST:**
```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000
```
*La documentación interactiva estará en `http://localhost:8000/docs`*

**Terminal 2 — Frontend Streamlit:**
```bash
streamlit run frontend.py
```
*Accede a la interfaz en `http://localhost:8501`*

---

### Opción B: CLI (Línea de comandos)
Puedes generar audio directamente sin levantar servidores:

**Generar audio simple (Voz por defecto):**
```bash
python vibevoice_app.py --text "Hola, bienvenido a TrueVoice" --output saludo.wav
```

**Clonar una voz desde un audio o vídeo:**
```bash
python vibevoice_app.py --clone-voice mi_referencia.wav --voice-name MiVoz
```

**Generar audio con una voz clonada:**
```bash
python vibevoice_app.py --text "Generando audio con mi voz" --voice-name MiVoz --output resultado.mp3
```

**Extraer voz desde YouTube:**
```bash
python vibevoice_app.py --youtube-voice "https://www.youtube.com/watch?v=VIDEO_ID" --start 00:01:30 --end 00:02:00 --voice-name VozYouTube
```

---

## 🎤 Voces Incluidas

| Alias | Archivo real | Idioma |
|-------|--------------|--------|
| `Alice` | `en-Alice_woman` | Inglés |
| `Carter` | `en-Carter_man` | Inglés |
| `Frank` | `en-Frank_man` | Inglés |
| `Mary` | `en-Mary_woman_bgm` | Inglés |
| `Maya` | `en-Maya_woman` | Inglés |
| `Samuel` | `in-Samuel_man` | Hindi |
| `Anchen` | `zh-Anchen_man_bgm` | Chino |
| `Bowen` | `zh-Bowen_man` | Chino |
| `Xinran` | `zh-Xinran_woman` | Chino |
| `Lobato` | `es-Lobato_man` | Español |

---

## ⚙️ Opciones CLI Completas

| Opción | Alias | Descripción |
|--------|-------|-------------|
| `--text` | `-t` | Texto a convertir en audio |
| `--output` | `-o` | Archivo de salida (determina el formato). Default: `output.wav` |
| `--clone-voice` | `-c` | Ruta a audio/vídeo local para clonar voz |
| `--youtube-voice` | `-y` | URL de YouTube para extraer voz |
| `--start` / `--end` | | Fragmento de tiempo `HH:MM:SS` para YouTube |
| `--voice-name` | `-v` | Nombre de la voz (guardada o existente). Default: `Alice` |
| `--model` | `-m` | Modelo HuggingFace (default: `microsoft/VibeVoice-1.5b`) |
| `--cfg-scale` | | Controla fidelidad al texto (0.5-5.0). Recomendado: 2.0 |
| `--ddpm-steps` | | Pasos de difusión (1-200). Recomendado: 30-50 |
| `--disable-prefill` | | Generación más rápida con voz genérica |
| `--list-voices` | `-l` | Lista las voces disponibles y sale |

---

## 🧠 Modelos Soportados

| Modelo | Parámetros | Notas |
|--------|------------|-------|
| `microsoft/VibeVoice-1.5b` | 1.5B | **Recomendado**, funciona bien en CPU y GPU (~6 GB) |
| `microsoft/VibeVoice-7b` | 7B | Mayor fidelidad, requiere GPU potente (~28 GB) |

---

## 🆘 Solución de Problemas

- **El audio suena mal o distorsionado:** Prueba a subir un audio de referencia más limpio (20-60s) o ajusta `cfg-scale` entre 1.5 y 2.5.
- **Error al procesar vídeo:** Asegúrate de tener `ffmpeg` instalado y accesible desde la terminal.
- **La API no conecta:** Verifica que `uvicorn api_server:app` se esté ejecutando en el puerto 8000.
- **El modelo genera solo 1 token y falla:** Asegúrate de no estar usando el modelo `Realtime-0.5B`, que no es compatible con este sistema de inferencia.

---

## 🔗 Referencias

- [VibeVoice Oficial (Microsoft)](https://github.com/microsoft/VibeVoice)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Streamlit Docs](https://docs.streamlit.io/)
