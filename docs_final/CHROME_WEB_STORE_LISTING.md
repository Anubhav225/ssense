# Ssense — Chrome Web Store Listing Copy

> This document contains the exact text to paste into the Chrome Web Store Developer Dashboard for each required field.

---

## Store Identity

| Field | Value |
|-------|-------|
| **Extension name** | Ssense — DPDP Privacy Shield |
| **Short name** | Ssense |
| **Version** | 2.3.0 |
| **Category** | Productivity |
| **Language** | English (India) |
| **Website** | https://ssense.app |
| **Support page** | https://ssense.app/support |
| **Privacy policy** | https://ssense.app/privacy |

---

## Short Description (132 characters max)

```
Instant DPDP Act 2023 compliance auditing for every website. AI trust scoring, violation detection & legal co-pilot. Zero setup.
```

---

## Full Description

```
Ssense is a DPDP Act 2023 compliance shield that works the moment you install it — no sign-up, no API key, no configuration, no model download.

Every website you visit is automatically scanned. Ssense finds the privacy policy, sends it to its AI audit engine, and surfaces a clear Trust Score (0–100) along with every specific violation it found — the entity responsible, the exact evidence quote from the policy, and the precise section of the DPDP Act that was breached.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 WHAT SSENSE DOES ON EVERY PAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍  Audits the privacy policy automatically
    Ssense finds the policy link (checking <head> metadata first, then footer), sends the URL to its server, and the server fetches, reads, and analyses the full policy text. The text itself is never stored — only the structured result.

📊  DPDP Trust Score & Obfuscation Subtlety Rating
    A 0–100 score grounded in India's Digital Personal Data Protection Act 2023. The Subtlety Score measures how hard the policy tries to obscure its data practices in legal language.

⚠️  Violation cards with evidence
    Each violation shows: the violation type, the statutory reference (e.g. "Section 7(b) — Consent Notice"), the exact quote from the policy, the network action, and the organisations involved.

🤖  DPDP Co-Pilot chat
    Ask anything about this site's data practices in plain English. The AI grounds every answer in the DPDP Act and this site's specific audit findings.

🛡️  Live DOM enforcement
    Tracking scripts and data-harvesting iframes identified as violators are actively removed from the page (not just hidden with CSS).

🕵️  Fingerprint defence
    Canvas, WebGL, and AudioContext APIs are spoofed from the moment a page starts loading, blinding enterprise fingerprinting libraries before they can run.

📁  Persistent history & offline viewing
    Every audit result is stored locally in your browser. Your 90-day audit history is available offline with full violation details — no server connection needed to review past results.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BUILT FOR INDIA'S DPDP ACT 2023
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The AI model was fine-tuned specifically on the DPDP Act 2023 using a two-track training pipeline: one adapter for precise forensic JSON audit output (rsLoRA r=128), another for natural conversational guidance (rsLoRA r=64). Every violation references the exact section and subsection of the Act.

Ssense understands:
• Data fiduciary obligations (Sections 8–11)
• Consent notice requirements (Section 5–7)
• Data localisation and cross-border transfer rules (Section 16)
• Children's data protections (Section 9)
• Grievance redressal mechanisms (Section 13)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PRIVACY FIRST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The policy text is fetched by the server, used once for AI analysis, then immediately discarded. It is never stored in a database, never logged, and never returned to your browser. The only thing that persists — on the server (for 90 days, shared across users to save compute) and locally in your browser — is the structured audit result: scores, violation types, and statutory references.

Ssense has no user accounts. No personal data is collected. No browsing history is transmitted.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SELF-HOSTABLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Ssense is fully open source (Apache 2.0). You can deploy your own SLM server using the provided Docker Compose configuration and point the extension at it through the Advanced section of Settings. The server runs on any NVIDIA GPU with 24 GB+ VRAM, or in CPU-only mode for low-traffic deployments.

Source: github.com/ssense/ssense
```

---

## Privacy Practices Declaration

Complete these in the "Privacy practices" tab of the Developer Dashboard.

### Does your extension collect user data?

**Yes** — with the following specifics:

