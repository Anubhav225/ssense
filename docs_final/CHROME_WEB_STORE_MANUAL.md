# Ssense — Chrome Web Store Manual (v2.3)

> **What changed from the earlier manual:** previous versions of this document described a dual-mode architecture with an offline Rust native daemon, a 9 GB model download, a progress-bar download UI, and a Cloud/Offline mode toggle. All of that has been removed. The current extension is zero-config: it connects to a centrally-hosted server automatically on install, with no setup required from the user. The full story is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## What Ssense Does

Ssense is a DPDP Act 2023 compliance shield. On every website you visit, it:

1. **Finds** the privacy policy link automatically — no button to click
2. **Audits** it using a fine-tuned 7B AI model, grounded in the DPDP Act 2023
3. **Shows** a Trust Score (0–100), each violation with the evidence quote and statutory reference, and an interactive co-pilot you can question
4. **Enforces** by actively removing tracking scripts from the page DOM
5. **Defends** against fingerprinting by spoofing Canvas, WebGL, and AudioContext APIs before they run

---

## First Launch

1. Install Ssense from the Chrome Web Store
2. The Ssense shield icon appears in your toolbar
3. Navigate to any website
4. Click the shield icon → **Open Privacy Panel**
5. The DPDP audit runs automatically within a few seconds

There is nothing to configure. There are no credentials to enter. There is no model to download.

---

## The Audit Panel

When you open the Side Panel, you see:

- **Domain and compliance badge** — site name with a colour-coded score dot (green ≥80, amber ≥50, red <50)
- **Audit button** — runs a fresh audit (or re-audits if the cached result is older than 90 days)
- **Thinking mode toggle** — switches the co-pilot between concise (2–4 sentence) and detailed (step-by-step reasoning) responses

### Trust Score

A 0–100 score computed by the DPDP audit model:

| Range | Meaning |
|-------|---------|
| 80–100 | Compliant — no critical violations detected |
| 50–79 | Caution — some practices require attention |
| 0–49 | Violations found — active data rights risks |

### Subtlety Score

Measures how hard the policy works to obscure its data practices through legal language. A high subtlety score alongside a low trust score indicates intentional obfuscation.

### Violation Cards

Each violation shows:
- **Type** — e.g. "Unlawful Data Sharing", "No Consent Notice"
- **Statutory reference** — the exact DPDP Act section and subsection
- **Evidence quote** — the verbatim text from the policy that triggered this finding
- **Network action** — what the system would do (COLLECT / SHARE / RETAIN / TRANSFER)
- **Offending entities** — third parties named in this violation

Click any evidence quote to highlight the relevant passage in the live page.

---

## Co-Pilot Chat

Ask anything about this site's data practices:

> "Is my location being shared with advertisers?"
> "What does this policy say about deleting my account data?"
> "Does Section 9 of the DPDP Act apply here?"

The co-pilot grounds every answer in:
1. This site's specific audit findings
2. The relevant DPDP Act sections retrieved from its legal corpus

**Rate limit:** 60 questions per minute per user. Audits are not rate-limited.

---

## History View

The history tab shows every site you've visited with:

- DPDP Trust Score (from the most recent audit)
- Violation count
- Total time spent on site
- Date and time of last visit / last audit

Audit results are cached for 90 days — a site's score persists until either the policy changes or 90 days elapse. After that, the next visit triggers a fresh audit automatically.

The history is stored locally in your browser. It is available offline. It is never transmitted to Ssense servers.

---

## Shield Settings

The shield panel (click the 🛡️ Shield button) lets you toggle:

| Setting | Default | What it does |
|---------|---------|-------------|
| Block Third-Party Trackers | On | Removes tracking scripts from the page DOM using `MutationObserver` |
| Spoof Hardware APIs | On | Masks Canvas, WebGL, AudioContext fingerprinting APIs |
| Inject Global Privacy Control | On | Adds the GPC signal to outgoing requests |

---

## Settings (Advanced Self-Host)

The Settings page is intentionally minimal. Ordinary users see a status indicator and nothing else — the extension is pre-configured to reach Ssense's shared server.

