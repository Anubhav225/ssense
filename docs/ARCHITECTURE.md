# Ssense — Architecture & Design History

> **Version history in this document:** v1 (dual-mode daemon) → v2 (server-only) → v2.3 (zero-config, server-side extraction)

---

## Current Architecture (v2.3 — Secure Zero-Config)

### System Overview

```mermaid
graph TB
    subgraph Browser["Chrome Extension (Manifest V3)"]
        direction TB
        SPOOF["api-spoof.ts — MAIN world<br/>Spoofs Canvas / WebGL / AudioContext<br/>at document_start"]
        EXT["extractor.ts — ISOLATED world<br/>Scans DOM for policy URL only<br/>Sends {domain, policyUrl} — no text"]
        DPB["dark-pattern-blocker.ts<br/>MutationObserver → el.remove()"]
        WIDGET["chat-widget.ts<br/>Floating overlay on page"]
        SW["service-worker.ts<br/>FOUND_POLICY_URL → api-client<br/>audit-cache.ts (chrome.storage.local)"]
        UI_SIDE["Side Panel<br/>ChatInterface / HistoryView / AuditReportView"]
        UI_POP["Popup<br/>Status · Open Panel · Settings"]
    end

    subgraph Server["SLM Server (FastAPI + vLLM)"]
        direction TB
        FETCH["policy_fetcher.py<br/>httpx fetch → lxml parse → language filter<br/>returns text + SHA-256 hash; text discarded after inference"]
        CACHE["audit_store.py<br/>SQLite WAL, 90-day TTL, shared cross-user<br/>chat_context pre-computed and stored"]
        ORCH["memory_orchestrator.py<br/>Hot LRU (512 entries, 5-min) over SQLite<br/>Chat-only rate limit (60/min per api_key+IP)<br/>Request coalescing for identical chat prompts"]
        RAG["rag_engine.py<br/>Hybrid BM25 + BGE-Small dense<br/>RRF fusion → cross-encoder reranking<br/>state-query intent detection"]
        LLM["engine.py<br/>vLLM multi-LoRA<br/>audit_lora (r=128) + chatbot_lora (r=64)"]
        SEC["security.py<br/>HMAC-SHA256 (30s window + nonce replay)<br/>Shannon entropy filter<br/>Anti-extraction guard"]
        NGINX["Nginx TLS proxy<br/>:443 → :8000, SSE buffering off"]
    end

    EXT -->|FOUND_POLICY_URL| SW
    SW -->|POST /v1/audit/by-url<br/>HMAC-signed HTTPS| NGINX
    NGINX --> SEC --> ORCH
    ORCH --> FETCH --> CACHE
    CACHE -->|cache miss only| LLM
    LLM --> RAG
    ORCH -->|GET /v1/audit/{domain}<br/>POST /v1/chat/stream| LLM
```

### What the Extension Sends to the Server

In v2.3 the extension sends **only a URL**, never policy text:

```
POST /v1/audit/by-url
{
  "domain":       "www.flipkart.com",
  "policyUrl":    "https://www.flipkart.com/pages/privacypolicy",
  "force_refresh": false
}
```

The server fetches that URL, extracts the text, audits it, caches the structured result, and returns:

```json
{
  "source": "inference",
  "data": {
    "dpdp_trust_score": 61,
    "subtlety_score": 74,
    "violations": [...],
    "global_legal_reasoning": "..."
  },
  "policy_url": "https://www.flipkart.com/pages/privacypolicy",
  "cached_at": null,
  "age_days": null
}
```

The policy text itself is used only during inference, then `del`-ed. It never reaches a database, the extension, or any log.

### Three-Tier Audit Cache

```
Request arrives for domain example.com
    │
    ▼
Tier 1: Hot in-memory LRU (512 entries, 5-min TTL)
    │   Hit → return (sub-millisecond)
    │   Miss ↓
    ▼
Tier 2: SQLite audit_store (all domains, 90-day TTL)
    │   Hit → warm hot layer → return (~1ms)
    │   Miss ↓
    ▼
Tier 3: Policy-hash shortcut
    │   Server fetches URL → computes SHA-256 of extracted text
    │   If hash matches stored hash → return cached result (policy unchanged)
    │   Miss ↓
    ▼
vLLM Inference (runs only on genuine miss or force_refresh=true)
    │   → validate_and_repair_report()
    │   → translate_audit_for_prompt() → stored as chat_context in SQLite
    └── → save to SQLite + warm all hot layers
```

