# v1 public-release upgrade — sign-in, scanning, history, sync

## What changed

| Area | Before | Now |
|---|---|---|
| Sign-in | Free-text name + e-mail; "Detect Google profile" only guessed an address | Real Google sign-in (`chrome.identity`); server verifies the token with Google (audience-checked) before issuing credentials |
| Account safety | `/v1/auth/register` returned an existing user's API key + HMAC secret to **anyone who typed their e-mail** | Refused by default (`SSENSE_REQUIRE_GOOGLE_AUTH=true`); only `/v1/auth/google` issues credentials |
| Install | Opened the Options page | Opens `welcome.html`: sign in → choose scan behaviour → done |
| Auto-scan | Every page load hit the server | Gated by prefs (auto-scan, ignore list, re-scan interval); fresh local results served with no network; late-rendered footers retried; already-open tabs scanned after install/sign-in; live status for every site |
| Audit history | Flat list | Portfolio summary + status bar, filter chips, search, 5 sorts, grouped by status, collapsible site cards → violations grouped High/Medium/Low → evidence; trend, reasoning, actions; expand/collapse all; live updates |
| Popup | Sign-up form / status | "This site" (score ring, live status, findings, scan/ignore) and "All sites" (collapsible portfolio); sync state footer |
| Settings | Handshake button + server override | Account, Scanning, Alerts & protection, Sync & devices, Appearance, Privacy & data, Server, About; instant-save; responsive |
| Sync | none | Per-account push/pull (server sequence cursor), last-writer-wins per site, visits/time summed per device; every 15 min, after scans, on sign-in/startup/online |
| Design | Inter + cyan/violet | Shared "compliance ledger" system: Fraunces + Schibsted Grotesk (bundled — no Google Fonts request), ink/paper themes with light/dark/system override |

## Deploy checklist

1. **Google Cloud Console → Credentials**
   - Create an OAuth client of type **Chrome extension**; Application ID = your Web Store extension id.
   - (Optional, for Edge/Brave/Kiwi) a **Web application** client with redirect URI `https://<extension-id>.chromiumapp.org/`.
2. **Server** `.env`: `SSENSE_GOOGLE_CLIENT_IDS=<client-id>[,<web-client-id>]`, keep `SSENSE_REQUIRE_GOOGLE_AUTH=true`.
3. **Extension** `.env.production`: `VITE_SSENSE_SERVER_URL`, `VITE_GOOGLE_CLIENT_ID` (+ optional `VITE_GOOGLE_WEB_CLIENT_ID`). Shared baked-in API keys are no longer used. For unpacked dev builds set `VITE_EXTENSION_KEY` so the id matches the OAuth client.
4. `npm ci && npm run build`, zip `dist/`, upload.

New endpoints: `POST /v1/auth/google`, `POST /v1/sync/push`, `GET /v1/sync/pull`, `DELETE /v1/sync/data`. New permissions: `alarms`, `identity.email`. Sync data lives in `ssense_sync.db` (included in db_sync export).

## Notes and limits

* **Mobile:** Chrome for Android does not run extensions. Sync works on any Chromium browser with extension + Google sign-in support (e.g. Kiwi on Android); the UI is responsive down to phone widths. A native/web companion would be needed for stock Chrome/Safari mobile.
* Violation severity (High/Medium/Low) is derived client-side from the violation type (`utils/severity.ts`); it does not change the trust score.
* "Time on site" and visit counts are tracked per device and summed; scan status and audits: newest wins.
* Local data is wiped if a *different* Google account signs in on the same browser, so histories never leak between accounts.
* Tests: `npm test` (22), `python -m pytest tests/test_google_sync.py` (12). Not run here: GPU-dependent server suites and a live Google/Chrome end-to-end sign-in (needs your OAuth client).
