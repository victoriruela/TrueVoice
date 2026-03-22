import torch
import soundfile
from pathlib import Path
from vibevoice.processor import VibeVoiceProcessor
from vibevoice import VibeVoiceStreamingForConditionalGenerationInference as Inference

def test_gen():
    model_name = "microsoft/VibeVoice-1.5b"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    
    processor = VibeVoiceProcessor.from_pretrained(model_name)
    model = Inference.from_pretrained(model_name).to(device)
    
    text = "Esto es una prueba corta para ver si genera audio real."
    voice_path = Path("voices/Lobato_WAV.wav")
    
    if not voice_path.exists():
        print("Alice voice not found, downloading...")
        import requests
        voice_path.parent.mkdir(exist_ok=True)
        r = requests.get("https://github.com/microsoft/VibeVoice/raw/main/demo/voices/en-Alice_woman.wav")
        voice_path.write_bytes(r.content)

    data, sample_rate = soundfile.read(str(voice_path))
    prompt_audio = torch.from_numpy(data).float()
    if prompt_audio.ndim == 1:
        prompt_audio = prompt_audio.unsqueeze(0)
    else:
        prompt_audio = prompt_audio.transpose(0, 1)

    formatted_text = f"Speaker 1: {text}"
    inputs = processor(
        text=formatted_text,
        voice_samples=[prompt_audio],
        return_tensors="pt",
        sampling_rate=24000
    ).to(device)

    print("Prefilling...")
    input_ids = inputs["input_ids"]
    attention_mask = inputs["attention_mask"]
    neg_text_input_id = processor.tokenizer.convert_tokens_to_ids("<|image_pad|>")
    neg_input_ids = torch.full((1, 1), neg_text_input_id, dtype=torch.long, device=device)
    neg_attention_mask = torch.ones((1, 1), dtype=torch.long, device=device)

    with torch.no_grad():
        lm_out = model.forward_lm(input_ids=input_ids, attention_mask=attention_mask, use_cache=True)
        speech_input_mask = inputs["speech_input_mask"]
        tts_text_masks = (~speech_input_mask).bool()
        
        tts_lm_out = model.forward_tts_lm(
            input_ids=input_ids, 
            attention_mask=attention_mask, 
            lm_last_hidden_state=lm_out.last_hidden_state,
            tts_text_masks=tts_text_masks,
            use_cache=True
        )
        
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

    inputs["tts_text_ids"] = inputs.get("input_ids")
    inputs["tts_lm_input_ids"] = input_ids
    inputs["tts_lm_attention_mask"] = attention_mask
    inputs["all_prefilled_outputs"] = all_prefilled_outputs

    print("Generating...")
    # Usamos pocos pasos para ir rápido en el test
    output = model.generate(
        **inputs,
        tokenizer=processor.tokenizer,
        cfg_scale=1.5,
        ddpm_steps=5, 
    )

    if hasattr(output, "speech_outputs") and output.speech_outputs:
        audio_tensor = output.speech_outputs[0].cpu()
        print(f"Generated audio shape: {audio_tensor.shape}")
        if audio_tensor.shape[-1] > 0:
            soundfile.write("debug_output.wav", audio_tensor.transpose(0, 1).numpy(), 24000)
            print("Audio saved to debug_output.wav")
        else:
            print("Generated audio is empty!")
    else:
        print("No speech_outputs found.")

if __name__ == "__main__":
    test_gen()
