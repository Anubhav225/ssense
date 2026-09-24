# 📢 Ssense Release Notes

## Version 1.0.0 — First General Release (Production Launch)

**Release Date:** September 23, 2026  
**Target:** Chrome Web Store (Manifest V3)

---

### 🌟 Release Highlights

- **Direct Cloud & Tunnel Architecture**: Completely removed the legacy native host dependency. The extension now communicates directly with the high-performance Ssense SLM Server using HMAC-SHA256 authenticated REST and SSE streaming endpoints. Zero external binary installation required.
- **Collapsible Compliance History**: Redesigned the History view into an interactive accordion. Expand any visited site to view its full statutory legal reasoning, evidence quotes, violation classifications, offending entities, and audit freshness timestamps.
- **Dynamic Dark / Light Theme Sync**: The extension now automatically detects and reflects the host browser's system theme (`prefers-color-scheme`), providing a tailored, high-contrast experience in both light and dark modes across the Side Panel, Popup, and Settings.
- **Enhanced Markdown Parser for Co-Pilot**: Upgraded the streaming chat tokenizer to support structured headers, bulleted lists, numbered statutory provisions, quotes, and code tokens with full CSP compliance and no `dangerouslySetInnerHTML`.
- **Responsive Layouts for Narrow Panels & Mobile Viewports**: Optimized toolbar spacing, site queue chips, input dock padding, and audit cards to adapt seamlessly from narrow 300px panels up to tablet and desktop viewport widths.
- **Streamlined 5-Section Settings Page**: Rebuilt `options.html` into clean, accessible sections: Connection Status, Account / Handshake, Zero-Harvesting Privacy architecture, Self-Hosted Server Override, and Version Details.
- **Robust Focused Window Panel Opener**: Fixed popup sidepanel launch to target the current active browser window reliably.

---

### 🛡️ Core Compliance Features

- **Automated DPDP Act 2023 Audits**: Heuristic policy extraction and automated scorecard scoring (Trust Score & Subtlety Index).
- **Statutory Section Mapping**: Direct attribution to sections of the DPDP Act 2023 (Section 5 Notice, Section 6 Consent, Section 8 Data Fiduciary obligations, Section 12 Erasure, etc.).
- **MAIN-World Anti-Fingerprinting**: Preemptive WebGL hardware masking, Canvas noise injection, and AudioContext quantization.
- **Interactive Legal Co-Pilot**: Switch between Regular (Concise) and Thinking (Deep reasoning) modes with persistent multi-site thread queueing.
- **Local Data Control**: Full IndexedDB site history and cache purge controls from the options page.


## 1.0.0 — final pre-release upgrade
Google sign-in with server-side verification, first-run welcome flow, automatic scanning controls with live per-site status, collapsible audit history (status-grouped, severity-grouped violations), redesigned popup and settings, cross-device sync, bundled fonts, new design system. See `docs/V1_RELEASE_UPGRADE.md`.
