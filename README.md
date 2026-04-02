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
- ✅ **Narración de carreras rFactor2**: Parseo de archivos XML de carrera, generación de textos con IA (Ollama) y síntesis de audio por evento.

---

## 🛠️ Instalación

### 1. Requisitos previos
- Python 3.10 o superior.
- [FFmpeg](https://ffmpeg.org/) instalado y en el PATH (necesario para procesar vídeo y audio).
- (Opcional) NVIDIA GPU con drivers actualizados para aceleración CUDA.
- (Opcional) [Ollama](https://ollama.com/) instalado y en ejecución para la generación de textos con IA (pestaña "Generar textos y audios de carrera").

### 2. Clonar e instalar dependencias
```bash
git clone https://github.com/tu-usuario/TrueVoice.git
cd TrueVoice
pip install -r requirements.txt
```

### 3. Ejecución rápida (Launcher)
Si prefieres no abrir varias terminales, puedes usar el lanzador automático:
```bash
python launcher.py
```
*Esto iniciará la API, el Frontend y abrirá tu navegador automáticamente.*

---

## 🖥️ Uso — Interfaz Web (Manual)

Para usar la interfaz web, se recomienda tener **dos terminales** abiertas:

**Terminal 1 — Iniciar la API REST:**
```bash
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000
```
*La API correrá por defecto en `http://localhost:8000`.*

**Terminal 2 — Iniciar el Frontend:**
```bash
streamlit run frontend.py
```
*El frontend se abrirá en tu navegador en `http://localhost:8501`.*

---

## 📝 Generar textos y audios de carrera (rFactor2)

La primera pestaña de la interfaz web, **"📝 Generar textos y audios de carrera"**, permite narrar automáticamente una carrera de rFactor2 a partir de su archivo XML de resultados.

### Flujo de trabajo

1. **Configurar Ollama**: Expande el panel "⚙️ Configuración de Ollama" e introduce la URL de tu instancia de Ollama (por defecto `http://localhost:11434`) y el nombre del modelo (por defecto `llama3.2`). También puedes configurar las carpetas de salida para audios y para el Excel de textos. La configuración se guarda automáticamente.

2. **Cargar archivo XML**: Sube el archivo `.xml` de resultados de carrera de rFactor2 y pulsa **"🔍 Parsear archivo"**. Se extraerá:
   - **Información de cabecera**: nombre del circuito, longitud, número de vueltas y orden de salida de los pilotos.
   - **Eventos de carrera** clasificados en tres tipos:
     - **Tipo 1 — Adelantamiento**: inferido a partir de los cambios de posición entre vueltas.
     - **Tipo 2 — Choque entre pilotos**: extraído de los incidentes `<Incident>` con otro vehículo, deduplicado por timestamp y par de pilotos.
     - **Tipo 3 — Choque contra el muro**: extraído de los incidentes `<Incident>` con el muro, deduplicado por timestamp y piloto.

3. **Generar intro con IA**: Pulsa **"🎙️ Generar intro con IA"** para que Ollama redacte una presentación de la carrera al estilo de un comentarista de Fórmula 1.

4. **Generar descripciones con IA**: Pulsa **"✨ Generar descripciones con IA"** para que Ollama genere una descripción narrativa y variada para cada evento de la tabla. También puedes:
   - Pulsar **"✍️ Generar texto"** en un evento concreto para regenerar solo esa descripción.
   - Editar manualmente cualquier texto generado directamente en el campo de texto.
   - Pulsar **"🗑️"** para eliminar un evento de la tabla.

5. **Generar audios**: Cada texto (intro y eventos) dispone de un botón **"🔊 Generar audio"** para sintetizar el audio con la voz configurada en TrueVoice. También hay un botón general **"🔊 Generar audio de todos los textos"** que procesa todos en cascada y puede detenerse en cualquier momento pulsando **"💾 Guardar sesión"**.

6. **Guardar y cargar sesiones**: Pulsa **"💾 Guardar sesión"** para persistir todos los textos, audios y eventos en un archivo JSON (nombrado con el circuito) y en un archivo Excel con las columnas: Vuelta, Timestamp, Tipo, Resumen, Descripción IA y Audio. Las sesiones guardadas aparecen en el selector de la parte superior para poder recargarlas en futuras sesiones.

### Tabla de eventos

Los eventos se muestran agrupados por vuelta (incluyendo la **Vuelta de formación** para eventos previos al inicio) y ordenados por timestamp dentro de cada vuelta. Cada fila contiene:

| Columna | Contenido |
|---------|-----------|
| **Timestamp** | Valor `et` del evento en segundos |
| **Tipo** | Tipo 1 / Tipo 2 / Tipo 3 |
| **Resumen** | Descripción genérica del evento |
| **Descripción IA** | Narración generada por Ollama (editable) |

### Deduplicación de eventos

- Los choques con el mismo timestamp y los mismos pilotos implicados se registran una sola vez.
- Si dos eventos del mismo tipo e implicados ocurren con menos de **7 segundos** de diferencia, solo se conserva el primero.

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
- **Ollama no genera texto:** Verifica que Ollama esté en ejecución (`ollama serve`) y que el modelo indicado esté descargado (`ollama pull llama3.2`). Los errores de conexión se muestran directamente en la interfaz.

---

## 📄 Referencias
- [VibeVoice Oficial](https://github.com/microsoft/VibeVoice)
- [Hugging Face Models](https://huggingface.co/collections/microsoft/vibevoice)
- [Ollama](https://ollama.com/)
