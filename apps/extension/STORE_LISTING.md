# 🏪 Ssense — Chrome Web Store Submission Package

This document contains the official metadata, copy, permission justifications, and privacy disclosures required for publishing Ssense to the **Chrome Web Store**.

---

## 🏷️ Store Listing Metadata

### Extension Name
`Ssense — DPDP Privacy Shield & Legal Co-Pilot`

### Short Name
`Ssense`

### Version
`1.0.0`

### Category
`Privacy & Security` (Secondary: `Productivity`)

### Short Description (Max 132 characters)
Instant DPDP Act 2023 compliance auditing, privacy policy trust scoring, and an interactive legal co-pilot for every site you visit.

---

## 📝 Detailed Description (Store Formatted)

**Ssense is an AI-powered legal co-pilot and active privacy shield built for India’s Digital Personal Data Protection (DPDP) Act 2023.**

Every day, websites collect your personal data under the guise of complex, unreadable privacy policies. Ssense levels the playing field by automatically extracting, auditing, and grading privacy policies the instant you visit a site — backed by an active anti-tracking shield and an interactive side-panel co-pilot.

---

### 🛡️ KEY FEATURES

#### 1. Instant DPDP Act 2023 Compliance Audits
- Automatically evaluates the active website's privacy policy against the requirements of the Digital Personal Data Protection Act 2023.
- Generates a **DPDP Trust Score** (0–100) indicating overall legal compliance.
- Analyzes **Subtlety & Obfuscation** to measure whether legal terms are intentionally misleading or difficult to comprehend.
- Cites specific sections of the DPDP Act (e.g., Notice under Section 5, Consent under Section 6, Right to Erasure under Section 12).

#### 2. Interactive Legal Co-Pilot (Side Panel)
- Ask any question about the website's privacy practices directly in Chrome's Side Panel.
- *"Does this site sell my personal data?"*
- *"Where is my data stored, and do they transfer it across borders?"*
- *"How do I delete my account and revoke consent?"*
- Supports both **Regular Mode** for quick, concise answers and **Thinking Mode** for deep statutory analysis.

#### 3. Active Fingerprint & Tracker Shield
- **Preemptive Canvas & Audio Spoofing**: Blocks stealth device fingerprinting before scripts execute.
- **WebGL Hardware Masking**: Prevents websites from cataloging your GPU hardware profile.
- **Dark Pattern & Beacon Neutralization**: Suppresses invasive tracking beacons and pre-ticked consent dialogs.
- **Global Privacy Control (GPC)**: Automatically injects GPC signals requesting that websites honor opt-out preferences.

#### 4. Collapsible Compliance History
- View your browsing compliance log with collapsible per-site audit cards.
- Inspect exact evidence quotes from policies and lists of offending third-party tracking entities.
- Track score trends over time with visual sparklines.
- Export complete compliance records to CSV for documentation or legal review.

#### 5. Native Theme Synchronization
- Automatically adapts to your browser’s dark or light theme with a clean, modern aesthetic.

---

### 🔒 PRIVACY-FIRST BY DESIGN

Ssense adheres to strict data minimization principles:
- **Zero Browsing History Uploads**: Your visited URLs and page browsing activities stay on your device.
- **Public Policy Audits Only**: Only the public text of the website's privacy policy is evaluated by our specialized legal model.
- **Local Storage**: Audits and history are stored securely in your browser's private IndexedDB and can be cleared at any time with a single click.

---

## 📋 Required Permission Justifications (For Reviewers)

| Permission | Technical Justification |
| :--- | :--- |
| `sidePanel` | Required to provide the interactive legal co-pilot chat and compliance audit dashboard directly alongside web content without interrupting browsing. |
| `storage` | Required to store user preferences, active shield settings, and locally cached audit summaries for fast offline display. |
| `scripting` | Required to inject the heuristic privacy policy extractor and active tracker blocker into web pages when requested by the user. |
| `tabs` | Required to detect the active website domain to display its corresponding compliance score and allow site-specific chat sessions. |
| `notifications` | Required to notify the user if a visited site is flagged for severe DPDP statutory violations or high-risk data practices. |
| `identity` | Optional: Used only to detect the user's active Chrome profile name and email for one-click local device registration and quota management. |
| `<all_urls>` (Host Permission) | Ssense is a universal web privacy shield. It must be capable of extracting public privacy policy links and blocking third-party tracking scripts across any website the user visits. No personal data from web pages is ever collected or exfiltrated. |

---

## 📜 Privacy Policy (For Store Submission URL)

**Effective Date:** September 23, 2026  
**Product:** Ssense Chrome Extension (v1.0.0)

**1. Data Collection & Processing**  
Ssense does not collect, sell, or monetize user data. When you visit a website, the extension identifies the URL of the site's public privacy policy page. That public policy text is processed by our automated legal engine solely to identify DPDP compliance violations and generate a compliance scorecard.

**2. Local Processing & Storage**  
All browsing history records, device visit counts, active time tracking, and cached audit reports are stored locally in your browser using IndexedDB. This data remains under your full control and can be purged at any time from the Ssense Settings page.

**3. Third-Party Disclosures**  
Ssense does not transmit user data to advertising networks, data brokers, or analytics third parties. Communication with the Ssense SLM server is cryptographically signed using HMAC-SHA256 for integrity and rate limiting.

**4. User Rights**  
In accordance with the DPDP Act 2023, you have the right to erase all locally held data at any time via the "Clear Data" option in the extension settings.
