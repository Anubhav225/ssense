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
    "Think step by step through the DPDP Act 2023 provisions. "
    "A thorough, well-reasoned statutory analysis is expected."
    "<|im_end|>\n"
)


def detect_hardware_capabilities() -> str:
    """
    Probes runtime environment for functional CUDA / GPU acceleration.
    Returns 'gpu', 'jetson', or 'cpu'.
    """
    if torch.cuda.is_available() and torch.cuda.device_count() > 0:
        try:
            probe = torch.zeros(1, device="cuda")
            del probe
            if Path("/etc/nv_tegra_release").exists() or Path("/sys/devices/soc0/family").exists():
                return "jetson"
            return "gpu"
        except Exception as exc:
            print(f"[EngineCore] CUDA device detected but tensor allocation failed ({exc}). Falling back to CPU.")
            return "cpu"
    return "cpu"


_target_mem_env = os.getenv("SSENSE_TARGET_MEMORY_GB", "").strip()
TARGET_TOTAL_MEMORY_GB = float(_target_mem_env) if _target_mem_env else 32.0


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
        tail = self.tokenizer.decode(gen_tokens[-8:], skip_special_tokens=True)
        if "}" in tail:
            raw_text = self.tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()
            full = raw_text if raw_text.startswith("{") else ("{\n" + raw_text)
            s = full.find("{")
            e = full.rfind("}")
            if s != -1 and e > s:
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
    Tier 2A — Sentence-boundary early stop for Concise mode.

    Halts generation after `max_sentences` complete sentences have been
    decoded. A sentence is considered complete when the decoded text contains
    at least `max_sentences` segments ending in '.', '!' or '?' followed by
    whitespace or end-of-string.

    Applied only when temperature == 0.0 (Concise mode greedy decoding).
    Average saving: 5-15 tokens × ~0.9s/token = 4.5-13.5s off decode time.
    """
    _SENT_RE = re.compile(r'(?<=[.!?])(?:\s|$)')

    def __init__(self, tokenizer, prompt_len: int, max_sentences: int = 2):
        self.tokenizer   = tokenizer
        self.prompt_len  = prompt_len
        self.max_sentences = max_sentences

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        gen_tokens = input_ids[0, self.prompt_len:]
        if len(gen_tokens) < 8:   # minimum tokens before checking
            return False
        text = self.tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()
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
        elif requested_profile in ("gpu", "jetson") and detected_hw == "cpu":
            print(f"⚠️ [EngineCore] Requested profile '{requested_profile}' but functional CUDA runtime not found.")
            print(f"⚠️ [EngineCore] Gracefully switching to 'cpu' profile to ensure server availability.")
            self.compute_profile = "cpu"
        else:
            self.compute_profile = requested_profile

        self.base_model_path = base_model_path
        self.audit_adapter_path = audit_adapter_path
        self.chatbot_adapter_path = chatbot_adapter_path

        if self.compute_profile == "cpu":
            self._init_cpu_hf_engine()
        elif self.compute_profile in ("gpu", "jetson"):
            self._init_vllm_engine()
        else:
            raise ValueError(
                f"Unknown SSENSE_COMPUTE_PROFILE '{compute_profile}'. "
                f"Expected one of: auto, gpu, jetson, cpu."
            )

    # ─────────────────────────────────────────────────────────────
    # CPU PROFILE: HuggingFace Transformers + PEFT
    # ─────────────────────────────────────────────────────────────
    def _init_cpu_hf_engine(self):
        self.backend = "transformers"
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
        # On x86 CPUs without AVX-512 VNNI, torchao dequantization overhead is ~28ms/layer
        # vs 5.8ms in native BF16 (oneDNN AMX/AVX2). Default to false for peak decode tok/s.
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
        print(f"✅ [EngineCore/cpu] Multi-LoRA HF Engine ready. Active adapters: {list(self.model.peft_config.keys())}")

    def _prewarm_kv_prefixes(self):
        """Pre-computes and caches KV states for fixed system headers at boot (Tier C)."""
        headers = {"concise": _SYS_CONCISE, "thinking": _SYS_THINKING}
        try:
            self.model.set_adapter("chatbot")
            for label, header in headers.items():
                ids = self.tokenizer(header, return_tensors="pt").input_ids
                n = ids.shape[1]
                with torch.no_grad():
                    out = self.model(ids, use_cache=True, return_dict=True)
                self._prefix_kv[label] = out.past_key_values
                self._prefix_ids[label] = n
                print(f"⚡ [EngineCore/cpu] Pre-warmed '{label}' KV prefix ({n} tokens)")
        except Exception as e:
            print(f"⚠️ [EngineCore/cpu] KV prefix pre-warm skipped ({e}). Full prefill will be used.")
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
            print("⚠️  [EngineCore] Gracefully falling back to Native Transformers Dual-LoRA Engine.")
            self.compute_profile = "cpu"
            self._init_cpu_hf_engine()
            return

        self._SamplingParams = SamplingParams
        self._StructuredOutputsParams = StructuredOutputsParams
        self._schema_cache: Dict[str, StructuredOutputsParams] = {}

        if self.compute_profile == "gpu":
            engine_args = self._build_gpu_args(AsyncEngineArgs)
        else:
            engine_args = self._build_jetson_args(AsyncEngineArgs)

        print(f"[EngineCore/{self.compute_profile}] Booting vLLM Engine...")
        self.engine = AsyncLLMEngine.from_engine_args(engine_args)

        self.lora_requests = {
            "audit": LoRARequest("audit_lora", 1, self.audit_adapter_path),
            "chatbot": LoRARequest("chatbot_lora", 2, self.chatbot_adapter_path),
        }
        print(f"✅ [EngineCore/{self.compute_profile}] vLLM Engine fully initialized.")

    def _build_gpu_args(self, AsyncEngineArgs) -> Any:
        total_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        if total_vram_gb > TARGET_TOTAL_MEMORY_GB:
            utilization = TARGET_TOTAL_MEMORY_GB / total_vram_gb
        else:
            utilization = 0.90

        major, _ = torch.cuda.get_device_capability(0)
        supports_fp8 = major >= 9 or (major == 8 and torch.cuda.get_device_name(0).lower().find("ada") != -1)
        kv_dtype = "fp8" if supports_fp8 else "auto"

        # ── Concurrency ceiling: env-tunable without a code change/rebuild ──
        # 256 is a reasonable default for a 7B model on a 32-40GB budget (see
        # docs/SLM_Server_Architecture.md's memory math), but the real ceiling
        # depends on average prompt/generation length and should be tuned per
        # deployment. This MUST stay <= SSENSE_MAX_CONCURRENT_INFERENCE in
        # docker-compose.yml (memory_orchestrator.InferenceQueue) — that
        # queue's job is to admit at most this many requests to the engine at
        # once, so the two numbers are two views of the same ceiling and
        # should be changed together.
        max_num_seqs = int(os.getenv("SSENSE_VLLM_MAX_NUM_SEQS", "256"))

        # ── CPU-RAM KV-cache overflow (paged "swap" space) ──────────────
        # vLLM's PagedAttention KV cache lives in a fixed-size GPU block pool
        # sized by gpu_memory_utilization. Under a genuine burst (many
        # sequences, long contexts) that pool can fill before max_num_seqs is
        # reached; without swap_space vLLM's only recourse is to *preempt*
        # (recompute from scratch) a lower-priority sequence — a latency
        # cliff for whoever gets preempted. swap_space lets it page cold
        # blocks out to host RAM instead and resume them cheaply. Default of
        # 4 GiB matches vLLM's own upstream default; raise it on a host with
        # RAM to spare (e.g. the 32-40GB VRAM + host RAM split this server is
        # designed for) to absorb bigger bursts before any preemption happens.
        swap_space_gb = float(os.getenv("SSENSE_VLLM_SWAP_SPACE_GB", "4"))

        return AsyncEngineArgs(
            model=self.base_model_path,
            enable_lora=True,
            max_loras=2,
            max_lora_rank=128,
            max_cpu_loras=4,
            max_model_len=8192,
            max_num_seqs=max_num_seqs,
            gpu_memory_utilization=utilization,
            kv_cache_dtype=kv_dtype,
            swap_space=swap_space_gb,
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
                inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048).to("cpu")
                in_len = inputs["input_ids"].shape[1]
                print(f"🔍 [Engine/Audit] Prefilling {in_len} tokens on CPU...")

                im_end_id = self.tokenizer.convert_tokens_to_ids("<|im_end|>")
                endoftext_id = self.tokenizer.convert_tokens_to_ids("<|endoftext|>")
                eos_ids = [self.tokenizer.eos_token_id]
                for sp_id in (im_end_id, endoftext_id):
                    if isinstance(sp_id, int) and sp_id not in eos_ids:
                        eos_ids.append(sp_id)

                criteria = self._StoppingCriteriaList([StopAtClosingBrace(self.tokenizer, in_len)])
                with torch.no_grad():
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=min(max_tokens, 256 if self.compute_profile == "cpu" else 768),
                        do_sample=False,
                        eos_token_id=eos_ids,
                        pad_token_id=self.tokenizer.pad_token_id,
                        stopping_criteria=criteria,
                        use_cache=True,
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
                    cache_pos = torch.arange(prefix_len, total_len, dtype=torch.long)
                    attn_mask = torch.ones(1, total_len, dtype=torch.long)
                    inputs = {
                        "input_ids": suffix_ids,
                        "attention_mask": attn_mask,
                    }
                    in_len = suffix_len  # stopping criteria checks generated tokens after suffix
                    use_cached_kv = True
                except Exception as e:
                    print(f"⚠️ [Engine/Chat] KV cache prefix reuse failed ({e}), falling back to full prefill.")
                    use_cached_kv = False

            if not use_cached_kv:
                inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024).to("cpu")
                in_len = inputs["input_ids"].shape[1]

            # Tier 1B: Trust the ceiling from main.py — no second cap here.
            chat_max = max_tokens
            print(
                f"💬 [Engine/Chat] prompt={in_len} tok (kv_cached={use_cached_kv}), max={chat_max}, "
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
            # Tier 2A: sentence-boundary stop for Concise (greedy) mode
            if not is_sampling:
                criteria_list.append(SentenceBoundaryStop(self.tokenizer, in_len, max_sentences=2))
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
                gen_kwargs["cache_position"] = cache_pos
            else:
                # Tier 1A: Prompt Lookup Decoding only when not using KV prefix (avoids rotary index mismatch)
                gen_kwargs["prompt_lookup_num_tokens"] = 3

            if is_sampling:
                gen_kwargs["temperature"] = temperature
                # Tier 2B: top_k=40 narrows from 151,936 → 40 logits before top_p.
                gen_kwargs["top_k"]  = 40
                gen_kwargs["top_p"]  = 0.85
            # Tier 2C: light repetition penalty for multi-site queries to suppress refusal loops.
            if multi_site:
                gen_kwargs["repetition_penalty"] = 1.05

            gen_error: Optional[Exception] = None

            def _run_chat_gen():
                nonlocal gen_error
                try:
                    # Tier A: Lock held ONLY for adapter switch (8.7ms), not for the entire 30-90s generation
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
                        await asyncio.sleep(0.005)   # yield event loop for 5ms
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
        sampling_params = self._SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
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