### Local Extension Store

```typescript
// chrome.storage.local, key: "audit:<domain>"
interface LocalAuditEntry {
  domain:          string;
  trust_score:     number;   // for immediate badge display
  subtlety_score:  number;
  violation_count: number;
  violations:      Violation[];
  global_legal_reasoning: string;
  policy_url:      string;
  audited_at:      number;
  age_days:        number;
  source:          string;
}
```

On every tab switch, `ChatInterface` reads the local entry first (instant, no server round-trip) and shows the score badge immediately. Violations and reasoning are already in the local entry, so the full panel also renders instantly for previously-audited sites.

---

## Design History

### v1 (2026-Q1) — Dual-Mode: Rust Native Daemon + Cloud Fallback

The original architecture was built around an **offline-first** philosophy: a bare-metal Rust binary (`ssense-native-daemon`) ran locally on the user's machine via Chrome's Native Messaging API, executing a quantised 9B GGUF model through `llama-cpp-rs`. The cloud server (`apps/slm-server`) was a fallback, reached only when the daemon was unavailable.

**Key components (now removed):**
- `apps/native-daemon/` — Rust binary with `llama-cpp-rs`, `rag_engine.rs`, `sqlite_store.rs`, and `framing.rs` (4-byte little-endian IPC framing matching Chromium's internal C++)
- `apps/extension/src/background/native-messaging.ts` — Chrome `runtime.connectNative()` bridge
- `apps/extension/src/background/privacy-store.ts` — IndexedDB store for full policy text (~25 KB per site)
- Engine-mode selector UI in popup (Cloud · Fast / Private · Offline toggle)
- Model download progress UI (progress bar, pause/resume, `.part` file resumption)
- `DOWNLOAD_OFFLINE`, `PAUSE_DOWNLOAD`, `SET_OFFLINE_MODE` service-worker handlers

**Why we had it:** Zero cloud dependency, full privacy — the policy text never left the device. The Rust daemon achieved <100 ms latency on GPU, and chunked 512-token prefill prevented GGML assertion aborts on long policies.

**Why we removed it:** The native daemon required a separately distributed signed installer (not shippable through the Chrome Web Store itself), OS-level registry entries on Windows, and a 9 GB first-run download before the extension could do anything. For a general public extension, this made the install experience unacceptable. The Rust daemon's `rag_engine.rs` had a bug where `is_state_query` was hardcoded `false` at its only call site, permanently excluding state-specific DPDP provisions from all RAG searches.

### v2 (2026-Q2) — Server-Only, Browser-Side Extraction

The native daemon was removed. The extension became cloud-only. However, the extraction pipeline still ran entirely in the browser:

**Extension extraction flow (v2):**
1. `extractor.ts` scanned the DOM for a policy link
2. `service-worker.ts` fetched the policy HTML via a `PROXY_FETCH` handler (SSRF-guarded)
3. `parsePolicyDocument()` stripped noise elements and extracted text
4. `stripNonEnglishLines()` filtered non-Latin-script lines
5. ~20 KB of policy text was sent over `chrome.runtime.sendMessage` to the service worker
6. The service worker saved the text to IndexedDB (`privacy-store.ts`) and forwarded it to the server

**Problems with this approach:**
- The extension sent ~20 KB of policy text over `chrome.runtime` on every page load
- The full policy text was stored in IndexedDB in the extension (sensitive data, unnecessary)
- The `PROXY_FETCH` handler was complex (SSRF guard, size cap, timeout, encoding detection)
- Browser `fetch()` in a service worker is subject to CSP of the surrounding page context and lacks HTTP/2 and proper header negotiation

### v2.3 (2026-Q3) — Zero-Config, Server-Side Extraction (Current)

**What changed:**
- `policy_fetcher.py` — all extraction logic moved to the server. The server fetches the policy URL directly using `httpx` (async, HTTP/2, browser-like headers, redirect following, 8 MB cap), parses HTML with BeautifulSoup4+lxml, applies the same content-selection and language-filter logic that was in `extractor-core.ts`, and discards the text after inference
- `extractor.ts` shrunk from ~120 lines to 37: it now finds the policy URL in the page DOM and sends `{domain, policyUrl}` — nothing else
- `extractor-core.ts` shrunk from ~250 lines to 94: only URL-discovery functions remain; `parsePolicyDocument`, `pickContentElement`, `stripNonEnglishLines`, `findLargestProseBlock` were all removed
- `privacy-store.ts` deleted; replaced by `audit-cache.ts` (a thin wrapper around `chrome.storage.local` that stores the JSON audit result, ~3 KB per site, no policy text)
- `PROXY_FETCH`, `PRIVACY_SNAPSHOT` service-worker handlers removed
- `audit_store.py` upgraded: `policyText` removed from schema; `chat_context` column added (pre-computed natural-language audit summary stored once, read on every chat request — avoids JSON parsing on the hot chat path)
- Credentials baked into the build (`VITE_SSENSE_*` env vars) — ordinary users never touch the Options page
- `rag_engine.py`: fixed `is_state_query` bug from the daemon (now a proper keyword regex that auto-detects jurisdiction-specific queries)
- Chat rate limiting separated from audit: audits are unlimited (shared server cache means inference rarely runs), chat is 60 req/min per `api_key+IP`

---

## ML Stack

### Training Pipeline

```
DPDP Act 2023 PDF + Global Policy Corpus
          │
          ▼
    GAN Synthesizer (72B Teacher via vLLM)
          │
          ├── Track 1: SFT pairs for forensic audit (structured JSON output)
          └── Track 2: SimPO pairs for conversational co-pilot
          │
          ▼
    Unsloth Fine-tuning on Qwen2.5-7B-Instruct
          │
          ├── audit_lora   — rsLoRA r=128, adamw_torch 32-bit
          └── chatbot_lora — rsLoRA r=64, SimPO beta=1.0
          │
          ▼
    vLLM Multi-LoRA serving (audit + chat on one GPU)
```

### Key ML Decisions & Research Grounding

For the exhaustive line-by-line parameter audit, mathematical formulations, and literature survey, see:
- [ML Architecture Research Grounding](file:///d:/Ssense/docs/ML_ARCHITECTURE_RESEARCH_GROUNDING.md) — Master architectural description covering Teacher-Student distillation, in-process hybrid retrieval, deterministic SCL, and evaluation suites.
- [Data Forge Research Grounding](file:///d:/Ssense/docs/DATA_FORGE_RESEARCH_GROUNDING.md) — In-depth analysis of 72B $\to$ 7B distillation, model collapse mitigation, and multi-turn Reflexion loops.
- [Training Research Grounding](file:///d:/Ssense/docs/TRAINING_RESEARCH_GROUNDING.md) — Comprehensive parameter audit, rsLoRA derivations, SimPO vs DPO mechanics, and token length firewalls.
- [Academic Citations Index](file:///d:/Ssense/docs/citations.md) — Complete publication-grade BibTeX and APA citations for all foundation, PEFT, alignment, retrieval, and legal domain papers.

| Decision | Empirical & Theoretical Grounding | Citation |
|----------|-----------------------------------|----------|
| **Qwen2.5-7B-Instruct** | Grouped-Query Attention (4 KV heads), RoPE base $\theta=10^6$ for 128k context, and high structural JSON token compression | Qwen Team (2024); Ainslie et al. (EMNLP 2023) |
| **rsLoRA r=128 for audit** | Scaling update by $\alpha/\sqrt{r}$ ($11.31\times$ stronger gradient) overcomes standard LoRA $\mathcal{O}(1/\sqrt{r})$ gradient collapse at high rank | Kalajdzievski (arXiv:2312.03732); Hu et al. (ICLR 2022) |
| **rsLoRA r=64 for chat** | Balanced expressiveness for conversational empathy without catastrophic forgetting of general dialogue priors | Kalajdzievski (2023); Ta et al. (IEEE 2025) |
| **Target All 7 Linear Modules** | Adapting `q, k, v, o, gate, up, down_proj` matches full fine-tuning performance across multi-step statutory deduction | Dettmers et al. (NeurIPS 2023); Wu & Ma (ACM 2025) |
| **SimPO Alignment (β=2.0, γ=0.5)** | Reference-free sequence average log-probability cuts 50% VRAM; eliminates DPO verbosity/length exploitation | Meng et al. (NeurIPS 2024); Park et al. (ACL 2024) |
| **NEFTune Regularization (α=5.0)** | Injects uniform noise into token embeddings, preventing memorization of synthetic prompt templates | Jain et al. (ICLR 2024) |
| **Response-Only Loss Masking** | Cross-entropy loss computed strictly over assistant JSON completion; user prompts masked with `-100` | ChatML Specification |
| **Token Length Firewall** | Pre-training token length filtering prevents silent truncation of closing JSON brackets by TRL batching | TRL Batching Analysis |
| **adamw_torch_fused 32-bit** | Decoupled weight decay with fused GPU kernels; exact variance tracking prevents statutory drift | Loshchilov & Hutter (ICLR 2019) |
| **Process Isolation (spawn)** | OS kills SFT child process, forcing the CUDA driver to release 100% VRAM before SimPO initializes | PyTorch Memory Profiling |
| **XGrammar Schema Enforcement** | FSM-constrained decoding guarantees `dpdp_schema.json` structural compliance at token generation | Willard & Louf (2023); XGrammar |
| **MinHash LSH Contamination Gate** | 128-permutation LCG MinHash with 7-gram shingles confirms zero train-test leakage ($J \le 0.85$) | Broder (1997); Lee et al. (ACL 2022) |
| **Statutory Compliance Layer (SCL)** | Lossless union post-processor ($V_{\text{final}} = V_{\text{SLM}} \cup V_{\text{SCL}}$) catches long-context attention decay without retraining | Chalkidis et al. (2022); Valvoda et al. (EMNLP 2021) |
| **In-Process Zero-Hop Hybrid RAG** | BM25Okapi + BGE-Large dense + BGE-Reranker-v2-m3 with RRF ($k=60$) and zero-copy safetensors mmap | Robertson & Zaragoza (2009); Cormack et al. (SIGIR 2009) |
| **Dual-Gate Reflexion Loop** | Generator-Discriminator loop with up to 3 verbal self-healing turns and 3 cognitive complexity silos | Shinn et al. (NeurIPS 2023); Madaan et al. (NeurIPS 2023) |
| **95% Wilson Score Gating** | Asymmetric binomial confidence bounds solving the Wilson Paradox on finite small samples ($N \approx 60$) | Wilson (JASA 1927) |
| **GGUF Q4_K_M Quantization** | K-quants hierarchical block quantization; enables 4.3 GB standalone edge CPU execution | Gerganov et al. (llama.cpp) |

---

## Security & Threat Model

| Threat | Mitigation |
|--------|-----------|
| **Canvas/WebGL/Audio fingerprinting** | `api-spoof.ts` injects Proxy objects at `document_start` in the MAIN world; proxies present as `[native code]` defeating `.toString()` detection by FingerprintJS v4 |
| **Clean-room iframe bypass** | Hooks `Node.prototype.appendChild` and `contentWindow` getters to recursively poison iframe environments |
| **SSRF via attacker-supplied policy URL** | `policy_fetcher.py` resolves the hostname before each hop and refuses private/loopback/link-local/reserved addresses; public URLs cannot 30x into the internal network |
| **HMAC replay** | `security.py` enforces a strict 30-second temporal window and caches nonces (LRU TTL cache in `memory_orchestrator.py`) |
| **Model extraction** | `AntiExtractionGuard` regex blocks chain-of-thought probes and injects statutory watermarks |
| **Policy text exposure** | Policy text is fetched by the server, used once for inference, then explicitly `del`-ed — it never reaches a database, a log, or the extension |
| **Chat rate abuse** | 60 req/min per `(api_key + client_IP)`; audits are deliberately unlimited since the shared cache means GPU inference rarely triggers |
| **VRAM exhaustion** | `engine.py` detects actual hardware (NVIDIA GPU / Jetson unified pool / CPU) and derives `max_num_seqs` from the real memory budget |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-07-03 | Initial architecture (dual-mode: Rust daemon + cloud server) |
| 2.0 | 2026-07-22 | Added Chrome MV3 + Native Messaging detail, AntiExtractionGuard, security table |
| 3.0 | 2026-08-03 | Docker orchestration, Unsloth process isolation, ML training rationale |
| 4.0 | 2026-09-18 | **Full rewrite for v2.3**: native daemon removed, server-side extraction, design history, accurate current architecture |
