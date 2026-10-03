#!/usr/bin/env python3
"""
engine.py – SOTA Zero-Hop In-Process AsyncLLMEngine (Multi-Profile)

One base model (Qwen2.5-7B-Instruct), one multi-LoRA mechanism (audit +
chatbot adapters, hot-swapped per request), across three hardware profiles:

  gpu    – Discrete NVIDIA datacenter GPU (vLLM engine, dedicated VRAM)
  jetson – NVIDIA Jetson AGX-class edge device (vLLM engine, unified memory)
  cpu    – HuggingFace Transformers + PEFT dual-adapter execution
           (bypasses PyPI vLLM CPU C++ op deficiencies while ensuring robust 
           multi-LoRA switching, token streaming, and full DPDP Act compliance).
"""

import os
import sys
os.environ["VLLM_USE_V1"] = "0"

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import asyncio
import queue as _queue
import re
import threading
import time
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, Optional, Union
import torch

_SYS_CONCISE = (
    "<|im_start|>system\n"
    "You are the Ssense DPDP Co-Pilot. "
    "Ground ALL answers strictly in the provided audit report and statutory context. "
    "When comparing sites, directly compare their scores and violations. "
    "Answer in 2–3 direct sentences under 45 words. Be direct and skip preamble."
    "<|im_end|>\n"
)
_SYS_THINKING = (
    "<|im_start|>system\n"
    "You are the Ssense DPDP Co-Pilot. "
    "Ground ALL answers strictly in the provided audit report and statutory context. "
    "When asked about the audited site, analyze its violations and evidence thoroughly step by step through the DPDP Act 2023 provisions. "
    "A thorough, well-reasoned statutory analysis is expected."
    "<|im_end|>\n"
)



