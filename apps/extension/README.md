# 🧩 Ssense Chrome Extension (MV3)

> **Browser-side Privacy Shield & DPDP Compliance Co-Pilot** built on Manifest V3, React 18, and TypeScript.

The Ssense Chrome Extension provides client-side privacy protection, deterministic DPDP compliance auditing, and an interactive legal co-pilot. It seamlessly bridges the browser sandbox to local bare-metal edge AI via Chrome Native Messaging and to enterprise cloud infrastructure via cryptographically signed Server-Sent Events (SSE).

---

## 🏛️ Architecture Overview

```mermaid
graph TD
    subgraph Browser Context
        CS1[Content Script: api-spoof.ts<br/>MAIN World DOM Start] --> |Spoof Canvas, WebGL, Audio| DOM[Web Page DOM]
        CS2[Content Script: extractor.ts<br/>ISOLATED World] --> |Extract & Truncate Policy| SW[Background Service Worker<br/>service-worker.ts]
        CS3[Content Script: dark-pattern-blocker.ts] --> |el.remove() Trackers & Fingerprinters| DOM
        CS4[Content Script: chat-widget.ts] --> |Floating Action Button| DOM
        
        POP[Popup: Popup.tsx<br/>AI Engine Switcher & Progress] --> SW
        SP[Side Panel: ChatInterface.tsx<br/>Co-Pilot & Forensic Report] --> SW
    end

    subgraph Native Host Bridge
        SW --> |4-Byte LE Binary Framing| NM[native-messaging.ts<br/>com.ssense.native_daemon]
        NM --> |IPC| ND[ssense-native-daemon.exe<br/>Local GGUF / RAG Engine]
    end

    subgraph Cloud Gateway
        SW --> |HMAC-SHA256 Signed SSE| SLM[FastAPI Virtual SLM Server<br/>vLLM + Nginx TLS]
    end
```

### Core Subsystems

1. **MAIN World Preemptive Spoofer (`src/content/api-spoof.ts`)**:
   - Injected at `document_start` into the `MAIN` execution world.
   - Masks device fingerprints before tracking scripts execute:
     - WebGL vendor/renderer spoofing (reports standard hardware profiles).
     - Canvas noise injection to defeat pixel-level hash extraction.
     - AudioContext buffer quantization.
     - `navigator.hardwareConcurrency` and battery API shielding.
   - Employs prototype proxy wrapping disguised as `[native code]` to bypass advanced bot/anti-tamper detectors like FingerprintJS v4.

2. **Policy Extractor (`src/content/extractor.ts`)**:
   - Discovers privacy policies via DOM heuristic scanning, link pattern matching, and fallback discovery.
   - Cleans HTML boilerplate, scripts, and stylesheets, extracting raw text with statutory structure.
   - Truncates policies to 16,000 characters to prevent context window overflow while preserving critical consent and data collection clauses.

3. **Active DOM Enforcer (`src/content/dark-pattern-blocker.ts`)**:
   - Actively removes (`el.remove()`) offending third-party tracking scripts, iframes, and beacons identified by the audit engine.
   - Applies `.ssense-blocked-element` CSS rules for visual suppression of dark-pattern banners.
   - Defeats click-jacking, pre-ticked consent checkboxes, and forced account creation dialogs.

4. **Background Service Worker & Native Messaging (`src/background/`)**:
   - Manages communication between extension UI components and the Native Daemon host.
   - **MV3 Keepalive**: Utilizes `chrome.alarms` (`ssense_native_keepalive`) alongside periodic interval pulses to prevent Chrome from terminating the service worker during multi-gigabyte GGUF model downloads.
   - **Stream Multiplexer**: Translates binary Native Messaging IPC packets into structured UI events (`CHAT_STREAM_CHUNK`, `DOWNLOAD_PROGRESS`, `AUDIT_REPORT`).

