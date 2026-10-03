import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import torch

try:
    if hasattr(torch, "ops") and hasattr(torch.ops, "_C"):
        if not hasattr(torch.ops._C, "init_cpu_memory_env"):
            torch.ops._C.init_cpu_memory_env = lambda *args, **kwargs: None
            print("[sitecustomize] Registered dummy torch.ops._C.init_cpu_memory_env")
except Exception as e:
    print(f"[sitecustomize] Warning torch.ops: {e}")

# SOTA COMPATIBILITY: PEFT unconditionally imports LinearActivationQuantizedTensor from torchao.quantization
# even when regular non-quantized LoRA adapters are used. Modern torchao moved this to a submodule.
try:
    import torchao.quantization as _tao_q
    if not hasattr(_tao_q, "LinearActivationQuantizedTensor"):
        try:
            from torchao.quantization.linear_activation_quantized_tensor import (
                LinearActivationQuantizedTensor as _RealLAQT,
            )
            _tao_q.LinearActivationQuantizedTensor = _RealLAQT
            print("[sitecustomize] Patched torchao.quantization.LinearActivationQuantizedTensor from submodule")
        except ImportError:
            class _StubLinearActivationQuantizedTensor:
                pass
            _tao_q.LinearActivationQuantizedTensor = _StubLinearActivationQuantizedTensor
            print("[sitecustomize] Registered stub LinearActivationQuantizedTensor in torchao.quantization")
except Exception as e:
    pass

# SOTA COMPATIBILITY: Accelerate's get_balanced_memory fails with TypeError: unhashable type: 'set'
# if no_split_module_classes contains nested sets or collections. Sanitize to flat list of strings.
try:
    import accelerate.utils.modeling as _acc_mod
    import accelerate.utils as _acc_u
    import accelerate as _acc
    import peft.peft_model as _peft_m

    def _flatten_strings(items):
        flat = []
        if isinstance(items, str):
            return [items]
        if isinstance(items, (list, tuple, set)):
            for it in items:
                flat.extend(_flatten_strings(it))
        return flat

    _orig_gbm = _acc_mod.get_balanced_memory

    def _safe_get_balanced_memory(*args, **kwargs):
        if "no_split_module_classes" in kwargs and kwargs["no_split_module_classes"] is not None:
            kwargs["no_split_module_classes"] = list(dict.fromkeys(_flatten_strings(kwargs["no_split_module_classes"])))
        elif len(args) > 2 and args[2] is not None:
            args_list = list(args)
            args_list[2] = list(dict.fromkeys(_flatten_strings(args_list[2])))
            args = tuple(args_list)
        return _orig_gbm(*args, **kwargs)

    _acc_mod.get_balanced_memory = _safe_get_balanced_memory
    if hasattr(_acc_u, "get_balanced_memory"):
        _acc_u.get_balanced_memory = _safe_get_balanced_memory
    if hasattr(_acc, "get_balanced_memory"):
        _acc.get_balanced_memory = _safe_get_balanced_memory
    if hasattr(_peft_m, "get_balanced_memory"):
        _peft_m.get_balanced_memory = _safe_get_balanced_memory

    _peft_m.PeftModel._no_split_modules = property(
        lambda self: list(dict.fromkeys(
            _flatten_strings(
                getattr(getattr(self, "base_model", self), "_no_split_modules", ["Qwen2DecoderLayer"])
                or ["Qwen2DecoderLayer"]
            )
        ))
    )
    print("[sitecustomize] Successfully patched get_balanced_memory & PeftModel._no_split_modules")
except Exception as e:
    print(f"[sitecustomize] Warning patching peft/accelerate: {e}")

if os.getenv("VLLM_TARGET_DEVICE") == "cpu" or os.getenv("SSENSE_COMPUTE_PROFILE") == "cpu":
    try:
        import vllm.platforms as p
        from vllm.platforms.cpu import CpuPlatform
        p.current_platform = CpuPlatform()
        print(f"[sitecustomize] Set vllm.platforms.current_platform to CpuPlatform")
    except Exception as e:
        print(f"[sitecustomize] Warning setting CpuPlatform: {e}")
