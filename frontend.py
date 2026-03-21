"""
Frontend Streamlit para TrueVoice.
Consume la API REST de api_server.py.
"""

import streamlit as st
import requests
import io

# ── Configuración ───────────────────────────────────────────────────────────
API_URL = "http://localhost:8000"

st.set_page_config(
    page_title="TrueVoice",
    page_icon="🎙️",
    layout="wide",
)


# ── Funciones auxiliares ────────────────────────────────────────────────────
def api_get(endpoint: str):
    """GET a la API."""
    try:
        r = requests.get(f"{API_URL}{endpoint}", timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError:
        st.error("❌ No se puede conectar con la API. ¿Está ejecutándose `api_server.py`?")
        st.info("Ejecuta en otra terminal: `uvicorn api_server:app --reload --port 8000`")
        st.stop()
    except Exception as e:
        st.error(f"Error de API: {e}")
        return None


def api_post_json(endpoint: str, data: dict):
    """POST JSON a la API."""
    try:
        r = requests.post(f"{API_URL}{endpoint}", json=data, timeout=600)
        return r
    except requests.ConnectionError:
        st.error("❌ No se puede conectar con la API.")
        st.stop()


def api_post_form(endpoint: str, data: dict, files: dict):
    """POST multipart a la API."""
    try:
        r = requests.post(f"{API_URL}{endpoint}", data=data, files=files, timeout=60)
        return r
    except requests.ConnectionError:
        st.error("❌ No se puede conectar con la API.")
        st.stop()


# ── Verificar conexión a la API ─────────────────────────────────────────────
api_status = api_get("/")
if not api_status:
    st.stop()


# ── Sidebar: Configuración ──────────────────────────────────────────────────
st.sidebar.title("⚙️ Configuración")

# Voces
voices_data = api_get("/voices") or []
voice_names = [v["alias"] or v["name"] for v in voices_data]

st.sidebar.subheader("🎤 Voz")
selected_voice = st.sidebar.selectbox(
    "Seleccionar voz",
    voice_names,
    index=voice_names.index("Alice") if "Alice" in voice_names else 0,
    help="Elige la voz para la generación de audio",
)

# Modelos
models_data = api_get("/models") or []
model_options = {m["name"]: m["id"] for m in models_data}

st.sidebar.subheader("🧠 Modelo")
selected_model_name = st.sidebar.selectbox(
    "Seleccionar modelo",
    list(model_options.keys()),
    index=0,
    help="Modelo más grande = mejor calidad pero más lento",
)
selected_model = model_options[selected_model_name]

# Formato de salida
st.sidebar.subheader("📁 Formato de salida")
output_format = st.sidebar.selectbox(
    "Formato",
    ["wav", "mp3", "flac", "ogg"],
    index=0,
)

# Parámetros avanzados
st.sidebar.subheader("🔧 Parámetros avanzados")

cfg_scale = st.sidebar.slider(
    "CFG Scale",
    min_value=0.5,
    max_value=5.0,
    value=2.0,
    step=0.1,
    help="Controla la fidelidad al texto. Más alto = sigue más el texto (1.5-2.5 recomendado)",
)

ddpm_steps = st.sidebar.slider(
    "DDPM Steps",
    min_value=1,
    max_value=100,
    value=30,
    step=1,
    help="Pasos de difusión. Más pasos = mejor calidad pero más lento (20-50 recomendado)",
)

disable_prefill = st.sidebar.checkbox(
    "Desactivar clonación de voz",
    value=False,
    help="Si se activa, usa una voz genérica (más rápido)",
)

# Info del preset seleccionado
st.sidebar.divider()
st.sidebar.caption(f"🔊 Voz: **{selected_voice}**")
st.sidebar.caption(f"🧠 Modelo: **{selected_model_name}**")
st.sidebar.caption(f"📊 CFG: **{cfg_scale}** | DDPM: **{ddpm_steps}**")


# ── Contenido principal ─────────────────────────────────────────────────────
st.title("🎙️ TrueVoice")
st.caption("Generación de audio con clonación de voz — Powered by VibeVoice")

tab_generate, tab_voices = st.tabs(["🗣️ Generar Audio", "🎤 Gestionar Voces"])

# ── TAB 1: Generar Audio ────────────────────────────────────────────────────
with tab_generate:
    st.subheader("Texto a convertir en audio")

    text_input = st.text_area(
        "Escribe o pega tu texto aquí:",
        height=200,
        placeholder="Primera carrera del campeonato en el circuito australiano de Albert Park...",
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        generate_btn = st.button("🚀 Generar Audio", type="primary", use_container_width=True)

    if generate_btn:
        if not text_input.strip():
            st.warning("⚠️ Escribe algo de texto primero.")
        else:
            with st.spinner(f"Generando audio con voz '{selected_voice}'... Esto puede tardar varios minutos."):
                payload = {
                    "text": text_input,
                    "voice_name": selected_voice,
                    "model": selected_model,
                    "output_format": output_format,
                    "cfg_scale": cfg_scale,
                    "ddpm_steps": ddpm_steps,
                    "disable_prefill": disable_prefill,
                }

                response = api_post_json("/generate", payload)

                if response and response.status_code == 200:
                    result = response.json()
                    audio_id = result["audio_id"]
                    filename = result["filename"]

                    st.success(f"✅ Audio generado: **{filename}**")

                    # Descarga y reproduce el audio
                    audio_response = requests.get(f"{API_URL}/audio/{audio_id}")
                    if audio_response.status_code == 200:
                        audio_bytes = audio_response.content

                        st.audio(audio_bytes, format=f"audio/{output_format}")

                        st.download_button(
                            label=f"⬇️ Descargar {filename}",
                            data=audio_bytes,
                            file_name=filename,
                            mime=f"audio/{output_format}",
                        )
                else:
                    error_detail = response.json().get("detail", "Error desconocido") if response else "Sin respuesta"
                    st.error(f"❌ Error: {error_detail}")


# ── TAB 2: Gestionar Voces ──────────────────────────────────────────────────
with tab_voices:
    st.subheader("Voces disponibles")

    # Recargar voces
    voices_data = api_get("/voices") or []

    if voices_data:
        cols = st.columns(3)
        for i, voice in enumerate(voices_data):
            with cols[i % 3]:
                alias_str = f" (alias: {voice['alias']})" if voice.get("alias") else ""
                is_default = voice.get("alias") is not None

                with st.container(border=True):
                    st.markdown(f"**{voice['name']}**{alias_str}")
                    st.caption(f"📄 {voice['filename']}")

                    if is_default:
                        st.caption("🔒 Voz predeterminada")
                    else:
                        if st.button(f"🗑️ Eliminar", key=f"del_{voice['name']}"):
                            r = requests.delete(f"{API_URL}/voices/{voice['name']}")
                            if r.status_code == 200:
                                st.success(f"✅ Voz '{voice['name']}' eliminada")
                                st.rerun()
                            else:
                                st.error(f"Error: {r.json().get('detail', 'Error')}")
    else:
        st.info("No hay voces disponibles.")

    st.divider()
    st.subheader("📤 Subir nueva voz")
    st.caption("Sube un archivo de audio (.wav) con una muestra de voz para clonar.")

    upload_col1, upload_col2 = st.columns([1, 2])
    with upload_col1:
        new_voice_name = st.text_input("Nombre de la voz", placeholder="MiVozPersonalizada")
    with upload_col2:
        uploaded_file = st.file_uploader(
            "Archivo de audio",
            type=["wav", "mp3", "flac", "ogg", "m4a"],
            help="Sube un archivo con 20-60 segundos de audio limpio de la voz que quieres clonar",
        )

    if st.button("📤 Subir voz", type="secondary"):
        if not new_voice_name.strip():
            st.warning("⚠️ Escribe un nombre para la voz.")
        elif not uploaded_file:
            st.warning("⚠️ Selecciona un archivo de audio.")
        else:
            with st.spinner(f"Procesando voz '{new_voice_name}'..."):
                files = {"audio_file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                data = {"voice_name": new_voice_name}
                response = api_post_form("/voices/upload", data, files)

                if response and response.status_code == 200:
                    st.success(f"✅ Voz '{new_voice_name}' añadida correctamente")
                    st.rerun()
                else:
                    error = response.json().get("detail", "Error") if response else "Sin respuesta"
                    st.error(f"❌ Error: {error}")