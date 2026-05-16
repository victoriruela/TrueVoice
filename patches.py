import torch
import types
import inspect


def _patch_load_state_dict_assign_compat():
    """Make Module.load_state_dict support 'assign=True' on torch <2.1 (e.g. 2.0.1).

    transformers 4.51+ passes assign=True to materialize meta tensors during
    from_pretrained.  torch 2.0.1 doesn't have that parameter so we emulate it:
    when assign=True, we directly replace each parameter/buffer in the module
    with the tensor from the state_dict (same semantics as the native assign=True).
    """
    module_cls = torch.nn.Module
    original = module_cls.load_state_dict

    if getattr(original, "_truevoice_assign_compat", False):
        return

    try:
        supports_assign = "assign" in inspect.signature(original).parameters
    except (TypeError, ValueError):
        supports_assign = True

    if supports_assign:
        return  # torch >=2.1 already handles assign natively

    def _compat_load_state_dict(self, state_dict, strict=True, *args, **kwargs):
        assign = kwargs.pop("assign", False)

        if not assign:
            # Regular path — no assign requested, use the original
            return original(self, state_dict, strict=strict, *args, **kwargs)

        # assign=True path: replace parameters/buffers directly (no copy).
        # This materialises meta tensors created by transformers' init_empty_weights().
        missing_keys = []
        unexpected_keys = []

        # Build a full name→module map for direct assignment
        module_map = {name: mod for name, mod in self.named_modules()}
        module_map[""] = self

        for full_name, tensor in state_dict.items():
            parts = full_name.rsplit(".", 1)
            if len(parts) == 2:
                parent_name, attr = parts
            else:
                parent_name, attr = "", parts[0]

            parent = module_map.get(parent_name)
            if parent is None:
                unexpected_keys.append(full_name)
                continue

            if attr in parent._parameters:
                parent._parameters[attr] = torch.nn.Parameter(tensor, requires_grad=parent._parameters[attr].requires_grad if parent._parameters[attr] is not None else tensor.requires_grad)
            elif attr in parent._buffers:
                parent._buffers[attr] = tensor
            else:
                unexpected_keys.append(full_name)

        if strict:
            # Collect parameters/buffers that were not in state_dict
            current_keys = set()
            for name, p in self.named_parameters():
                current_keys.add(name)
            for name, b in self.named_buffers():
                current_keys.add(name)
            sd_keys = set(state_dict.keys())
            missing_keys = [k for k in current_keys if k not in sd_keys]

        from collections import namedtuple
        _IncompatibleKeys = namedtuple("IncompatibleKeys", ["missing_keys", "unexpected_keys"])
        result = _IncompatibleKeys(missing_keys, unexpected_keys)

        # strict mode raises if there are unexpected keys
        if strict and unexpected_keys:
            raise RuntimeError(
                f"Error(s) in loading state_dict:\n"
                f"\tUnexpected key(s) in state_dict: {unexpected_keys}"
            )
        return result

    _compat_load_state_dict._truevoice_assign_compat = True
    module_cls.load_state_dict = _compat_load_state_dict


_patch_load_state_dict_assign_compat()

if not hasattr(torch, "compiler"):
    def _noop_disable(*args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator

    torch.compiler = types.SimpleNamespace(disable=_noop_disable)

if not hasattr(torch, "float8_e4m3fn"):
    torch.float8_e4m3fn = torch.float16

if not hasattr(torch, "float8_e5m2"):
    torch.float8_e5m2 = torch.float16

def _fake_device_namespace():
    return types.SimpleNamespace(
        empty_cache=lambda: None,
        is_available=lambda: False,
        device_count=lambda: 0,
        current_device=lambda: 0,
        manual_seed=lambda seed: None,
        manual_seed_all=lambda seed: None,
        seed=lambda: None,
        seed_all=lambda: None,
    )

if not hasattr(torch, "xpu"):
    torch.xpu = _fake_device_namespace()

for _dev in ("mps", "npu", "mlu", "musa", "sdaa"):
    if not hasattr(torch, _dev):
        setattr(torch, _dev, _fake_device_namespace())

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

        # 4. Patch generate to print progress
        old_generate = VibeVoiceForConditionalGenerationInference.generate

        def progressive_generate(self, *args, **kwargs):
            # We want to catch the 'step' in the loop. 
            # Since the loop is inside generate, we can't easily hook it without 
            # re-implementing or using a custom tqdm_class.
            
            class ProgressTqdm:
                def __init__(self, iterable, **tqdm_kwargs):
                    self.iterable = iterable
                    try:
                        self.total = len(iterable)
                    except (TypeError, AttributeError):
                        self.total = 0
                    self.n = 0
                    if self.total > 0:
                        import sys
                        sys.stdout.write(f"PROGRESS_START:{self.total}\n")
                        sys.stdout.flush()
                        sys.stderr.write(f"PROGRESS_START:{self.total}\n")
                        sys.stderr.flush()

                def __iter__(self):
                    if self.total == 0:
                        try:
                            self.total = len(self.iterable)
                            if self.total > 0:
                                import sys
                                sys.stdout.write(f"PROGRESS_START:{self.total}\n")
                                sys.stdout.flush()
                                sys.stderr.write(f"PROGRESS_START:{self.total}\n")
                                sys.stderr.flush()
                        except: pass
                    
                    import sys
                    for item in self.iterable:
                        yield item
                        self.n += 1
                        sys.stdout.write(f"PROGRESS_STEP:{self.n}\n")
                        sys.stdout.flush()
                        # También a stderr por si acaso la API lee de ahí
                        sys.stderr.write(f"PROGRESS_STEP:{self.n}\n")
                        sys.stderr.flush()

                def set_description(self, desc, refresh=True): pass
                def close(self): pass

            kwargs['tqdm_class'] = ProgressTqdm
            kwargs['show_progress_bar'] = True
            return old_generate(self, *args, **kwargs)

        VibeVoiceForConditionalGenerationInference.generate = progressive_generate

    except (ImportError, AttributeError):
        pass
