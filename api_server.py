"""
API REST para VibeVoice TTS con FastAPI.
Sirve como capa intermedia entre el frontend (Streamlit) y el backend (vibevoice_app.py).
"""

import os
import sys
import uuid
import subprocess
import traceback
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import json
import time

app = FastAPI(
    title="TrueVoice API",
    description="API REST para generación de audio con VibeVoice y clonación de voz",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rutas del proyecto ──────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.resolve()
VIBEVOICE_REPO = PROJECT_ROOT / "VibeVoice"
# Directorio por defecto: carpeta voices de TrueVoice
DEFAULT_VOICES_DIR = PROJECT_ROOT / "voices"
VIBEVOICE_VOICES_DIR = VIBEVOICE_REPO / "demo" / "voices"
OUTPUTS_DIR = PROJECT_ROOT / "api_outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)
DEFAULT_VOICES_DIR.mkdir(exist_ok=True) # Asegurar que existe

# Variable global para mantener compatibilidad con código antiguo que pueda usarla
VOICES_DIR = DEFAULT_VOICES_DIR

# ── Almacenamiento de Progreso ──────────────────────────────────────────────
# Estructura: { "audio_id": { "total": 100, "current": 10, "start_time": float, "last_update": float } }
PROGRESS_STORE = {}

print(f"[API] PROJECT_ROOT: {PROJECT_ROOT}")
print(f"[API] DEFAULT_VOICES_DIR: {DEFAULT_VOICES_DIR}")
print(f"[API] OUTPUTS_DIR:  {OUTPUTS_DIR}")


# ── Modelos Pydantic ────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Texto a convertir en audio")
    voice_name: str = Field("Alice", description="Nombre de la voz o ruta completa al archivo .wav")
    custom_output_name: Optional[str] = Field(None, description="Nombre personalizado para el archivo de salida")
    output_directory: Optional[str] = Field(None, description="Directorio de salida personalizado")
    audio_id_hint: Optional[str] = Field(None, description="Sugerencia de ID para rastrear progreso")
    model: str = Field("microsoft/VibeVoice-1.5b", description="Modelo HuggingFace")
    output_format: str = Field("wav", description="Formato de salida: wav, mp3, flac, ogg")
    cfg_scale: float = Field(2.0, ge=0.5, le=5.0, description="CFG scale (0.5-5.0)")
    ddpm_steps: int = Field(30, ge=1, le=200, description="Pasos DDPM (1-200)")
    disable_prefill: bool = Field(False, description="Desactivar clonación de voz")


class OutputFileInfo(BaseModel):
    id: str
    filename: str
    path: str
    size: int
    created: float


class VoiceInfo(BaseModel):
    name: str
    filename: str
    alias: Optional[str] = None


class GenerateResponse(BaseModel):
    success: bool
    message: str
    audio_id: Optional[str] = None
    filename: Optional[str] = None


# ── Utilidades ──────────────────────────────────────────────────────────────
DEFAULT_VOICES = {
    "Alice": "en-Alice_woman",
    "Carter": "en-Carter_man",
    "Frank": "en-Frank_man",
    "Mary": "en-Mary_woman_bgm",
    "Maya": "en-Maya_woman",
    "Samuel": "in-Samuel_man",
    "Anchen": "zh-Anchen_man_bgm",
    "Bowen": "zh-Bowen_man",
    "Xinran": "zh-Xinran_woman",
}

ALIAS_REVERSE = {v: k for k, v in DEFAULT_VOICES.items()}


def _resolve_voice(voice_name: str, directory: Optional[str] = None) -> Optional[str]:
    """Resuelve un nombre de voz al nombre exacto del archivo WAV o ruta absoluta."""
    # Si es una ruta absoluta y existe, la usamos directamente
    if os.path.isabs(voice_name) and voice_name.lower().endswith(".wav") and os.path.exists(voice_name):
        return voice_name

    # Determinar qué directorio usar
    target_dir = DEFAULT_VOICES_DIR
    if directory:
        custom_dir = Path(directory)
        if custom_dir.exists() and custom_dir.is_dir():
            target_dir = custom_dir

    if voice_name in DEFAULT_VOICES:
        resolved = DEFAULT_VOICES[voice_name]
        # Primero buscamos en el directorio proporcionado (con el nombre resuelto o el alias)
        if (target_dir / f"{resolved}.wav").exists():
            return str(target_dir / f"{resolved}.wav")
        if (target_dir / f"{voice_name}.wav").exists():
            return str(target_dir / f"{voice_name}.wav")
        # Fallback a VibeVoice original para las voces por defecto
        if (VIBEVOICE_VOICES_DIR / f"{resolved}.wav").exists():
            return str(VIBEVOICE_VOICES_DIR / f"{resolved}.wav")

    if (target_dir / f"{voice_name}.wav").exists():
        return str(target_dir / f"{voice_name}.wav")

    voice_lower = voice_name.lower()
    for wav in target_dir.glob("*.wav"):
        if voice_lower == wav.stem.lower(): # Coincidencia exacta primero
            return str(wav)
    
    for wav in target_dir.glob("*.wav"):
        if voice_lower in wav.stem.lower(): # Coincidencia parcial después
            return str(wav)

    return None


# ── Endpoints ───────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "ok", "service": "TrueVoice API", "version": "1.0.0"}


@app.get("/voices", response_model=list[VoiceInfo])
def list_voices(directory: Optional[str] = None):
    """Lista todas las voces disponibles en el directorio especificado o el predeterminado."""
    voices = []
    target_dir = DEFAULT_VOICES_DIR
    
    if directory:
        custom_dir = Path(directory)
        if custom_dir.exists() and custom_dir.is_dir():
            target_dir = custom_dir
        else:
            # Si el directorio no existe, devolvemos lista vacía
            return []

    for wav in sorted(target_dir.glob("*.wav")):
        alias = ALIAS_REVERSE.get(wav.stem)
        voices.append(VoiceInfo(name=wav.stem, filename=wav.name, alias=alias))
    
    return voices


@app.post("/generate", response_model=GenerateResponse)
def generate_audio(req: GenerateRequest, voice_directory: Optional[str] = None):
    """Genera audio a partir de texto usando VibeVoice."""
    try:
        print(f"[API] Solicitud de generación recibida. Voz: {req.voice_name}, Directorio: {voice_directory}")
        # Valida la voz (pasamos el directorio si existe)
        resolved_path = _resolve_voice(req.voice_name, voice_directory)
        if resolved_path is None:
            raise HTTPException(404, f"Voz '{req.voice_name}' no encontrada en el directorio especificado ({voice_directory or 'default'}).")

        # Valida formato
        fmt = req.output_format.lower().lstrip(".")
        if fmt not in ("wav", "mp3", "flac", "ogg"):
            raise HTTPException(400, f"Formato '{fmt}' no soportado. Usa: wav, mp3, flac, ogg")

        # Determinar directorio de salida
        target_output_dir = OUTPUTS_DIR
        if req.output_directory:
            custom_out = Path(req.output_directory)
            if custom_out.exists() and custom_out.is_dir():
                target_output_dir = custom_out
            else:
                try:
                    custom_out.mkdir(parents=True, exist_ok=True)
                    target_output_dir = custom_out
                except Exception as e:
                    print(f"[API] No se pudo crear el directorio de salida personalizado: {e}")

        # Genera un ID único para este audio
        if req.custom_output_name:
            # Sanitizar nombre (quitar extensión si la puso)
            base_name = Path(req.custom_output_name).stem
            # Lógica de evitar duplicados: ejemplo, ejemplo_1, ejemplo_2...
            final_name = f"{base_name}.{fmt}"
            counter = 1
            while (target_output_dir / final_name).exists():
                final_name = f"{base_name}_{counter}.{fmt}"
                counter += 1
            output_file = target_output_dir / final_name
            audio_id = Path(final_name).stem # Usamos el nombre base como ID si es personalizado
        else:
            # Comportamiento por defecto (UUID)
            audio_id = uuid.uuid4().hex[:12]
            output_file = target_output_dir / f"{audio_id}.{fmt}"

        # Si el cliente nos da una sugerencia (hint) para el progreso, la usamos o añadimos a la store
        progress_id = req.audio_id_hint if req.audio_id_hint else audio_id

        # Si el ID ya existe (por un reintento o coincidencia), limpiar progreso previo
        if progress_id in PROGRESS_STORE:
            print(f"[API] Limpiando progreso previo para {progress_id}")
            del PROGRESS_STORE[progress_id]

        # Inicializar progreso
        PROGRESS_STORE[progress_id] = {
            "total": 0,
            "current": 0,
            "start_time": time.time(),
            "last_update": time.time(),
            "status": "starting"
        }

        # Construye el comando
        vibevoice_script = PROJECT_ROOT / "vibevoice_app.py"
        # MODO TEST SI SE ACTIVA: 
        # vibevoice_script = PROJECT_ROOT / "test_gen_sim.py"
        cmd = [
            sys.executable, str(vibevoice_script),
            "--text", req.text,
            "--voice-name", resolved_path, # Pasamos la ruta resuelta
            "--model", req.model,
            "--output", str(output_file),
            "--cfg-scale", str(req.cfg_scale),
            "--ddpm-steps", str(req.ddpm_steps),
        ]
        if req.disable_prefill:
            cmd.append("--disable-prefill")

        print(f"\n{'='*60}")
        print(f"[API] Generando audio...")
        print(f"[API] Voz: {req.voice_name} → {resolved_path}")
        print(f"[API] Output: {output_file}")
        print(f"[API] Comando: {' '.join(cmd[:6])}...")
        print(f"{'='*60}")

        # Ejecución con captura de progreso
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            # encoding="utf-8",
            errors="replace",
            cwd=str(PROJECT_ROOT),
            bufsize=1, # Line buffered
        )

        stdout_acc = []
        stderr_acc = []

        # Usar un hilo para leer stderr y evitar bloqueos de buffer
        import threading
        def enqueue_stderr(pipe, acc, prog_id):
            try:
                for line in iter(pipe.readline, ''):
                    acc.append(line)
                    clean_line = line.strip()
                    # También buscamos progreso en stderr por si acaso
                    if clean_line.startswith("PROGRESS_STEP:"):
                        try:
                            current = int(clean_line.split(":")[1])
                            PROGRESS_STORE[prog_id]["current"] = current
                            PROGRESS_STORE[prog_id]["last_update"] = time.time()
                        except: pass
                    # print(f"[API-ERR] {line.strip()}")
            finally:
                pipe.close()

        stderr_thread = threading.Thread(target=enqueue_stderr, args=(process.stderr, stderr_acc, progress_id), daemon=True)
        stderr_thread.start()

        # Leer stdout línea a línea para el progreso
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                stdout_acc.append(line)
                clean_line = line.strip()
                # print(f"[API-OUT] {clean_line}") # Debug: Ver todo lo que sale
                if clean_line.startswith("PROGRESS_START:"):
                    try:
                        total = int(clean_line.split(":")[1])
                        PROGRESS_STORE[progress_id]["total"] = total
                        PROGRESS_STORE[progress_id]["status"] = "generating"
                        print(f"[API] Progreso detectado: Total {total}")
                    except: pass
                elif clean_line.startswith("PROGRESS_STEP:"):
                    try:
                        current = int(clean_line.split(":")[1])
                        PROGRESS_STORE[progress_id]["current"] = current
                        PROGRESS_STORE[progress_id]["last_update"] = time.time()
                        # print(f"[API] Progreso detectado: Step {current}/{PROGRESS_STORE[progress_id]['total']}")
                    except: pass
                # print(f"[API-PROC] {clean_line}")

        # Capturar stderr restante (aunque ya lo hace el hilo, esperamos a que termine)
        stderr_thread.join(timeout=5)
        
        # Log completo para debug
        print(f"[API] Return code: {process.returncode}")
        
        if process.returncode != 0:
            PROGRESS_STORE[progress_id]["status"] = "failed"
            detail = "".join(stderr_acc)[-500:] or "".join(stdout_acc)[-500:] or "Sin salida"
            raise HTTPException(500, f"Error en vibevoice_app.py (code {process.returncode}):\n{detail}")

        if not output_file.exists():
            PROGRESS_STORE[progress_id]["status"] = "failed"
            raise HTTPException(500, f"El script terminó OK pero no generó el archivo: {output_file}")

        PROGRESS_STORE[progress_id]["status"] = "completed"
        PROGRESS_STORE[progress_id]["current"] = PROGRESS_STORE[progress_id]["total"]
        print(f"[API] ✅ Audio generado: {output_file} ({output_file.stat().st_size} bytes)")

        return GenerateResponse(
            success=True,
            message="Audio generado correctamente",
            audio_id=audio_id,
            filename=output_file.name,
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] ❌ Excepción no controlada: {e}")
        traceback.print_exc()
        raise HTTPException(500, f"Error interno: {str(e)}")


