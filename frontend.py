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
import time
from ctypes import wintypes
from pathlib import Path

# ── Configuración ───────────────────────────────────────────────────────────
API_URL = "http://localhost:8000"
CONFIG_FILE = Path("frontend_config.json")

def cleanup_temp_api():
    try:
        requests.post(f"{API_URL}/cleanup_temp", timeout=5)
    except:
        pass

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Asegurar que las carpetas de salida tengan valores por defecto si no existen
                if "output_folder_type" not in config:
                    config["output_folder_type"] = "Usar carpeta por defecto (api_outputs)"
                if "texts_folder_type" not in config:
                    config["texts_folder_type"] = "Usar carpeta por defecto (race_sessions/textos)"
                return config
        except Exception:
            return {}
    return {
        "output_folder_type": "Usar carpeta por defecto (api_outputs)",
        "texts_folder_type": "Usar carpeta por defecto (race_sessions/textos)"
    }

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error guardando config: {e}")

def select_folder_windows(title="Selecciona una carpeta"):
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
    bi.lpszTitle = title
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

    # --- Gestión de múltiples tareas de generación ---
if "generation_tasks" not in st.session_state:
    # Intentamos cargar las tareas guardadas en config
    saved_tasks = st.session_state.config.get("generation_tasks", [])
    if saved_tasks:
        st.session_state.generation_tasks = saved_tasks
    else:
        # Si no hay tareas guardadas, usamos los campos antiguos o uno vacío
        last_text = st.session_state.config.get("last_text_input", "")
        last_name = st.session_state.config.get("last_custom_name", "")
        st.session_state.generation_tasks = [
            {"text": last_text, "custom_name": last_name, "id": 0, "status": "idle", "result": None}
        ]

def add_generation_task():
    # Obtener el último nombre para incremental
    last_task = st.session_state.generation_tasks[-1] if st.session_state.generation_tasks else None
    new_name = ""
    if last_task and last_task["custom_name"]:
        import re
        name = last_task["custom_name"]
        # Buscar número al final del nombre
        match = re.search(r'(\d+)$', name)
        if match:
            num = int(match.group(1))
            prefix = name[:match.start()]
            # Manejar si el prefijo termina en guion bajo o similar
            new_name = f"{prefix}{num + 1}"
        else:
            # Si no hay número, añadir _1 o 1 según prefieras
            # Usaremos _1 si no hay número
            new_name = f"{name}_1"
    else:
        new_name = f"audio_1"
    
    new_id = int(time.time() * 1000) # ID único basado en tiempo para evitar colisiones
    st.session_state.generation_tasks.append({
        "text": "", 
        "custom_name": new_name, 
        "id": new_id, 
        "status": "idle", 
        "result": None
    })

def remove_generation_task(task_id):
    if len(st.session_state.generation_tasks) > 1:
        st.session_state.generation_tasks = [t for t in st.session_state.generation_tasks if t["id"] != task_id]
    else:
        # Si es el último, solo lo limpiamos
        st.session_state.generation_tasks = [
            {"text": "", "custom_name": "", "id": 0, "status": "idle", "result": None}
        ]

# Sincronizar selectboxes y campos de texto con la configuración cargada
if "folder_type_selectbox" not in st.session_state:
    st.session_state.folder_type_selectbox = st.session_state.config.get("voice_folder_type", "Carpeta por defecto (TrueVoice/voices)")

if "output_folder_type_selectbox" not in st.session_state:
    st.session_state.output_folder_type_selectbox = st.session_state.config.get("output_folder_type", "Carpeta por defecto (api_outputs)")

if "text_input" not in st.session_state:
    st.session_state.text_input = st.session_state.config.get("last_text_input", "")

if "custom_name" not in st.session_state:
    st.session_state.custom_name = st.session_state.config.get("last_custom_name", "")

st.set_page_config(
    page_title="TrueVoice",
    page_icon="🎙️",
    layout="wide",
)


# ── Funciones auxiliares ────────────────────────────────────────────────────
@st.cache_data(ttl=10, show_spinner="Cargando...")
def api_get(endpoint: str, params: dict = None):
    """GET a la API con caché ligera."""
    try:
        r = requests.get(f"{API_URL}{endpoint}", params=params, timeout=10)
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
# Al iniciar/refrescar la página, limpiar temporales
if "init_cleanup_done" not in st.session_state:
    cleanup_temp_api()
    st.session_state.init_cleanup_done = True

# No usamos caché para el healthcheck inicial
try:
    api_status = requests.get(f"{API_URL}/", timeout=5).json()
except:
    st.error("❌ No se puede conectar con la API.")
    st.stop()


