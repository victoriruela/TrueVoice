"""
Frontend Streamlit para TrueVoice.
Consume la API REST de api_server.py.
"""

import streamlit as st
import requests
import io
import json
import os
import ctypes
from ctypes import wintypes
from pathlib import Path

# ── Configuración ───────────────────────────────────────────────────────────
API_URL = "http://localhost:8000"
CONFIG_FILE = Path("frontend_config.json")

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error guardando config: {e}")

def select_folder_windows():
    """Abre un diálogo nativo de Windows para seleccionar una carpeta sin usar tkinter."""
    # Estructura BROWSEINFO para SHBrowseForFolderW
    class BROWSEINFO(ctypes.Structure):
        _fields_ = [
            ("hwndOwner", wintypes.HWND),
            ("pidlRoot", ctypes.c_void_p),
            ("pszDisplayName", wintypes.LPWSTR),
            ("lpszTitle", wintypes.LPWSTR),
            ("ulFlags", wintypes.UINT),
            ("lpfn", ctypes.c_void_p),
            ("lParam", wintypes.LPARAM),
            ("iImage", ctypes.c_int),
        ]

    # Flags: BIF_RETURNONLYFSDIRS (1), BIF_NEWDIALOGSTYLE (64), BIF_USENEWUI (0x0040 | 0x0010)
    BIF_RETURNONLYFSDIRS = 0x0001
    BIF_NEWDIALOGSTYLE = 0x0040
    BIF_EDITBOX = 0x0010

    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32
    user32 = ctypes.windll.user32

    # Definir prototipos de funciones para evitar problemas de memoria
    shell32.SHBrowseForFolderW.argtypes = [ctypes.POINTER(BROWSEINFO)]
    shell32.SHBrowseForFolderW.restype = ctypes.c_void_p
    shell32.SHGetPathFromIDListW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR]
    shell32.SHGetPathFromIDListW.restype = wintypes.BOOL
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole32.CoTaskMemFree.restype = None

    # Inicializar COM (necesario para el diálogo moderno con BIF_NEWDIALOGSTYLE)
    ole32.CoInitialize(None)

    bi = BROWSEINFO()
    # Intentamos obtener la ventana activa para que el diálogo aparezca en primer plano
    bi.hwndOwner = user32.GetForegroundWindow() 
    bi.lpszTitle = "Selecciona la carpeta donde están tus voces (.wav)"
    bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE | BIF_EDITBOX

    pidl = shell32.SHBrowseForFolderW(ctypes.byref(bi))
    
    selected_path = None
    if pidl:
        path_buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        if shell32.SHGetPathFromIDListW(pidl, path_buf):
            selected_path = path_buf.value
        # MUY IMPORTANTE: Liberar la memoria asignada por SHBrowseForFolderW
        ole32.CoTaskMemFree(pidl)
        
    ole32.CoUninitialize()
    return selected_path

# Carga inicial de configuración
if "config" not in st.session_state:
    st.session_state.config = load_config()

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
st.sidebar.subheader("🎤 Selección de Voces")

# Tipo de carpeta
folder_options = ["Carpeta por defecto (TrueVoice/voices)", "Escoger carpeta local"]
saved_folder_type = st.session_state.config.get("voice_folder_type", folder_options[0])
default_folder_idx = folder_options.index(saved_folder_type) if saved_folder_type in folder_options else 0

def on_folder_type_change():
    if st.session_state.folder_type_selectbox == "Escoger carpeta local":
        new_path = select_folder_windows()
        if new_path:
            st.session_state.config["custom_folder_path"] = new_path
            # No necesitamos llamar a st.rerun() aquí, on_change se encarga de que Streamlit continúe

selected_folder_type = st.sidebar.selectbox(
    "Origen de las voces",
    folder_options,
    index=default_folder_idx,
    help="Selecciona de dónde cargar las voces",
    key="folder_type_selectbox",
    on_change=on_folder_type_change
)

voice_directory = None
if selected_folder_type == "Escoger carpeta local":
    custom_folder_path = st.session_state.config.get("custom_folder_path", "")
    if custom_folder_path:
        st.sidebar.caption(f"📁 Ruta: {custom_folder_path}")
    
    # Botón para cambiar la carpeta local en cualquier momento
    if st.sidebar.button("📂 Cambiar carpeta", help="Abrir explorador de archivos para elegir otra carpeta", use_container_width=True):
        new_path = select_folder_windows()
        if new_path:
            st.session_state.config["custom_folder_path"] = new_path
            st.rerun()
    
    if custom_folder_path.strip():
        voice_directory = custom_folder_path
