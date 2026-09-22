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

if os.getenv("VLLM_TARGET_DEVICE") == "cpu" or os.getenv("SSENSE_COMPUTE_PROFILE") == "cpu":
    try:
        import vllm.platforms as p
        from vllm.platforms.cpu import CpuPlatform
        p.current_platform = CpuPlatform()
        print(f"[sitecustomize] Set vllm.platforms.current_platform to CpuPlatform")
    except Exception as e:
        print(f"[sitecustomize] Warning setting CpuPlatform: {e}")
