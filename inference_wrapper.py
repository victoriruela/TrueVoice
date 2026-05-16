import os
import re
import sys
import time
import argparse
import tempfile

import torch
import numpy as np

# Maximizar uso de CPU: usar todos los cores disponibles
_cpu_count = os.cpu_count() or 4
torch.set_num_threads(_cpu_count)
torch.set_num_interop_threads(max(1, _cpu_count // 2))

# 1. Configurar path para encontrar el paquete 'vibevoice'
# (Se espera que este script se ejecute con PYTHONPATH apuntando a VibeVoice, 
# o lo configuramos aquí basándonos en la ubicación esperada)
# Asumimos que el script corre desde la raíz del proyecto TrueVoice.

project_root = os.path.dirname(os.path.abspath(__file__))
vibe_voice_repo = os.path.join(project_root, "VibeVoice")
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if vibe_voice_repo not in sys.path:
    sys.path.insert(0, vibe_voice_repo)

# 2. Aplicar parches antes de importar cualquier cosa de vibevoice
from patches import apply_patches
apply_patches()

# 3. Importar componentes de vibevoice
from vibevoice.modular.modeling_vibevoice_inference import VibeVoiceForConditionalGenerationInference
from vibevoice.modular.lora_loading import load_lora_assets
from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor
from transformers.utils import logging

logging.set_verbosity_info()
logger = logging.get_logger(__name__)

# Re-implementar VoiceMapper localmente para evitar cambios en VibeVoice
class VoiceMapper:
    """Maps speaker names to voice file paths"""
    def __init__(self, voices_dir):
        self.voices_dir = voices_dir
        self.setup_voice_presets()

    def setup_voice_presets(self):
        if not os.path.exists(self.voices_dir):
            print(f"Warning: Voices directory not found at {self.voices_dir}")
            self.voice_presets = {}
            return

        self.voice_presets = {}
        wav_files = [f for f in os.listdir(self.voices_dir)
                    if f.lower().endswith('.wav') and os.path.isfile(os.path.join(self.voices_dir, f))]

        for wav_file in wav_files:
            name = os.path.splitext(wav_file)[0]
            full_path = os.path.join(self.voices_dir, wav_file)
            self.voice_presets[name] = full_path

        # Añadir variaciones (con y sin prefijos/sufijos)
        new_dict = {}
        for name, path in self.voice_presets.items():
            clean_name = name
            if '_' in clean_name: clean_name = clean_name.split('_')[0]
            if '-' in clean_name: clean_name = clean_name.split('-')[-1]
            new_dict[clean_name] = path
        self.voice_presets.update(new_dict)
        self.voice_presets = dict(sorted(self.voice_presets.items()))

    def get_voice_path(self, speaker_name: str):
        # Si es una ruta absoluta que existe, devolverla directamente
        if os.path.isabs(speaker_name) and os.path.exists(speaker_name):
            return speaker_name

        if speaker_name in self.voice_presets:
            return self.voice_presets[speaker_name]
        
        # Fallback exact match
        path = os.path.join(self.voices_dir, f"{speaker_name}.wav")
        if os.path.exists(path): return path
        
        # Return first available if not found
        if self.voice_presets:
            return list(self.voice_presets.values())[0]
        return None

def parse_txt_script(txt_content: str):
    import re
    scripts = []
    speaker_numbers = []
    lines = txt_content.strip().split('\n')
    current_speaker = None
    current_text = ""

    for line in lines:
        line = line.strip()
        if not line: continue
        
        match = re.match(r'^Speaker\s+(\d+):\s*(.*)', line, re.IGNORECASE)
        if match:
            if current_speaker and current_text:
                scripts.append(f"Speaker {current_speaker}: {current_text.strip()}")
                speaker_numbers.append(current_speaker)
            current_speaker = match.group(1)
            current_text = match.group(2)
        else:
            if current_speaker:
                current_text += " " + line
            else:
                current_text = line

    if current_speaker and current_text:
        scripts.append(f"Speaker {current_speaker}: {current_text.strip()}")
        speaker_numbers.append(current_speaker)
    return scripts, speaker_numbers


# ── Pause tag parsing ─────────────────────────────────────────────────
_PAUSE_RE = re.compile(r"\[pause(?::(\d+))?\]", re.IGNORECASE)


def parse_pause_tags(text: str):
    """Splits text into [('text', str) | ('silence', ms_int)] segments."""
    parts = []
    last = 0
    for m in _PAUSE_RE.finditer(text):
        seg = text[last:m.start()].strip()
        if seg:
            parts.append(('text', seg))
        ms = int(m.group(1)) if m.group(1) else 1000
        parts.append(('silence', ms))
        last = m.end()
    tail = text[last:].strip()
    if tail:
        parts.append(('text', tail))
    return parts if parts else [('text', text)]


def chunk_text_by_words(text: str, max_words: int):
    """Splits text into sub-chunks of at most max_words words, respecting sentence boundaries."""
    if max_words <= 0:
        return [text]
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current, count = [], [], 0
    for sent in sentences:
        words = len(sent.split())
        if count + words > max_words and current:
            chunks.append(' '.join(current))
            current, count = [sent], words
        else:
            current.append(sent)
            count += words
    if current:
        chunks.append(' '.join(current))
    return chunks if chunks else [text]


def _audio_to_numpy(audio_obj):
    """Best-effort conversion of model output (tensor/list/np) to mono float numpy array."""
    if hasattr(audio_obj, 'detach'):
        arr = audio_obj.detach().cpu().numpy()
    elif isinstance(audio_obj, np.ndarray):
        arr = audio_obj
    else:
        arr = np.asarray(audio_obj)
    return arr.squeeze()

def main():
    parser = argparse.ArgumentParser(description="VibeVoice Wrapper Inference")
    parser.add_argument("--ddpm_steps", type=int, default=10)
    parser.add_argument("--model_path", type=str, default="microsoft/VibeVoice-1.5b")
    parser.add_argument("--txt_path", type=str, required=True)
    parser.add_argument("--speaker_names", type=str, nargs='+', default=['Alice'])
    parser.add_argument("--output_dir", type=str, default="./outputs")
    parser.add_argument("--device", type=str, default=("cuda" if torch.cuda.is_available() else "cpu"))
    parser.add_argument("--checkpoint_path", type=str, default=None)
    parser.add_argument("--disable_prefill", action="store_true")
    parser.add_argument("--cfg_scale", type=float, default=1.3)
    parser.add_argument("--seed", type=int, default=None)

    # Advanced generation parameters
    parser.add_argument("--temperature", type=float, default=0.95)
    parser.add_argument("--top_p", type=float, default=0.95)
    parser.add_argument("--use_sampling", action="store_true", default=False)
    parser.add_argument("--quantize_llm", type=str, default="none",
                        choices=["none", "4bit", "8bit"])
    parser.add_argument("--voice_speed_factor", type=float, default=1.0)
    parser.add_argument("--max_words_per_chunk", type=int, default=250)

    args = parser.parse_args()

    if args.seed is not None:
        torch.manual_seed(args.seed)

    voices_dir = os.path.join(vibe_voice_repo, "demo", "voices")
    voice_mapper = VoiceMapper(voices_dir)

    with open(args.txt_path, 'r', encoding='utf-8') as f:
        txt_content = f.read()
    scripts, speaker_numbers = parse_txt_script(txt_content)
    
    # Mapping logic (simplified from original)
    speaker_name_mapping = {str(i+1): name for i, name in enumerate(args.speaker_names)}
    
    unique_speaker_numbers = []
    seen = set()
    for sn in speaker_numbers:
        if sn not in seen:
            unique_speaker_numbers.append(sn)
            seen.add(sn)

    voice_samples = []
    for sn in unique_speaker_numbers:
        name = speaker_name_mapping.get(sn, f"Speaker {sn}")
        path = voice_mapper.get_voice_path(name)
        voice_samples.append(path)

    # ── Voice speed control ──────────────────────────────────────────
    # Apply time-stretching to reference voices before they are passed to the processor.
    if args.voice_speed_factor != 1.0:
        try:
            import librosa
            import soundfile as sf
            new_voice_samples = []
            for vpath in voice_samples:
                if vpath and os.path.exists(vpath):
                    audio, sr = librosa.load(vpath, sr=None, mono=True)
                    stretched = librosa.effects.time_stretch(audio, rate=args.voice_speed_factor)
                    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                    tmp.close()
                    sf.write(tmp.name, stretched, sr)
                    new_voice_samples.append(tmp.name)
                else:
                    new_voice_samples.append(vpath)
            voice_samples = new_voice_samples
            print(f"Voice speed factor applied: {args.voice_speed_factor}", flush=True)
        except Exception as e:
            print(f"WARNING: voice speed factor failed ({e}), using original voices", flush=True)

    full_script = '\n'.join(scripts).replace("’", "'")
    
    processor = VibeVoiceProcessor.from_pretrained(args.model_path)
    
    # float32 usa instrucciones AVX2/MKL nativas en CPU; en CPU forzamos eager
    # para no depender de SDPA (torch>=2.1.1) en runtimes empaquetados antiguos.
    load_dtype = torch.float32
    attn_impl = "flash_attention_2" if args.device == "cuda" else "eager"

    # ── Dynamic quantization (CUDA only) ─────────────────────────────
    quantization_config = None
    if args.device == "cuda" and args.quantize_llm != "none":
        try:
            from transformers import BitsAndBytesConfig
            if args.quantize_llm == "4bit":
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.float16,
                )
            elif args.quantize_llm == "8bit":
                quantization_config = BitsAndBytesConfig(load_in_8bit=True)
            print(f"Using quantization: {args.quantize_llm}", flush=True)
        except ImportError:
            print("WARNING: bitsandbytes no disponible, ignorando cuantización", flush=True)
            quantization_config = None
        except Exception as e:
            print(f"WARNING: quantization setup failed ({e}), continuing without it", flush=True)
            quantization_config = None

    from_pretrained_kwargs = dict(
        torch_dtype=load_dtype,
        device_map=args.device,
        attn_implementation=attn_impl,
        low_cpu_mem_usage=True,
    )
    if quantization_config is not None:
        from_pretrained_kwargs["quantization_config"] = quantization_config

    model = VibeVoiceForConditionalGenerationInference.from_pretrained(
        args.model_path,
        **from_pretrained_kwargs,
    )
    
    if args.checkpoint_path:
        load_lora_assets(model, args.checkpoint_path)

    model.eval()
    if hasattr(model, 'set_ddpm_inference_steps'):
        model.set_ddpm_inference_steps(num_steps=args.ddpm_steps)

    # ── Build generation kwargs (sampling vs greedy) ─────────────────
    extra_gen_kwargs: dict = {}
    if args.use_sampling:
        extra_gen_kwargs['do_sample'] = True
        extra_gen_kwargs['temperature'] = args.temperature
        extra_gen_kwargs['top_p'] = args.top_p

    def _generate_for_text(text_block: str):
        """Run a single inference for a given script text and return numpy audio array."""
        inputs = processor(
            text=[text_block],
            voice_samples=[voice_samples],
            padding=True,
            return_tensors="pt",
        ).to(args.device)

        outputs = model.generate(
            **inputs,
            max_new_tokens=None,
            cfg_scale=args.cfg_scale,
            tokenizer=processor.tokenizer,
            is_prefill=not args.disable_prefill,
            **extra_gen_kwargs,
        )
        return _audio_to_numpy(outputs.speech_outputs[0])

    # ── Pause tag + chunking pipeline ────────────────────────────────
    # 1) Split by pause tags. 2) For each text segment, chunk by words.
    pause_segments = parse_pause_tags(full_script)

    # Inspect sample rate from processor's audio config (fallback 24000)
    sample_rate = 24000
    try:
        ac = getattr(processor, 'audio_processor', None) or getattr(processor, 'feature_extractor', None)
        if ac is not None and hasattr(ac, 'sampling_rate'):
            sample_rate = int(ac.sampling_rate)
    except Exception:
        pass

    has_pause = any(kind == 'silence' for kind, _ in pause_segments)
    will_chunk = any(
        kind == 'text' and len(val.split()) > args.max_words_per_chunk
        for kind, val in pause_segments
    )

    print(f"Generating with cfg_scale={args.cfg_scale}, ddpm_steps={args.ddpm_steps}, "
          f"sampling={args.use_sampling}, pause_tags={has_pause}, chunking={will_chunk}...", flush=True)
    start_time = time.time()

    if not has_pause and not will_chunk:
        audio_np = _generate_for_text(full_script)
        final_audio = audio_np
    else:
        pieces = []
        for kind, val in pause_segments:
            if kind == 'silence':
                n_samples = int(sample_rate * (val / 1000.0))
                pieces.append(np.zeros(n_samples, dtype=np.float32))
                continue
            # text segment — chunk by words if needed
            chunks = chunk_text_by_words(val, args.max_words_per_chunk)
            for ch in chunks:
                if not ch.strip():
                    continue
                # Reset seed before each chunk for stability/repeatability
                if args.seed is not None:
                    torch.manual_seed(args.seed)
                a = _generate_for_text(ch)
                pieces.append(a.astype(np.float32))
        final_audio = np.concatenate(pieces) if pieces else np.zeros(1, dtype=np.float32)

    print(f"Generation took {time.time() - start_time:.2f}s", flush=True)

    os.makedirs(args.output_dir, exist_ok=True)
    txt_filename = os.path.splitext(os.path.basename(args.txt_path))[0]
    output_path = os.path.join(args.output_dir, f"{txt_filename}_generated.wav")

    # processor.save_audio expects torch-compatible input; pass a tensor
    processor.save_audio(torch.from_numpy(final_audio), output_path=output_path)
    print(f"Saved to {output_path}", flush=True)

if __name__ == "__main__":
    main()
