# Ssense — Security Model

---

## Shared Install Credentials

The most common question about Ssense's security model: **"Aren't the API key and HMAC secret baked into the extension bundle a public secret?"**

Yes, deliberately.

### Why this is accepted practice

A Chrome Web Store package is a downloadable zip. Anyone can unpack it and read the minified JS. There is no technical mechanism to hide a value that ships inside a browser extension from the person running that extension. This is identical to how browser-exposed API keys (Google Maps, Firebase, Stripe publishable keys) work — the key is in the JS, and that's expected.

The actual security properties we care about come from the **server side**, not the confidentiality of the key:

| Property | Where it's enforced |
|----------|-------------------|
| **Request authentication** | HMAC-SHA256 (`X-Ssense-Signature`): even knowing the API key, you cannot forge a request without also knowing the HMAC secret. Both are needed |
| **Replay prevention** | 30-second temporal window + per-nonce caching in `memory_orchestrator.py`. Captured requests expire after 30 seconds |
| **Per-user rate limiting (chat)** | Keyed on `api_key + client_IP` — not just `api_key`. Two users sharing the same key each get their own 60-req/min bucket |
| **Circuit breaker** | `SSENSE_MAX_QUEUE_DEPTH` rejects requests when concurrent in-flight count hits the cap, protecting VRAM from coordinated abuse |
| **Credential rotation** | If the shared key is ever abused: rotate `SSENSE_API_KEYS` + `SSENSE_HMAC_SECRET` on the server, ship a new extension build with the new values. The old key stops working server-side immediately |

### What the key is NOT for

- It is not a user identity — Ssense has no user accounts
- It is not a billing gate — there is no per-user metering
- It is not a privacy boundary — request content is protected by HTTPS, not by the key

### Self-hosters

If you deploy your own SLM server, generate your own `SSENSE_API_KEYS` and `SSENSE_HMAC_SECRET`, set them as environment variables on the server (never committed, never hardcoded), and bake the same values into your extension build via `.env.production`. The shared key model still applies within your own deployment.

---

## Threat Model

### What Ssense protects users from

| Threat | Mitigation |
|--------|-----------|
| **Canvas fingerprinting** | `api-spoof.ts` injects Proxy objects in the MAIN world at `document_start`. The proxy randomises canvas read-back per session. `.toString()` on the proxy returns `[native code]`, defeating FingerprintJS v4's detection heuristic |
| **WebGL fingerprinting** | Same Proxy injection covers `WebGLRenderingContext.getParameter()` and `getExtension()` |
| **AudioContext fingerprinting** | `AudioContext.createOscillator()` and `AnalyserNode` read-backs are intercepted |
| **Hardware fingerprinting** | `navigator.hardwareConcurrency` is spoofed |
| **Clean-room iframe bypass** | `Node.prototype.appendChild` and `contentWindow` getters are hooked to propagate spoofing into iframe environments |
| **Third-party trackers** | `dark-pattern-blocker.ts` uses `MutationObserver` to call `el.remove()` on flagged elements; they are removed from the DOM, not merely hidden with CSS |
| **Telemetry header exfiltration** | `chat-widget.ts` intercepts `window.fetch` and `XMLHttpRequest` to scrub tracking headers (`X-Telemetry`, `X-Mixpanel`, etc.) |

### What the server protects itself from

| Threat | Mitigation |
|--------|-----------|
| **SSRF via attacker-supplied policy URL** | `policy_fetcher.py` resolves the hostname before every HTTP hop and refuses private/loopback/link-local/cloud-metadata ranges. A redirect chain cannot move from a public host to an internal one |
| **HMAC replay** | Strict 30-second window; nonce cached in `LRUTTLCache` (50k entries, 120s TTL) |
| **Origin spoofing** | `X-Ssense-Signature = HMAC-SHA256(METHOD:PATH:TIMESTAMP:NONCE)` — correct signature requires the HMAC secret, not just the API key |
| **Base64 / obfuscated injection** | Shannon entropy filter in `security.py` rejects inputs whose bit-entropy exceeds the threshold for natural language |
| **ChatML role injection** | `<|im_start|>` and `<|im_end|>` delimiter sequences are stripped from user input before prompt assembly |
| **Model distillation probes** | `AntiExtractionGuard` regex matches chain-of-thought elicitation patterns and returns `HTTP 429` |
| **VRAM exhaustion** | `engine.py` derives `max_num_seqs` from the real detected hardware memory. `SSENSE_MAX_QUEUE_DEPTH` circuit-breaks at a configurable in-flight cap |

### What we deliberately do NOT protect

| Item | Why |
|------|-----|
| **Policy text confidentiality during transit** | Policy texts are publicly available documents. HTTPS handles transit encryption. The server discards the text after inference — it's not stored anywhere |
| **Audit result confidentiality** | Audit results are shared across users for efficiency. If user A and user B both visit `amazon.in`, they get the same cached result. This is a feature, not a bug |
| **User identity / anonymity** | Ssense has no accounts. Client IP is used only for per-IP rate limiting — it is not logged or associated with audit requests |

---

## Data Flow Summary

```
Browser                          Server                    Storage
  │                                │                          │
  │ {domain, policyUrl}            │                          │
  │──────── HTTPS + HMAC ─────────►│                          │
  │                                │ fetch(policyUrl)         │
  │                                │──────────────────────►   │
  │                                │ HTML response            │
  │                                │◄──────────────────────   │
  │                                │ extract text             │
  │                                │ run vLLM inference       │
  │                                │ del policy_text          │
  │                                │──── save report ────────►│ SQLite audit_store
  │                                │◄─── cached_at ──────────│
  │ {report JSON, ~3 KB}           │                          │
  │◄─────── HTTPS ─────────────────│                          │
  │                                │                          │
  │ chrome.storage.local           │                          │
  │──── save LocalAuditEntry ───►  │                          │
  │     (no policy text)           │                          │
```

The only data that permanently exists anywhere:
- **Server SQLite:** domain, trust score, violation list, legal reasoning, policy URL, policy hash, chat_context, timestamps. **No policy text.**
- **Extension `chrome.storage.local`:** same structured data. **No policy text.**
- **User's browser history:** the URLs they visited (standard browser behaviour, unrelated to Ssense)
