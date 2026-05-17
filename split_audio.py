"""
split_audio.py — Separa audio en fragmentos y transcribe con faster-whisper.

Uso:
    python split_audio.py \
        --input largo.mp3 \
        --output_dir training_data/session_id \
        --whisper_model tiny \
        --silence_threshold -35 \
        --min_silence_len 0.5 \
        --min_segment_len 2.0 \
        --max_segment_len 30.0 \
        --speaker_number 1

Protocolo de progreso (stdout):
    SPLIT_PROGRESS:N/TOTAL     — cada fragmento terminado
    SPLIT_DONE:N               — totalmenteterminado con N segmentos
    SPLIT_ERROR:mensaje        — error fatal
"""
import os
import sys
import argparse
import json
import subprocess
import tempfile
import re

def detect_silence_ranges(input_path, silence_db=-35.0, min_silence_len=0.5):
    """
    Usa ffmpeg silencedetect para encontrar rangos de silencio.
    Retorna lista de (start, end) en segundos.
    """
    cmd = [
        "ffmpeg", "-i", input_path,
        "-af", f"silencedetect=noise={silence_db}dB:d={min_silence_len}",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stderr  # ffmpeg logs to stderr

    silences = []
    starts = []
    ends = []
    for line in output.splitlines():
        m = re.search(r"silence_start:\s*([\d.]+)", line)
        if m:
            starts.append(float(m.group(1)))
        m = re.search(r"silence_end:\s*([\d.]+)", line)
        if m:
            ends.append(float(m.group(1)))

    for s, e in zip(starts, ends):
        silences.append((s, e))
    return silences


def get_audio_duration(input_path):
    """Obtiene la duración del audio en segundos usando ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", input_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])
    except Exception:
        return None


def compute_segments(silences, duration, min_seg=2.0, max_seg=30.0):
    """
    A partir de rangos de silencio, calcula segmentos de habla.
    Fuerza que cada segmento esté entre min_seg y max_seg segundos.
    """
    # Puntos de corte = centro de cada silencio
    cuts = [0.0]
    for s_start, s_end in silences:
        mid = (s_start + s_end) / 2.0
        cuts.append(mid)
    cuts.append(duration)

    segments = []
    current_start = 0.0
    for i in range(1, len(cuts)):
        seg_end = cuts[i]
        seg_len = seg_end - current_start
        if seg_len < min_seg:
            # Fusionar con el siguiente
            continue
        if seg_len > max_seg:
            # Dividir en trozos de max_seg
            pos = current_start
            while pos + max_seg < seg_end:
                segments.append((pos, pos + max_seg))
                pos += max_seg
            if seg_end - pos >= min_seg:
                segments.append((pos, seg_end))
        else:
            segments.append((current_start, seg_end))
        current_start = seg_end

    return segments


def extract_segment(input_path, output_path, start, end):
    """Extrae un segmento de audio con ffmpeg."""
    duration = end - start
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-t", f"{duration:.3f}",
        "-i", input_path,
        "-acodec", "pcm_s16le",
        "-ar", "22050",
        "-ac", "1",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def transcribe_segment(audio_path, model, speaker_number=1):
    """
    Transcribe un segmento de audio con faster-whisper.
    Retorna el texto en formato 'Speaker N: texto'.
    """
    segments, _ = model.transcribe(audio_path, beam_size=5, language=None)
    text_parts = []
    for seg in segments:
        text_parts.append(seg.text.strip())
    text = " ".join(text_parts).strip()
    if not text:
        return None
    return f"Speaker {speaker_number}: {text}"


def main():
    parser = argparse.ArgumentParser(description="Split audio and transcribe with Whisper")
    parser.add_argument("--input", required=True, help="Input audio file")
    parser.add_argument("--output_dir", required=True, help="Output directory for segments")
    parser.add_argument("--whisper_model", default="base", choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper model size (default: base)")
    parser.add_argument("--silence_threshold", type=float, default=-35.0,
                        help="Silence detection threshold in dB (default: -35)")
    parser.add_argument("--min_silence_len", type=float, default=0.5,
                        help="Minimum silence duration in seconds (default: 0.5)")
    parser.add_argument("--min_segment_len", type=float, default=2.0,
                        help="Minimum segment length in seconds (default: 2.0)")
    parser.add_argument("--max_segment_len", type=float, default=30.0,
                        help="Maximum segment length in seconds (default: 30.0)")
    parser.add_argument("--speaker_number", type=int, default=1,
                        help="Speaker number for transcript format 'Speaker N:' (default: 1)")
    parser.add_argument("--base_name", type=str, default=None,
                        help="Base name for output files (default: input filename stem)")
    parser.add_argument("--device", type=str, default="cpu", choices=["cpu", "cuda"],
                        help="Device for Whisper inference (default: cpu)")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"SPLIT_ERROR:Input file not found: {args.input}", flush=True)
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    # Detectar duración
    duration = get_audio_duration(args.input)
    if duration is None:
        print("SPLIT_ERROR:Could not read audio duration (ffprobe failed)", flush=True)
        sys.exit(1)

    print(f"SPLIT_INFO:Audio duration: {duration:.1f}s", flush=True)

    # Detectar silencios
    print("SPLIT_INFO:Detecting silence...", flush=True)
    silences = detect_silence_ranges(args.input, args.silence_threshold, args.min_silence_len)
    print(f"SPLIT_INFO:Found {len(silences)} silence regions", flush=True)

    # Calcular segmentos
    segments = compute_segments(silences, duration, args.min_segment_len, args.max_segment_len)
    total = len(segments)
    if total == 0:
        print("SPLIT_ERROR:No segments found — try adjusting silence threshold", flush=True)
        sys.exit(1)

    print(f"SPLIT_INFO:Will produce {total} segments", flush=True)

    # Cargar modelo Whisper
    print(f"SPLIT_INFO:Loading faster-whisper model '{args.whisper_model}'...", flush=True)
    try:
        from faster_whisper import WhisperModel
        compute_type = "float32" if args.device == "cpu" else "float16"
        whisper_model = WhisperModel(args.whisper_model, device=args.device, compute_type=compute_type)
    except ImportError:
        print("SPLIT_ERROR:faster-whisper not installed. Run: pip install faster-whisper", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"SPLIT_ERROR:Failed to load Whisper model: {e}", flush=True)
        sys.exit(1)

    base_name = args.base_name
    if not base_name:
        base_name = os.path.splitext(os.path.basename(args.input))[0]
    # Sanitize base_name
    base_name = re.sub(r'[^\w\-]', '_', base_name)

    produced = []
    for idx, (seg_start, seg_end) in enumerate(segments, start=1):
        seg_name = f"{base_name}_{idx:03d}"
        wav_path = os.path.join(args.output_dir, f"{seg_name}.wav")
        txt_path = os.path.join(args.output_dir, f"{seg_name}.txt")

        # Extraer segmento
        if not extract_segment(args.input, wav_path, seg_start, seg_end):
            print(f"SPLIT_WARN:Failed to extract segment {idx}, skipping", flush=True)
            print(f"SPLIT_PROGRESS:{idx}/{total}", flush=True)
            continue

        # Transcribir
        try:
            transcript = transcribe_segment(wav_path, whisper_model, args.speaker_number)
        except Exception as e:
            transcript = None
            print(f"SPLIT_WARN:Transcription failed for segment {idx}: {e}", flush=True)

        if transcript:
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(transcript)
            produced.append({"audio": f"{seg_name}.wav", "transcript": f"{seg_name}.txt",
                              "base_name": seg_name, "start": seg_start, "end": seg_end,
                              "duration": seg_end - seg_start, "text": transcript})
        else:
            # Keep the wav but no transcript — user can manually transcribe
            produced.append({"audio": f"{seg_name}.wav", "transcript": None,
                              "base_name": seg_name, "start": seg_start, "end": seg_end,
                              "duration": seg_end - seg_start, "text": ""})

        print(f"SPLIT_PROGRESS:{idx}/{total}", flush=True)

    # Write summary JSON
    summary_path = os.path.join(args.output_dir, "split_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"total": len(produced), "segments": produced}, f, ensure_ascii=False, indent=2)

    print(f"SPLIT_DONE:{len(produced)}", flush=True)


if __name__ == "__main__":
    main()
