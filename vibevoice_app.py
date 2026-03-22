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
import shutil
from pathlib import Path

import torch
import torchaudio
import soundfile
from huggingface_hub import hf_hub_download

# Importaciones de la librería VibeVoice
try:
    from vibevoice.processor import VibeVoiceProcessor
    from vibevoice import VibeVoiceStreamingForConditionalGenerationInference as Inference
except ImportError:
    print("❌ Error: La librería 'vibevoice' no está instalada.")
    print("   Instálala con: pip install git+https://github.com/microsoft/VibeVoice.git")
    sys.exit(1)


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
        data, sample_rate = soundfile.read(input_path)
        waveform = torch.from_numpy(data)
        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)
        else:
            waveform = waveform.transpose(0, 1) # soundfile returns [frames, channels], torch expects [channels, frames]
        
        # torchaudio.save(output_path, waveform, sample_rate)
        # Usamos soundfile para evitar errores de torchcodec
        soundfile.write(output_path, waveform.transpose(0, 1).numpy(), sample_rate)
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
        import vibevoice
    except ImportError as e:
        print(f"❌ Error: Falta una dependencia requerida: {e}")
        print("\n Para instalar las dependencias, ejecuta:")
        print("pip install -r requirements.txt")
        sys.exit(1)


def download_default_voices(voices_dir):
    """Descarga algunas voces predeterminadas desde el repositorio oficial si no existen"""
    voices_dir.mkdir(parents=True, exist_ok=True)
    
    # URL base de las voces en el repositorio de Microsoft
    base_url = "https://github.com/microsoft/VibeVoice/raw/main/demo/voices/"
    
    # Solo descargamos un par de ejemplo para no saturar si no existen
    voices_to_download = ["en-Alice_woman", "es-Lobato_man"]
    
    for voice in voices_to_download:
        voice_path = voices_dir / f"{voice}.wav"
        if not voice_path.exists():
            print(f"📥 Descargando voz predeterminada: {voice}...")
            try:
                import requests
                r = requests.get(f"{base_url}{voice}.wav")
                if r.status_code == 200:
                    voice_path.write_bytes(r.content)
                    print(f"✅ Descargada: {voice}")
                else:
                    print(f"⚠️ No se pudo descargar {voice} (status {r.status_code})")
            except Exception as e:
                print(f"⚠️ Error descargando {voice}: {e}")


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


def setup_vibevoice_environment():
    """Configura el entorno de VibeVoice y retorna el directorio de voces"""
    # En la nueva versión como librería, las voces están en la raíz del proyecto
    voices_dir = Path("voices")
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

        data, sample_rate = soundfile.read(reference_audio_path)
        waveform = torch.from_numpy(data).float()
        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)
        else:
            waveform = waveform.transpose(0, 1)

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
        # torchaudio.save(str(voice_path), waveform, sample_rate)
        # Usamos soundfile para evitar errores de torchcodec en Windows
        soundfile.write(str(voice_path), waveform.transpose(0, 1).numpy(), sample_rate)

        print(f"✅ Voz guardada: {voice_path}")
        print(f"   Usa '--voice-name {voice_name}' para generar audio con esta voz")

        return voice_name

    except Exception as e:
        print(f"❌ Error al procesar el audio de referencia: {e}")
        return None


