# 🛡️ Ssense — DPDP Privacy Shield

> **Instant AI-powered DPDP Act 2023 compliance auditing for every website you visit.**

[![Version](https://img.shields.io/badge/version-2.3.0-blue.svg)](https://github.com/ssense/ssense/releases)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Manifest V3](https://img.shields.io/badge/Chrome%20Extension-Manifest%20V3-success.svg)](https://developer.chrome.com/docs/extensions/mv3/intro/)
[![FastAPI](https://img.shields.io/badge/Server-FastAPI%20%2B%20vLLM-009688.svg)](https://fastapi.tiangolo.com/)
[![DPDP Act 2023](https://img.shields.io/badge/Compliance-DPDP%20Act%202023-purple.svg)](https://www.meity.gov.in/)

Ssense is a production-grade, AI-powered privacy compliance platform built around India's **Digital Personal Data Protection (DPDP) Act 2023**. Install it from the Chrome Web Store and it works immediately — no sign-up, no API key entry, no model downloads, no configuration.

---

## ✨ What Ssense Does

When you visit any website, Ssense:

1. **Discovers** the privacy policy link automatically (scanning `<head>` metadata first, then footer DOM)
2. **Audits** the policy server-side — the full text is fetched, parsed, and analysed by a fine-tuned 7B LLM, then discarded; it never reaches your browser or any database
3. **Scores** the site on a **DPDP Trust Score (0–100)** and an **Obfuscation Subtlety Score**, both grounded in the Act's specific sections
4. **Surfaces** each violation with the offending entity, the exact evidence quote from the policy, and the precise statutory reference (`Section 7(b)`, etc.)
5. **Answers** your questions through an interactive co-pilot grounded in both the Act and this site's specific findings
6. **Enforces** at the DOM level: tracking scripts flagged as violators are actively removed (`el.remove()`), not merely hidden
7. **Defends** against fingerprinting: Canvas, WebGL, AudioContext, and hardware APIs are spoofed from `document_start` before fingerprinters execute

Audit results are cached server-side for **90 days** — a second user visiting the same site gets an instant response. Results are also stored locally in the browser for instant offline display.

---

## 🏛️ Architecture (v2.3 — Zero-Config Server-First)

```
┌──────────────────────────────── Chrome Extension (MV3) ─────────────────────────────────┐
│                                                                                          │
│  MAIN world (document_start)                  ISOLATED world (document_idle)             │
│  ┌─────────────────────────┐      ┌───────────────────────────────────────────────────┐ │
│  │ api-spoof.ts            │      │ extractor.ts          dark-pattern-blocker.ts     │ │
│  │ Canvas / WebGL / Audio  │      │ Scans DOM for         MutationObserver →          │ │
│  │ API Proxy injection     │      │ policy URL only →     el.remove() trackers        │ │
│  │ (blinds FingerprintJS)  │      │ sends {domain, URL}   chat-widget.ts overlay      │ │
│  └─────────────────────────┘      └─────────────┬─────────────────────────────────────┘ │
│                                                  │                                       │
│                                    ┌─────────────▼──────────────────┐                   │
│                                    │  service-worker.ts             │                   │
│                                    │  FOUND_POLICY_URL handler      │                   │
│                                    │  audit-cache.ts (local store)  │                   │
│                                    └─────────────┬──────────────────┘                   │
└──────────────────────────────────────────────────┼──────────────────────────────────────┘
                                                   │ HTTPS + HMAC-SHA256
                                    ┌──────────────▼───────────────────────────────────────┐
                                    │         SLM Server (apps/slm-server)                 │
                                    │                                                       │
                                    │  POST /v1/audit/by-url                               │
                                    │    1. policy_fetcher.py → fetch URL, extract text    │
                                    │    2. audit_store.py   → 3-tier cache check          │
                                    │       (hot LRU → SQLite 90-day → policy-hash)        │
                                    │    3. vLLM inference (only on genuine cache miss)     │
                                    │    4. Return report; discard policy text              │
                                    │                                                       │
                                    │  POST /v1/chat/stream (SSE, rate-limited)             │
                                    │    Hybrid BM25+dense RAG + pre-computed audit context │
                                    │                                                       │
                                    │  GET  /v1/audit/{domain}  — retrieve cached report   │
                                    └───────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | What we chose | What we tried before | Why we changed |
|----------|--------------|---------------------|----------------|
| **Policy extraction** | `policy_fetcher.py` runs on the server | `extractor.ts` fetched HTML in the browser via `PROXY_FETCH` service worker handler | Moving extraction server-side eliminates ~20 KB of policy text transiting the extension, removes a complex SSRF-guarded handler, and gives the server better HTTP headers and redirect handling than browser `fetch()` |
| **Policy text storage** | Never persisted anywhere | Stored in IndexedDB (`privacy-store.ts`) with the full text | Policy text is sensitive. The server uses it once for inference then discards it. The extension receives a structured JSON result, not prose |
| **Audit results (local)** | `chrome.storage.local` — simple key→JSON, per-domain | IndexedDB with full policy text blob | Removing the text cut each entry from ~25 KB to ~3 KB; `chrome.storage.local` API is simpler and faster for the read-on-tab-switch pattern |
| **Audit results (server)** | SQLite via `aiosqlite`, 90-day TTL, shared across users | In-memory LRU caches (24-hour TTL, lost on restart) | Shared persistent cache means user B benefits from user A's audit instantly; 90-day TTL matches realistic policy-update cadence |
| **Inference backend** | vLLM server only (cloud + self-host) | Dual-mode: Rust native daemon (`llama-cpp-rs`) for offline + vLLM for cloud | The Rust daemon required a separately installed native binary, OS-level registry entries, and a 9 GB model download before first use — a very high barrier for a general public extension. A centrally-hosted server with baked-in shared credentials removes all friction while remaining fully self-hostable |
| **Credentials** | Baked into the build (`VITE_*` env vars) | User-entered API key and HMAC secret in an Options page | Ordinary users should never need to open a settings page; the extension should work on install. Self-hosters get an "Advanced" section in Options to override the defaults |
| **Rate limiting** | Chat-only (60 req/min per api_key+IP); audits unlimited | Blanket rate limit on all endpoints | Audit results are shared server-wide, so the expensive inference path rarely runs. Throttling audits penalises honest users for no GPU-cost benefit |

---

## 📂 Repository Layout

```
Ssense/
├── apps/
│   ├── extension/               Chrome MV3 extension (React + Vite + TypeScript)
│   │   ├── src/
│   │   │   ├── background/      service-worker, api-client, audit-cache, history, chat stores
│   │   │   ├── content/         extractor (URL only), api-spoof, dark-pattern-blocker, chat-widget
│   │   │   ├── sidebar/         Side panel React app (ChatInterface, HistoryView, PrivacyView)
│   │   │   ├── popup/           Popup React app
│   │   │   ├── options/         Options page (zero-config by default, Advanced self-host section)
│   │   │   └── types/           server-protocol.ts (AuditReport, Violation, ServiceResponse)
│   │   └── public/              manifest.json, icons, content.css
│   └── slm-server/              FastAPI + vLLM inference server
│       ├── main.py              API routes (/v1/audit/by-url, /v1/chat/stream, /v1/audit/{domain})
│       ├── policy_fetcher.py    Server-side URL fetch + HTML extraction + language filter
│       ├── audit_store.py       SQLite persistent audit cache (90-day TTL, aiosqlite)
│       ├── memory_orchestrator.py  Hot in-memory layer + chat rate limiter + request coalescing
│       ├── rag_engine.py        Hybrid BM25+dense RAG with cross-encoder reranking
│       ├── engine.py            vLLM multi-LoRA inference driver
│       ├── security.py          HMAC verification, Shannon entropy filter, anti-extraction guard
│       ├── nginx/               Nginx TLS reverse-proxy configs (GPU / CPU / Jetson profiles)
│       ├── Dockerfile.gpu       CUDA 12 + vLLM production image
│       ├── Dockerfile.cpu       CPU-only image (testing/low-traffic deployments)
│       └── docker-compose.yml   Multi-container orchestration
└── docs/
    ├── ARCHITECTURE.md          Full design history and current architecture
    ├── BUILD.md                 Step-by-step build guide (extension + server)
    ├── DEPLOYMENT.md            Server deployment (Docker, Nginx, env vars)
    └── SECURITY.md              Security model, threat vectors, shared-credential rationale
```

---

## 🚀 Quick Start

### For End Users
Install from the Chrome Web Store. That's it. Ssense connects to our centrally-hosted server automatically — no key, no URL, no download.

### For Developers (Extension)

```bash
cd apps/extension
npm install

# Copy and fill in the production env (see .env.production.example)
cp .env.production.example .env.production
# VITE_SSENSE_SERVER_URL=https://api.ssense.app
# VITE_SSENSE_API_KEY=<your-key>
# VITE_SSENSE_HMAC_SECRET=<your-secret>

npm run build          # output → apps/extension/dist/
npm test               # 18-case extractor test suite (offline, no npm install needed)
```

Load `apps/extension/dist/` as an unpacked extension in `chrome://extensions/`.

### For Self-Hosters (Server)

```bash
cd apps/slm-server

# GPU (recommended)
docker compose up --build -d

# CPU only (testing)
docker compose -f docker-compose.yml up --build -d   # uses Dockerfile.cpu profile automatically

# Verify
curl http://localhost:8000/health
```

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for full env-var reference, Nginx TLS setup, and the Jetson Orin profile.

---

## 🧪 Test Matrix

```bash
# Extension: 18 offline extractor tests (URL discovery, SSRF guard, language filter, latency)
cd apps/extension
node --experimental-strip-types --test src/content/extractor.test.ts

# Server: security unit tests (HMAC, entropy, schema repair, anti-extraction)
python -m unittest apps/slm-server/tests/test_server_security.py
# → 8 passed in 0.007s

# TypeScript: strict compile check (no chrome.* deps required)
tsc --noEmit --skipLibCheck --strict src/content/extractor-core.ts src/types/server-protocol.ts
```

---

## 📄 License

Apache License 2.0 — see [`LICENSE`](LICENSE).
