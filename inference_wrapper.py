import os
import sys
import torch
import time
import argparse

# 1. Configurar path para encontrar el paquete 'vibevoice'
# (Se espera que este script se ejecute con PYTHONPATH apuntando a VibeVoice, 
# o lo configuramos aquí basándonos en la ubicación esperada)
# Asumimos que el script corre desde la raíz del proyecto TrueVoice.

project_root = os.path.dirname(os.path.abspath(__file__))
vibe_voice_repo = os.path.join(project_root, "VibeVoice")
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

def main():
    parser = argparse.ArgumentParser(description="VibeVoice Wrapper Inference")
    parser.add_argument("--ddpm_steps", type=int, default=30)
    parser.add_argument("--model_path", type=str, default="microsoft/VibeVoice-1.5b")
    parser.add_argument("--txt_path", type=str, required=True)
    parser.add_argument("--speaker_names", type=str, nargs='+', default=['Alice'])
    parser.add_argument("--output_dir", type=str, default="./outputs")
    parser.add_argument("--device", type=str, default=("cuda" if torch.cuda.is_available() else "cpu"))
    parser.add_argument("--checkpoint_path", type=str, default=None)
    parser.add_argument("--disable_prefill", action="store_true")
    parser.add_argument("--cfg_scale", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=None)
    
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

    full_script = '\n'.join(scripts).replace("’", "'")
    
    processor = VibeVoiceProcessor.from_pretrained(args.model_path)
    
    load_dtype = torch.bfloat16 if args.device == "cuda" else torch.float32
    attn_impl = "flash_attention_2" if args.device == "cuda" else "sdpa"
    
    model = VibeVoiceForConditionalGenerationInference.from_pretrained(
        args.model_path,
        torch_dtype=load_dtype,
        device_map=args.device,
        attn_implementation=attn_impl,
    )
    
    if args.checkpoint_path:
        load_lora_assets(model, args.checkpoint_path)

    model.eval()
    if hasattr(model, 'set_ddpm_inference_steps'):
        model.set_ddpm_inference_steps(num_steps=args.ddpm_steps)

    inputs = processor(
        text=[full_script],
        voice_samples=[voice_samples],
        padding=True,
        return_tensors="pt",
    ).to(args.device)

    print(f"Generating with cfg_scale={args.cfg_scale}, ddpm_steps={args.ddpm_steps}...")
    start_time = time.time()
    outputs = model.generate(
        **inputs,
        max_new_tokens=None,
        cfg_scale=args.cfg_scale,
        tokenizer=processor.tokenizer,
        generation_config={'do_sample': False},
        is_prefill=not args.disable_prefill,
    )
    print(f"Generation took {time.time() - start_time:.2f}s")

    os.makedirs(args.output_dir, exist_ok=True)
    txt_filename = os.path.splitext(os.path.basename(args.txt_path))[0]
    output_path = os.path.join(args.output_dir, f"{txt_filename}_generated.wav")
    
    processor.save_audio(outputs.speech_outputs[0], output_path=output_path)
    print(f"Saved to {output_path}")

if __name__ == "__main__":
    main()