def generate_speech_vibevoice(text, output_path,
                               model_name="microsoft/VibeVoice-1.5b",
                               voice_name="Alice",
                               disable_prefill=False,
                               cfg_scale=1.5,
                               ddpm_steps=20):
    """
    Genera audio desde texto usando VibeVoice como librería.
    """
    voices_dir = Path("voices")
    
    # Resuelve el nombre de voz al archivo real
    resolved_voice = resolve_voice_name(voice_name, voices_dir)
    if resolved_voice is None:
        # Intenta descargar si es una de las default
        download_default_voices(voices_dir)
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

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f" Dispositivo: {device}")

    try:
        print(" Cargando procesador y modelo...")
        processor = VibeVoiceProcessor.from_pretrained(model_name)
        model = Inference.from_pretrained(model_name).to(device)

        voice_wav_path = voices_dir / f"{resolved_voice}.wav"
        
        # ✅ Usamos soundfile directamente para evitar errores de torchcodec en Windows
        data, sample_rate = soundfile.read(str(voice_wav_path))
        prompt_audio = torch.from_numpy(data).float()
        if prompt_audio.ndim == 1:
            prompt_audio = prompt_audio.unsqueeze(0)
        else:
            prompt_audio = prompt_audio.transpose(0, 1)

        print(" Ejecutando generación...")
        
        # ✅ VibeVoiceProcessor requiere el formato "Speaker {ID}: {Texto}"
        formatted_text = f"Speaker 1: {text}"
        
        # ✅ Importante: Pasar voice_samples como una LISTA de tensores de audio
        # para que el procesador genere speech_tensors y speech_masks
        inputs = processor(
            text=formatted_text,
            voice_samples=[prompt_audio],
            return_tensors="pt",
            sampling_rate=24000
        ).to(device)

        # ✅ Separamos el prefill del texto a generar para evitar duplicidades
        # 1. Generamos los tokens de "prompt" (Voz + Instrucciones del sistema)
        print(" Preparando prefill (Voice Prompt)...")
        # Usamos un texto mínimo para que el procesador genere el formato, pero luego lo recortamos
        prompt_inputs = processor(
            text="Speaker 1: .", # Texto mínimo
            voice_samples=[prompt_audio],
            return_tensors="pt",
            sampling_rate=24000
        ).to(device)
        
        # El procesador genera algo como: [System Prompt] [Voice Input] [Text Input] [Speaker 1: .] [Speech Output]
        # Queremos recortar justo ANTES del texto "." para que el prefill sea solo el contexto.
        # Según nuestras pruebas, los últimos 6 tokens corresponden a "Speaker 0: . \n Speech output: \n <|vision_start|>"
        # Vamos a ser más precisos: buscamos el final del prompt de voz.
        # En VibeVoice 1.5b, el prefill suele terminar antes de "Text input:"
        
        # Para simplificar y asegurar compatibilidad, vamos a usar el input completo del texto real
        # PERO nos aseguramos de que 'tts_text_ids' en generate() no empiece desde el principio si ya está en el prefill.
        
        # Sin embargo, la forma más robusta con la librería es:
        # 1. Prefill de TODO (Voz + Texto)
        # 2. En generate, pasar 'tts_text_ids' que sea SOLO el texto a generar.
        
        full_inputs = processor(
            text=f"Speaker 1: {text}",
            voice_samples=[prompt_audio],
            return_tensors="pt",
            sampling_rate=24000
        ).to(device)

        # Identificamos dónde empieza el texto del speaker en los tokens
        # El formato es: ... Text input: \n Speaker 0: {text} \n Speech output: \n <|vision_start|>
        # Queremos que el prefill incluya TODO hasta justo antes del primer token de audio generado.
        
        input_ids = full_inputs["input_ids"]
        attention_mask = full_inputs["attention_mask"]
        
        # 'tts_text_ids' para el bucle de generación debe ser el texto formateado
        # Pero 'generate' lo va consumiendo en ventanas.
        # Si le pasamos el 'input_ids' completo como 'tts_text_ids', volverá a procesar el audio del prompt.
        
        # Lo correcto es:
        # input_ids (prefill) = [Prompt + Audio + Texto]
        # tts_text_ids (generación) = [Texto] (pero el modelo lo concatena internamente)
        
        # Según el código de generate():
        # cur_input_tts_text_ids = tts_text_ids[:, index*WINDOW: (index+1)*WINDOW]
        # input_ids = torch.cat([input_ids, cur_input_tts_text_ids], dim=-1)
        
        # Si el prefill ya tiene el texto, tts_text_ids debe estar vacío o ser lo que viene DESPUÉS.
        # Pero el bucle 'while True' de generate necesita algo en tts_text_ids para correr.
        
        # Vamos a probar la configuración que funcionó en debug_gen.py pero asegurándonos de que
        # el clasificador EOS no se dispare. Aumentamos DDPM steps y bajamos CFG scale ligeramente.
        
        neg_text_input_id = processor.tokenizer.convert_tokens_to_ids("<|image_pad|>")
        neg_input_ids = torch.full((1, 1), neg_text_input_id, dtype=torch.long, device=device)
        neg_attention_mask = torch.ones((1, 1), dtype=torch.long, device=device)

        with torch.no_grad():
            # Prefill Positivo
            lm_out = model.forward_lm(input_ids=input_ids, attention_mask=attention_mask, use_cache=True)
            
            speech_input_mask = full_inputs["speech_input_mask"]
            tts_text_masks = (~speech_input_mask).bool()
            
            tts_lm_out = model.forward_tts_lm(
                input_ids=input_ids, 
                attention_mask=attention_mask, 
                lm_last_hidden_state=lm_out.last_hidden_state,
                tts_text_masks=tts_text_masks,
                use_cache=True
            )
            
            # Prefill Negativo
            neg_lm_out = model.forward_lm(input_ids=neg_input_ids, attention_mask=neg_attention_mask, use_cache=True)
            neg_tts_text_masks = torch.ones((1, 1), dtype=torch.bool, device=device)
            neg_tts_lm_out = model.forward_tts_lm(
                input_ids=neg_input_ids,
                attention_mask=neg_attention_mask,
                lm_last_hidden_state=neg_lm_out.last_hidden_state,
                tts_text_masks=neg_tts_text_masks,
                use_cache=True
            )

        all_prefilled_outputs = {
            "lm": lm_out,
            "tts_lm": tts_lm_out,
            "neg_lm": neg_lm_out,
            "neg_tts_lm": neg_tts_lm_out
        }

        # Para evitar que el modelo genere un audio vacío por ver texto duplicado:
        # Pasamos como tts_text_ids una versión que solo contiene el texto final
        # Pero el prefill debe contener el contexto previo.
        
        # Intentamos este truco: tts_text_ids será solo el texto.
        # Pero como el modelo ya hizo prefill de TODO el input_ids, 
        # le decimos que el tts_text_ids empiece DESPUÉS de lo que ya pre-llenamos.
        
        full_inputs["tts_text_ids"] = input_ids # Por ahora mantenemos esto
        full_inputs["tts_lm_input_ids"] = input_ids
        full_inputs["tts_lm_attention_mask"] = attention_mask
        full_inputs["all_prefilled_outputs"] = all_prefilled_outputs

        with torch.no_grad():
            output = model.generate(
                **full_inputs,
                tokenizer=processor.tokenizer,
                cfg_scale=cfg_scale,
                ddpm_steps=ddpm_steps,
                disable_prefill=disable_prefill,
                max_new_tokens=1000 # Aseguramos un límite razonable
            )

        # La salida suele ser un tensor de audio en output.speech_outputs[0]
        if hasattr(output, "speech_outputs") and output.speech_outputs:
            audio_tensor = output.speech_outputs[0].cpu()
            
            # Guardar temporalmente como WAV
            temp_wav = "temp_generated.wav"
            # torchaudio.save(temp_wav, audio_tensor, 24000)
            # Usamos soundfile para evitar errores de torchcodec en Windows
            soundfile.write(temp_wav, audio_tensor.transpose(0, 1).numpy(), 24000)
            
            if convert_audio(temp_wav, output_path):
                print(f"\n✅ Audio guardado en: {output_path}")
                return True
            else:
                return False
        else:
            print("❌ No se generó audio en la salida del modelo.")
            return False

    except Exception as e:
        print(f"❌ Error durante la generación: {e}")
        import traceback
        traceback.print_exc()
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
    voices_dir = setup_vibevoice_environment()

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
                                             voice_name,
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