# ── Sidebar: Configuración ──────────────────────────────────────────────────
@st.fragment
def render_sidebar(voices_data, models_data):
    st.title("⚙️ Configuración")

    # Voces
    st.subheader("🎤 Selección de Voces")

    # Tipo de carpeta
    folder_options = ["Carpeta por defecto (TrueVoice/voices)", "Escoger carpeta local"]

    def on_folder_type_change():
        cleanup_temp_api()
        if "current_generated_audio" in st.session_state:
            del st.session_state.current_generated_audio
        if st.session_state.folder_type_selectbox == "Escoger carpeta local":
            new_path = select_folder_windows("Selecciona la carpeta donde están tus voces (.wav)")
            if new_path:
                st.session_state.config["custom_folder_path"] = new_path
                st.session_state.config["voice_folder_type"] = "Escoger carpeta local"
                save_config(st.session_state.config)
            else:
                # Si cancela, volvemos a la por defecto
                st.session_state.folder_type_selectbox = "Carpeta por defecto (TrueVoice/voices)"
                st.session_state.config["voice_folder_type"] = "Carpeta por defecto (TrueVoice/voices)"
                save_config(st.session_state.config)
        # Necesitamos rerun global porque la lista de voces cambiará
        st.cache_data.clear() # Limpiar cache para que se actualice la lista de voces
        # st.rerun() # Eliminado para evitar error en callback

    def on_output_folder_type_change():
        cleanup_temp_api()
        if "current_generated_audio" in st.session_state:
            del st.session_state.current_generated_audio
        if st.session_state.output_folder_type_selectbox == "Escoger carpeta local":
            new_path = select_folder_windows("Selecciona la carpeta para guardar los audios")
            if new_path:
                st.session_state.config["custom_output_path"] = new_path
                st.session_state.config["output_folder_type"] = "Escoger carpeta local"
                save_config(st.session_state.config)
            else:
                # Si cancela, volvemos a la por defecto
                st.session_state.output_folder_type_selectbox = "Carpeta por defecto (api_outputs)"
                st.session_state.config["output_folder_type"] = "Carpeta por defecto (api_outputs)"
                save_config(st.session_state.config)
        else:
            # Si se cambia a la carpeta por defecto manualmente
            st.session_state.config["output_folder_type"] = "Carpeta por defecto (api_outputs)"
            save_config(st.session_state.config)
        
        # Forzar que la lista de audios se actualice inmediatamente
        st.cache_data.clear()
        # st.rerun() # Eliminado para evitar error en callback

    selected_folder_type = st.selectbox(
        "Origen de las voces",
        folder_options,
        help="Selecciona de dónde cargar las voces",
        key="folder_type_selectbox",
        on_change=on_folder_type_change
    )

    voice_directory = None
    if selected_folder_type == "Escoger carpeta local":
        custom_folder_path = st.session_state.config.get("custom_folder_path", "")
        if custom_folder_path:
            st.caption(f"📁 Ruta: {custom_folder_path}")
        
        # Botón para cambiar la carpeta local en cualquier momento
        if st.button("📂 Cambiar carpeta", help="Abrir explorador de archivos para elegir otra carpeta", use_container_width=True):
            new_path = select_folder_windows()
            if new_path:
                st.session_state.config["custom_folder_path"] = new_path
                save_config(st.session_state.config)
                st.cache_data.clear() # Limpiar cache para que se actualice la lista de voces
                st.rerun() # Rerun global para que la lista de voces se actualice
        
        if custom_folder_path.strip():
            voice_directory = custom_folder_path
    else:
        custom_folder_path = ""

    # Obtener voces de la carpeta seleccionada (pasadas por parámetro)
    voice_names = [v["alias"] or v["name"] for v in voices_data]

    if not voice_names:
        st.warning("No se encontraron archivos .wav en la carpeta.")
        selected_voice = ""
    else:
        saved_voice = st.session_state.config.get("selected_voice")
        default_voice_idx = 0
        if saved_voice in voice_names:
            default_voice_idx = voice_names.index(saved_voice)
        
        selected_voice = st.selectbox(
            "Seleccionar voz",
            voice_names,
            index=default_voice_idx,
            help="Elige la voz para la generación de audio",
            key="selected_voice_sidebar"
        )

    # Modelos (pasados por parámetro)
    model_options = {m["name"]: m["id"] for m in models_data}
    model_names = list(model_options.keys())

    saved_model = st.session_state.config.get("selected_model_name")
    default_model_idx = model_names.index(saved_model) if saved_model in model_names else 0

    st.subheader("🧠 Modelo")
    selected_model_name = st.selectbox(
        "Seleccionar modelo",
        model_names,
        index=default_model_idx,
        help="Modelo más grande = mejor calidad pero más lento",
        key="selected_model_name_sidebar"
    )
    selected_model = model_options[selected_model_name]

    # Formato de salida
    st.subheader("📁 Salida de Audio")
    output_folder_options = ["Carpeta por defecto (api_outputs)", "Escoger carpeta local"]
    selected_output_folder_type = st.selectbox(
        "Carpeta de salida",
        output_folder_options,
        key="output_folder_type_selectbox",
        on_change=on_output_folder_type_change
    )

    output_directory = None
    if selected_output_folder_type == "Escoger carpeta local":
        custom_output_path = st.session_state.config.get("custom_output_path", "")
        if custom_output_path:
            st.caption(f"📁 Ruta: {custom_output_path}")
        
        if st.button("📂 Cambiar carpeta de salida", help="Elegir otra carpeta para guardar audios", key="btn_change_out_audio", use_container_width=True):
            new_path = select_folder_windows("Selecciona la carpeta para guardar los audios")
            if new_path:
                st.session_state.config["custom_output_path"] = new_path
                save_config(st.session_state.config)
                st.cache_data.clear() # Limpiar cache para que se actualice la lista de audios
                st.rerun() # Rerun global para que el tab de audios se actualice
        
        if custom_output_path.strip():
            output_directory = custom_output_path
    else:
        custom_output_path = ""

    # Formato de salida de texto (Excel)
    st.subheader("📄 Salida de Texto")
    
    def on_texts_folder_type_change():
        if st.session_state.texts_folder_type_selectbox == "Escoger carpeta local":
            new_path = select_folder_windows("Selecciona la carpeta para guardar los archivos Excel")
            if new_path:
                st.session_state.config["custom_texts_path"] = new_path
                st.session_state.config["texts_folder_type"] = "Escoger carpeta local"
                save_config(st.session_state.config)
            else:
                st.session_state.texts_folder_type_selectbox = "Carpeta por defecto (race_sessions/textos)"
                st.session_state.config["texts_folder_type"] = "Carpeta por defecto (race_sessions/textos)"
                save_config(st.session_state.config)
        else:
            st.session_state.config["texts_folder_type"] = "Carpeta por defecto (race_sessions/textos)"
            save_config(st.session_state.config)
        # st.rerun() # Eliminado para evitar error en callback

    texts_folder_options = ["Carpeta por defecto (race_sessions/textos)", "Escoger carpeta local"]
    saved_texts_folder_type = st.session_state.config.get("texts_folder_type", "Carpeta por defecto (race_sessions/textos)")
    
    # Asegurar que el index coincida
    default_texts_folder_idx = texts_folder_options.index(saved_texts_folder_type) if saved_texts_folder_type in texts_folder_options else 0

    st.selectbox(
        "Carpeta de salida Excel",
        texts_folder_options,
        index=default_texts_folder_idx,
        key="texts_folder_type_selectbox",
        on_change=on_texts_folder_type_change
    )

    if st.session_state.config.get("texts_folder_type") == "Escoger carpeta local":
        custom_texts_path = st.session_state.config.get("custom_texts_path", "")
        if custom_texts_path:
            st.caption(f"📁 Ruta: {custom_texts_path}")
        
        if st.button("📂 Cambiar carpeta de textos", help="Elegir otra carpeta para guardar Excel", key="btn_change_out_texts", use_container_width=True):
            new_path = select_folder_windows("Selecciona la carpeta para guardar los archivos Excel")
            if new_path:
                st.session_state.config["custom_texts_path"] = new_path
                save_config(st.session_state.config)
                st.rerun()

    st.divider()
    format_options = ["wav", "mp3", "flac", "ogg"]
    saved_format = st.session_state.config.get("output_format")
    default_format_idx = format_options.index(saved_format) if saved_format in format_options else 0

    output_format = st.selectbox(
        "Formato",
        format_options,
        index=default_format_idx,
        key="output_format_sidebar"
    )

    # Parámetros avanzados
    st.subheader("🔧 Parámetros avanzados")

    cfg_scale = st.slider(
        "CFG Scale",
        min_value=0.5,
        max_value=5.0,
        value=st.session_state.config.get("cfg_scale", 2.3),
        step=0.1,
        help="Controla la fidelidad al texto. Más alto = sigue más el texto (1.5-2.5 recomendado)",
        key="cfg_scale_sidebar"
    )

    ddpm_steps = st.slider(
        "DDPM Steps",
        min_value=1,
        max_value=100,
        value=st.session_state.config.get("ddpm_steps", 25),
        step=1,
        help="Pasos de difusión. Más pasos = mejor calidad pero más lento (20-50 recomendado)",
        key="ddpm_steps_sidebar"
    )

    disable_prefill = st.checkbox(
        "Desactivar clonación de voz",
        value=st.session_state.config.get("disable_prefill", False),
        help="Si se activa, usa una voz genérica (más rápido)",
        key="disable_prefill_sidebar"
    )

    # Info del preset seleccionado
    st.divider()
    st.caption(f"🔊 Voz: **{selected_voice}**")
    st.caption(f"🧠 Modelo: **{selected_model_name}**")
    st.caption(f"📊 CFG: **{cfg_scale}** | DDPM: **{ddpm_steps}**")

    # Retornamos los valores actuales para que estén disponibles en el estado global
    # pero como usamos key="...", ya se guardan en session_state.
    # Actualizamos el estado interno de config para que sea accesible fuera del fragmento
    # si es necesario, aunque lo ideal es leer de session_state directamente.
    
    # IMPORTANTE: Para que los valores persistan fuera del fragmento, debemos sincronizarlos
    # pero sin forzar rerun global.
    sidebar_values = {
        "voice_folder_type": selected_folder_type,
        "custom_folder_path": custom_folder_path,
        "output_folder_type": selected_output_folder_type,
        "custom_output_path": custom_output_path,
        "selected_voice": selected_voice,
        "selected_model_name": selected_model_name,
        "selected_model": selected_model,
        "output_format": output_format,
        "cfg_scale": cfg_scale,
        "ddpm_steps": ddpm_steps,
        "disable_prefill": disable_prefill,
        "output_directory": output_directory,
        "voice_directory": voice_directory
    }

    # Comprobar si algo ha cambiado para guardar la config
    changed = False
    for k, v in sidebar_values.items():
        if st.session_state.config.get(k) != v:
            st.session_state.config[k] = v
            changed = True
    
    if changed:
        save_config(st.session_state.config)

    st.session_state.last_sidebar_values = sidebar_values

# Extraer valores para el sidebar antes de llamar al fragmento
# Así evitamos "Running API Get" cada vez que se interactúa con el fragmento
v_dir = None
if st.session_state.folder_type_selectbox == "Escoger carpeta local":
    v_dir = st.session_state.config.get("custom_folder_path", "")

v_params = {"directory": v_dir} if v_dir else {}
v_data = api_get("/voices", params=v_params) or []
m_data = api_get("/models") or []

with st.sidebar:
    render_sidebar(v_data, m_data)

# Extraer valores para el resto de la app
sidebar_values = st.session_state.get("last_sidebar_values", {})
selected_voice = sidebar_values.get("selected_voice", "")
selected_model_name = sidebar_values.get("selected_model_name", "")
selected_model = sidebar_values.get("selected_model", "qwen2.5_1.5b_64k")
output_format = sidebar_values.get("output_format", "wav")
cfg_scale = sidebar_values.get("cfg_scale", 2.3)
ddpm_steps = sidebar_values.get("ddpm_steps", 25)
disable_prefill = sidebar_values.get("disable_prefill", False)
output_directory = sidebar_values.get("output_directory")
voice_directory = sidebar_values.get("voice_directory")
selected_folder_type = sidebar_values.get("voice_folder_type")
custom_folder_path = sidebar_values.get("custom_folder_path")
selected_output_folder_type = sidebar_values.get("output_folder_type")
custom_output_path = sidebar_values.get("custom_output_path")


