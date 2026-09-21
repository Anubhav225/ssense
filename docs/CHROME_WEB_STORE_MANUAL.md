# Ssense — Chrome Web Store Listing & Release Guide

> This document previously described a native Rust daemon, an "Offline /
> Private Mode" with multi-gigabyte resumable model downloads, and a
> Native Messaging host registration step. **None of that exists in this
> version** — `apps/native-daemon` has been removed and the extension
> talks to one hosted SLM server exclusively. This revision matches the
> actual shipped extension.

---

## What Ssense does (user-facing)

Ssense is a DPDP Act 2023 compliance shield for Chrome. It audits the
privacy policies of sites you visit, surfaces statutory violations with
citations, scores each site for trustworthiness, and provides a
DPDP-focused co-pilot you can ask questions about any audited site.

It works immediately on install — no account, no setup, no model
download.

## First launch

1. Install Ssense from the Chrome Web Store.
2. Click the Ssense icon in the toolbar.
3. That's it. Ssense is already connected to its hosted audit service.
4. Browse to any site with a privacy policy and open the full report.

There is deliberately **no setup step and nothing technical shown to
users** — no server URL, no API key, no credentials. Those are baked
into the build (see `docs/SECURITY.md`). The only thing in Settings is a
status card, a "Check connection" button, and a collapsed **Advanced**
section for the small minority who want to point the extension at their
own self-hosted server.

### Why doesn't it download gigabytes of models?

It doesn't run models locally at all. Inference happens on the hosted
SLM server, so the extension package stays small and the first run is
instant.

## What leaves the user's machine

Worth being precise about, since this drives the store's privacy
disclosures:

- **Sent to the server:** the domain being audited and the URL of its
  privacy policy (the server fetches and extracts the policy text
  itself), plus chat questions the user types.
- **Never sent:** browsing history, page content, cookie *values*,
  personal data, or anything identifying the user. There are no user
  accounts.
- **Stored locally only** (browser storage, never uploaded): audit
  history, per-site time tracking, and chat history.

## Chrome permissions, and why each is needed

| Permission | Why |
|---|---|
| `sidePanel` | The full audit report UI |
| `storage` | Local audit cache, chat history, settings |
| `scripting`, `tabs` | Detecting the current site and locating its privacy-policy link |
| `notifications` | Alerting on high-severity violations |
| `host_permissions: <all_urls>` | The audit works on whatever site the user is currently on, which can't be known in advance |

No Native Messaging permission is requested — there's no native
component to talk to anymore.

---

# Maintainer: release process

## 1. Deploy (or confirm) the server first

The extension is useless without a reachable SLM server, and the build
step below needs that server's credentials. Follow
`docs/DEPLOYMENT.md` §1–4 first, and have the domain live behind TLS.

## 2. Bake the server credentials into the build

From `apps/extension`:

```bash
cp .env.production.example .env.production
```

Fill in all three values — they must match the deployed server's own
`.env` exactly:

```ini
VITE_SSENSE_SERVER_URL=https://api.yourdomain.example.com
VITE_SSENSE_API_KEY=<same as server's SSENSE_API_KEYS entry>
VITE_SSENSE_HMAC_SECRET=<same as server's SSENSE_HMAC_SECRET>
```

Read `docs/SECURITY.md` before doing this if you haven't. Short version:
these end up readable inside the published extension by anyone who
unpacks it, that is expected and accepted for this project, and the
protections that actually matter are server-side.

`.env.production` is gitignored — never commit it.

## 3. Build

```bash
npm install
npm run build
```

The build **fails loudly** if any of the three `VITE_SSENSE_*` values are
missing, rather than silently shipping an extension that can't reach any
server. The uploadable directory is `apps/extension/dist`.

## 4. Publish

Zip the contents of `apps/extension/dist` and upload through the Chrome
Web Store Developer Dashboard.

## 5. Lock down CORS to the published extension ID

After first publication, Chrome assigns a permanent extension ID. Take
it and set it on the **server**:

```ini
SSENSE_ALLOWED_ORIGINS=chrome-extension://<published-extension-id>
```

then restart the server (`docker compose --profile <profile> up -d
--force-recreate slm-server-<profile>`). This is the one post-publication
server change required — until you do it, `SSENSE_ALLOWED_ORIGINS` is
likely still `*`. Note this is a deterrent, not a hard boundary (see
`docs/SECURITY.md` on what CORS does and doesn't stop).

## 6. Store listing language

Accurate claims to make:

- **Zero setup** — works the moment it's installed; no account, no keys.
- **No multi-gigabyte download** — inference is hosted, so the package is
  small and the first run is instant.
- **Policy-only data transfer** — only the audited site's domain and
  policy URL leave the browser; history and page content never do.
- **DPDP Act 2023 citations** — findings reference specific statutory
  sections.

Claims to avoid:

- Anything about on-device/offline/local inference, or privacy guarantees
  premised on it — the model does not run locally in this version.
- Anything implying audit results are legal advice.

## 7. Pre-submission QA

- Fresh install in a clean Chrome profile: confirm the extension is
  immediately functional with no configuration.
- Confirm Settings shows **no** API key or HMAC secret fields by default,
  and no server URL.
- Confirm the popup shows a real status (not "Not configured") on a
  fresh install.
- Audit a site end-to-end; confirm the report renders with citations.
- Ask the co-pilot a question about that site; confirm it answers
  grounded in that site's audit.
- Turn on the Advanced self-host override, point it at a local dev
  server, confirm it takes effect; turn it off, confirm it reverts to
  the hosted server.
- Confirm behavior on a browser system page (`chrome://settings`) is a
  clean "not applicable" message, not a stale or fake score.
- Confirm behavior when the server is unreachable: a plain user-facing
  error, no stack traces, no leaked URLs or credentials in any UI
  surface or console output.
- Verify `dist/` contains no source maps and no `.env*` files.
- Set `SSENSE_ALLOWED_ORIGINS` to the published extension ID (step 5) and
  re-verify the extension still works afterward.
- Review the store privacy disclosures against the "What leaves the
  user's machine" section above.
