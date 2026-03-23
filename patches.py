import torch
import transformers
from transformers import modeling_utils

def apply_patches():
    """Applies all necessary patches to transformers and VibeVoice classes at runtime."""
    
    # 1. Patch transformers.modeling_utils for parallel styles if missing
    if not hasattr(modeling_utils, "ALL_PARALLEL_STYLES") or modeling_utils.ALL_PARALLEL_STYLES is None:
        modeling_utils.ALL_PARALLEL_STYLES = ["tp", "none", "colwise", "rowwise"]
    
    # 2. Patch VibeVoiceConfig to include num_hidden_layers if not present
    try:
        from vibevoice.modular.configuration_vibevoice import VibeVoiceConfig, VibeVoiceASRConfig
        
        if not hasattr(VibeVoiceConfig, 'num_hidden_layers'):
            @property
            def num_hidden_layers(self):
                return self.decoder_config.num_hidden_layers
            VibeVoiceConfig.num_hidden_layers = num_hidden_layers
            
        if not hasattr(VibeVoiceASRConfig, 'num_hidden_layers'):
            @property
            def num_hidden_layers_asr(self):
                return self.decoder_config.num_hidden_layers
            VibeVoiceASRConfig.num_hidden_layers = num_hidden_layers_asr
    except ImportError:
        pass # Will be handled when vibevoice is in path

    # 3. Patch VibeVoiceForConditionalGenerationInference for transformers compatibility
    try:
        from vibevoice.modular.modeling_vibevoice_inference import VibeVoiceForConditionalGenerationInference
        
        # Original call in modeling_vibevoice_inference.py: 
        # self._prepare_cache_for_generation(generation_config, model_kwargs, None, batch_size, max_cache_length, device)
        # 6 arguments.
        # Transformers 4.45+ (likely what's installed) expects 5 arguments:
        # (generation_config, model_kwargs, batch_size, max_cache_length, device)
        
        old_prep = VibeVoiceForConditionalGenerationInference._prepare_cache_for_generation
        
        def robust_prep(self, *args, **kwargs):
            # Check if we were called with 6 arguments (the VibeVoice way)
            if len(args) == 6: 
                try:
                    return old_prep(self, *args, **kwargs)
                except TypeError:
                    # Remove the 3rd argument (the 'None') and try with 5 args
                    # args are: (generation_config, model_kwargs, None, batch_size, max_cache_length, device)
                    # We want: (generation_config, model_kwargs, batch_size, max_cache_length, device)
                    new_args = (args[0], args[1], args[3], args[4], args[5])
                    return old_prep(self, *new_args, **kwargs)
            return old_prep(self, *args, **kwargs)
        
        VibeVoiceForConditionalGenerationInference._prepare_cache_for_generation = robust_prep
    except (ImportError, AttributeError):
        pass