# ── Contenido principal ─────────────────────────────────────────────────────
st.title("🎙️ TrueVoice")
st.caption("Generación de audio con clonación de voz — Powered by VibeVoice")

tab_texts, tab_generate, tab_outputs, tab_voices = st.tabs(["📝 Generar textos y audios de carrera", "🗣️ Generar Audio", "📂 Audios Generados", "🎤 Gestionar Voces"])

# ── TAB 1: Generar Audio ────────────────────────────────────────────────────
with tab_generate:
    st.subheader("Configuración de audios")
    
    # Contenedor para las tareas (LIMPIAR DUPLICADO ANTERIOR SI EXISTE)
    # Nota: El bloque anterior quedó arriba por el search_replace previo.
    # Vamos a limpiar el bloque duplicado que quedó entre lineas 472-529 aprox.

    # Botones de control global
    st.divider()
    
    # --- Definición de función de generación ---
    def run_generation(task_idx):
        task = st.session_state.generation_tasks[task_idx]
        if not task["text"].strip():
            st.warning(f"⚠️ El audio #{task_idx + 1} no tiene texto.")
            return False
        
        payload = {
            "text": task["text"],
            "voice_name": st.session_state.selected_voice_sidebar,
            "custom_output_name": task["custom_name"] if task["custom_name"].strip() else None,
            "output_directory": output_directory,
            "model": selected_model,
            "output_format": output_format,
            "cfg_scale": cfg_scale,
            "ddpm_steps": ddpm_steps,
            "disable_prefill": disable_prefill,
        }

        # Usar una columna para que aparezca a la izquierda
        c_status, _ = st.columns([2, 1])
        with c_status:
            with st.status(f"Generando Audio #{task_idx + 1}...", expanded=True) as status:
                prog_bar = st.progress(0)
                status_txt = st.empty()
                time_txt = st.empty()
            
            endpoint = "/generate"
            if voice_directory:
                endpoint += f"?voice_directory={requests.utils.quote(voice_directory)}"

            try:
                import threading
                response_container = []
                temp_id = task["custom_name"].strip() if task["custom_name"].strip() else f"gen_{task['id']}_{int(time.time() * 1000)}"
                payload["audio_id_hint"] = temp_id 
                
                def make_request():
                    try:
                        resp = requests.post(f"{API_URL}{endpoint}", json=payload, timeout=600)
                        response_container.append(resp)
                    except Exception as ex:
                        response_container.append(ex)

                thread = threading.Thread(target=make_request)
                thread.start()

                start_time = time.time()
                last_progress_update = start_time
                
                while thread.is_alive():
                    try:
                        p_resp = requests.get(f"{API_URL}/progress/{temp_id}", timeout=2)
                        if p_resp.status_code == 200:
                            p_data = p_resp.json()
                            total = p_data.get("total", 0)
                            current = p_data.get("current", 0)
                            p_start = p_data.get("start_time", start_time)
                            
                            if total > 0:
                                pct = min(current / total, 0.99)
                                prog_bar.progress(pct)
                                elapsed = time.time() - p_start
                                if current > 0:
                                    if time.time() - last_progress_update > 0.5:
                                        speed = current / elapsed
                                        remaining = (total - current) / speed
                                        time_txt.caption(f"⏱️ {elapsed:.1f}s | ⏳ Est: {remaining:.1f}s")
                                        status_txt.info(f"Paso {current}/{total} ({pct*100:.1f}%)")
                                        last_progress_update = time.time()
                                else:
                                    status_txt.info(f"🚀 Iniciando ({elapsed:.1f}s)...")
                    except: pass
                    time.sleep(0.5)

                thread.join()
                response = response_container[0]
                if isinstance(response, Exception): raise response

                if response.status_code == 200:
                    result = response.json()
                    task["result"] = {
                        "audio_id": result["audio_id"],
                        "filename": result["filename"],
                        "output_directory": output_directory
                    }
                    prog_bar.progress(100)
                    status.update(label=f"✅ Audio #{task_idx + 1} listo", state="complete", expanded=False)
                    return True
                else:
                    st.error(f"Error en audio #{task_idx + 1}: {response.json().get('detail')}")
                    return False
            except Exception as e:
                st.error(f"Error conexión: {e}")
                return False

    # Redefinir el loop de tareas para usar la función
    # (En una app real lo ideal es no re-renderizar todo, pero aquí es más simple)
    # Sin embargo, Streamlit re-ejecuta todo el script, así que necesitamos capturar el clic antes.
    
    # Para que los botones individuales funcionen correctamente con la función, 
    # los manejaremos mediante variables en session_state o comprobando el botón en el loop.
    
    # RE-IMPLEMENTACIÓN DEL LOOP CON GENERACIÓN FUNCIONAL
    st.empty() # Placeholder
    
    @st.fragment
    def render_generation_tasks():
        # Estilo CSS para botones dinámicos y globales
        st.markdown("""
            <style>
            /* Botón GUARDAR TODO (verde) */
            div.stButton > button[key="btn_save_all_green"] {
                background-color: #28a745 !important;
                color: white !important;
                border: 1px solid #28a745 !important;
            }
            div.stButton > button[key="btn_save_all_green"]:hover {
                background-color: #218838 !important;
                border-color: #1e7e34 !important;
            }

            /* Botones de GUARDAR individuales (verde) */
            div.stButton > button[key^="s_"] {
                background-color: #28a745 !important;
                color: white !important;
                border: 1px solid #28a745 !important;
            }
            div.stButton > button[key^="s_"]:hover {
                background-color: #218838 !important;
                border-color: #1e7e34 !important;
            }

            /* Botones de GENERAR individuales (rojo) */
            div.stButton > button[key^="g_"] {
                background-color: #dc3545 !important;
                color: white !important;
                border: 1px solid #dc3545 !important;
            }
            div.stButton > button[key^="g_"]:hover {
                background-color: #c82333 !important;
                border-color: #bd2130 !important;
            }

            /* Botón GENERAR TODO (rojo) */
            div.stButton > button[key="btn_gen_all"] {
                background-color: #dc3545 !important;
                color: white !important;
                border: 1px solid #dc3545 !important;
            }
            div.stButton > button[key="btn_gen_all"]:hover {
                background-color: #c82333 !important;
                border-color: #bd2130 !important;
            }
            
            /* Asegurar que el texto sea blanco para todos estos botones */
            div.stButton > button[key="btn_save_all_green"] p,
            div.stButton > button[key^="s_"] p,
            div.stButton > button[key^="g_"] p,
            div.stButton > button[key="btn_gen_all"] p {
                color: white !important;
            }
            </style>
        """, unsafe_allow_html=True)

        tasks_changed = False
        for idx, task in enumerate(st.session_state.generation_tasks):
            with st.expander(f"Audio #{idx + 1}: {task['custom_name'] or 'Sin nombre'}", expanded=(task["result"] is None)):
                col_t1, col_t2 = st.columns([4, 1])
                with col_t1:
                    # Cálculo de altura dinámica para que se vea todo el texto
                    text_content = task["text"] or ""
                    num_lines = text_content.count("\n") + 1
                    dynamic_height = max(100, min(500, num_lines * 25 + 20)) # Min 100, Max 500 para evitar que sea excesivamente largo
                    
                    new_text = st.text_area(
                        f"Texto {idx+1}", 
                        value=task["text"], 
                        height=dynamic_height, 
                        key=f"t_{task['id']}"
                    )
                    if new_text != task["text"]:
                        task["text"] = new_text
                        tasks_changed = True
                with col_t2:
                    new_name = st.text_input("Nombre", value=task["custom_name"], key=f"n_{task['id']}")
                    if new_name != task["custom_name"]:
                        task["custom_name"] = new_name
                        tasks_changed = True
                    if st.button("🗑️", key=f"d_{task['id']}", use_container_width=True):
                        remove_generation_task(task["id"])
                        st.session_state.config["generation_tasks"] = st.session_state.generation_tasks
                        save_config(st.session_state.config)
                        st.rerun(scope="fragment")

                if task["result"]:
                    res = task["result"]
                    audio_get_url = f"{API_URL}/audio/{res['audio_id']}"
                    audio_response = requests.get(audio_get_url)
                    if audio_response.status_code == 200:
                        st.audio(audio_response.content, format=f"audio/{output_format}")
                
                c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 2])
                
                with c_btn1:
                    # Botón GUARDAR a la izquierda si hay resultado
                    if task["result"]:
                        res = task["result"]
                        if st.button("💾 GUARDAR", key=f"s_{task['id']}", use_container_width=True):
                            save_payload = {"audio_id": res["audio_id"], "output_directory": output_directory}
                            s_resp = requests.post(f"{API_URL}/confirm_save", json=save_payload)
                            if s_resp.status_code == 200:
                                st.toast(f"✅ Guardado")
                                task["result"] = None
                                st.cache_data.clear()
                                st.rerun() # Rerun global para refrescar el tab de audios generados
                    else:
                        st.empty()

                with c_btn2:
                    if st.button("🚀 Generar", key=f"g_{task['id']}", use_container_width=True):
                        # Asegurar que la voz seleccionada se guarde antes de generar
                        st.session_state.config["selected_voice"] = st.session_state.get("selected_voice_sidebar")
                        save_config(st.session_state.config)
                        run_generation(idx)
                        st.rerun() # Rerun global para mostrar reproductor y botón de guardar correctamente

        if tasks_changed:
            st.session_state.config["generation_tasks"] = st.session_state.generation_tasks
            save_config(st.session_state.config)

        # Determinar si hay audios pendientes de guardar
        pending_save = [t for t in st.session_state.generation_tasks if t["result"] is not None]

        if pending_save:
            col_g1, col_g2, col_g3, col_g4 = st.columns([1, 1, 1, 1])
            with col_g1:
                btn_save_all = st.button("💾 GUARDAR TODO", use_container_width=True, key="btn_save_all_green")
            with col_g2:
                btn_gen_all = st.button("🚀 GENERAR TODO", use_container_width=True, key="btn_gen_all")
            with col_g3:
                btn_add = st.button("➕ Añadir texto", use_container_width=True, key="btn_add_bottom")
            with col_g4:
                btn_clear = st.button("🧹 Limpiar todo", use_container_width=True, key="btn_clear_all")
        else:
            # Si no hay botón guardar todo, centramos los otros 3
            btn_save_all = False
            _, col_g2, col_g3, col_g4, _ = st.columns([0.5, 1, 1, 1, 0.5])
            with col_g2:
                btn_gen_all = st.button("🚀 GENERAR TODO", use_container_width=True, key="btn_gen_all")
            with col_g3:
                btn_add = st.button("➕ Añadir texto", use_container_width=True, key="btn_add_bottom")
            with col_g4:
                btn_clear = st.button("🧹 Limpiar todo", use_container_width=True, key="btn_clear_all")

        # Lógica de los botones
        if btn_save_all:
            # Asegurar que la voz seleccionada se guarde (por si acaso se cambió antes de guardar)
            st.session_state.config["selected_voice"] = st.session_state.get("selected_voice_sidebar")
            save_config(st.session_state.config)
            saved_count = 0
            for task in pending_save:
                res = task["result"]
                save_payload = {"audio_id": res["audio_id"], "output_directory": output_directory}
                s_resp = requests.post(f"{API_URL}/confirm_save", json=save_payload)
                if s_resp.status_code == 200:
                    task["result"] = None
                    saved_count += 1
            
            if saved_count > 0:
                st.toast(f"✅ Se han guardado {saved_count} audios")
                st.cache_data.clear()
                st.rerun()

        # Lógica de los botones (fuera de las columnas para evitar duplicidad de código si es posible)
        if btn_gen_all:
            # Asegurar que la voz seleccionada se guarde antes de generar
            st.session_state.config["selected_voice"] = st.session_state.get("selected_voice_sidebar")
            save_config(st.session_state.config)
            cleanup_temp_api()
            for i in range(len(st.session_state.generation_tasks)):
                run_generation(i)
            st.rerun()

        if btn_add:
            add_generation_task()
            st.session_state.config["generation_tasks"] = st.session_state.generation_tasks
            save_config(st.session_state.config)
            st.rerun(scope="fragment")

        if btn_clear:
            st.session_state.generation_tasks = [{"text": "", "custom_name": "", "id": 0, "status": "idle", "result": None}]
            st.session_state.config["generation_tasks"] = st.session_state.generation_tasks
            save_config(st.session_state.config)
            cleanup_temp_api()
            st.rerun(scope="fragment")

    render_generation_tasks()


