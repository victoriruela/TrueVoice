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
}


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
                               disable_prefill=False):
    """
    Genera audio desde texto usando VibeVoice.

    Args:
        text: Texto a convertir en audio
        output_path: Ruta donde guardar el audio generado
        model_name: Modelo HuggingFace a usar
        voice_name: Nombre de la voz (alias o nombre exacto del archivo)
        repo_path: Ruta al repositorio de VibeVoice
        disable_prefill: Deshabilitar clonación de voz (más rápido, voz genérica)
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

    print(f"\n️  Generando audio...")
    print(f" Texto:  {text[:100]}{'...' if len(text) > 100 else ''}")
    print(f" Voz:    {resolved_voice}")
    print(f" Modelo: {model_name}")

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
    ]
    if disable_prefill:
        cmd.append("--disable_prefill")

    print(" Ejecutando generación...")
    print("   (La primera vez descarga el modelo ~6GB, puede tardar varios minutos)\n")

    # capture_output=False para ver el progreso en tiempo real en la consola
    result = subprocess.run(cmd, capture_output=False, text=True)

    if result.returncode == 0:
        generated_file = output_dir / "temp_input_generated.wav"
        if generated_file.exists():
            import shutil
            shutil.move(str(generated_file), output_path)
            print(f"\n✅ Audio guardado en: {output_path}")
            if os.path.exists(temp_txt):
                os.remove(temp_txt)
            return True
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

  Usar una voz específica:
    python vibevoice_app.py --text "Hello world" --voice-name Maya --output maya.wav

  Añadir voz personalizada desde audio:
    python vibevoice_app.py --clone-voice mi_voz.wav --voice-name MiVoz

  Añadir voz desde video:
    python vibevoice_app.py --clone-voice video.mp4 --voice-name VozVideo

  Generar audio con voz personalizada:
    python vibevoice_app.py --text "Texto de prueba" --voice-name MiVoz --output resultado.wav

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
                        help="Archivo de audio/video para añadir como voz de referencia")
    parser.add_argument("--voice-name", "-v", type=str, default="Alice",
                        help="Nombre de la voz a usar (default: Alice). Ver --list-voices.")
    parser.add_argument("--model", "-m", type=str,
                        default="microsoft/VibeVoice-1.5b",
                        help="Modelo a usar (default: microsoft/VibeVoice-1.5b)")
    parser.add_argument("--disable-prefill", action="store_true",
                        help="Deshabilitar clonación de voz (más rápido, voz genérica)")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Modo interactivo para ingresar múltiples textos")
    parser.add_argument("--list-voices", "-l", action="store_true",
                        help="Listar voces disponibles y salir")

    args = parser.parse_args()

    print("=" * 70)
    print("️  VIBEVOICE - Generador de Audio con Clonación de Voz")
    print("=" * 70)

    check_dependencies()
    repo_path = check_vibevoice_repo()
    voices_dir = setup_vibevoice_environment(repo_path)

    if args.list_voices:
        list_available_voices(voices_dir)
        return

    voice_name = args.voice_name

    # Clona/importa voz personalizada si se especifica
    if args.clone_voice:
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

        # Si no hay texto ni modo interactivo, termina aquí
        if not args.text and not args.interactive:
            return

    # Modo interactivo
    if args.interactive:
        print("\n" + "=" * 70)
        print(" MODO INTERACTIVO  (escribe 'salir' para terminar)")
        print("=" * 70 + "\n")

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

                output_file = f"output_{counter}.wav"
                if generate_speech_vibevoice(text, output_file, args.model,
                                              voice_name, repo_path,
                                              args.disable_prefill):
                    counter += 1
                    print(f" Guardado: {output_file}\n")

            except KeyboardInterrupt:
                print("\n\n ¡Hasta luego!")
                break

    elif args.text:
        if generate_speech_vibevoice(args.text, args.output, args.model,
                                      voice_name, repo_path,
                                      args.disable_prefill):
            print("✨ Proceso completado exitosamente")

    else:
        print("\n⚠️  Especifica --text, --interactive, --clone-voice o --list-voices")
        print("   Usa --help para ver todos los comandos disponibles")


if __name__ == "__main__":
    main()
