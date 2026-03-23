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
        st.rerun()

    def on_output_folder_type_change():
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
        st.rerun()

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
                st.rerun(scope="fragment")
        
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
        
        if st.button("📂 Cambiar carpeta de salida", help="Elegir otra carpeta para guardar audios", use_container_width=True):
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
    st.session_state.last_sidebar_values = {
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

tab_generate, tab_outputs, tab_voices = st.tabs(["🗣️ Generar Audio", "📂 Audios Generados", "🎤 Gestionar Voces"])

# ── TAB 1: Generar Audio ────────────────────────────────────────────────────
with tab_generate:
    st.subheader("Texto a convertir en audio")

    text_input = st.text_area(
        "Escribe o pega tu texto aquí:",
        height=200,
        placeholder="Primera carrera del campeonato en el circuito australiano de Albert Park...",
        key="text_input"
    )

    st.subheader("Nombre del archivo de salida")
    custom_name = st.text_input(
        "Nombre personalizado (opcional)", 
        placeholder="ejemplo",
        help="Si no se especifica, se usará un ID aleatorio. Si el nombre ya existe, se añadirá un sufijo (_1, _2, etc.)",
        key="custom_name"
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        generate_btn = st.button("🚀 Generar Audio", type="primary", use_container_width=True)

    if generate_btn:
        # Persistir configuración actual antes de generar
        st.session_state.config.update({
            "voice_folder_type": selected_folder_type,
            "custom_folder_path": custom_folder_path,
            "output_folder_type": selected_output_folder_type,
            "custom_output_path": custom_output_path,
            "selected_voice": selected_voice,
            "selected_model_name": selected_model_name,
            "output_format": output_format,
            "cfg_scale": cfg_scale,
            "ddpm_steps": ddpm_steps,
            "disable_prefill": disable_prefill,
            "last_text_input": text_input,
            "last_custom_name": custom_name
        })
        save_config(st.session_state.config)

        if not text_input.strip():
            st.warning("⚠️ Escribe algo de texto primero.")
        elif not selected_voice:
            st.warning("⚠️ Selecciona una voz.")
        else:
            payload = {
                "text": text_input,
                "voice_name": selected_voice,
                "custom_output_name": custom_name if custom_name.strip() else None,
                "output_directory": output_directory,
                "model": selected_model,
                "output_format": output_format,
                "cfg_scale": cfg_scale,
                "ddpm_steps": ddpm_steps,
                "disable_prefill": disable_prefill,
            }

            # Para manejar el ID antes de que termine el POST (complicado si es síncrono)
            # pero vamos a usar el nombre personalizado si existe para pre-calcular el ID
            temp_audio_id = custom_name.strip() if custom_name.strip() else "gen_audio"

            with st.spinner(f"Generando audio..."):
                # Mostrar barra de progreso vacía
                prog_bar = st.progress(0)
                status_txt = st.empty()
                time_txt = st.empty()
                
                status_txt.info("🚀 Iniciando generación...")

                # Como la API es síncrona, no podemos actualizar la barra MIENTRAS corre requests.post
                # A menos que usemos un hilo, pero Streamlit no lo gestiona bien.
                # Lo ideal sería que la API fuera asíncrona.
                # Como compromiso, vamos a mostrar que está en proceso.
                
                endpoint = "/generate"
                if voice_directory:
                    endpoint += f"?voice_directory={requests.utils.quote(voice_directory)}"

                try:
                    # Estrategia: Polling del progreso en un bucle mientras el POST está pendiente (en otro hilo)
                    # Usamos un hilo para que Streamlit no se bloquee y pueda actualizar la UI.
                    
                    import threading
                    
                    response_container = []
                    # Generar un ID temporal para rastrear el progreso si no hay custom_name
                    # Usamos milisegundos para evitar colisiones si el usuario pulsa rápido
                    temp_id = custom_name.strip() if custom_name.strip() else f"gen_{int(time.time() * 1000)}"
                    payload["audio_id_hint"] = temp_id 
                    
                    def make_request():
                        try:
                            # Hacemos el POST de generación de forma síncrona dentro del hilo
                            resp = requests.post(f"{API_URL}{endpoint}", json=payload, timeout=600)
                            response_container.append(resp)
                        except Exception as ex:
                            response_container.append(ex)

                    thread = threading.Thread(target=make_request)
                    thread.start()

                    start_time = time.time()
                    last_progress_update = start_time
                    
                    while thread.is_alive():
                        # Consultar progreso cada 0.5s
                        try:
                            p_resp = requests.get(f"{API_URL}/progress/{temp_id}", timeout=2)
                            if p_resp.status_code == 200:
                                p_data = p_resp.json()
                                total = p_data.get("total", 0)
                                current = p_data.get("current", 0)
                                p_start = p_data.get("start_time", start_time)
                                p_status = p_data.get("status", "starting")
                                
                                if total > 0:
                                    pct = min(current / total, 0.99)
                                    prog_bar.progress(pct)
                                    elapsed = time.time() - p_start
                                    
                                    if current > 0:
                                        # Actualizar UI cada 0.5s para no saturar
                                        if time.time() - last_progress_update > 0.5:
                                            speed = current / elapsed
                                            remaining = (total - current) / speed
                                            time_txt.caption(f"⏱️ Transcurrido: {elapsed:.1f}s | ⏳ Restante est.: {remaining:.1f}s")
                                            status_txt.info(f"Generando... Paso {current}/{total} ({pct*100:.1f}%)")
                                            last_progress_update = time.time()
                                    else:
                                        # Si el total ya se conoce pero vamos por el paso 0
                                        elapsed = time.time() - p_start
                                        status_txt.info(f"🚀 Iniciando difusión (Paso 0/{total})... ({elapsed:.1f}s)")
                                        time_txt.caption(f"⏱️ Transcurrido: {elapsed:.1f}s")
                                elif p_status == "starting":
                                    elapsed = time.time() - p_start
                                    status_txt.info(f"🚀 Iniciando generación... ({elapsed:.1f}s)")
                                    time_txt.caption(f"⏱️ Transcurrido: {elapsed:.1f}s")
                        except Exception:
                            pass
                        
                        time.sleep(0.5)

                    thread.join()
                    if not response_container:
                        st.error("❌ No se recibió respuesta de la API.")
                        st.stop()

                    response = response_container[0]
                    
                    if isinstance(response, Exception):
                        raise response

                    if response.status_code == 200:
                        result = response.json()
                        audio_id = result["audio_id"]
                        filename = result["filename"]

                        prog_bar.progress(100)
                        st.success(f"✅ Audio generado: **{filename}**")
                        
                        final_dir = output_directory if output_directory else "api_outputs"
                        st.info(f"📍 Ruta: `{final_dir}/{filename}`")

                        # Descarga y reproduce el audio
                        audio_get_url = f"{API_URL}/audio/{audio_id}"
                        if output_directory:
                            audio_get_url += f"?directory={requests.utils.quote(output_directory)}"
                            
                        audio_response = requests.get(audio_get_url)
                        if audio_response.status_code == 200:
                            st.audio(audio_response.content, format=f"audio/{output_format}")
                    else:
                        error_detail = response.json().get("detail", "Error desconocido")
                        st.error(f"❌ Error: {error_detail}")
                except Exception as e:
                    st.error(f"❌ Error de conexión: {e}")


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