5. **UI Layer (`src/popup/`, `src/sidebar/`, `src/options/`)**:
   - Built with React 18, Tailwind CSS, Lucide icons, and Framer Motion.
   - **Popup**: Dual-mode switch (`Cloud · Fast` vs. `Private · Offline`), live download progress indicators with transfer rate telemetry and SHA-256 verification status.
   - **Side Panel**: Interactive DPDP Co-Pilot with real-time token streaming, citation badges linking directly to statutory sections, and one-click forensic report exports.

---

## 📦 Directory Structure

```text
apps/extension/
├── public/                 # Static extension assets and icons
├── src/
│   ├── background/         # Chrome MV3 service worker
│   │   ├── service-worker.ts   # Event router and cache manager
│   │   └── native-messaging.ts # Native host IPC bridge and keepalive
│   ├── content/            # Content scripts injected into web pages
│   │   ├── api-spoof.ts        # MAIN-world anti-fingerprinting rootkit
│   │   ├── extractor.ts        # Privacy policy DOM parser
│   │   ├── dark-pattern-blocker.ts # Active DOM tracker remover
│   │   └── chat-widget.ts      # Floating on-page co-pilot button
│   ├── popup/              # Extension toolbar popup (React)
│   ├── sidebar/            # Chrome Side Panel UI (React)
│   │   ├── components/     # ChatInterface, AuditScorecard, ViolationCard
│   │   └── styles/         # Glassmorphic Tailwind styling
│   ├── options/            # Settings and server configuration page
│   └── types/              # TypeScript interfaces and native messaging protocol
├── manifest.json           # Chrome Extension Manifest V3 definition
├── package.json            # Node.js dependencies and scripts
├── tsconfig.json           # TypeScript 5.5+ bundler configuration
└── vite.config.ts          # Vite build pipeline with CRX / multi-page configuration
```

---

## 🛠️ Building & Developing

### Prerequisites
- **Node.js**: v18.0.0 or later (v20+ recommended)
- **npm**: v9.0.0 or later

### Installation
From the `apps/extension` directory (or workspace root):

```bash
cd apps/extension
npm install
```

### Production Build
Compile TypeScript and bundle via Vite:

```bash
npm run build
```

The compiled extension is output to `apps/extension/dist/`.

### Development Mode with Hot Reload
To run Vite in watch mode during extension development:

```bash
npm run dev
```

---

## 🌐 Loading in Google Chrome

1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** using the toggle switch in the top-right corner.
3. Click the **Load unpacked** button in the top-left toolbar.
4. Select the directory: `d:\Ssense\apps\extension\dist` (or `<path-to-repo>/apps/extension/dist`).
5. Ssense will appear in your extensions list. Pin it to your Chrome toolbar for easy access.

---

## ⚙️ Extension Settings & Configuration

Click the extension icon, click the gear icon (Settings), or open `chrome-extension://<EXTENSION_ID>/dist/options.html`:

| Setting | Default | Description |
| :--- | :--- | :--- |
| **Inference Mode** | `Cloud · Fast` | Toggle between Cloud SLM Server and local Native Host Daemon. |
| **Server URL** | `http://localhost:8000` | Address of the FastAPI Virtual SLM Server / Nginx gateway. |
| **API Key** | `ephemeral` | Authentication key required for HMAC challenge-response signing. |
| **HMAC Secret** | `ephemeral` | Secret key used by Web Crypto to sign request payloads. |
| **Hardware Spoofing**| `Enabled` | Enables MAIN-world WebGL, Canvas, and AudioContext masking. |
| **Tracker Blocking** | `Enabled` | Actively removes third-party tracking scripts and iframes from the DOM. |

---

## 🔍 Debugging & Logs

- **Service Worker Logs**: Go to `chrome://extensions/` → click **service worker** link under Ssense.
- **Side Panel / Popup Logs**: Right-click anywhere in the Side Panel or Popup and select **Inspect**.
- **Content Script Logs**: Open Chrome DevTools on any webpage (`F12`) and view the Console (filter by `[Ssense]`).