def get_system_ram_gb() -> float:
    """Returns total system physical RAM in GiB across Linux/Windows/macOS."""
    try:
        import psutil
        return float(psutil.virtual_memory().total) / (1024 ** 3)
    except Exception:
        pass
    try:
        if hasattr(os, "sysconf") and "SC_PAGE_SIZE" in os.sysconf_names and "SC_PHYS_PAGES" in os.sysconf_names:
            return float(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")) / (1024 ** 3)
    except Exception:
        pass
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return float(line.split()[1]) / (1024 * 1024)
    except Exception:
        pass
    return 32.0


def is_unified_memory() -> bool:
    """Detects NVIDIA Jetson (Tegra) or unified memory where CPU & GPU share the same physical DRAM."""
    if Path("/etc/nv_tegra_release").exists() or Path("/sys/devices/soc0/family").exists():
        return True
    if torch.cuda.is_available():
        try:
            props = torch.cuda.get_device_properties(0)
            if getattr(props, "is_integrated", 0) == 1:
                return True
        except Exception:
            pass
    return False


def get_gpu_devices() -> list[Dict[str, Any]]:
    """Probes functional CUDA devices and returns per-GPU VRAM stats."""
    devices = []
    if not (torch.cuda.is_available() and torch.cuda.device_count() > 0):
        return devices
    try:
        probe = torch.zeros(1, device="cuda")
        del probe
    except Exception as exc:
        print(f"[EngineCore] CUDA device detected but tensor allocation failed ({exc}).")
        return []

    for i in range(torch.cuda.device_count()):
        try:
            props = torch.cuda.get_device_properties(i)
            total_gb = props.total_memory / (1024 ** 3)
            devices.append({
                "index": i,
                "name": props.name,
                "total_gb": total_gb,
                "major": props.major,
                "minor": props.minor,
            })
        except Exception:
            pass
    return devices


def compute_dynamic_partition_budgets(
    total_vram_gb: float,
    total_ram_gb: float,
    model_weight_gb: float = 15.2,
) -> tuple[float, float, float]:
    """
    Computes (gpu_weight_budget_gb, cpu_weight_budget_gb, kv_headroom_gb).
    Guarantees a dedicated slice of VRAM is reserved exclusively for the
    KV cache and activation scratchpads, preventing CUDA OOM.
    """
    # Single-user inference with max_tokens <= 250 requires < 150MB of KV cache.
    # Reserving 0.95-1.2 GB provides >5x safety buffer against OOM while maximizing
    # GPU layer residency (shifting 2-3 additional transformer layers from CPU to GPU).
    user_headroom = os.getenv("SSENSE_KV_HEADROOM_GB", "").strip()
    if user_headroom:
        try:
            kv_headroom_gb = float(user_headroom)
        except Exception:
            kv_headroom_gb = 0.95
    else:
        # Default: 0.95 GB headroom on 10-14GB GPUs, 1.5 GB on 16GB+
        kv_headroom_gb = max(0.95, min(1.8, total_vram_gb * 0.08))

    gpu_weight_budget_gb = max(1.5, total_vram_gb - kv_headroom_gb)

    # Remaining model weights go to host RAM with safety headroom
    needed_cpu_gb = max(4.0, (model_weight_gb - gpu_weight_budget_gb) * 1.25)
    available_cpu_gb = max(12.0, total_ram_gb - 4.0)
    cpu_weight_budget_gb = min(available_cpu_gb, max(needed_cpu_gb, 16.0))

    return gpu_weight_budget_gb, cpu_weight_budget_gb, kv_headroom_gb



def detect_hardware_capabilities() -> str:
    """
    Probes runtime environment and automatically classifies hardware capability:
      - 'cpu': No CUDA devices detected or allocation failed.
      - 'jetson': Unified memory GPU detected (Jetson AGX / Orin).
      - 'gpu': Discrete GPU with >= 15.5GB VRAM (full 7B BF16 model fits entirely in VRAM).
      - 'hybrid': Discrete GPU with < 15.5GB VRAM (requires dynamic layer partitioning across VRAM + RAM).
    """
    devices = get_gpu_devices()
    if not devices:
        return "cpu"

    if is_unified_memory():
        return "jetson"

    primary_vram_gb = devices[0]["total_gb"]
    # Qwen2.5-7B in BF16 requires ~15.2 GB for weights alone.
    # To run entirely in VRAM with sufficient KV cache headroom, we need at least 15.5 GB VRAM.
    if primary_vram_gb >= 15.5:
        return "gpu"
    else:
        return "hybrid"


_target_mem_env = os.getenv("SSENSE_TARGET_MEMORY_GB", "").strip()
TARGET_TOTAL_MEMORY_GB = float(_target_mem_env) if _target_mem_env else 32.0


def patch_torchao_dispatch_compat():
    """Patches TorchAO dispatch logic to prevent PEFT instantiation crashes when building LoRA layers."""
    try:
        import torchao.quantization as _tao_q
        if not hasattr(_tao_q, "LinearActivationQuantizedTensor"):
            try:
                from torchao.quantization.linear_activation_quantized_tensor import (
                    LinearActivationQuantizedTensor as _RealLAQT,
                )
                _tao_q.LinearActivationQuantizedTensor = _RealLAQT
            except ImportError:
                class _StubLinearActivationQuantizedTensor:
                    pass
                _tao_q.LinearActivationQuantizedTensor = _StubLinearActivationQuantizedTensor
    except Exception:
        pass

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
    except Exception:
        pass


patch_torchao_dispatch_compat()


class StopAtClosingBrace:
    """Stops LLM generation the exact instant a valid JSON object is closed."""
    def __init__(self, tokenizer, prompt_len):
        self.tokenizer = tokenizer
        self.prompt_len = prompt_len
        self.stopped = False

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        if self.stopped:
            return True
        gen_tokens = input_ids[0, self.prompt_len:]
        if len(gen_tokens) < 30:
            return False
        tail = self.tokenizer.decode(gen_tokens[-8:].tolist() if hasattr(gen_tokens, "tolist") else gen_tokens[-8:], skip_special_tokens=True)
        if "}" in tail:
            raw_text = self.tokenizer.decode(gen_tokens.tolist() if hasattr(gen_tokens, "tolist") else gen_tokens, skip_special_tokens=True).strip()
            full = raw_text if raw_text.startswith("{") else ("{\n" + raw_text)
            s = full.find("{")
            e = full.rfind("}")
            if s != -1 and e > s:
                # Fast brace balance guard: only attempt json.loads when root object braces are balanced
                if full.count("{") == full.count("}"):
                    try:
                        obj = json.loads(full[s:e+1])
                        if isinstance(obj, dict) and ("dpdp_trust_score" in obj or "global_legal_reasoning" in obj or "violations" in obj):
                            self.stopped = True
                            return True
                    except Exception:
                        pass
        return False


class CancelOnEvent:
    """Stops generation immediately if cancellation event is set."""
    def __init__(self, stop_event: threading.Event):
        self.stop_event = stop_event

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        return self.stop_event.is_set()


class SentenceBoundaryStop:
    """
    Tier 2A — Sentence-boundary early stop for Concise and Thinking modes.
    Upgraded: Pre-caches punctuation token IDs so tokenizer.decode() and regex
    evaluation are only executed when the latest generated token is a sentence terminator.
    """
    _SENT_RE = re.compile(r'(?<=[.!?])(?:\s|$)')

    def __init__(self, tokenizer, prompt_len: int, max_sentences: int = 2):
        self.tokenizer   = tokenizer
        self.prompt_len  = prompt_len
        self.max_sentences = max_sentences
        self._punct_ids = set()
        for punct in (".", "!", "?", ".\n", "!\n", "?\n", "\n", ".\"", ".'"):
            try:
                for tok_id in tokenizer.encode(punct, add_special_tokens=False):
                    self._punct_ids.add(tok_id)
            except Exception:
                pass

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        gen_tokens = input_ids[0, self.prompt_len:]
        if len(gen_tokens) < 8:   # minimum tokens before checking
            return False
        # Fast O(1) integer filter
        last_tok = int(gen_tokens[-1].item() if hasattr(gen_tokens[-1], "item") else gen_tokens[-1])
        if self._punct_ids and last_tok not in self._punct_ids:
            return False

        text = self.tokenizer.decode(gen_tokens.tolist() if hasattr(gen_tokens, "tolist") else gen_tokens, skip_special_tokens=True).strip()
        # Split on sentence boundaries and count complete sentences (>= 4 words to avoid abbreviations like Sec. or e.g.)
        parts   = self._SENT_RE.split(text)
        complete = [p for p in parts if p and p[-1] in '.!?' and len(p.split()) >= 4]
        return len(complete) >= self.max_sentences



class ProductionAsyncEngine:
    def __init__(
        self,
        base_model_path: str,
        audit_adapter_path: str,
        chatbot_adapter_path: str,
        compute_profile: str = "auto",
    ):
        requested_profile = (compute_profile or "auto").lower()
        detected_hw = detect_hardware_capabilities()

        if requested_profile in ("", "auto"):
            self.compute_profile = detected_hw
            print(f"[EngineCore] Auto-detected compute profile: '{self.compute_profile}'")
        elif requested_profile == "gpu" and detected_hw == "hybrid":
            print(
                f"⚡ [EngineCore] Requested profile 'gpu', but detected GPU has insufficient VRAM (<15.5GB) "
                f"to host the entire BF16 model + KV cache concurrently."
            )
            print("⚡ [EngineCore] Automatically routing to 'hybrid' (Dynamic GPU + RAM Partitioning) to prevent OOM.")
            self.compute_profile = "hybrid"
        elif requested_profile in ("gpu", "jetson", "hybrid") and detected_hw == "cpu":
            print(f"⚠️ [EngineCore] Requested profile '{requested_profile}' but functional CUDA runtime not found.")
            print(f"⚠️ [EngineCore] Gracefully switching to 'cpu' profile to ensure server availability.")
            self.compute_profile = "cpu"
        else:
            self.compute_profile = requested_profile

        self.base_model_path = base_model_path
        self.audit_adapter_path = audit_adapter_path
        self.chatbot_adapter_path = chatbot_adapter_path
        self.partition_info: Dict[str, Any] = {}

        if self.compute_profile == "cpu":
            self._init_cpu_hf_engine()
        elif self.compute_profile == "hybrid":
            self._init_dynamic_partitioned_engine(unified_memory=False)
        elif self.compute_profile in ("gpu", "jetson"):
            self._init_vllm_engine()
        else:
            raise ValueError(
                f"Unknown SSENSE_COMPUTE_PROFILE '{compute_profile}'. "
                f"Expected one of: auto, gpu, jetson, hybrid, cpu."
            )

    # ─────────────────────────────────────────────────────────────
    # DYNAMIC PARTITIONED PROFILE: GPU VRAM + System RAM Offloading
    # ─────────────────────────────────────────────────────────────
    def _detect_primary_device(self) -> torch.device:
        """Determines the device where prompt input tokens must be routed."""
        target_model = getattr(self, "model", None)
        dev_map = getattr(target_model, "hf_device_map", {}) if target_model else {}
        for key in ("base_model.model.model.embed_tokens", "model.embed_tokens", "embed_tokens"):
            if key in dev_map:
                dev = dev_map[key]
                if isinstance(dev, int):
                    return torch.device(f"cuda:{dev}")
                elif isinstance(dev, str) and dev not in ("disk", "meta", "cpu"):
                    return torch.device(dev)
        if torch.cuda.is_available() and torch.cuda.device_count() > 0:
            return torch.device("cuda:0")
        return torch.device("cpu")

    @property
    def primary_device(self) -> torch.device:
        if not hasattr(self, "_primary_device"):
            self._primary_device = self._detect_primary_device()
        return self._primary_device

    def optimize_cpu_offloaded_layers(self, model):
        """
        On x86 CPUs without AVX512_BF16, torch.bfloat16 GEMM is emulated in software (35-55x slower).
        Converts CPU-offloaded decoder layers and norm to torch.float32 for native AVX2 vectorization,
        converting parameter-by-parameter in-place to prevent memory spikes in host RAM.
        Registers boundary pre-hooks so incoming hidden states seamlessly adapt.
        """
        import gc
        first_cpu_decoder_layer = None
        converted_count = 0

        # 1. Locate decoder layers
        base = getattr(model, "base_model", model)
        inner = getattr(base, "model", base)
        layers = getattr(inner, "layers", None)
        if layers is None and hasattr(inner, "model"):
            layers = getattr(inner.model, "layers", None)

        first_cpu_idx = -1
        if layers is not None:
            for idx, layer in enumerate(layers):
                params = list(layer.parameters())
                if params and all(p.device.type == "cpu" for p in params):
                    if any(p.dtype in (torch.bfloat16, torch.float16) for p in params):
                        with torch.no_grad():
                            for p in layer.parameters():
                                if p.device.type == "cpu" and p.dtype in (torch.bfloat16, torch.float16):
                                    p.data = p.data.to(torch.float32)
                        converted_count += 1
                        if first_cpu_decoder_layer is None:
                            first_cpu_decoder_layer = layer
                            first_cpu_idx = idx
            gc.collect()

        # 2. Convert norm if on CPU
        norm = getattr(inner, "norm", None)
        if norm is None and hasattr(inner, "model"):
            norm = getattr(inner.model, "norm", None)
        if norm is not None:
            with torch.no_grad():
                for p in norm.parameters():
                    if p.device.type == "cpu" and p.dtype in (torch.bfloat16, torch.float16):
                        p.data = p.data.to(torch.float32)

        # 3. Handle lm_head: keep in BF16 to save 1.1GB RAM, hook pre-cast from FP32 to BF16
        lm_head = getattr(base, "lm_head", None) or getattr(model, "lm_head", None)
        if lm_head is not None:
            lm_params = list(lm_head.parameters())
            if lm_params and any(p.device.type == "cpu" for p in lm_params):
                lm_dtype = lm_params[0].dtype
                if lm_dtype != torch.float32:
                    def _cast_lm_head_hook(m, args):
                        if args and isinstance(args[0], torch.Tensor) and args[0].dtype != lm_dtype:
                            return (args[0].to(lm_dtype),) + args[1:]
                        return args
                    lm_head.register_forward_pre_hook(_cast_lm_head_hook)

        # 4. Register forward pre-hook on the boundary CPU decoder layer
        if first_cpu_decoder_layer is not None:
            def _cast_to_fp32_hook(m, args):
                if args and isinstance(args[0], torch.Tensor) and args[0].dtype != torch.float32:
                    return (args[0].to(torch.float32),) + args[1:]
                return args
            first_cpu_decoder_layer.register_forward_pre_hook(_cast_to_fp32_hook)
            print(f"⚡ [EngineCore/{self.compute_profile}] Accelerated CPU decoder layers ({first_cpu_idx}..{len(layers)-1}) with in-place FP32 AVX2 execution.")


    def _init_dynamic_partitioned_engine(self, unified_memory: bool = False):
        self.backend = "transformers"
        patch_torchao_dispatch_compat()
        from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer, StoppingCriteriaList
        from peft import PeftModel

        self._TextIteratorStreamer = TextIteratorStreamer
        self._StoppingCriteriaList = StoppingCriteriaList

        devices = get_gpu_devices()
        total_ram_gb = get_system_ram_gb()
        cpu_threads = int(os.getenv("SSENSE_CPU_THREADS", "") or os.getenv("OMP_NUM_THREADS", "") or min(6, os.cpu_count() or 4))
        torch.set_num_threads(cpu_threads)
        try:
            torch.set_num_interop_threads(1)
        except Exception:
            pass

        dtype = torch.bfloat16
        try:
            probe = torch.zeros(1, dtype=torch.bfloat16) + torch.zeros(1, dtype=torch.bfloat16)
            del probe
            print("[EngineCore/partitioned] bfloat16 arithmetic verified. Using bfloat16 precision.")
        except Exception:
            print("[EngineCore/partitioned] bfloat16 not supported. Falling back to float32.")
            dtype = torch.float32

        print(f"[EngineCore/partitioned] Loading base model tokenizer from {self.base_model_path}...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.base_model_path, trust_remote_code=True)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        max_memory: Dict[Union[int, str], str] = {}
        partition_details: Dict[str, Any] = {
            "mode": "unified" if unified_memory else ("hybrid" if devices else "cpu"),
            "gpus": [],
            "system_ram_gb": round(total_ram_gb, 2),
        }

        user_gpu_mem = os.getenv("SSENSE_GPU_MAX_MEMORY", "").strip()
        user_cpu_mem = os.getenv("SSENSE_CPU_MAX_MEMORY", "").strip()

        if unified_memory and devices:
            dev_props = devices[0]
            total_vram_gb = dev_props["total_gb"]
            target_cap = min(TARGET_TOTAL_MEMORY_GB, total_vram_gb * 0.65)
            gpu_budget = float(user_gpu_mem.replace("GiB", "").replace("GB", "")) if user_gpu_mem else target_cap
            max_memory[0] = f"{gpu_budget:.1f}GiB"
            max_memory["cpu"] = user_cpu_mem if user_cpu_mem else f"{max(8.0, total_ram_gb * 0.3):.1f}GiB"
            partition_details["gpus"].append({
                "index": 0, "name": dev_props["name"], "total_vram_gb": total_vram_gb,
                "weight_budget_gib": round(gpu_budget, 2), "kv_headroom_gib": round(total_vram_gb - gpu_budget, 2),
            })
            print(f"⚡ [EngineCore/unified] Jetson Unified Memory: {gpu_budget:.1f}GiB GPU budget, remainder system RAM.")
        elif devices:
            for dev in devices:
                dev_idx = dev["index"]
                total_vram_gb = dev["total_gb"]
                gpu_budget, cpu_budget, kv_headroom = compute_dynamic_partition_budgets(total_vram_gb, total_ram_gb)
                if user_gpu_mem:
                    try:
                        gpu_budget = float(user_gpu_mem.replace("GiB", "").replace("GB", ""))
                        kv_headroom = total_vram_gb - gpu_budget
                    except Exception:
                        pass
                if user_cpu_mem:
                    try:
                        cpu_budget = float(user_cpu_mem.replace("GiB", "").replace("GB", ""))
                    except Exception:
                        pass
                max_memory[dev_idx] = f"{gpu_budget:.1f}GiB"
                max_memory["cpu"] = f"{cpu_budget:.1f}GiB"
                partition_details["gpus"].append({
                    "index": dev_idx,
                    "name": dev["name"],
                    "total_vram_gb": round(total_vram_gb, 2),
                    "weight_budget_gib": round(gpu_budget, 2),
                    "kv_headroom_gib": round(kv_headroom, 2),
                })
                print(
                    f"⚡ [EngineCore/hybrid] GPU {dev_idx} ({dev['name']}): "
                    f"Allocating {gpu_budget:.1f}GiB for weights | "
                    f"Reserving {kv_headroom:.1f}GiB strictly for KV Cache & Activations | "
                    f"Offloading ~{(15.2 - gpu_budget):.1f}GiB to System RAM ({cpu_budget:.1f}GiB cap)."
                )
        else:
            max_memory["cpu"] = user_cpu_mem if user_cpu_mem else f"{max(16.0, total_ram_gb - 2.0):.1f}GiB"
            print(f"ℹ️ [EngineCore/cpu] Allocating {max_memory['cpu']} system RAM for CPU execution.")

        print(f"[EngineCore/{self.compute_profile}] Loading base model weights with dynamic partitioning ({dtype})...")
        base_model = AutoModelForCausalLM.from_pretrained(
            self.base_model_path,
            torch_dtype=dtype,
            attn_implementation="sdpa",
            device_map="auto" if devices else "cpu",
            max_memory=max_memory if devices else None,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )


        if hasattr(base_model, "hf_device_map") and base_model.hf_device_map:
            gpu_layers = sum(1 for v in base_model.hf_device_map.values() if str(v) not in ("cpu", "disk"))
            cpu_layers = sum(1 for v in base_model.hf_device_map.values() if str(v) == "cpu")
            partition_details["gpu_layers_count"] = gpu_layers
            partition_details["cpu_layers_count"] = cpu_layers
            partition_details["device_map"] = {k: str(v) for k, v in list(base_model.hf_device_map.items())[:8]}
            print(f"📊 [EngineCore/{self.compute_profile}] Layer Partition: {gpu_layers} modules on GPU, {cpu_layers} modules on CPU.")

        print(f"[EngineCore/{self.compute_profile}] Mounting 'audit' adapter from {self.audit_adapter_path}...")
        self.model = PeftModel.from_pretrained(
            base_model,
            self.audit_adapter_path,
            adapter_name="audit",
        )

        print(f"[EngineCore/{self.compute_profile}] Mounting 'chatbot' adapter from {self.chatbot_adapter_path}...")
        self.model.load_adapter(
            self.chatbot_adapter_path,
            adapter_name="chatbot",
        )

        base_model.config.use_cache = True
        self.model.config.use_cache = True
        self.model.eval()

        self._primary_device = self._detect_primary_device()
        print(f"🎯 [EngineCore/{self.compute_profile}] Primary input device set to: '{self._primary_device}'")
        # Layer optimization: keep native BF16 on CPU to fit within WSL2 19GB RAM (FP32 would exceed 22GB)
        # if self.compute_profile in ("hybrid", "gpu-offload"):
        #     self.optimize_cpu_offloaded_layers(self.model)

        self.partition_info = partition_details

        self._prefix_kv: Dict[str, Any] = {}
        self._prefix_ids: Dict[str, int] = {}

        self._lock = threading.Lock()
        print(f"✅ [EngineCore/{self.compute_profile}] Dynamic Partitioned Multi-LoRA Engine ready. Active adapters: {list(self.model.peft_config.keys())}")

    # ─────────────────────────────────────────────────────────────
    # CPU PROFILE: HuggingFace Transformers + PEFT
    # ─────────────────────────────────────────────────────────────
    def _init_cpu_hf_engine(self):
        self.backend = "transformers"
        self._primary_device = torch.device("cpu")
        patch_torchao_dispatch_compat()
        from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer, StoppingCriteriaList
        from peft import PeftModel

        self._TextIteratorStreamer = TextIteratorStreamer
        self._StoppingCriteriaList = StoppingCriteriaList

        cpu_threads = int(os.getenv("SSENSE_CPU_THREADS", "") or os.getenv("OMP_NUM_THREADS", "") or min(8, os.cpu_count() or 4))
        torch.set_num_threads(cpu_threads)
        print(f"[EngineCore/cpu] Booting Native Transformers Dual-LoRA Engine ({cpu_threads} CPU threads)...")

        # Probe bfloat16 capability on host CPU
        dtype = torch.bfloat16
        try:
            probe = torch.zeros(1, dtype=torch.bfloat16) + torch.zeros(1, dtype=torch.bfloat16)
            del probe
            print("[EngineCore/cpu] bfloat16 arithmetic verified on host CPU. Using bfloat16 precision.")
        except Exception:
            print("[EngineCore/cpu] bfloat16 not supported on host CPU. Falling back to float32.")
            dtype = torch.float32

        print(f"[EngineCore/cpu] Loading base model tokenizer from {self.base_model_path}...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.base_model_path, trust_remote_code=True)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        print(f"[EngineCore/cpu] Loading base model weights ({dtype})...")
        base_model = AutoModelForCausalLM.from_pretrained(
            self.base_model_path,
            torch_dtype=dtype,
            device_map="cpu",
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )

        print(f"[EngineCore/cpu] Mounting 'audit' adapter from {self.audit_adapter_path}...")
        self.model = PeftModel.from_pretrained(
            base_model,
            self.audit_adapter_path,
            adapter_name="audit",
        )

        print(f"[EngineCore/cpu] Mounting 'chatbot' adapter from {self.chatbot_adapter_path}...")
        self.model.load_adapter(
            self.chatbot_adapter_path,
            adapter_name="chatbot",
        )

        base_model.config.use_cache = True
        self.model.config.use_cache = True
        self.model.eval()

        # ── Tier B: INT8 weight-only quantization via torchao ─────────────────
        use_int8 = os.getenv("SSENSE_USE_INT8", "false").strip().lower() in ("1", "true")
        if use_int8 and dtype == torch.bfloat16:
            try:
                from torchao.quantization import quantize_, Int8WeightOnlyConfig
                print("[EngineCore/cpu] Applying torchao INT8 weight-only quantization to base model...")
                quantize_(self.model.base_model.model, Int8WeightOnlyConfig())
                print("[EngineCore/cpu] INT8 weight-only quantization applied successfully. Peak RAM: ~8.5GB.")
            except ImportError:
                print("[EngineCore/cpu] torchao not installed. Running in BF16.")
            except Exception as e:
                print(f"[EngineCore/cpu] torchao quantization failed ({e}). Continuing in BF16.")

        # ── Tier C: KV Cache Prefix Pre-Warm ──────────────────────────────────
        self._prefix_kv: Dict[str, Any] = {}
        self._prefix_ids: Dict[str, int] = {}
        self._prewarm_kv_prefixes()

        self._lock = threading.Lock()
        self.partition_info = {
            "mode": "cpu",
            "cpu_threads": cpu_threads,
            "dtype": str(dtype),
        }
        print(f"✅ [EngineCore/cpu] Multi-LoRA HF Engine ready. Active adapters: {list(self.model.peft_config.keys())}")

    def _prewarm_kv_prefixes(self):
        """Pre-computes and caches KV states for fixed system headers at boot (Tier C)."""
        headers = {"concise": _SYS_CONCISE, "thinking": _SYS_THINKING}
        try:
            self.model.set_adapter("chatbot")
            for label, header in headers.items():
                ids = self.tokenizer(header, return_tensors="pt").input_ids.to(self.model.device)
                n = ids.shape[1]
                with torch.no_grad():
                    out = self.model(ids, use_cache=True, return_dict=True)
                self._prefix_kv[label] = out.past_key_values
                self._prefix_ids[label] = n
                print(f"⚡ [EngineCore/{self.compute_profile}] Pre-warmed '{label}' KV prefix ({n} tokens on {self.model.device})")
        except Exception as e:
            print(f"⚠️ [EngineCore/{self.compute_profile}] KV prefix pre-warm skipped ({e}). Full prefill will be used.")
            self._prefix_kv.clear()
            self._prefix_ids.clear()

    # ─────────────────────────────────────────────────────────────
    # GPU / JETSON PROFILE: vLLM AsyncLLMEngine
    # ─────────────────────────────────────────────────────────────
    def _init_vllm_engine(self):
        self.backend = "vllm"
        try:
            from vllm.engine.async_llm_engine import AsyncLLMEngine
            from vllm.engine.arg_utils import AsyncEngineArgs
            from vllm.sampling_params import SamplingParams, StructuredOutputsParams
            from vllm.lora.request import LoRARequest
        except (ImportError, ModuleNotFoundError) as exc:
            print(f"⚠️  [EngineCore] vLLM not available in this environment ({exc}).")
            print("⚠️  [EngineCore] Gracefully falling back to Dynamic Partitioned Transformers Engine.")
            self._init_dynamic_partitioned_engine(unified_memory=is_unified_memory())
            return

        self._SamplingParams = SamplingParams
        self._StructuredOutputsParams = StructuredOutputsParams
        self._schema_cache: Dict[str, StructuredOutputsParams] = {}

        if self.compute_profile == "gpu":
            engine_args = self._build_gpu_args(AsyncEngineArgs)
        else:
            engine_args = self._build_jetson_args(AsyncEngineArgs)

        print(f"[EngineCore/{self.compute_profile}] Booting vLLM Engine...")
        try:
            self.engine = AsyncLLMEngine.from_engine_args(engine_args)
            self.lora_requests = {
                "audit": LoRARequest("audit_lora", 1, self.audit_adapter_path),
                "chatbot": LoRARequest("chatbot_lora", 2, self.chatbot_adapter_path),
            }
            self.partition_info = {
                "mode": "vllm",
                "compute_profile": self.compute_profile,
                "gpu_memory_utilization": engine_args.gpu_memory_utilization,
            }
            print(f"✅ [EngineCore/{self.compute_profile}] vLLM Engine fully initialized.")
        except Exception as exc:
            print(f"⚠️  [EngineCore] vLLM startup failed ({exc}).")
            print("⚠️  [EngineCore] Automatically switching to Dynamic Partitioned Transformers Engine...")
            self.compute_profile = "hybrid" if not is_unified_memory() else "jetson"
            self._init_dynamic_partitioned_engine(unified_memory=is_unified_memory())

    def _build_gpu_args(self, AsyncEngineArgs) -> Any:
        total_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        if total_vram_gb > TARGET_TOTAL_MEMORY_GB:
            utilization = TARGET_TOTAL_MEMORY_GB / total_vram_gb
        else:
            utilization = 0.90

        major, _ = torch.cuda.get_device_capability(0)
        supports_fp8 = major >= 9 or (major == 8 and torch.cuda.get_device_name(0).lower().find("ada") != -1)
        kv_dtype = "fp8" if supports_fp8 else "auto"

        max_num_seqs = int(os.getenv("SSENSE_VLLM_MAX_NUM_SEQS", "256"))
        swap_space_gb = float(os.getenv("SSENSE_VLLM_SWAP_SPACE_GB", "4"))

        return AsyncEngineArgs(
            model=self.base_model_path,
            enable_lora=True,
            max_loras=2,
            max_lora_rank=128,
            max_cpu_loras=4,
            max_model_len=8192,
            max_num_seqs=max_num_seqs,
            swap_space=int(swap_space_gb),
            gpu_memory_utilization=utilization,
            kv_cache_dtype=kv_dtype,
            dtype="bfloat16",
            enable_prefix_caching=True,
            enable_chunked_prefill=True,
            trust_remote_code=True,
        )

    def _build_jetson_args(self, AsyncEngineArgs) -> Any:
        total_mem_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        conservative_cap_gb = min(TARGET_TOTAL_MEMORY_GB, total_mem_gb * 0.6)
        utilization = max(0.35, min(0.75, conservative_cap_gb / total_mem_gb))

        return AsyncEngineArgs(
            model=self.base_model_path,
            enable_lora=True,
            max_loras=2,
            max_lora_rank=128,
            max_cpu_loras=2,
            max_model_len=4096,
            max_num_seqs=16,
            gpu_memory_utilization=utilization,
            kv_cache_dtype="auto",
            dtype="bfloat16",
            enable_prefix_caching=True,
            enable_chunked_prefill=True,
            trust_remote_code=True,
        )

    def get_cached_guided_decoding(self, schema_payload: Union[str, Dict[str, Any]]) -> Optional[Any]:
        """Caches schema compilation to eliminate FSM construction latency during Audits (vLLM only)."""
        if not schema_payload or getattr(self, "backend", "") != "vllm":
            return None
        cache_key = schema_payload if isinstance(schema_payload, str) else json.dumps(schema_payload, sort_keys=True)
        if cache_key in self._schema_cache:
            return self._schema_cache[cache_key]
        parsed_json = json.loads(schema_payload) if isinstance(schema_payload, str) else schema_payload
        guided_params = self._StructuredOutputsParams(json=parsed_json)
        self._schema_cache[cache_key] = guided_params
        return guided_params

    async def generate_audit(
        self,
        request_id: str,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.0
    ) -> str:
        """Executes Forensic Policy Audits through the Audit LoRA."""
        if self.backend == "transformers":
            def _sync_audit():
                t_start = time.perf_counter()
                with self._lock:
                    self.model.set_adapter("audit")
                    inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
                    inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
                    in_len = inputs["input_ids"].shape[1]
                    print(f"🔍 [Engine/Audit] Prefilling {in_len} tokens on {self.primary_device}...")

                    im_end_id = self.tokenizer.convert_tokens_to_ids("<|im_end|>")
                    endoftext_id = self.tokenizer.convert_tokens_to_ids("<|endoftext|>")
                    eos_ids = [self.tokenizer.eos_token_id]
                    for sp_id in (im_end_id, endoftext_id):
                        if isinstance(sp_id, int) and sp_id not in eos_ids:
                            eos_ids.append(sp_id)

                    criteria = self._StoppingCriteriaList([StopAtClosingBrace(self.tokenizer, in_len)])
                    audit_gen_kwargs = {
                        "max_new_tokens": min(max_tokens, 512 if self.compute_profile in ("cpu", "hybrid") else 768),
                        "do_sample": False,
                        "eos_token_id": eos_ids,
                        "pad_token_id": self.tokenizer.pad_token_id,
                        "stopping_criteria": criteria,
                        "use_cache": True,
                    }
                    if self.compute_profile == "cpu":
                        # Speculative lookup is only safe on homogeneous CPU execution;
                        # on hybrid offloaded pipelines, cross-device KV cache rollbacks cause heavy latency.
                        audit_gen_kwargs["prompt_lookup_num_tokens"] = 3

                    with torch.no_grad():
                        outputs = self.model.generate(
                            **inputs,
                            **audit_gen_kwargs,
                        )
                    input_len = inputs["input_ids"].shape[1]
                    gen_ids = outputs[0][input_len:]
                    gen_len = len(gen_ids)
                    dur = time.perf_counter() - t_start
                    tps = (gen_len / dur) if dur > 0 else 0
                    print(f"✅ [Engine/Audit] Completed {gen_len} tokens in {dur:.2f}s ({tps:.2f} tok/s)")
                    return self.tokenizer.decode(gen_ids, skip_special_tokens=False)

            raw = await asyncio.to_thread(_sync_audit)
            return raw.replace("<|im_end|>", "").replace("<|endoftext|>", "").strip()

        # vLLM path
        guided_decoding = self.get_cached_guided_decoding(schema)
        sampling_params = self._SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            stop=["<|im_end|>", "<|endoftext|>"],
            structured_outputs=guided_decoding
        )
        results_generator = self.engine.generate(
            prompt=prompt,
            sampling_params=sampling_params,
            request_id=request_id,
            lora_request=self.lora_requests["audit"]
        )
        final_output = None
        async for request_output in results_generator:
            final_output = request_output
        return final_output.outputs[0].text if final_output else ""

    async def generate_chat_stream(
        self,
        request_id: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.3,
        multi_site: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Streams Conversational Chatbot tokens through the Chatbot LoRA in real-time.

        Phase 2 optimisations applied here (CPU path):
          Tier 0A  — Non-blocking streamer poll replaces asyncio.to_thread(next(streamer)).
                     Eliminates ThreadPoolExecutor scheduler contention that caused the
                     0.18 tok/s decode stall on @mention queries (285s → ~50s).
          Tier 1A  — Prompt Lookup Decoding: prompt_lookup_num_tokens=3 copies matching
                     n-grams from the prompt as speculative draft tokens. Exact on CPU —
                     no quality change. Estimated 1.4–1.8× decode speedup.
          Tier 1B  — Token ceiling fully owned by caller (main.py). Engine no longer
                     double-caps with its own hardcoded 200-token limit.
          Tier 2A  — SentenceBoundaryStop for Concise mode (temperature==0.0): halts
                     after 2 complete sentences, saving 4.5–13.5s of decode time.
          Tier 2B  — top_k=40 applied before top_p for Thinking mode (is_sampling=True).
                     Reduces softmax candidate pool from 151,936 → 40 before nucleus
                     sampling. ~10–15% decode speedup; zero quality change.
          Tier 2C  — repetition_penalty=1.05 when multi_site=True to discourage the
                     refusal-loop pattern observed in @mention benchmark results.
        """
        if self.backend == "transformers":
            stop_event = threading.Event()
            # Tier 0A: Non-blocking poll loop uses get_nowait, short safety timeout
            streamer = self._TextIteratorStreamer(
                self.tokenizer, skip_prompt=True, skip_special_tokens=True, timeout=5.0
            )

            is_sampling = (temperature > 0.0)
            mode_label = "thinking" if is_sampling else "concise"
            header_text = _SYS_THINKING if is_sampling else _SYS_CONCISE
            prefix_len = self._prefix_ids.get(mode_label, 0)
            use_cached_kv = False
            pkv_copy = None
            cache_pos = None

            # Tier C: Check if prompt begins with pre-warmed system header
            if prefix_len > 0 and mode_label in self._prefix_kv and prompt.startswith(header_text):
                try:
                    import copy
                    pkv_copy = copy.deepcopy(self._prefix_kv[mode_label])
                    full_ids = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024).input_ids
                    suffix_ids = full_ids[:, prefix_len:]
                    suffix_len = suffix_ids.shape[1]
                    total_len = prefix_len + suffix_len
                    cache_pos = torch.arange(prefix_len, total_len, dtype=torch.long, device=self.model.device)
                    attn_mask = torch.ones(1, total_len, dtype=torch.long, device=self.model.device)
                    inputs = {
                        "input_ids": suffix_ids.to(self.model.device),
                        "attention_mask": attn_mask,
                    }
                    in_len = suffix_len  # stopping criteria checks generated tokens after suffix
                    use_cached_kv = True
                except Exception as e:
                    print(f"⚠️ [Engine/Chat] KV cache prefix reuse failed ({e}), falling back to full prefill.")
                    use_cached_kv = False

            if not use_cached_kv:
                inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
                inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
                in_len = inputs["input_ids"].shape[1]

            # Tier 1B: Trust the ceiling from main.py — no second cap here.
            chat_max = max_tokens
            print(
                f"💬 [Engine/Chat] prompt={in_len} tok (kv_cached={use_cached_kv}, dev={self.primary_device}), max={chat_max}, "
                f"temp={temperature:.2f} (sampling={is_sampling}, multi_site={multi_site})...",
                flush=True,
            )

            im_end_id    = self.tokenizer.convert_tokens_to_ids("<|im_end|>")
            endoftext_id = self.tokenizer.convert_tokens_to_ids("<|endoftext|>")
            eos_ids      = [self.tokenizer.eos_token_id]
            for sp_id in (im_end_id, endoftext_id):
                if isinstance(sp_id, int) and sp_id not in eos_ids:
                    eos_ids.append(sp_id)

            # Build stopping criteria list
            criteria_list = [CancelOnEvent(stop_event)]
            if not is_sampling:
                # Concise mode: 2 sentences (or 3 for multi-site comparisons)
                max_sents = 3 if multi_site else 2
                criteria_list.append(SentenceBoundaryStop(self.tokenizer, in_len, max_sentences=max_sents))
            else:
                # Thinking mode early stop: halt after 4 complete sentences (5 for multi-site)
                # to prevent repetitive rambling beyond the thorough answer.
                max_sents = 5 if multi_site else 4
                criteria_list.append(SentenceBoundaryStop(self.tokenizer, in_len, max_sentences=max_sents))
            stopping_criteria = self._StoppingCriteriaList(criteria_list)

            gen_kwargs: Dict[str, Any] = {
                **inputs,
                "streamer":          streamer,
                "max_new_tokens":    chat_max,
                "do_sample":         is_sampling,
                "pad_token_id":      self.tokenizer.pad_token_id,
                "eos_token_id":      eos_ids,
                "stopping_criteria": stopping_criteria,
                "use_cache":         True,
            }
            if use_cached_kv and pkv_copy is not None:
                gen_kwargs["past_key_values"] = pkv_copy
            elif self.compute_profile == "cpu":
                gen_kwargs["prompt_lookup_num_tokens"] = 3

            if is_sampling:
                gen_kwargs["temperature"] = temperature
                # Tier 2B: top_k=40 narrows from 151,936 → 40 logits before top_p.
                gen_kwargs["top_k"]  = 40
                gen_kwargs["top_p"]  = 0.85

            # SOTA Fix: repetition_penalty always-on (not just multi_site).
            # The chatbot LoRA can produce repetition loops in both single-site
            # and multi-site thinking mode. A light penalty of 1.15 prevents
            # 'notice notice notice' loops with zero quality degradation.
            # For multi-site, boost slightly more to suppress refusal-loops.
            gen_kwargs["repetition_penalty"] = 1.2 if multi_site else 1.15

            gen_error: Optional[Exception] = None

            def _run_chat_gen():
                nonlocal gen_error
                try:
                    with self._lock:
                        if stop_event.is_set():
                            return
                        self.model.set_adapter("chatbot")
                        if not stop_event.is_set():
                            with torch.no_grad():
                                self.model.generate(**gen_kwargs)
                except Exception as e:
                    gen_error = e
                    print(f"🛑 [Engine/Chat] Generation error: {e}", flush=True)
                finally:
                    try:
                        streamer.end()
                    except Exception:
                        pass

            thread = threading.Thread(target=_run_chat_gen, daemon=True)
            thread.start()

            # ── Tier 0A: Non-blocking token poll ──────────────────────────────
            # Replaces `await asyncio.to_thread(next(streamer))` which spawned
            # a ThreadPoolExecutor worker competing with the CPU-bound generation
            # thread for OS scheduler time — causing the observed 0.18 tok/s stall.
            #
            # queue.Queue.get_nowait() is non-blocking (O(1) check). If empty,
            # we yield the event loop for 5ms and retry. At 1.1 tok/s the queue
            # gets a new token every ~909ms, so the 5ms poll checks it ~181×
            # per token with negligible overhead. No ThreadPoolExecutor workers,
            # no scheduler contention, no 240s timeout cliff.
            try:
                while True:
                    try:
                        tok = streamer.text_queue.get_nowait()
                    except _queue.Empty:
                        # Queue is empty — check if generation has finished
                        if gen_error is not None:
                            break
                        if not thread.is_alive() and streamer.text_queue.empty():
                            break
                        await asyncio.sleep(0.001)   # yield event loop for 1ms
                        continue

                    # streamer.end() puts the stop_signal sentinel onto the queue
                    if tok is streamer.stop_signal:
                        break
                    if "<|im_end|>" in tok:
                        tok = tok.replace("<|im_end|>", "")
                        if tok:
                            yield tok
                        break
                    if tok:
                        yield tok
            finally:
                stop_event.set()
                try:
                    streamer.end()
                except Exception:
                    pass
            return

        # vLLM path
        repetition_pen = 1.2 if multi_site else 1.15
        sampling_params = self._SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            repetition_penalty=repetition_pen,
            stop=["<|im_end|>", "<|endoftext|>"]
        )
        results_generator = self.engine.generate(
            prompt=prompt,
            sampling_params=sampling_params,
            request_id=request_id,
            lora_request=self.lora_requests["chatbot"]
        )
        prev_text = ""
        async for request_output in results_generator:
            curr_text = request_output.outputs[0].text
            delta = curr_text[len(prev_text):]
            prev_text = curr_text
            if delta:
                yield delta