| Data type | Collected? | How used | Stored? |
|-----------|-----------|----------|---------|
| Browsing history (URLs) | **No** | — | Never |
| Policy text from visited pages | **Temporarily** | Fetched server-side for AI analysis only; discarded immediately after inference | Never |
| Website domain names | **Yes** | Used to look up / cache the audit result for that domain | Server SQLite (90 days), extension `chrome.storage.local` (user-controlled) |
| Audit results (scores, violations) | **Yes** | Shown to the user; shared across users for the same domain to avoid redundant inference | Server SQLite (90 days), extension local storage |
| User messages (co-pilot chat) | **Yes** | Sent to the server for RAG-augmented AI response generation | Not persisted on the server; stored locally in the extension for chat history |
| Personal information | **No** | — | Never |
| Financial information | **No** | — | Never |
| Authentication information | **No** | — | Never |
| Location | **No** | — | Never |

### Privacy policy URL
`https://ssense.app/privacy`

### Single-purpose description
Ssense audits privacy policies for compliance with India's DPDP Act 2023 and enforces active privacy protection in the browser.

---

## Permissions Justification

The Chrome Web Store review team requires justification for every permission. Use this text in your submission notes.

| Permission | Justification |
|-----------|--------------|
| `sidePanel` | The main Ssense interface (audit report, co-pilot chat, history) lives in the Chrome Side Panel to avoid interrupting page layout |
| `storage` | Stores audit results locally (`chrome.storage.local`) for instant offline display and 90-day history. Also stores optional self-host server configuration |
| `scripting` | Injects `extractor.js` into pages to discover privacy policy links (DOM access required); injects `api-spoof.js` in the MAIN world to spoof fingerprinting APIs; re-injects extractor on retry |
| `tabs` | Reads the active tab URL to determine which domain is being visited; used for time-on-site tracking in history view |
| `notifications` | Shows a native browser notification when a site scores below 40/100 (critical DPDP violations) |
| `host_permissions: <all_urls>` | Required to inject content scripts on all websites the user visits (policy extraction, fingerprint defence, dark-pattern blocking) |

---

## Screenshots — What to Capture

Capture at 1280×800 or 640×400. The store allows up to 5 screenshots.

| # | Screen to capture | Key elements to show |
|---|-----------------|---------------------|
| 1 | Side panel — Audit card expanded | Trust Score badge, violation cards with evidence quotes, Export button |
| 2 | Side panel — Chat interface | Co-pilot answering a DPDP question with statutory citations |
| 3 | Side panel — History view | Multiple sites listed with scores and visit counts |
| 4 | Popup | Status indicator (Connected), domain chip, Open Panel button |
| 5 | Options page | Default (zero-config) state with "Ready — no setup required" badge |

---

## Promotional Tile (440×280)

Suggested layout:
- Background: `#09090B` (Ssense dark)
- Shield icon (white, 80×80) centered-left
- Headline: **"DPDP Compliance AI"** (white, 24px bold)
- Subline: **"Instant. Zero Setup. Forensic."** (cyan `#06B6D4`, 14px)
- Bottom-right: Ssense wordmark in gradient (cyan → violet)

---

## Pre-Submission QA Checklist

- [ ] Fresh Chrome profile with no prior Ssense data
- [ ] Extension opens popup without errors
- [ ] Popup shows "Ssense AI — Connected" (confirms baked credentials reach the server)
- [ ] Visit a major e-commerce site; wait 5–10 seconds; open Side Panel → audit card renders
- [ ] Expand audit card — violations show with evidence quotes and statutory references
- [ ] Ask co-pilot "Is my data being shared with third parties?" — answer references this site's specific findings
- [ ] Open History view — site appears with score and visit count
- [ ] Open Options page — shows "Ready — no setup required", no server URL visible to user
- [ ] Open Options page → "Use a different server" advanced section works correctly
- [ ] Visit `chrome://newtab` — Side Panel shows "Disabled on system pages"
- [ ] Disconnect from internet → revisit a previously audited site → audit report still shows from local cache
- [ ] Check `chrome://extensions/` → Service Worker → console: no errors, audit log visible
- [ ] Manifest version matches release tag (`2.3.0`)
- [ ] No `localhost` URLs or development credentials in the packaged build
- [ ] `VITE_SSENSE_SERVER_URL` points to the live production server, not a tunnel