else:
    custom_folder_path = ""

# Obtener voces de la carpeta seleccionada
params = {"directory": voice_directory} if voice_directory else {}
try:
    r = requests.get(f"{API_URL}/voices", params=params, timeout=10)
    r.raise_for_status()
    voices_data = r.json()
except Exception as e:
    st.sidebar.error(f"Error cargando voces: {e}")
    voices_data = []

voice_names = [v["alias"] or v["name"] for v in voices_data]

if not voice_names:
    st.sidebar.warning("No se encontraron archivos .wav en la carpeta.")
    selected_voice = ""
else:
    saved_voice = st.session_state.config.get("selected_voice")
    default_voice_idx = 0
    if saved_voice in voice_names:
        default_voice_idx = voice_names.index(saved_voice)
    
    selected_voice = st.sidebar.selectbox(
        "Seleccionar voz",
        voice_names,
        index=default_voice_idx,
        help="Elige la voz para la generación de audio",
    )

# Modelos
models_data = api_get("/models") or []
model_options = {m["name"]: m["id"] for m in models_data}
model_names = list(model_options.keys())

saved_model = st.session_state.config.get("selected_model_name")
default_model_idx = model_names.index(saved_model) if saved_model in model_names else 0

st.sidebar.subheader("🧠 Modelo")
selected_model_name = st.sidebar.selectbox(
    "Seleccionar modelo",
    model_names,
    index=default_model_idx,
    help="Modelo más grande = mejor calidad pero más lento",
)
selected_model = model_options[selected_model_name]

# Formato de salida
st.sidebar.subheader("📁 Formato de salida")
format_options = ["wav", "mp3", "flac", "ogg"]
saved_format = st.session_state.config.get("output_format")
default_format_idx = format_options.index(saved_format) if saved_format in format_options else 0

output_format = st.sidebar.selectbox(
    "Formato",
    format_options,
    index=default_format_idx,
)

# Parámetros avanzados
st.sidebar.subheader("🔧 Parámetros avanzados")

cfg_scale = st.sidebar.slider(
    "CFG Scale",
    min_value=0.5,
    max_value=5.0,
    value=st.session_state.config.get("cfg_scale", 2.3),
    step=0.1,
    help="Controla la fidelidad al texto. Más alto = sigue más el texto (1.5-2.5 recomendado)",
)

ddpm_steps = st.sidebar.slider(
    "DDPM Steps",
    min_value=1,
    max_value=100,
    value=st.session_state.config.get("ddpm_steps", 25),
    step=1,
    help="Pasos de difusión. Más pasos = mejor calidad pero más lento (20-50 recomendado)",
)

disable_prefill = st.sidebar.checkbox(
    "Desactivar clonación de voz",
    value=st.session_state.config.get("disable_prefill", False),
    help="Si se activa, usa una voz genérica (más rápido)",
)

# Guardar configuración automáticamente cuando cambia algo
current_config = {
    "voice_folder_type": selected_folder_type,
    "custom_folder_path": custom_folder_path,
    "selected_voice": selected_voice,
    "selected_model_name": selected_model_name,
    "output_format": output_format,
    "cfg_scale": cfg_scale,
    "ddpm_steps": ddpm_steps,
    "disable_prefill": disable_prefill
}

if current_config != st.session_state.config:
    st.session_state.config = current_config
    save_config(current_config)

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

    st.subheader("Nombre del archivo de salida")
    custom_name = st.text_input(
        "Nombre personalizado (opcional)", 
        placeholder="ejemplo",
        help="Si no se especifica, se usará un ID aleatorio. Si el nombre ya existe, se añadirá un sufijo (_1, _2, etc.)"
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        generate_btn = st.button("🚀 Generar Audio", type="primary", use_container_width=True)

    if generate_btn:
        if not text_input.strip():
            st.warning("⚠️ Escribe algo de texto primero.")
        elif not selected_voice:
            st.warning("⚠️ Selecciona una voz.")
        else:
            with st.spinner(f"Generando audio... Esto puede tardar varios minutos."):
                payload = {
                    "text": text_input,
                    "voice_name": selected_voice,
                    "custom_output_name": custom_name if custom_name.strip() else None,
                    "model": selected_model,
                    "output_format": output_format,
                    "cfg_scale": cfg_scale,
                    "ddpm_steps": ddpm_steps,
                    "disable_prefill": disable_prefill,
                }

                # Añadir directorio si es personalizado
                endpoint = "/generate"
                if voice_directory:
                    endpoint += f"?voice_directory={requests.utils.quote(voice_directory)}"

                response = api_post_json(endpoint, payload)

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