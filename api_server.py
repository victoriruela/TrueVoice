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

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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
VOICES_DIR = VIBEVOICE_REPO / "demo" / "voices"
OUTPUTS_DIR = PROJECT_ROOT / "api_outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

print(f"[API] PROJECT_ROOT: {PROJECT_ROOT}")
print(f"[API] VOICES_DIR:   {VOICES_DIR}")
print(f"[API] OUTPUTS_DIR:  {OUTPUTS_DIR}")
print(f"[API] VOICES_DIR exists: {VOICES_DIR.exists()}")


# ── Modelos Pydantic ────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Texto a convertir en audio")
    voice_name: str = Field("Alice", description="Nombre de la voz a usar")
    model: str = Field("microsoft/VibeVoice-1.5b", description="Modelo HuggingFace")
    output_format: str = Field("wav", description="Formato de salida: wav, mp3, flac, ogg")
    cfg_scale: float = Field(2.0, ge=0.5, le=5.0, description="CFG scale (0.5-5.0)")
    ddpm_steps: int = Field(30, ge=1, le=200, description="Pasos DDPM (1-200)")
    disable_prefill: bool = Field(False, description="Desactivar clonación de voz")


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
    "Lobato": "es-Lobato_man",
}

ALIAS_REVERSE = {v: k for k, v in DEFAULT_VOICES.items()}


def _resolve_voice(voice_name: str) -> Optional[str]:
    """Resuelve un nombre de voz al nombre exacto del archivo WAV."""
    if voice_name in DEFAULT_VOICES:
        resolved = DEFAULT_VOICES[voice_name]
        if (VOICES_DIR / f"{resolved}.wav").exists():
            return resolved

    if (VOICES_DIR / f"{voice_name}.wav").exists():
        return voice_name

    voice_lower = voice_name.lower()
    for wav in VOICES_DIR.glob("*.wav"):
        if voice_lower in wav.stem.lower():
            return wav.stem

    return None


# ── Endpoints ───────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "ok", "service": "TrueVoice API", "version": "1.0.0"}


@app.get("/voices", response_model=list[VoiceInfo])
def list_voices():
    """Lista todas las voces disponibles."""
    voices = []
    for wav in sorted(VOICES_DIR.glob("*.wav")):
        alias = ALIAS_REVERSE.get(wav.stem)
        voices.append(VoiceInfo(name=wav.stem, filename=wav.name, alias=alias))
    return voices


@app.post("/generate", response_model=GenerateResponse)
def generate_audio(req: GenerateRequest):
    """Genera audio a partir de texto usando VibeVoice."""
    try:
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

        # Construye el comando
        vibevoice_script = PROJECT_ROOT / "vibevoice_app.py"
        cmd = [
            sys.executable, str(vibevoice_script),
            "--text", req.text,
            "--voice-name", req.voice_name,
            "--model", req.model,
            "--output", str(output_file),
            "--cfg-scale", str(req.cfg_scale),
            "--ddpm-steps", str(req.ddpm_steps),
        ]
        if req.disable_prefill:
            cmd.append("--disable-prefill")

        print(f"\n{'='*60}")
        print(f"[API] Generando audio...")
        print(f"[API] Voz: {req.voice_name} → {resolved}")
        print(f"[API] Output: {output_file}")
        print(f"[API] Comando: {' '.join(cmd[:6])}...")
        print(f"{'='*60}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(PROJECT_ROOT),  # Asegura que el working directory sea el correcto
        )

        # Log completo para debug
        print(f"[API] Return code: {result.returncode}")
        if result.stdout:
            # Solo las últimas líneas para no saturar
            stdout_lines = result.stdout.strip().split("\n")
            print(f"[API] STDOUT (últimas 20 líneas):")
            for line in stdout_lines[-20:]:
                print(f"  {line}")
        if result.stderr:
            stderr_lines = result.stderr.strip().split("\n")
            print(f"[API] STDERR (últimas 20 líneas):")
            for line in stderr_lines[-20:]:
                print(f"  {line}")

        if result.returncode != 0:
            detail = result.stderr[-500:] if result.stderr else result.stdout[-500:] if result.stdout else "Sin salida"
            raise HTTPException(500, f"Error en vibevoice_app.py (code {result.returncode}):\n{detail}")

        if not output_file.exists():
            raise HTTPException(500, f"El script terminó OK pero no generó el archivo: {output_file}")

        print(f"[API] ✅ Audio generado: {output_file} ({output_file.stat().st_size} bytes)")

        return GenerateResponse(
            success=True,
            message="Audio generado correctamente",
            audio_id=audio_id,
            filename=output_file.name,
        )

    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Timeout: la generación tardó más de 10 minutos")
    except Exception as e:
        print(f"[API] ❌ Excepción no controlada: {e}")
        traceback.print_exc()
        raise HTTPException(500, f"Error interno: {str(e)}")


@app.get("/audio/{audio_id}")
def download_audio(audio_id: str):
    """Descarga un audio generado por su ID."""
    matches = list(OUTPUTS_DIR.glob(f"{audio_id}.*"))
    if not matches:
        raise HTTPException(404, f"Audio '{audio_id}' no encontrado")
    return FileResponse(matches[0], media_type="audio/mpeg", filename=matches[0].name)


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

    voice_path = VOICES_DIR / f"{voice_name}.wav"
    if not voice_path.exists():
        raise HTTPException(500, f"Error procesando voz: {result.stderr[-300:]}")

    return VoiceInfo(name=voice_name, filename=voice_path.name)


@app.delete("/voices/{voice_name}")
def delete_voice(voice_name: str):
    """Elimina una voz personalizada."""
    voice_path = VOICES_DIR / f"{voice_name}.wav"
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
