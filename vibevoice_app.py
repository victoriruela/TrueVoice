"""
Aplicación de consola para generar audio con VibeVoice
Soporta:
- Generación de audio desde texto (TTS)
- Clonación de voz desde archivos de audio/video
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path


sys.stdout.reconfigure(encoding='utf-8')

# Voces predeterminadas disponibles en el repositorio
DEFAULT_VOICES = {
    "Alice":  "en-Alice_woman",
    "Carter": "en-Carter_man",
    "Frank":  "en-Frank_man",
    "Mary":   "en-Mary_woman_bgm",
    "Maya":   "en-Maya_woman",
    "Samuel": "in-Samuel_man",
    "Anchen": "zh-Anchen_man_bgm",
    "Bowen":  "zh-Bowen_man",
    "Xinran": "zh-Xinran_woman",
    "Lobato": "es-Lobato_man",
    "Lobato2": "Extract_Lobato",
}

SUPPORTED_OUTPUT_FORMATS = {".wav", ".mp3", ".flac", ".ogg"}


def convert_audio(input_path, output_path):
    """
    Convierte un archivo de audio WAV al formato indicado por la extensión de output_path.

    Args:
        input_path: Ruta al archivo WAV de entrada
        output_path: Ruta de salida (la extensión determina el formato)

    Returns:
        bool: True si la conversión fue exitosa
    """
    import torchaudio

    ext = Path(output_path).suffix.lower()

    if ext == ".wav":
        # No necesita conversión, mueve directamente
        import shutil
        shutil.move(input_path, output_path)
        return True

    if ext not in SUPPORTED_OUTPUT_FORMATS:
        print(f"⚠️  Formato '{ext}' no soportado. Formatos válidos: {', '.join(SUPPORTED_OUTPUT_FORMATS)}")
        print(f"   Guardando como WAV en su lugar: {output_path}")
        import shutil
        shutil.move(input_path, str(Path(output_path).with_suffix(".wav")))
        return True

    try:
        print(f" Convirtiendo a {ext.upper()[1:]}...")
        waveform, sample_rate = torchaudio.load(input_path)
        torchaudio.save(output_path, waveform, sample_rate)
        os.remove(input_path)
        return True
    except Exception as e:
        print(f"❌ Error al convertir a {ext}: {e}")
        print(f"   El audio WAV original está en: {input_path}")
        return False


def check_dependencies():
    """Verifica que las dependencias necesarias estén instaladas"""
    try:
        import torch
        import torchaudio
        import transformers
        import soundfile
    except ImportError as e:
        print(f"❌ Error: Falta una dependencia requerida: {e}")
        print("\n Para instalar las dependencias, ejecuta:")
        print("pip install torch torchaudio transformers soundfile accelerate huggingface_hub")
        sys.exit(1)


def check_vibevoice_repo():
    """Verifica si el repositorio de VibeVoice está clonado e instalado"""
    repo_path = Path("VibeVoice")

    if not repo_path.exists():
        print("\n El repositorio de VibeVoice no está disponible localmente.")
        print(" Clonando el repositorio...")
        try:
            subprocess.run([
                "git", "clone",
                "https://github.com/vibevoice-community/VibeVoice.git"
            ], check=True)
            print("✅ Repositorio clonado exitosamente")
        except subprocess.CalledProcessError:
            print("❌ Error al clonar el repositorio")
            print("   Clona manualmente con:")
            print("   git clone https://github.com/vibevoice-community/VibeVoice.git")
            sys.exit(1)
        except FileNotFoundError:
            print("❌ Git no está instalado")
            print("   Instala Git desde: https://git-scm.com/downloads")
            sys.exit(1)

    try:
        import vibevoice  # noqa: F401
    except ImportError:
        print("\n Instalando el paquete vibevoice...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", str(repo_path)],
                check=True
            )
            print("✅ Paquete vibevoice instalado exitosamente")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error al instalar el paquete: {e}")
            print(f"   Intenta manualmente: pip install -e {repo_path}")
            sys.exit(1)

    return repo_path


def extract_audio_from_video(video_path, output_audio_path):
    """
    Extrae el audio de un archivo de video

    Args:
        video_path: Ruta al archivo de video
        output_audio_path: Ruta donde guardar el audio extraído
    """
    try:
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  FFmpeg no está instalado. Intentando con moviepy...")
            try:
                from moviepy.editor import VideoFileClip
                video = VideoFileClip(video_path)
                video.audio.write_audiofile(output_audio_path)
                video.close()
                return True
            except ImportError:
                print("❌ Instala ffmpeg (conda install ffmpeg -c conda-forge)")
                print("   o moviepy (pip install moviepy)")
                return False

        cmd = [
            "ffmpeg", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "24000", "-ac", "1",
            output_audio_path, "-y"
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        print(f"✅ Audio extraído exitosamente: {output_audio_path}")
        return True

    except Exception as e:
        print(f"❌ Error al extraer audio del video: {e}")
        return False


def check_ffmpeg():
    """Verifica que ffmpeg esté instalado, necesario para procesar audio de YouTube"""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_ytdlp():
    """Verifica que yt-dlp esté instalado"""
    try:
        import yt_dlp  # noqa: F401
        return True
    except ImportError:
        return False


def time_to_seconds(time_str):
    """
    Convierte un string HH:MM:SS a segundos totales.

    Args:
        time_str: Tiempo en formato HH:MM:SS

    Returns:
        int: Segundos totales

    Raises:
        ValueError: Si el formato no es válido
    """
    parts = time_str.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"Formato de tiempo inválido: '{time_str}'. Usa HH:MM:SS")
    try:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        raise ValueError(f"Formato de tiempo inválido: '{time_str}'. Usa HH:MM:SS con números enteros")
    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"Minutos y segundos deben ser menores que 60: '{time_str}'")
    return hours * 3600 + minutes * 60 + seconds


def extract_voice_from_youtube(youtube_url, start_time, end_time, voice_name, voices_dir):
    """
    Descarga un fragmento de audio de un vídeo de YouTube y lo guarda como preset de voz.

    Args:
        youtube_url: URL del vídeo de YouTube
        start_time: Tiempo de inicio en formato HH:MM:SS
        end_time: Tiempo de fin en formato HH:MM:SS
        voice_name: Nombre con el que guardar la voz (sin extensión)
        voices_dir: Directorio donde guardar el archivo de voz

    Returns:
        str: Nombre de la voz guardada, o None si hubo un error
    """
    # Verifica dependencias
    if not check_ytdlp():
        print("❌ yt-dlp no está instalado.")
        print("   Instálalo con: pip install yt-dlp")
        return None

    if not check_ffmpeg():
        print("❌ FFmpeg no está instalado, es necesario para recortar el audio.")
        print("   Instálalo con: conda install ffmpeg -c conda-forge")
        return None

    # Valida y convierte los tiempos
    try:
        start_seconds = time_to_seconds(start_time)
        end_seconds = time_to_seconds(end_time)
    except ValueError as e:
        print(f"❌ Error en el formato de tiempo: {e}")
        return None

    if end_seconds <= start_seconds:
        print(f"❌ El tiempo de fin ({end_time}) debe ser mayor que el de inicio ({start_time})")
        return None

    duration = end_seconds - start_seconds
    print(f"\n Extrayendo fragmento de voz desde YouTube...")
    print(f" URL:      {youtube_url}")
    print(f" Inicio:   {start_time}  ({start_seconds}s)")
    print(f" Fin:      {end_time}  ({end_seconds}s)")
    print(f" Duración: {duration}s")
    print(f" Nombre:   {voice_name}")

    temp_dir = Path("temp_youtube")
    temp_dir.mkdir(exist_ok=True)
    
    # Nombre fijo para evitar problemas
    temp_audio_stem = "yt_download_temp"
    temp_full_audio = temp_dir / f"{temp_audio_stem}.wav"
    output_path = voices_dir / f"{voice_name}.wav"

    # Limpia descargas anteriores
    for old_file in temp_dir.glob(f"{temp_audio_stem}*"):
        old_file.unlink()

    try:
        print("\n Paso 1/2: Descargando audio del vídeo...")
        import yt_dlp

        # ⚠️ SOLUCIÓN: Usa cookies del navegador para evitar bloqueo de YouTube
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(temp_dir / f"{temp_audio_stem}.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }],
            # ✅ Usa cookies del navegador Chrome (cambia si usas otro navegador)
            "cookiesfrombrowser": ("chrome",),  # Opciones: chrome, firefox, edge, safari, opera, brave
            "quiet": False,
            "no_warnings": False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])

        # Busca el archivo descargado
        downloaded_files = list(temp_dir.glob(f"{temp_audio_stem}*"))
        wav_files = [f for f in downloaded_files if f.suffix.lower() == ".wav"]

        if not wav_files:
            print(f"⚠️  No se encontró .wav directamente. Archivos: {[f.name for f in downloaded_files]}")
            if downloaded_files:
                source_file = downloaded_files[0]
                print(f" Convirtiendo {source_file.name} a WAV...")
                convert_cmd = [
                    "ffmpeg", "-i", str(source_file),
                    "-acodec", "pcm_s16le",
                    str(temp_full_audio), "-y"
                ]
                subprocess.run(convert_cmd, capture_output=True, check=True)
                source_file.unlink()
            else:
                print("❌ No se descargó ningún archivo. Verifica la URL.")
                return None
        else:
            temp_full_audio = wav_files[0]

        if not temp_full_audio.exists():
            print(f"❌ No se encontró el archivo de audio descargado.")
            return None

        print("✅ Audio descargado correctamente")

        # Paso 2: Recorta el fragmento con ffmpeg
        print(f"\n Paso 2/2: Recortando fragmento {start_time} → {end_time}...")
        cmd = [
            "ffmpeg",
            "-i", str(temp_full_audio),
            "-ss", str(start_seconds),
            "-t", str(duration),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "24000",
            "-ac", "1",
            str(output_path),
            "-y"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"❌ Error al recortar el audio con ffmpeg:")
            print(result.stderr)
            return None

        print(f"✅ Fragmento recortado correctamente")

        # Limpia archivos temporales
        for f in temp_dir.glob(f"{temp_audio_stem}*"):
            f.unlink()
        if temp_dir.exists() and not any(temp_dir.iterdir()):
            temp_dir.rmdir()

        print(f"\n✅ Voz guardada en: {output_path}")
        print(f"   Usa '--voice-name {voice_name}' para generar audio con esta voz")

        return voice_name

    except Exception as e:
        print(f"❌ Error al extraer voz de YouTube: {e}")
        
        # Si el error es de autenticación, da instrucciones detalladas
        error_str = str(e)
        if "bot" in error_str.lower() or "sign in" in error_str.lower():
            print("\n⚠️  YouTube está bloqueando la descarga.")
            print("\n Solución: Asegúrate de estar usando cookies de tu navegador.")
            print("   El código ya está configurado para usar cookies de Chrome.")
            print("\n Si usas otro navegador, edita vibevoice_app.py y cambia:")
            print('   "cookiesfrombrowser": ("chrome",)  # Cambiar a: firefox, edge, safari, etc.')
            print("\n Si el problema persiste:")
            print("   1. Abre YouTube en tu navegador y asegúrate de estar logueado")
            print("   2. Cierra completamente el navegador")
            print("   3. Vuelve a intentar")
        
        import traceback
        traceback.print_exc()
        
        # Limpia archivos temporales en caso de error
        for f in temp_dir.glob(f"{temp_audio_stem}*"):
            try:
                f.unlink()
            except Exception:
                pass
        return None


def setup_vibevoice_environment(repo_path):
    """Configura el entorno de VibeVoice y retorna el directorio de voces"""
    voices_dir = repo_path / "demo" / "voices"
    voices_dir.mkdir(parents=True, exist_ok=True)
    return voices_dir


def resolve_voice_name(voice_name, voices_dir):
    """
    Resuelve el nombre de voz al nombre exacto del archivo WAV.
    Primero busca en alias predeterminados, luego por nombre exacto o parcial.

    Args:
        voice_name: Nombre de voz proporcionado por el usuario
        voices_dir: Directorio de voces del repositorio

    Returns:
        str: Nombre de voz resuelto (sin extensión) o None si no se encuentra
    """
    # 1. Alias predeterminados (ej: "Alice" -> "en-Alice_woman")
    if voice_name in DEFAULT_VOICES:
        resolved = DEFAULT_VOICES[voice_name]
        if (voices_dir / f"{resolved}.wav").exists():
            return resolved
        print(f"⚠️  Alias '{voice_name}' → '{resolved}' pero el archivo no existe.")

    # 2. Nombre exacto de archivo
    if (voices_dir / f"{voice_name}.wav").exists():
        return voice_name

    # 3. Búsqueda parcial (case-insensitive)
    voice_lower = voice_name.lower()
    for wav_file in voices_dir.glob("*.wav"):
        if voice_lower in wav_file.stem.lower():
            print(f" '{voice_name}' resuelto como '{wav_file.stem}'")
            return wav_file.stem

    return None


def clone_voice(reference_audio_path, voice_name, voices_dir):
    """
    Procesa un audio de referencia y lo guarda como preset de voz personalizada

    Args:
        reference_audio_path: Ruta al audio de referencia
        voice_name: Nombre para guardar la voz
        voices_dir: Directorio donde guardar las voces
    """
    try:
        import torch
        import torchaudio

        print(f"\n Procesando audio de referencia: {reference_audio_path}")

        waveform, sample_rate = torchaudio.load(reference_audio_path)

        # Resamplea a 24kHz (sample rate nativo de VibeVoice)
        if sample_rate != 24000:
            print(f" Resampling de {sample_rate}Hz a 24000Hz...")
            resampler = torchaudio.transforms.Resample(sample_rate, 24000)
            waveform = resampler(waveform)
            sample_rate = 24000

        # Convierte a mono si es estéreo
        if waveform.shape[0] > 1:
            print(" Convirtiendo a mono...")
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        voice_path = voices_dir / f"{voice_name}.wav"
        torchaudio.save(str(voice_path), waveform, sample_rate)

        print(f"✅ Voz guardada: {voice_path}")
        print(f"   Usa '--voice-name {voice_name}' para generar audio con esta voz")

        return voice_name

    except Exception as e:
        print(f"❌ Error al procesar el audio de referencia: {e}")
        return None


def generate_speech_vibevoice(text, output_path,
                               model_name="microsoft/VibeVoice-1.5b",
                               voice_name="Alice", repo_path=None,
                               disable_prefill=False,
                               cfg_scale=1.5,  # Añadido parámetro
                               ddpm_steps=20):  # Añadido parámetro
    """
    Genera audio desde texto usando VibeVoice.

    Args:
        text: Texto a convertir en audio
        output_path: Ruta donde guardar el audio generado
        model_name: Modelo HuggingFace a usar
        voice_name: Nombre de la voz (alias o nombre exacto del archivo)
        repo_path: Ruta al repositorio de VibeVoice
        disable_prefill: Deshabilitar clonación de voz (más rápido, voz genérica)
        cfg_scale: CFG scale para la generación (default: 1.5, rango: 1.0-3.0)
        ddpm_steps: Número de pasos DDPM (default: 20, rango: 5-100)
    """
    voices_dir = repo_path / "demo" / "voices"

    # Resuelve el nombre de voz al archivo real
    resolved_voice = resolve_voice_name(voice_name, voices_dir)
    if resolved_voice is None:
        available = [f.stem for f in voices_dir.glob("*.wav")]
        print(f"❌ Voz '{voice_name}' no encontrada.")
        print(f"   Voces disponibles: {', '.join(available) if available else 'ninguna'}")
        print(f"   Alias soportados:  {', '.join(DEFAULT_VOICES.keys())}")
        return False

    output_ext = Path(output_path).suffix.lower()
    if output_ext not in SUPPORTED_OUTPUT_FORMATS:
        print(f"⚠️  Formato '{output_ext}' no soportado. Usando .wav por defecto.")
        output_path = str(Path(output_path).with_suffix(".wav"))

    print(f" Texto:      {text[:100]}{'...' if len(text) > 100 else ''}")
    print(f" Voz:        {resolved_voice}")
    print(f" Modelo:     {model_name}")
    print(f" Formato:    {Path(output_path).suffix.upper()[1:]}")
    print(f" CFG Scale:  {cfg_scale}")
    print(f" DDPM Steps: {ddpm_steps}")

    # Escribe el texto en el formato que espera el script de VibeVoice
    temp_txt = "temp_input.txt"
    with open(temp_txt, "w", encoding="utf-8") as f:
        f.write(f"Speaker 1: {text}")

    demo_script = repo_path / "demo" / "inference_from_file.py"
    if not demo_script.exists():
        print(f"❌ Script de inferencia no encontrado: {demo_script}")
        return False

    output_dir = Path("temp_outputs")
    output_dir.mkdir(exist_ok=True)

    cmd = [
        sys.executable, str(demo_script),
        "--model_path", model_name,
        "--txt_path", temp_txt,
        "--speaker_names", resolved_voice,
        "--output_dir", str(output_dir),
        "--cfg_scale", str(cfg_scale),      # Pasa cfg_scale
        "--ddpm_steps", str(ddpm_steps),    # Pasa ddpm_steps
    ]
    if disable_prefill:
        cmd.append("--disable_prefill")

    print(" Ejecutando generación...")
    print("   (La primera vez descarga el modelo ~6GB, puede tardar varios minutos)\n")

    result = subprocess.run(cmd, capture_output=False, text=True)

    if result.returncode == 0:
        generated_file = output_dir / "temp_input_generated.wav"
        if generated_file.exists():
            if convert_audio(str(generated_file), output_path):
                print(f"\n✅ Audio guardado en: {output_path}")
                if os.path.exists(temp_txt):
                    os.remove(temp_txt)
                return True
            else:
                print(f"❌ Falló la conversión del audio generado")
                return False
        else:
            print(f"❌ El script terminó sin errores pero no generó el archivo esperado.")
            return False
    else:
        print(f"❌ El script de inferencia terminó con error (código {result.returncode})")
        return False


def list_available_voices(voices_dir):
    """Lista las voces disponibles"""
    print("\n Voces disponibles:")

    wav_files = list(voices_dir.glob("*.wav"))
    if wav_files:
        print("\n Archivos de voz en el repositorio:")
        for f in sorted(wav_files):
            alias = next((k for k, v in DEFAULT_VOICES.items() if v == f.stem), None)
            alias_str = f"  → alias: --voice-name {alias}" if alias else ""
            print(f"   - {f.stem}{alias_str}")
    else:
        print("   No hay archivos de voz disponibles.")

    print("\n Alias rápidos disponibles:")
    for alias, real_name in DEFAULT_VOICES.items():
        exists = (voices_dir / f"{real_name}.wav").exists()
        status = "✅" if exists else "❌ archivo no encontrado"
        print(f"   --voice-name {alias:<10} → {real_name}  {status}")


def main():
    parser = argparse.ArgumentParser(
        description="️  VibeVoice TTS - Generador de Audio con Clonación de Voz",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  Ver voces disponibles:
    python vibevoice_app.py --list-voices

  Generar audio con voz predeterminada:
    python vibevoice_app.py --text "Hola, esto es una prueba" --output prueba.wav

  Alta calidad (más lento, mejor resultado):
    python vibevoice_app.py --text "Hola mundo" --cfg-scale 1.8 --ddpm-steps 30 --output audio.wav

  Baja calidad (más rápido):
    python vibevoice_app.py --text "Hola mundo" --cfg-scale 1.2 --ddpm-steps 5 --output audio.wav

    python vibevoice_app.py --youtube-voice "https://youtube.com/watch?v=..." --start 00:01:30 --end 00:02:00 --voice-name MiVoz

  Generar audio con voz extraída de YouTube:
    python vibevoice_app.py --text "Texto de prueba" --voice-name MiVoz --output resultado.mp3

  Añadir voz personalizada desde audio local:
    python vibevoice_app.py --clone-voice mi_voz.wav --voice-name MiVoz

  Añadir voz desde video local:
    python vibevoice_app.py --clone-voice video.mp4 --voice-name VozVideo

  Modo interactivo:
    python vibevoice_app.py --interactive --voice-name Alice

  Sin clonación de voz (más rápido, voz genérica):
    python vibevoice_app.py --text "Hola" --disable-prefill --output prueba.wav

NOTA: La primera ejecución descargará el modelo (~6GB). El modelo Realtime-0.5B
      no es compatible con CPU; se usa VibeVoice-1.5b por defecto.
        """
    )

    parser.add_argument("--text", "-t", type=str,
                        help="Texto a convertir en audio")
    parser.add_argument("--output", "-o", type=str, default="output.wav",
                        help="Archivo de salida (default: output.wav)")
    parser.add_argument("--clone-voice", "-c", type=str,
                        help="Archivo de audio/video local para añadir como voz de referencia")
    parser.add_argument("--youtube-voice", "-y", type=str,
                        help="URL de YouTube de la que extraer la voz de referencia")
    parser.add_argument("--start", type=str, default=None,
                        help="Tiempo de inicio del fragmento en formato HH:MM:SS (para --youtube-voice)")
    parser.add_argument("--end", type=str, default=None,
                        help="Tiempo de fin del fragmento en formato HH:MM:SS (para --youtube-voice)")
    parser.add_argument("--voice-name", "-v", type=str, default="Alice",
                        help="Nombre de la voz a usar o guardar (default: Alice). Ver --list-voices.")
    parser.add_argument("--model", "-m", type=str,
                        default="microsoft/VibeVoice-1.5b",
                        help="Modelo a usar (default: microsoft/VibeVoice-1.5b)")
    
    # NUEVOS PARÁMETROS DE CALIDAD
    parser.add_argument("--cfg-scale", type=float, default=2,
                        help="CFG scale para generación (1.0-3.0, default: 1.5). Más alto = más fidelidad al texto.")
    parser.add_argument("--ddpm-steps", type=int, default=30,
                        help="Pasos de difusión DDPM (5-100, default: 20). Más pasos = mejor calidad pero más lento.")
    
    parser.add_argument("--disable-prefill", action="store_true",
                        help="Deshabilitar clonación de voz (más rápido, voz genérica)")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Modo interactivo para ingresar múltiples textos")
    parser.add_argument("--list-voices", "-l", action="store_true",
                        help="Listar voces disponibles y salir")

    args = parser.parse_args()

    check_dependencies()
    repo_path = check_vibevoice_repo()
    voices_dir = setup_vibevoice_environment(repo_path)

    if args.list_voices:
        list_available_voices(voices_dir)
        return

    voice_name = args.voice_name

    # Extrae voz desde YouTube
    if args.youtube_voice:
        if not args.start or not args.end:
            print("❌ Debes especificar --start y --end junto con --youtube-voice")
            print("   Ejemplo: --start 00:01:30 --end 00:02:00")
            sys.exit(1)

        extracted = extract_voice_from_youtube(
            youtube_url=args.youtube_voice,
            start_time=args.start,
            end_time=args.end,
            voice_name=args.voice_name,
            voices_dir=voices_dir,
        )
        if extracted:
            voice_name = extracted
        else:
            print("❌ No se pudo extraer la voz desde YouTube")
            sys.exit(1)

        print(f"\n✅ Voz '{voice_name}' lista para usar.")
        print(f"   Genera audio con: python vibevoice_app.py --text \"Tu texto\" --voice-name {voice_name}")

        if not args.text and not args.interactive:
            return

    # Clona voz desde archivo local
    elif args.clone_voice:
        reference_audio = args.clone_voice

        if reference_audio.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')):
            print("\n Detectado archivo de video, extrayendo audio...")
            temp_audio = "temp_extracted_audio.wav"
            if not extract_audio_from_video(reference_audio, temp_audio):
                print("❌ No se pudo extraer el audio del video")
                sys.exit(1)
            reference_audio = temp_audio

        if not os.path.exists(reference_audio):
            print(f"❌ El archivo de referencia no existe: {reference_audio}")
            sys.exit(1)

        cloned = clone_voice(reference_audio, args.voice_name, voices_dir)
        if cloned:
            voice_name = cloned

        if reference_audio == "temp_extracted_audio.wav" and os.path.exists(reference_audio):
            os.remove(reference_audio)

        print(f"\n✅ Voz '{voice_name}' lista para usar.")
        print(f"   Genera audio con: python vibevoice_app.py --text \"Tu texto\" --voice-name {voice_name}")

        if not args.text and not args.interactive:
            return

    # Modo interactivo
    if args.interactive:
        print("\n" + "=" * 70)
        print(" MODO INTERACTIVO  (escribe 'salir' para terminar)")
        print("=" * 70)
        print(f" CFG Scale:  {args.cfg_scale}")
        print(f" DDPM Steps: {args.ddpm_steps}\n")

        output_ext = Path(args.output).suffix or ".wav"

        counter = 1
        while True:
            try:
                text = input(" Ingresa el texto: ").strip()

                if text.lower() in ['salir', 'exit', 'quit']:
                    print("\n ¡Hasta luego!")
                    break

                if not text:
                    print("⚠️  El texto no puede estar vacío\n")
                    continue

                output_file = f"output_{counter}{output_ext}"
                if generate_speech_vibevoice(text, output_file, args.model,
                                             voice_name, repo_path,
                                             args.disable_prefill):
                    counter += 1
                    print(f" Guardado: {output_file}\n")

            except KeyboardInterrupt:
                print("\n\n ¡Hasta luego!")
                break

    elif args.text:
        if generate_speech_vibevoice(
            text=args.text,
            output_path=args.output,
            model_name=args.model,
            voice_name=voice_name,
            repo_path=repo_path,
            disable_prefill=args.disable_prefill,
            cfg_scale=args.cfg_scale,      # Pasa el parámetro
            ddpm_steps=args.ddpm_steps     # Pasa el parámetro
        ):
            print("✨ Proceso completado exitosamente")

    else:
        print("\n⚠️  Especifica --text, --interactive, --clone-voice, --youtube-voice o --list-voices")
        print("   Usa --help para ver todos los comandos disponibles")


if __name__ == "__main__":
    main()
