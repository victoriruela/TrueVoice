# VibeVoice - Aplicación de Consola TTS con Clonación de Voz

Aplicación de línea de comandos para generar audio a partir de texto usando
[VibeVoice de Microsoft](https://github.com/microsoft/VibeVoice), con soporte
para clonación de voz desde archivos de audio o video.

## Características

- ✅ Conversión de texto a audio (TTS)
- ✅ Clonación de voz desde archivos de audio locales
- ✅ Extracción de voz desde archivos de video locales
- ✅ Extracción de voz desde vídeos de YouTube por fragmento de tiempo
- ✅ Salida en múltiples formatos: WAV, MP3, FLAC, OGG
- ✅ Modo interactivo para múltiples generaciones
- ✅ Soporte para GPU (CUDA) y CPU
- ✅ Clonación automática del repositorio de VibeVoice

### Extraer voz desde YouTube

Puedes crear un preset de voz directamente desde un fragmento de un vídeo de
YouTube indicando la URL, el tiempo de inicio y el tiempo de fin en formato
`HH:MM:SS`:

```bash
python vibevoice_app.py --youtube-voice "https://www.youtube.com/watch?v=VIDEO_ID" --start 00:01:30 --end 00:02:00 --voice-name MiVoz
```

## Instalación

### 1. Instalar dependencias

bash pip install -r requirements.txt

### 2. Primera ejecución

La primera vez que ejecutes la aplicación se realizará automáticamente:
1. Clonación del repositorio de VibeVoice
2. Instalación del paquete `vibevoice`
3. Descarga del modelo (~6GB para `VibeVoice-1.5b`)

## Uso

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

bash python vibevoice_app.py --text "Hello world" --voice-name Maya --output maya.wav

### Añadir voz personalizada desde audio

bash python vibevoice_app.py --clone-voice mi_voz.wav --voice-name MiVoz

### Añadir voz desde un video

bash python vibevoice_app.py --clone-voice video.mp4 --voice-name MiVoz

Formatos de video soportados: `.mp4`, `.avi`, `.mov`, `.mkv`, `.flv`, `.wmv`

### Generar audio con voz personalizada

python vibevoice_app.py --text "Hola, esto es una prueba" --voice-name MiVoz --output resultado.mp3

### Modo interactivo

bash python vibevoice_app.py --interactive --voice-name Alice

### Sin clonación de voz (más rápido)

bash python vibevoice_app.py --text "Hola" --disable-prefill --output prueba.wav

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
pip install yt-dlp -c conda-forge
pip install yt-dlp -c conda-forge
pip install yt-dlp -c conda-forge
pip install yt-dlp -c conda-forge
pip install yt-dlp -c conda-forge
pip install yt-dlp -c conda-forge
pip install yt-dlp -c conda-forge
pip install yt-dlp -c conda-forge -c conda-forge -c conda-forge
pip install yt-dlp


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

```

Instala la nueva dependencia y pruébalo:

```bash
pip install yt-dlp
```

```bash
# Extraer voz de un fragmento de YouTube
python vibevoice_app.py --youtube-voice "https://www.youtube.com/watch?v=VIDEO_ID" --start 00:00:30 --end 00:01:00 --voice-name MiVoz

# Generar audio con esa voz
python vibevoice_app.py --text "Hola, esto es una prueba" --voice-name MiVoz --output resultado.mp3
```

También puedes **encadenar los dos pasos en un solo comando**:

```bash
python vibevoice_app.py \
  --youtube-voice "https://www.youtube.com/watch?v=VIDEO_ID" \
  --start 00:00:30 --end 00:01:00 \
  --voice-name MiVoz \
  --text "Hola, esto es una prueba" \
  --output resultado.mp3
```