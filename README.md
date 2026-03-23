# TrueVoice — Generador de Audio con Clonación de Voz

Aplicación completa para generar audio a partir de texto usando [VibeVoice de Microsoft](https://github.com/microsoft/VibeVoice), con soporte para clonación de voz desde archivos de audio, vídeo o YouTube.

Incluye **interfaz web (Streamlit)**, **API REST (FastAPI)** y **CLI** (línea de comandos).

## 🚀 Características

- ✅ **Conversión de texto a audio (TTS)** con clonación de voz.
- ✅ **Interfaz web** intuitiva con Streamlit.
- ✅ **API REST** con FastAPI (documentación interactiva en `/docs`).
- ✅ **CLI completo** para uso automatizado o por terminal.
- ✅ **Clonación de voz** desde archivos de audio (`.wav`, `.mp3`) o vídeo (`.mp4`, `.mkv`, etc.).
- ✅ **Extracción desde YouTube**: Crea voces directamente desde fragmentos de vídeos.
- ✅ **Múltiples formatos**: Salida en WAV, MP3, FLAC u OGG.
- ✅ **Control de calidad**: Ajuste de parámetros como CFG Scale y DDPM Steps.
- ✅ **Gestión de voces**: Listar, subir y eliminar voces personalizadas.
- ✅ **Soporte Hardware**: Compatible con GPU (CUDA) y CPU.

---

## 🛠️ Instalación

### 1. Requisitos previos
- Python 3.10 o superior.
- [FFmpeg](https://ffmpeg.org/) instalado y en el PATH (necesario para procesar vídeo y audio).
- (Opcional) NVIDIA GPU con drivers actualizados para aceleración CUDA.

### 2. Clonar e instalar dependencias
```bash
git clone https://github.com/tu-usuario/TrueVoice.git
cd TrueVoice
pip install -r requirements.txt
```

### 3. Primera ejecución
La primera vez que uses la aplicación, se descargará automáticamente:
1. El repositorio oficial de VibeVoice.
2. El modelo pre-entrenado (~6 GB para la versión 1.5b).

---

## 🖥️ Uso — Interfaz Web (Recomendado)

Para usar la interfaz web, se recomienda tener **dos terminales** abiertas:

**Terminal 1 — Iniciar la API REST:**
```bash
python api_server.py
```
*La API correrá por defecto en `http://localhost:8000`.*

**Terminal 2 — Iniciar el Frontend:**
```bash
streamlit run frontend.py
```
*El frontend se abrirá en tu navegador en `http://localhost:8501`.*

---

## 🔌 API REST

Si prefieres integrar TrueVoice en otras aplicaciones, usa la API.

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/` | Estado de la API |
| `GET` | `/voices` | Lista de voces disponibles |
| `POST` | `/generate` | Genera audio (JSON) |
| `GET` | `/audio/{id}`| Descarga el audio generado |
| `POST` | `/voices/upload`| Sube una nueva voz (Multipart) |
| `DELETE`| `/voices/{name}`| Elimina una voz personalizada |

**Documentación Interactiva:** Visita `http://localhost:8000/docs` una vez iniciada la API.

---

## 💻 Uso — CLI (Línea de Comandos)

El script principal es `vibevoice_app.py`.

### Comandos comunes:

**Listar voces:**
```bash
python vibevoice_app.py --list-voices
```

**Generar audio con voz predeterminada:**
```bash
python vibevoice_app.py --text "Hola, bienvenido a TrueVoice." --output saludo.wav
```

**Clonar una voz desde un archivo local:**
```bash
python vibevoice_app.py --clone-voice mi_referencia.mp3 --voice-name MiVoz --text "Texto con mi voz."
```

**Extraer voz desde YouTube:**
```bash
python vibevoice_app.py --youtube-voice "URL_VIDEO" --start 00:00:10 --end 00:00:20 --voice-name ViralVoice
```

---

## ⚙️ Configuración y Calidad

### Parámetros ajustables:

| Parámetro | Descripción | Rango | Recomendado |
|-----------|-------------|-------|-------------|
| **CFG Scale** | Fidelidad al texto. | 0.5 – 5.0 | 1.5 – 2.5 |
| **DDPM Steps**| Calidad/Detalle. | 1 – 200 | 20 – 50 |

### Modelos:
- `microsoft/VibeVoice-1.5b` (Default): Equilibrio entre velocidad y calidad. Funciona bien en CPU.
- `microsoft/VibeVoice-7b`: Máxima calidad. Requiere ~28GB de VRAM (GPU).

---

## ❓ Solución de Problemas

- **Error de Symlinks en Windows:** Activa el **Modo Desarrollador** en la configuración de Windows.
- **FFmpeg no encontrado:** Asegúrate de que `ffmpeg` esté instalado. Prueba ejecutando `ffmpeg -version` en tu terminal.
- **Memoria insuficiente:** Si usas el modelo 7B y falla, intenta volver al 1.5b (por defecto).

---

## 📄 Referencias
- [VibeVoice Oficial](https://github.com/microsoft/VibeVoice)
- [Hugging Face Models](https://huggingface.co/collections/microsoft/vibevoice)