@app.get("/audio/{audio_id}")
def download_audio(audio_id: str, directory: Optional[str] = None):
    """Descarga un audio generado por su ID."""
    target_dir = OUTPUTS_DIR
    if directory:
        custom_dir = Path(directory)
        if custom_dir.exists() and custom_dir.is_dir():
            target_dir = custom_dir

    matches = list(target_dir.glob(f"{audio_id}.*"))
    if not matches:
        raise HTTPException(404, f"Audio '{audio_id}' no encontrado")
    return FileResponse(matches[0], media_type="audio/mpeg", filename=matches[0].name)


@app.get("/progress/{audio_id}")
def get_progress(audio_id: str):
    """Obtiene el progreso de una generación específica."""
    if audio_id not in PROGRESS_STORE:
        raise HTTPException(404, "ID de audio no encontrado")
    return PROGRESS_STORE[audio_id]


@app.get("/outputs", response_model=list[OutputFileInfo])
def list_outputs(directory: Optional[str] = None):
    """Lista todos los audios generados en el directorio especificado."""
    target_dir = OUTPUTS_DIR
    if directory:
        custom_dir = Path(directory)
        if custom_dir.exists() and custom_dir.is_dir():
            target_dir = custom_dir

    files = []
    # Extensiones de audio comunes
    for ext in ("*.wav", "*.mp3", "*.flac", "*.ogg"):
        for f in target_dir.glob(ext):
            files.append(OutputFileInfo(
                id=f.stem,
                filename=f.name,
                path=str(f),
                size=f.stat().st_size,
                created=f.stat().st_mtime
            ))
    
    # Ordenar por fecha de creación descendente
    files.sort(key=lambda x: x.created, reverse=True)
    return files