The **"Use a different server"** section (collapsed by default) is for developers and organisations who have deployed their own SLM server. Fill in your server URL, API key, and HMAC secret to override the shared defaults.

---

## Offline Behaviour

Ssense caches every audit result locally in your browser (`chrome.storage.local`). If you visit a previously audited site without internet access, the full report — score, all violation cards, legal reasoning — loads instantly from the local cache with no server round-trip.

The co-pilot chat requires a live server connection.

---

## Audit Freshness

Server-side: audit results are cached for 90 days per domain, shared across all users.
- If two users visit `amazon.in` within 90 days, the second gets an instant cached response
- A new audit runs only when the cache expires or when the policy text has changed (detected by SHA-256 hash comparison)

To force a fresh audit at any time, click the **Audit** button in the toolbar. This bypasses all caches and runs a new inference.

---

## Permissions Explained

| Permission | Why Ssense needs it |
|-----------|-------------------|
| **Side panel** | The main interface lives in Chrome's built-in Side Panel |
| **Storage** | Saves audit results and history locally in your browser |
| **Scripting** | Injects the policy finder and fingerprint-defence scripts into pages |
| **Tabs** | Reads the current tab's URL to know which site to audit |
| **Notifications** | Alerts you when a site scores critically low (<40/100) |
| **All URLs** | Required to run on every website you visit |

Ssense does **not** use: `nativeMessaging`, `downloads`, `background` (service worker is used instead), `cookies`, `webRequest`, or `proxy`.

---

## Privacy

- **Policy text** is fetched server-side, used once for AI analysis, then deleted. It is never stored in a database, never logged, never returned to your browser.
- **Audit results** (scores, violations) are stored on the server for 90 days (shared across users) and locally in your browser (yours only, no expiry).
- **Chat messages** are sent to the server for AI processing. They are not persisted on the server. They are stored locally in your browser for your chat history.
- **No personal data** is collected. No user accounts. No browsing history transmitted.

---

# Maintainer: Chrome Web Store Release Guide

## Build

```bash
cd apps/extension
cp .env.production.example .env.production
# Fill: VITE_SSENSE_SERVER_URL, VITE_SSENSE_API_KEY, VITE_SSENSE_HMAC_SECRET

npm install
npm run build
# Output → apps/extension/dist/
```

## Package

```bash
cd apps/extension/dist
zip -r ssense-v2.3.0-release.zip .
```

Upload `ssense-v2.3.0-release.zip` through the Chrome Web Store Developer Dashboard.

## What Changed from the v1 Release Package

| v1 | v2.3 |
|----|------|
| Required shipping a separate Rust native daemon installer | No native component — extension is self-contained |
| User needed to enter a server URL and API key on first use | Zero-config: credentials baked in, works on install |
| Included `nativeMessaging` permission | Permission removed |
| Extension downloaded 9 GB model on first use | No model download — server handles inference |
| `apps/extension/src/background/native-messaging.ts` | File deleted |
| `apps/extension/src/background/privacy-store.ts` (25 KB policy text in IndexedDB) | Replaced by `audit-cache.ts` (3 KB structured result in chrome.storage.local) |
| `PROXY_FETCH` service-worker handler | Handler deleted — server does the fetching |
| Options page showed server URL and API key fields to all users | Options page shows only status; advanced section hidden by default |

## Pre-Submission Checklist

- [ ] `manifest.json` version matches release tag
- [ ] `VITE_SSENSE_SERVER_URL` is the live production URL (not `localhost` or a tunnel)
- [ ] `VITE_SSENSE_API_KEY` and `VITE_SSENSE_HMAC_SECRET` are the shared production credentials
- [ ] `.env.production` is **not** included in the zip (only `dist/` contents)
- [ ] Fresh install test: popup opens, status shows Connected, audit runs on a real website
- [ ] Offline test: previously audited site shows full report without internet
- [ ] Settings page shows default state (no fields visible to user)
- [ ] `chrome://extensions/` service worker console shows no errors
- [ ] No `nativeMessaging` in manifest permissions
- [ ] Privacy policy URL resolves correctly
