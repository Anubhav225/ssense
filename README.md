# 🛡️ Ssense

> **Zero-Knowledge Edge AI for Privacy Policy Analysis and Browser-Side Enforcement.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Manifest V3](https://img.shields.io/badge/Chrome%20Extension-Manifest%20V3-success.svg)](https://developer.chrome.com/docs/extensions/mv3/intro/)
[![Rust 2021](https://img.shields.io/badge/Rust-Native%20Daemon%202021-orange.svg)](https://www.rust-lang.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%2B%20vLLM-009688.svg)](https://fastapi.tiangolo.com/)
[![DPDP Act 2023](https://img.shields.io/badge/Compliance-DPDP%20Act%202023-purple.svg)](https://www.meity.gov.in/)

Ssense is a production-grade, edge-native privacy platform that combines on-device AI analysis with browser-side privacy controls. It empowers users to understand data collection practices in plain English and automatically mitigates enterprise tracking techniques in accordance with India's **Digital Personal Data Protection (DPDP) Act 2023**.

Unlike cloud-dependent privacy extensions, Ssense operates with an **Edge-First / Zero-Knowledge** philosophy: it can run a quantized 9-billion parameter Small Language Model locally on your machine via a bare-metal Rust Native Host daemon, auditing privacy policies and powering an interactive legal co-pilot without transmitting policy text to the cloud.

---

## 📑 Table of Contents

1. [Architecture & System Overview](#-architecture--system-overview)
2. [Subsystems & Major Folders](#-subsystems--major-folders)
3. [Walkthrough: Running & Testing in Browser with Native Host](#-walkthrough-running--testing-in-browser-with-the-native-host)
   - [Prerequisites](#prerequisites)
   - [Step 1: Compile the Rust Native Daemon](#step-1-compile-the-rust-native-daemon)
   - [Step 2: Register the Native Host with Chrome](#step-2-register-the-native-host-with-chrome)
   - [Step 3: Build the Chrome Extension](#step-3-build-the-chrome-extension)
   - [Step 4: Load Extension in Google Chrome](#step-4-load-extension-in-google-chrome)
   - [Step 5: End-to-End Verification & Browser Testing](#step-5-end-to-end-verification--browser-testing)
   - [Step 6: Diagnostic Logs & Troubleshooting](#step-6-diagnostic-logs--troubleshooting)
4. [Running the Virtual SLM Cloud Server](#-running-the-virtual-slm-cloud-server)
5. [Automated Verification & Test Matrix](#-automated-verification--test-matrix)
6. [License](#-license)

---

## 🏛️ Architecture & System Overview

```mermaid
graph TB
    subgraph Browser["Google Chrome (Manifest V3)"]
        direction TB
        A1[MAIN World API Spoofer<br/>api-spoof.ts] --> |Blind Fingerprinters| DOM[Webpage DOM]
        A2[DOM Extractor<br/>extractor.ts] --> |Extract & Truncate Policy| SW[Background Service Worker<br/>service-worker.ts]
        A3[Dark Pattern Blocker<br/>dark-pattern-blocker.ts] --> |el.remove() Trackers| DOM
        
        UI_POP[Popup UI<br/>AI Engine Switcher] --> SW
        UI_SIDE[Side Panel UI<br/>Co-Pilot & Scorecard] --> SW
    end

    subgraph NativeEdge["Local Edge Layer (Zero-Knowledge)"]
        direction TB
        SW --> |Chrome Native Messaging<br/>4-Byte LE Binary Framing| IPC[Native Messaging Host<br/>com.ssense.native_daemon]
        IPC --> DAEMON[Rust Native Daemon<br/>ssense-native-daemon.exe]
        DAEMON --> MM[Model Manager<br/>Tree API + SHA-256 Stream]
        DAEMON --> LE[llama-cpp-2 Local Engine<br/>512 Chunked Prefill]
        DAEMON --> RAG[Local Safetensors RAG]
        LE --> |Token-by-Token Streaming| IPC
    end

    subgraph CloudBackup["Cloud Layer (Virtual SLM Server)"]
        direction TB
        SW -.-> |HMAC-SHA256 Signed SSE| NGINX[Nginx SSL Proxy<br/>:443]
        NGINX --> SLM[FastAPI + vLLM Server<br/>Multi-LoRA Multiplexing]
    end
```

### Core Value Pillars

* **Local Private AI**: Audits privacy policies and answers questions locally using `Qwen/Qwen3.5-9B` GGUF models executed by llama.cpp.
* **GGML Stability**: Implements 512-token chunked prefill batching, preventing GGML assertion aborts and memory spikes during long legal policy evaluation.
* **Real-Time Token Streaming**: Streams generated tokens directly across Chrome Native Messaging IPC, delivering immediate interactive chat responses in the sidebar.
* **Resumable Downloads & MV3 Keepalive**: Hugging Face tree API metadata resolution, HTTP range-request resumption with `.part` file preservation, and 500ms integrity verification heartbeats that keep Manifest V3 service workers active.
* **Preemptive Fingerprinting Defense**: Injects MAIN-world prototype proxies at `document_start` to mask Canvas, WebGL, AudioContext, and hardware concurrency APIs.

---

## 📂 Subsystems & Major Folders

Detailed documentation is available in each component directory:

| Component | Path | Description |
| :--- | :--- | :--- |
| **Chrome Extension** | [`apps/extension`](file:///d:/Ssense/apps/extension/README.md) | React 18, Vite, TypeScript Manifest V3 extension with Side Panel and Popup. |
| **Rust Native Daemon** | [`apps/native-daemon`](file:///d:/Ssense/apps/native-daemon/README.md) | Bare-metal Native Messaging Host with llama.cpp chunked prefill & GGUF streaming. |
| **Virtual SLM Server** | [`apps/slm-server`](file:///d:/Ssense/apps/slm-server/README.md) | FastAPI + Async vLLM server with HMAC authentication, Nginx SSL proxy, and RAG. |
| **Statutory Contracts** | [`libs/contracts`](file:///d:/Ssense/libs/contracts/README.md) | Canonical `dpdp_schema.json` and `dpdp_act_tree.json` specifications. |
| **ML & Data Forge** | [`ml`](file:///d:/Ssense/ml/README.md) | Synthetic data generation, Unsloth SFT / SimPO fine-tuning, and GGUF quantization. |

---

## 🚀 Walkthrough: Running & Testing in Browser with the Native Host

Follow these step-by-step instructions to compile the native daemon, register it with Chrome, load the extension, and execute end-to-end local inference.

### Prerequisites

1. **Google Chrome** (v116+ recommended for Side Panel and Native Messaging support).
2. **Node.js** (v18.0.0+ or v20+) and **npm**.
3. **Rust Toolchain** (1.75+): Install via [rustup.rs](https://rustup.rs/).
4. **C/C++ Build Environment**:
   - **Windows**: MSYS2 UCRT64 (`pacman -S mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-clang mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-ninja`) or Visual Studio C++ Build Tools.
   - **Linux**: `sudo apt-get install build-essential cmake clang libclang-dev`
   - **macOS**: `xcode-select --install` and `brew install cmake`

---

### Step 1: Compile the Rust Native Daemon

Set your environment variables (Windows UCRT64 example) and compile the native host:

```powershell
# Set path to libclang and compiler tools (Windows PowerShell)
$env:LIBCLANG_PATH = "C:\msys64\ucrt64\bin"
$env:PATH = "C:\msys64\ucrt64\bin;" + $env:PATH

# Build the release binary
cargo build --release -p ssense-native-daemon
```

*For faster iteration during development, you can run `cargo build -p ssense-native-daemon` (debug profile).*

The compiled binary will be located at:
- `target/release/ssense-native-daemon.exe` (Windows)
- `target/release/ssense-native-daemon` (Linux/macOS)

---

### Step 2: Register the Native Host with Chrome

Chrome identifies native messaging hosts via an OS-level manifest registration. Run the automated registration script from the repository root:

```bash
node scripts/register-nmh.js
```

**What this accomplishes:**
* Locates the built binary in `target/release/` or `target/debug/`.
* Writes `apps/native-daemon/com.ssense.native_daemon.json` with the exact binary path.
* Registers the host in the Windows Registry under:
  `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.ssense.native_daemon`
  *(On Linux, creates symlink in `~/.config/google-chrome/NativeMessagingHosts/`)*.

---

### Step 3: Build the Chrome Extension

Navigate to the extension directory and build the production bundle:

```bash
cd apps/extension
npm install
npm run build
```

This compiles TypeScript and uses Vite to generate the output files in `apps/extension/dist/`.

---

### Step 4: Load Extension in Google Chrome

1. Open Google Chrome and visit `chrome://extensions/`.
2. Turn **ON** the **Developer mode** toggle in the top-right corner.
3. Click the **Load unpacked** button in the top-left toolbar.
4. Select the directory:
   ```text
   d:\Ssense\apps\extension\dist
   ```
5. Ssense will appear in your extensions list. Note the extension ID (e.g., `abcdefghijklmnopqrstuvwxyz123456`).
6. Pin Ssense to your browser toolbar.

---

### Step 5: End-to-End Verification & Browser Testing

#### A. Connect to the Native Host & Start Model Download
1. Click the **Ssense shield icon** in your Chrome toolbar to open the Popup.
2. Under **AI ENGINE**, click the switch to change from **Cloud · Fast** to **Private · Offline**.
3. **Observe the Download Progress**:
   - The popup connects via Native Messaging to `ssense-native-daemon.exe`.
   - The daemon queries Hugging Face and begins downloading `Qwen/Qwen3.5-9B` GGUF and safetensors embedding weights into `%LOCALAPPDATA%\Ssense\models\`.
   - Progress bar displays download percentage, transfer speed, and current file.
   - Resuming works automatically via `.part` files if paused.
   - When download reaches 100%, observe the SHA-256 verification phase streaming progress every 500ms without timing out.
4. Once verified, the popup displays: **"Offline models are installed and ready"**.

#### B. Test Token Streaming & Chunked Prefill in the Side Panel
1. Open the Chrome Side Panel by clicking the Ssense icon or pressing the side panel toolbar button.
2. In the **DPDP Co-Pilot Chat**:
   - Ask: *"What are the data fiduciary obligations under Section 6 regarding consent notice?"*
3. **Verify Real-Time Streaming**:
   - Notice tokens appear progressively in the chat interface as they are generated by the llama.cpp tensor engine.
   - Check that prompts with long statutory context decode smoothly without memory spikes or aborts due to 512-token chunked prefill.

#### C. Test Privacy Policy Extraction & Dark Pattern Enforcement
1. Navigate to any website with a privacy policy (or a test privacy policy page).
2. The Ssense floating widget or popup will detect the policy.
3. Click **"Audit Policy"**.
4. The audit scorecard renders the **DPDP Trust Score (0-100)** and **Obfuscation Subtlety Rating**.
5. Check the browser console (`F12`) to verify that tracking scripts or iframes flagged as violations are automatically removed from the live DOM (`el.remove()`).

---

### Step 6: Diagnostic Logs & Troubleshooting

* **Chrome Service Worker Logs**:
  1. Open `chrome://extensions/`.
  2. Click the **"service worker"** inspect link under Ssense.
  3. View console logs prefixed with `[NativeMessaging]` or `[ServiceWorker]`.
* **Native Daemon Process Inspection**:
  - Open Windows Task Manager / Process Hacker and verify `ssense-native-daemon.exe` is running when the extension is active.
* **Native Host Connection Error ("Specified native messaging host not found")**:
  - Re-run `node scripts/register-nmh.js` to ensure registry entries match the current binary location.
  - Verify that `allowed_origins` in `com.ssense.native_daemon.json` contains `chrome-extension://<YOUR_EXTENSION_ID>/`.

---

## ☁️ Running the Virtual SLM Cloud Server

If you prefer to run Ssense in Cloud Mode or host your own centralized compliance backend:

```bash
cd apps/slm-server

# Standalone local run:
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000

# Or production multi-container Docker with GPU:
docker compose up --build -d
```

Verify server health:
```bash
curl http://localhost:8000/health
```

---

## 🧪 Automated Verification & Test Matrix

All sub-projects are backed by continuous automated test suites:

```bash
# 1. Python Security Suite (HMAC, Shannon Entropy, Schema Repair, Hallucination Gate)
python -m unittest apps/slm-server/tests/test_server_security.py
# Result: 8 passed in 0.007s

# 2. Chrome Extension Build & TypeScript Verification
cd apps/extension && npm run build
# Result: 0 TypeScript errors, built in <1s

# 3. Rust Native Daemon Compiler & Tensor Bindings Check
cargo check -p ssense-native-daemon
# Result: Clean compilation (0 errors, 0 warnings)
```

---

## 📄 License

Ssense is licensed under the [Apache License 2.0](LICENSE).