@app.delete("/outputs/delete")
def delete_outputs(filenames: list[str] = Query(...), directory: Optional[str] = None):
    """Borra uno o varios archivos de audio."""
    target_dir = OUTPUTS_DIR
    if directory:
        custom_dir = Path(directory)
        if custom_dir.exists() and custom_dir.is_dir():
            target_dir = custom_dir

    deleted = []
    errors = []
    
    for filename in filenames:
        file_path = target_dir / filename
        if file_path.exists() and file_path.is_file():
            try:
                os.remove(file_path)
                deleted.append(filename)
            except Exception as e:
                errors.append(f"Error al borrar {filename}: {str(e)}")
        else:
            errors.append(f"Archivo no encontrado: {filename}")
            
    return {"deleted": deleted, "errors": errors}


@app.post("/voices/upload", response_model=VoiceInfo)
async def upload_voice(
    voice_name: str = Form(..., description="Nombre para la nueva voz"),
    audio_file: UploadFile = File(..., description="Archivo de audio WAV"),
):
    """Sube un archivo de audio como nueva voz personalizada."""
    if not voice_name.strip():
        raise HTTPException(400, "El nombre de la voz no puede estar vacío")

    temp_path = OUTPUTS_DIR / f"upload_{uuid.uuid4().hex[:8]}.wav"
    content = await audio_file.read()
    temp_path.write_bytes(content)

    cmd = [
        sys.executable, str(PROJECT_ROOT / "vibevoice_app.py"),
        "--clone-voice", str(temp_path),
        "--voice-name", voice_name,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(PROJECT_ROOT))

    if temp_path.exists():
        temp_path.unlink()

    voice_path = DEFAULT_VOICES_DIR / f"{voice_name}.wav"
    if not voice_path.exists():
        raise HTTPException(500, f"Error procesando voz: {result.stderr[-300:]}")

    return VoiceInfo(name=voice_name, filename=voice_path.name)


@app.delete("/voices/{voice_name}")
def delete_voice(voice_name: str):
    """Elimina una voz personalizada (solo del directorio por defecto)."""
    voice_path = DEFAULT_VOICES_DIR / f"{voice_name}.wav"
    if not voice_path.exists():
        raise HTTPException(404, f"Voz '{voice_name}' no encontrada")

    if voice_name in ALIAS_REVERSE:
        raise HTTPException(403, f"No se puede eliminar la voz predeterminada '{voice_name}'")

    voice_path.unlink()
    return {"success": True, "message": f"Voz '{voice_name}' eliminada"}


@app.get("/models")
def list_models():
    """Lista los modelos disponibles."""
    return [
        {"id": "microsoft/VibeVoice-1.5b", "name": "VibeVoice 1.5B (recomendado)", "size": "~6GB"},
        {"id": "microsoft/VibeVoice-7b", "name": "VibeVoice 7B (alta calidad)", "size": "~28GB"},
    ]