# ── TAB 2: Audios Generados ─────────────────────────────────────────────────
with tab_outputs:
    # --- Inicialización de estado para selección de archivos ---
    if "selected_files" not in st.session_state:
        st.session_state.selected_files = set()

    @st.fragment
    def render_outputs(outputs_list):
        st.subheader("📁 Audios Generados")
        
        # outputs_list se pasa por parámetro para evitar Running API Get constante
        outputs = outputs_list

        if not outputs:
            st.info("No hay audios generados en esta carpeta.")
        else:
            # Fila superior: Conteo y Botones de selección/borrado
            col_header1, col_header2, col_header3, col_header4 = st.columns([2, 1, 1, 1.5])
            with col_header1:
                st.write(f"Se han encontrado **{len(outputs)}** archivos en la carpeta de salida.")
            
            with col_header2:
                if st.button("Seleccionar todos"):
                    st.session_state.selected_files = {f["filename"] for f in outputs}
                    # Al ser fragmento, este rerun es local al fragmento
                    st.rerun(scope="fragment")
            
            with col_header3:
                if st.button("Desseleccionar todos"):
                    st.session_state.selected_files = set()
                    st.rerun(scope="fragment")

            with col_header4:
                # Sincronizar selected_files con outputs actuales
                current_filenames = {f["filename"] for f in outputs}
                st.session_state.selected_files = {f for f in st.session_state.selected_files if f in current_filenames}
                
                num_selected = len(st.session_state.selected_files)
                if num_selected > 0:
                    if st.button(f"🗑️ Borrar los {num_selected} audios seleccionados", type="primary"):
                        del_params = {"filenames": list(st.session_state.selected_files)}
                        if output_directory:
                            del_params["directory"] = output_directory
                        
                        try:
                            # Para borrar no usamos caché, invalidamos la caché de la lista de archivos
                            st.cache_data.clear() 
                            del_resp = requests.delete(f"{API_URL}/outputs/delete", params=del_params)
                            if del_resp.status_code == 200:
                                st.success(f"Borrados: {len(del_resp.json()['deleted'])} archivos")
                                st.session_state.selected_files = set()
                                # Aquí sí necesitamos rerun global porque la lista de archivos cambió
                                st.rerun()
                            else:
                                st.error("Error al borrar archivos")
                        except Exception as e:
                            st.error(f"Error de conexión: {e}")

            st.divider()
            
            # Estilo para los botones de selección
            st.markdown("""
                <style>
                /* Estilo base para los botones de selección */
                div.stButton > button[key^="btn_sel_"] {
                    text-align: left;
                    justify-content: flex-start;
                    border: none !important;
                    background: transparent !important;
                    padding: 0 !important;
                    color: inherit !important;
                    font-weight: bold;
                    width: 100% !important;
                    height: auto !important;
                }
                
                /* Estilo para la marca de selección roja */
                .selection-mark {
                    color: #ff4b4b;
                    font-size: 1.5rem;
                    line-height: 1;
                    margin-right: 5px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100%;
                }
                </style>
            """,unsafe_allow_html=True)

            # Tabla de archivos
            for f in outputs:
                filename = f["filename"]
                is_selected = filename in st.session_state.selected_files
                
                # Usamos un container para agrupar
                with st.container(border=True):
                    c_info, c_play, c_sel_mark, c_del = st.columns([4, 1.5, 0.4, 0.6])
                    
                    with c_info:
                        # Al pulsar en el nombre, se selecciona/deselecciona
                        if st.button(f"📄 **{filename}**", key=f"btn_sel_{filename}", use_container_width=True):
                            if is_selected:
                                st.session_state.selected_files.remove(filename)
                            else:
                                st.session_state.selected_files.add(filename)
                            st.rerun(scope="fragment")
                        st.caption(f"📅 {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(f['created']))} | 📏 {f['size']/1024:.1f} KB")
                    
                    with c_play:
                        audio_id = f["id"]
                        audio_url = f"{API_URL}/audio/{audio_id}"
                        if output_directory:
                            audio_url += f"?directory={requests.utils.quote(output_directory)}"
                        
                        if st.button("▶️ Escuchar", key=f"play_{filename}"):
                            st.audio(audio_url)
                    
                    with c_sel_mark:
                        if is_selected:
                            st.markdown('<div class="selection-mark" title="Seleccionado para borrar">🔴</div>', unsafe_allow_html=True)
                        else:
                            st.write("") # Espacio vacío si no está seleccionado
                    
                    with c_del:
                        if st.button("🗑️", key=f"del_ind_{filename}", help="Borrar este audio permanentemente"):
                            del_params = {"filenames": [filename]}
                            if output_directory:
                                del_params["directory"] = output_directory
                            try:
                                st.cache_data.clear()
                                requests.delete(f"{API_URL}/outputs/delete", params=del_params)
                                if filename in st.session_state.selected_files:
                                    st.session_state.selected_files.remove(filename)
                                # Aquí también rerun global porque la lista cambió
                                st.rerun()
                            except:
                                st.error("Error al borrar")

    # Fuera del fragmento cargamos la lista (con caché)
    out_params = {"directory": output_directory} if output_directory else {}
    outputs_data = api_get("/outputs", params=out_params) or []
    render_outputs(outputs_data)


# ── TAB 3: Gestionar Voces ──────────────────────────────────────────────────
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


# ── TAB 1: Generar textos y audios de carrera ──────────────────────────────
with tab_texts:
    from race_parser import parse_race_file, parse_race_header, generate_ai_descriptions, generate_ai_intro, RaceEvent, RaceHeader

    st.subheader("📝 Generar textos y audios de carrera")
    st.caption("Sube un archivo XML de resultados de rFactor2 para extraer y narrar los eventos de la carrera.")

    # ── Configuración Ollama ────────────────────────────────────────────────
    with st.expander("⚙️ Configuración de Ollama", expanded=False):
        col_url, col_model = st.columns([2, 1])
        with col_url:
            def on_ollama_url_change():
                st.session_state.config["ollama_url"] = st.session_state.ollama_url_input
                save_config(st.session_state.config)

            ollama_url = st.text_input(
                "URL de Ollama",
                value=st.session_state.config.get("ollama_url", "http://localhost:11434"),
                placeholder="http://localhost:11434",
                key="ollama_url_input",
                on_change=on_ollama_url_change
            )
        with col_model:
            def on_ollama_model_change():
                st.session_state.config["ollama_model"] = st.session_state.ollama_model_input
                save_config(st.session_state.config)

            ollama_model = st.text_input(
                "Modelo",
                value=st.session_state.config.get("ollama_model", "llama3.2"),
                placeholder="llama3.2",
                key="ollama_model_input",
                on_change=on_ollama_model_change
            )

    ollama_url = st.session_state.get("ollama_url_input") or st.session_state.config.get("ollama_url", "http://localhost:11434")
    ollama_model = st.session_state.get("ollama_model_input") or st.session_state.config.get("ollama_model", "llama3.2")

    st.divider()

    # Sesiones y rutas
    import os, json as _json, dataclasses
    SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "race_sessions")
    _default_audios_dir_main = os.path.join(SESSIONS_DIR, "audios")
    _default_api_outputs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_outputs")
    
    # AUDIOS_DIR: Ahora unificado con "Salida de Audio"
    if st.session_state.config.get("output_folder_type") == "Escoger carpeta local":
        AUDIOS_DIR = st.session_state.config.get("custom_output_path", _default_api_outputs)
    else:
        AUDIOS_DIR = _default_api_outputs
    
    # TEXTS_DIR: Basado en "Salida de Texto"
    _default_texts_dir_main = os.path.join(SESSIONS_DIR, "textos")
    if st.session_state.config.get("texts_folder_type") == "Escoger carpeta local":
        TEXTS_DIR = st.session_state.config.get("custom_texts_path", _default_texts_dir_main)
    else:
        TEXTS_DIR = _default_texts_dir_main

    os.makedirs(SESSIONS_DIR, exist_ok=True)
    os.makedirs(AUDIOS_DIR, exist_ok=True)
    os.makedirs(TEXTS_DIR, exist_ok=True)

    def _sanitize_filename(s: str, max_len: int = 60) -> str:
        """Convierte una cadena en un nombre de archivo seguro."""
        import re
        s = re.sub(r'[^\w\s\-]', '', s, flags=re.UNICODE)
        s = re.sub(r'[\s]+', '_', s.strip())
        return s[:max_len]

    def _audio_filename_for_event(ev) -> str:
        lap_str = "formacion" if ev.lap == 0 else str(ev.lap)
        ts_str = f"{ev.timestamp:.0f}"
        summary_str = _sanitize_filename(ev.summary, 40)
        return f"{lap_str}_{ts_str}_{summary_str}.wav"

    def _audio_filename_for_intro() -> str:
        return "intro_carrera.wav"

    def _generate_audio_for_text(text: str, audio_filename: str) -> str:
        """Generar audio vía API y guardarlo en AUDIOS_DIR con lógica de no-sobrescritura. 
        Devuelve el nombre final del archivo generado o cadena vacía si falla."""
        import requests as _req2
        import shutil
        import os
        import time as _time

        # Determinar nombre final (evitar sobrescribir)
        base, ext = os.path.splitext(audio_filename)
        target_path = os.path.join(AUDIOS_DIR, audio_filename)
        counter = 1
        final_filename = audio_filename
        while os.path.exists(target_path):
            final_filename = f"{base} ({counter}){ext}"
            target_path = os.path.join(AUDIOS_DIR, final_filename)
            counter += 1

        payload = {
            "text": text,
            "voice_name": st.session_state.get("selected_voice_sidebar", ""),
            "custom_output_name": os.path.splitext(final_filename)[0],
            "output_directory": AUDIOS_DIR,
            "model": selected_model,
            "output_format": "wav",
            "cfg_scale": cfg_scale,
            "ddpm_steps": ddpm_steps,
            "disable_prefill": disable_prefill,
        }
        
        start_t = _time.time()
        try:
            # Mostrar contador mientras se genera
            resp = None
            
            # Contenedor para el estado y el tiempo transcurrido
            status_placeholder = st.empty()
            
            import threading
            
            response_container = []
            exception_container = []
            
            def _make_request():
                try:
                    r = _req2.post(f"{API_URL}/generate", json=payload, timeout=300)
                    response_container.append(r)
                except Exception as e:
                    exception_container.append(e)
            
            thread = threading.Thread(target=_make_request)
            thread.start()
            
            while thread.is_alive():
                current_elapsed = _time.time() - start_t
                status_placeholder.markdown(f"⏱️ **{current_elapsed:.1f}s**")
                _time.sleep(0.1)
            
            if exception_container:
                raise exception_container[0]
            
            resp = response_container[0] if response_container else None
            
            status_placeholder.empty() # Limpiar al terminar
            end_t = _time.time()
            elapsed = end_t - start_t
            
            if resp and resp.status_code == 200:
                result = resp.json()
                # El archivo ya debería estar en AUDIOS_DIR con el nombre solicitado
                generated_name = result.get("filename", "")
                generated_path = os.path.join(AUDIOS_DIR, generated_name)
                
                # Si el nombre generado por la API no coincide con el final_filename (por la lógica de la API)
                # o si necesitamos asegurar que se movió al destino final exacto
                if generated_name != final_filename and os.path.exists(generated_path):
                    shutil.move(generated_path, target_path)
                
                # Forzar confirm_save para asegurar que se mueva a la carpeta final (AUDIOS_DIR)
                # si es que la API lo dejó en temporal (is_temp=True)
                if result.get("is_temp"):
                    save_payload = {
                        "audio_id": result.get("audio_id"),
                        "output_directory": AUDIOS_DIR
                    }
                    _req2.post(f"{API_URL}/confirm_save", json=save_payload, timeout=30)

                # Guardar el tiempo de generación
                if "audio_generation_times" not in st.session_state:
                    st.session_state["audio_generation_times"] = {}
                st.session_state["audio_generation_times"][final_filename] = elapsed

                return final_filename
            return ""
        except Exception:
            return ""

    def _generate_text_for_event(event, ollama_url: str, ollama_model: str, used_descriptions: list = None,
                                    all_events: list = None) -> str:
        """Genera descripción IA para un único evento. Devuelve el texto generado o cadena vacía si falla."""
        import requests as _req
        type_hints = {
            1: "adelantamiento en carrera de Fórmula 1",
            2: "choque o contacto entre dos pilotos en carrera de Fórmula 1",
            3: "choque de un piloto contra el muro o barrera en carrera de Fórmula 1"
        }
        avoid_hint = ""
        if used_descriptions:
            last_few = used_descriptions[-5:]
            avoid_hint = f" Evita frases similares a: {'; '.join(last_few)}"
        # Contexto de adelantamientos previos del piloto (solo para Tipo 1)
        overtake_hint = ""
        if event.event_type == 1 and all_events:
            driver_a = event.summary.split(" adelanta a ")[0] if " adelanta a " in event.summary else ""
            if driver_a:
                prev_overtakes = sum(
                    1 for e in all_events
                    if e is not event and e.event_type == 1
                    and " adelanta a " in e.summary and e.summary.startswith(driver_a)
                    and (e.lap < event.lap or (e.lap == event.lap and e.timestamp < event.timestamp))
                )
                if prev_overtakes >= 3:
                    overtake_hint = f" Menciona que este piloto ya lleva {prev_overtakes} adelantamientos en la carrera."
        prompt = (
            f"Eres un comentarista deportivo de Fórmula 1 apasionado y dinámico. "
            f"Genera UNA SOLA frase corta (máximo 25 palabras) y emocionante describiendo este evento de "
            f"{type_hints.get(event.event_type, 'carrera')}: '{event.summary}' en la vuelta {event.lap}. "
            f"La descripción debe ser variada, natural y diferente a las anteriores.{overtake_hint} "
            f"Responde SOLO con la frase, sin comillas ni explicaciones adicionales.{avoid_hint}"
        )
        try:
            resp = _req.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.9, "top_p": 0.95, "seed": id(event) % 9999}
                },
                timeout=30
            )
            if resp.status_code == 200:
                return resp.json().get("response", "").strip().strip('"\'')
            else:
                st.error(f"❌ Ollama respondió {resp.status_code}: {resp.text[:300]}")
        except Exception as _ex:
            st.error(f"❌ Error al conectar con Ollama: {_ex}")
        return ""


    def _save_excel(name: str):
        """Guarda la tabla de eventos en un archivo Excel en TEXTS_DIR."""
        try:
            import openpyxl
        except ImportError:
            return None
        hdr = st.session_state.get("race_header")
        evs = st.session_state.get("race_events", [])
        event_audios = {}
        for i, ev in enumerate(evs):
            akey = f"event_audio_{i}"
            if st.session_state.get(akey):
                event_audios[str(i)] = st.session_state[akey]
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Eventos"
        ws.append(["Vuelta", "Timestamp", "Tipo", "Resumen", "Descripción IA", "Audio"])
        # Ordenar eventos por vuelta y luego por timestamp
        sorted_evs = sorted(enumerate(evs), key=lambda x: (x[1].lap if x[1].lap != 0 else -1, x[1].timestamp))
        for i, ev in sorted_evs:
            lap_label = "Vuelta de formación" if ev.lap == 0 else str(ev.lap)
            tipo = f"Tipo {ev.event_type}"
            desc = st.session_state.get(f"desc_edit_{i}", ev.description or "")
            audio_name = event_audios.get(str(i), "")
            ws.append([lap_label, ev.timestamp, tipo, ev.summary, desc, audio_name])
        safe_name = ".".join(c if c.isalnum() or c in " _-" else "_" for c in (name or "sesion")).strip()
        excel_path = os.path.join(TEXTS_DIR, f"{safe_name}.xlsx")
        wb.save(excel_path)
        return excel_path

    def _list_sessions():
        return sorted([f[:-5] for f in os.listdir(SESSIONS_DIR) if f.endswith(".json")])

    def _save_session(name: str):
        hdr = st.session_state.get("race_header")
        evs = st.session_state.get("race_events", [])
        intro = st.session_state.get("race_intro_text", "")
        # Recoger descripciones editadas del session_state
        for i, ev in enumerate(evs):
            key = f"desc_edit_{i}"
            if key in st.session_state:
                ev.description = st.session_state[key]
        # Recoger audios generados
        intro_audio = st.session_state.get("intro_audio_file", "")
        event_audios = {}
        for i, ev in enumerate(evs):
            akey = f"event_audio_{i}"
            if st.session_state.get(akey):
                event_audios[str(i)] = st.session_state[akey]
        data = {
            "intro_text": intro,
            "intro_audio": intro_audio,
            "header": dataclasses.asdict(hdr) if hdr else {},
            "events": [dataclasses.asdict(ev) for ev in evs],
            "event_audios": event_audios,
        }
        path = os.path.join(SESSIONS_DIR, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_session(name: str):
        from race_parser import RaceEvent, RaceHeader
        path = os.path.join(SESSIONS_DIR, f"{name}.json")
        with open(path, encoding="utf-8") as f:
            data = _json.load(f)
        hdr_d = data.get("header", {})
        hdr = RaceHeader(**hdr_d) if hdr_d else None
        evs = [RaceEvent(**e) for e in data.get("events", [])]
        intro = data.get("intro_text", "")
        intro_audio = data.get("intro_audio", "")
        event_audios = data.get("event_audios", {})
        
        # Guardar en configuración como última sesión
        st.session_state.config["last_race_session"] = name
        save_config(st.session_state.config)
        
        return hdr, evs, intro, intro_audio, event_audios

    def on_session_change():
        selected = st.session_state.get("session_selector")
        if selected and selected != "— Nueva sesión —":
            try:
                hdr_l, evs_l, intro_l, intro_audio_l, event_audios_l = _load_session(selected)
                st.session_state["race_header"] = hdr_l
                st.session_state["race_events"] = evs_l
                st.session_state["race_intro_text"] = intro_l
                st.session_state["race_ai_done"] = any(ev.description for ev in evs_l)
                st.session_state["intro_audio_file"] = intro_audio_l
                
                # Limpiar y restaurar session_state
                for k in list(st.session_state.keys()):
                    if k.startswith("desc_edit_") or k.startswith("event_audio_"):
                        del st.session_state[k]
                for i, ev in enumerate(evs_l):
                    st.session_state[f"desc_edit_{i}"] = ev.description or ""
                    akey = str(i)
                    if akey in event_audios_l:
                        st.session_state[f"event_audio_{i}"] = event_audios_l[akey]
                # Nota: success se mostrará en el siguiente rerun o mediante st.toast si estuviera disponible
            except Exception as ex:
                st.error(f"❌ Error al cargar sesión: {ex}")

    sessions = _list_sessions()
    
    # Carga automática de la última sesión al iniciar
    if "race_header" not in st.session_state and "last_race_session" in st.session_state.config:
        last_sess = st.session_state.config["last_race_session"]
        if last_sess in sessions:
            try:
                hdr_l, evs_l, intro_l, intro_audio_l, event_audios_l = _load_session(last_sess)
                st.session_state["race_header"] = hdr_l
                st.session_state["race_events"] = evs_l
                st.session_state["race_intro_text"] = intro_l
                st.session_state["race_ai_done"] = any(ev.description for ev in evs_l)
                st.session_state["intro_audio_file"] = intro_audio_l
                for i, ev in enumerate(evs_l):
                    st.session_state[f"desc_edit_{i}"] = ev.description or ""
                    akey = str(i)
                    if akey in event_audios_l:
                        st.session_state[f"event_audio_{i}"] = event_audios_l[akey]
            except:
                pass

    col_sess_load, col_sess_save = st.columns([2, 1])
    with col_sess_load:
        if sessions:
            # Determinar el índice por defecto para el selectbox
            default_ix = 0
            if "last_race_session" in st.session_state.config:
                ls = st.session_state.config["last_race_session"]
                if ls in sessions:
                    default_ix = sessions.index(ls) + 1 # +1 por "Nueva sesión"

            selected_session = st.selectbox(
                "📁 Cargar sesión guardada",
                options=["— Nueva sesión —"] + sessions,
                index=default_ix,
                key="session_selector",
                on_change=on_session_change
            )
        else:
            selected_session = "— Nueva sesión —"
            st.info("No hay sesiones guardadas aún.")
    with col_sess_save:
        save_session_btn = st.button(
            "💾 Guardar sesión",
            type="secondary",
            disabled=("race_header" not in st.session_state),
            key="btn_save_session"
        )

    if save_session_btn and st.session_state.get("race_header"):
        # Si hay generación de audios en curso, pararla
        if st.session_state.get("all_audio_running"):
            st.session_state["all_audio_stop"] = True
        hdr_tmp = st.session_state["race_header"]
        session_name = hdr_tmp.track_event or "sesion"
        # Sanitizar nombre de archivo
        session_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in session_name).strip()
        _save_session(session_name)
        
        # Guardar en configuración como última sesión
        st.session_state.config["last_race_session"] = session_name
        save_config(st.session_state.config)
        
        excel_path = _save_excel(session_name)
        if excel_path:
            st.success(f"✅ Sesión guardada como **{session_name}** (Excel: `{os.path.basename(excel_path)}`)")
        else:
            st.success(f"✅ Sesión guardada como **{session_name}**")
        st.session_state["all_audio_running"] = False
        st.session_state["all_audio_stop"] = False
        st.rerun()

    st.divider()

    # ── Subida de archivo ───────────────────────────────────────────────────
    uploaded_xml = st.file_uploader(
        "📂 Sube el archivo XML de resultados de carrera",
        type=["xml"],
        key="race_xml_uploader"
    )

    col_parse, col_intro, col_ai, col_all_audio = st.columns([1, 1, 1, 1])
    with col_parse:
        parse_btn = st.button("🔍 Parsear archivo", type="primary", disabled=(uploaded_xml is None), key="btn_parse_race")
    with col_intro:
        intro_btn = st.button(
            "🎙️ Generar intro con IA",
            type="secondary",
            disabled=("race_header" not in st.session_state),
            key="btn_intro_race"
        )
    with col_ai:
        ai_btn = st.button(
            "🤖 Generar descripciones con IA",
            type="secondary",
            disabled=("race_events" not in st.session_state or not st.session_state.get("race_events")),
            key="btn_ai_race"
        )
    with col_all_audio:
        all_audio_btn = st.button(
            "🔊 Generar audio de todos los textos",
            type="secondary",
            disabled=("race_events" not in st.session_state or not st.session_state.get("race_events")),
            key="btn_all_audio_race"
        )

    # ── Parseo ──────────────────────────────────────────────────────────────
    if parse_btn and uploaded_xml is not None:
        with st.spinner("Parseando archivo..."):
            try:
                xml_content = uploaded_xml.read().decode("utf-8", errors="replace")
                header = parse_race_header(xml_content)
                events = parse_race_file(xml_content)
                st.session_state["race_header"] = header
                st.session_state["race_events"] = events
                st.session_state["race_ai_done"] = False
                st.session_state["race_intro_text"] = ""
                st.session_state["intro_audio_file"] = ""
                # Limpiar textos editables y audios previos
                for k in list(st.session_state.keys()):
                    if k.startswith("desc_edit_") or k.startswith("event_audio_"):
                        del st.session_state[k]
                if events:
                    st.success(f"✅ Se han extraído **{len(events)} eventos** de la carrera.")
                else:
                    st.warning("⚠️ No se encontraron eventos en el archivo.")
                st.rerun()
            except Exception as ex:
                st.error(f"❌ Error al parsear: {ex}")

    # ── Generación intro IA ─────────────────────────────────────────────────
    if intro_btn and st.session_state.get("race_header"):
        with st.spinner("🎙️ Generando presentación de la carrera con IA..."):
            try:
                header = generate_ai_intro(
                    st.session_state["race_header"], ollama_url, ollama_model
                )
                st.session_state["race_header"] = header
                st.session_state["race_intro_text"] = header.intro_text or ""
                st.success("✅ Presentación generada.")
                st.rerun()
            except Exception as ex:
                st.error(f"❌ Error al generar intro: {ex}")
                import traceback
                st.code(traceback.format_exc())

    # ── Generar audio de todos los textos ──────────────────────────────────
    if all_audio_btn and st.session_state.get("race_events"):
        # Iniciar proceso paso a paso
        all_events_init = st.session_state["race_events"]
        intro_text_init = st.session_state.get("race_intro_text") or ""
        has_intro_init = bool(intro_text_init.strip())
        # El índice -1 representa la intro, 0..N-1 los eventos
        start_idx = -1 if has_intro_init else 0
        st.session_state["all_audio_running"] = True
        st.session_state["all_audio_stop"] = False
        st.session_state["all_audio_idx"] = start_idx
        st.session_state["all_audio_total"] = len(all_events_init) + (1 if has_intro_init else 0)
        st.session_state["all_audio_done"] = 0
        st.rerun()

    # ── Proceso paso a paso de generación de audios ─────────────────────────
    if st.session_state.get("all_audio_running"):
        all_events_run = st.session_state.get("race_events", [])
        idx_run = st.session_state.get("all_audio_idx", 0)
        total_run = st.session_state.get("all_audio_total", 1)
        done_run = st.session_state.get("all_audio_done", 0)

        # Comprobar si se ha pedido parar
        if st.session_state.get("all_audio_stop"):
            st.session_state["all_audio_running"] = False
            st.session_state["all_audio_stop"] = False
            st.info(f"⏹️ Generación de audios detenida ({done_run}/{total_run} completados).")
        else:
            prog_all = st.progress(done_run / total_run if total_run > 0 else 0)
            
            if idx_run == -1:
                # Generar audio de la intro
                intro_text_run = st.session_state.get("race_intro_text") or ""
                fname_intro_run = _audio_filename_for_intro()
                final_fname_intro = _generate_audio_for_text(intro_text_run, fname_intro_run)
                if final_fname_intro:
                    st.session_state["intro_audio_file"] = final_fname_intro
                st.session_state["all_audio_idx"] = 0
                st.session_state["all_audio_done"] = done_run + 1
                st.rerun()
            elif idx_run < len(all_events_run):
                # Generar audio de un evento
                ev_run = all_events_run[idx_run]
                text_run = st.session_state.get(f"desc_edit_{idx_run}") or ev_run.description or ev_run.summary
                fname_run = _audio_filename_for_event(ev_run)
                final_fname_run = _generate_audio_for_text(text_run, fname_run)
                if final_fname_run:
                    st.session_state[f"event_audio_{idx_run}"] = final_fname_run
                st.session_state["all_audio_idx"] = idx_run + 1
                st.session_state["all_audio_done"] = done_run + 1
                st.rerun()
            else:
                # Proceso completado
                prog_all.empty()
                st.success(f"✅ Audios generados: {done_run}/{total_run}")
                st.session_state["all_audio_running"] = False

    # ── Generación IA ───────────────────────────────────────────────────────
    if ai_btn and st.session_state.get("race_events"):
        events_to_describe = st.session_state["race_events"]
        progress_bar = st.progress(0)
        status_placeholder = st.empty()
        total = len(events_to_describe)

        import requests as _req
        used_descriptions = []

        for i, event in enumerate(events_to_describe):
            status_placeholder.info(f"🤖 Generando descripción {i+1}/{total}...")
            progress_bar.progress((i + 1) / total)

            type_hints = {
                1: "adelantamiento en carrera de Fórmula 1",
                2: "choque o contacto entre dos pilotos en carrera de Fórmula 1",
                3: "choque de un piloto contra el muro o barrera en carrera de Fórmula 1"
            }
            avoid_hint = ""
            if used_descriptions:
                last_few = used_descriptions[-5:]
                avoid_hint = f" Evita frases similares a: {'; '.join(last_few)}"

            prompt = (
                f"Eres un comentarista deportivo de Fórmula 1 apasionado y dinámico. "
                f"Genera UNA SOLA frase corta (máximo 25 palabras) y emocionante describiendo este evento de "
                f"{type_hints.get(event.event_type, 'carrera')}: '{event.summary}' en la vuelta {event.lap}. "
                f"La descripción debe ser variada, natural y diferente a las anteriores. "
                f"Responde SOLO con la frase, sin comillas ni explicaciones adicionales.{avoid_hint}"
            )

            try:
                resp = _req.post(
                    f"{ollama_url}/api/generate",
                    json={
                        "model": ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.9, "top_p": 0.95, "seed": i * 37 + 13}
                    },
                    timeout=30
                )
                if resp.status_code == 200:
                    desc = resp.json().get("response", "").strip().strip('"\'')
                    event.description = desc
                    used_descriptions.append(desc)
                else:
                    event.description = event.summary
                    status_placeholder.error(f"❌ Ollama respondió {resp.status_code}: {resp.text[:300]}")
                    break
            except Exception as _ex:
                event.description = event.summary
                status_placeholder.error(f"❌ Error en evento {i+1}: {_ex}")
                break

        progress_bar.empty()
        status_placeholder.success(f"✅ Descripciones generadas para {total} eventos.")
        st.session_state["race_events"] = events_to_describe
        st.session_state["race_ai_done"] = True
        # Inicializar textos editables con las descripciones generadas
        for i, ev in enumerate(events_to_describe):
            st.session_state[f"desc_edit_{i}"] = ev.description or ev.summary
        st.rerun()

    # ── Apartado de cabecera de la carrera ─────────────────────────────────
    if st.session_state.get("race_header"):
        hdr: RaceHeader = st.session_state["race_header"]
        st.divider()
        st.subheader("🏟️ Información de la carrera")
        with st.container(border=True):
            col_a, col_b, col_c, col_d = st.columns([2, 1.5, 1, 1])
            col_a.metric("Circuito", hdr.track_event)
            col_b.metric("Longitud", f"{hdr.track_length:.0f} m")
            col_c.metric("Vueltas", hdr.race_laps)
            col_d.metric("Pilotos", hdr.num_drivers)

            if hdr.grid_order:
                st.markdown("**🚦 Orden de salida:**")
                grid_cols = st.columns(min(4, len(hdr.grid_order)))
                for idx, driver in enumerate(hdr.grid_order):
                    grid_cols[idx % len(grid_cols)].markdown(f"**{idx+1}.** {driver}")

            if st.session_state.get("race_intro_text") or hdr.intro_text:
                st.divider()
                intro_val = st.session_state.get("race_intro_text") or hdr.intro_text or ""
                edited_intro = st.text_area(
                    "🎙️ Presentación de la carrera (editable)",
                    value=intro_val,
                    height=100,
                    key="intro_text_area"
                )
                if edited_intro != intro_val:
                    st.session_state["race_intro_text"] = edited_intro
                    hdr.intro_text = edited_intro
                    st.session_state["race_header"] = hdr

                # Botones de audio para la intro
                intro_audio_file = st.session_state.get("intro_audio_file", "")
                intro_audio_path = os.path.join(AUDIOS_DIR, intro_audio_file) if intro_audio_file else ""
                btn_col_intro_gen, btn_col_intro_play = st.columns([1, 3])
                with btn_col_intro_gen:
                    if st.button("🔊 Generar audio", key="btn_gen_audio_intro"):
                        with st.spinner("Generando audio de la intro..."):
                            fname = _audio_filename_for_intro()
                            final_fname = _generate_audio_for_text(edited_intro or intro_val, fname)
                            if final_fname:
                                st.session_state["intro_audio_file"] = final_fname
                                # st.success(f"✅ Audio generado en carpeta: {final_fname}")
                                st.rerun()
                            else:
                                st.error("❌ Error al generar audio")
                with btn_col_intro_play:
                    if intro_audio_file and os.path.exists(intro_audio_path):
                        # Mostrar tiempo de generación si existe
                        gen_time = st.session_state.get("audio_generation_times", {}).get(intro_audio_file)
                        time_str = f" ({gen_time:.1f}s)" if gen_time else ""
                        st.caption(f"🎵 `{intro_audio_file}`{time_str}")
                        # Reproductor directo
                        st.audio(intro_audio_path, format="audio/wav")

    # ── Tabla de eventos ────────────────────────────────────────────────────
    if st.session_state.get("race_events"):
        events: list = st.session_state["race_events"]
        ai_done: bool = st.session_state.get("race_ai_done", False)

        st.divider()
        st.subheader("📊 Eventos de la carrera")

        type_labels = {1: "🏎️ Adelantamiento", 2: "💥 Choque entre pilotos", 3: "🧱 Choque contra el muro"}

        # Agrupar eventos por vuelta
        from collections import defaultdict
        events_by_lap: dict = defaultdict(list)
        for ev in events:
            events_by_lap[ev.lap].append(ev)

        for lap_num in sorted(events_by_lap.keys()):
            # Ordenar por timestamp dentro de cada vuelta
            lap_events = sorted(events_by_lap[lap_num], key=lambda e: e.timestamp)

            lap_label = f"Vuelta {lap_num}" if lap_num > 0 else "Vuelta de formación"

            with st.container(border=True):
                st.markdown(f"**🏁 {lap_label}** &nbsp;·&nbsp; {len(lap_events)} evento(s)")

                # Cabecera de columnas
                h1, h2, h3, h4 = st.columns([1, 1.2, 2, 3])
                h1.markdown("**Timestamp**")
                h2.markdown("**Tipo**")
                h3.markdown("**Resumen**")
                h4.markdown("**Descripción IA**")
                st.divider()

                for ev in lap_events:
                    # Calcular índice global del evento
                    ev_idx = events.index(ev)
                    ts_str = f"{ev.timestamp:.1f}s" if ev.timestamp > 0 else "—"
                    type_str = type_labels.get(ev.event_type, str(ev.event_type))
                    default_desc = ev.description if ev.description else ("" if not ai_done else ev.summary)
                    edit_key = f"desc_edit_{ev_idx}"
                    # Si hay una descripción nueva pendiente (generada por IA), actualizar antes del widget
                    pending_key = f"desc_pending_{ev_idx}"
                    if pending_key in st.session_state:
                        st.session_state[edit_key] = st.session_state.pop(pending_key)
                    elif edit_key not in st.session_state:
                        st.session_state[edit_key] = default_desc

                    c1, c2, c3, c4, c_del = st.columns([1, 1.2, 2, 3, 0.4])
                    c1.markdown(f"`{ts_str}`")
                    c2.markdown(type_str)
                    c3.markdown(ev.summary)
                    with c_del:
                        if st.button("🗑️", key=f"btn_del_ev_{ev_idx}", help="Eliminar este evento"):
                            st.session_state["race_events"].remove(ev)
                            # Limpiar claves de session_state asociadas
                            for _k in [edit_key, f"event_audio_{ev_idx}"]:
                                st.session_state.pop(_k, None)
                            st.rerun()
                    with c4:
                        edited = st.text_area(
                            "Descripción",
                            value=st.session_state[edit_key],
                            height=80,
                            key=edit_key,
                            label_visibility="collapsed"
                        )
                        if edited != ev.description:
                            ev.description = edited

                        # Botones de texto y audio para el evento
                        ev_audio_key = f"event_audio_{ev_idx}"
                        ev_audio_file = st.session_state.get(ev_audio_key, "")
                        ev_audio_path = os.path.join(AUDIOS_DIR, ev_audio_file) if ev_audio_file else ""
                        ab0, ab1, ab2 = st.columns([1.2, 1, 3])
                        with ab0:
                            if st.button("✍️ Generar texto", key=f"btn_gen_text_ev_{ev_idx}"):
                                with st.spinner("Generando texto..."):
                                    new_desc = _generate_text_for_event(ev, ollama_url, ollama_model, all_events=events)
                                    if new_desc:
                                        ev.description = new_desc
                                        st.session_state[pending_key] = new_desc
                                        st.rerun()
                        with ab1:
                            if st.button("🔊 Generar audio", key=f"btn_gen_audio_ev_{ev_idx}"):
                                with st.spinner("Generando..."):
                                    fname_ev = _audio_filename_for_event(ev)
                                    text_ev = st.session_state.get(edit_key) or ev.summary
                                    final_fname_ev = _generate_audio_for_text(text_ev, fname_ev)
                                    if final_fname_ev:
                                        st.session_state[ev_audio_key] = final_fname_ev
                                        # st.success(f"✅ Audio generado en carpeta: {final_fname_ev}")
                                        st.rerun()
                                    else:
                                        st.error("❌ Error")
                        with ab2:
                            if ev_audio_file and os.path.exists(ev_audio_path):
                                # Mostrar tiempo de generación si existe
                                gen_time = st.session_state.get("audio_generation_times", {}).get(ev_audio_file)
                                time_str = f" ({gen_time:.1f}s)" if gen_time else ""
                                st.caption(f"🎵 `{ev_audio_file}`{time_str}")
                                st.audio(ev_audio_path, format="audio/wav")