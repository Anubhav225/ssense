# Ssense v2.3 — Complete Windows Testing Guide

> **Every command in this guide is for Windows PowerShell 7+ (pwsh) or
> Windows Terminal.** Run them in order. Each phase builds on the last.
> The guide covers the CPU profile (no GPU required) so it works on any
> developer machine. GPU testing is noted where it differs.

---

## Prerequisites checklist

Open PowerShell and verify each one before starting:

```powershell
# 1. Node.js 20+
node --version
# Expected: v20.x.x or v22.x.x

# 2. npm 10+
npm --version
# Expected: 10.x.x

# 3. Docker Desktop (must be RUNNING — open it from Start menu first)
docker --version
# Expected: Docker version 26.x.x or later

docker compose version
# Expected: Docker Compose version v2.x.x
# NOTE: must be "docker compose" (space), not "docker-compose" (hyphen)

# 4. Python 3.11+ (used to generate secrets and run test scripts)
python --version
# Expected: Python 3.11.x or 3.12.x
# If this shows 3.x.x but is < 3.11, download from python.org

# 5. Git (needed if you want to clone; not needed if you have the zip)
git --version

# 6. curl.exe (built into Windows 10/11 — confirm it's the REAL curl, not PS alias)
curl.exe --version
# Expected: curl 8.x.x (curl.exe) ...
# If you see "Invoke-WebRequest" output, use curl.exe explicitly throughout
```

**Install anything missing before continuing.**

- Docker Desktop: https://www.docker.com/products/docker-desktop/
- Node.js 20 LTS: https://nodejs.org/
- Python 3.12: https://python.org/downloads/

---

## Phase 0 — Extract the project

```powershell
# Extract the zip to a working directory (adjust path as needed)
# Right-click Ssense-v2.3-final.zip → Extract All → C:\Projects\Ssense

# Navigate into it
cd C:\Projects\Ssense

# Confirm structure
ls
# You should see: apps\  docs\  libs\  ml\  scripts\  Cargo.toml  README.md  ...

# Navigate to slm-server for all server work
cd apps\slm-server
ls
# You should see: main.py  policy_fetcher.py  audit_store.py  docker-compose.yml  ...
```

---

## Phase 1 — Generate secrets and create `.env`

The server refuses to start without credentials. Generate them now.

```powershell
# Make sure you are in apps\slm-server
cd C:\Projects\Ssense\apps\slm-server

# Generate API key (32-byte URL-safe token)
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Example output: xK8mP2nQrT5vW9yZ3aB6cE0fH4jL7oN1

# Copy that output. Now generate HMAC secret (48-byte token)
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Example output: dF2gH5jK8mN1pQ4rS7tV0wX3yA6bC9eG2hJ5kL8nP1qR4s

# Save both values — you will need them in TWO places:
#   1. apps\slm-server\.env    (for the Docker server)
#   2. apps\extension\.env.production   (baked into the extension build)
```

Now create the `.env` file for the server. Replace the example values with your generated ones:

```powershell
# Create .env (use the API_KEY and HMAC_SECRET you just generated)
@"
SSENSE_ENV=development
SSENSE_API_KEYS=xK8mP2nQrT5vW9yZ3aB6cE0fH4jL7oN1
SSENSE_ENTERPRISE_API_KEYS=
SSENSE_HMAC_SECRET=dF2gH5jK8mN1pQ4rS7tV0wX3yA6bC9eG2hJ5kL8nP1qR4s
SSENSE_ALLOWED_ORIGINS=*
SSENSE_MAX_QUEUE_DEPTH=5000
"@ | Out-File -FilePath .env -Encoding utf8

# Verify it was written correctly
cat .env
```

> **NOTE:** `SSENSE_ENV=development` means the server auto-generates
> ephemeral credentials if the file is somehow missing, and prints them
> to the log. For production, change this to `SSENSE_ENV=production`.

---

## Phase 2 — Start the server (CPU profile, no GPU needed)

```powershell
# Confirm you are in apps\slm-server
cd C:\Projects\Ssense\apps\slm-server

# Build and start all containers (CPU profile)
# This downloads ~15 GB of model weights on FIRST RUN — be patient
docker compose --profile cpu up --build -d

# Watch the live output (Ctrl+C to stop watching, containers keep running)
docker compose logs -f
```

### What you will see during first boot (takes 5–20 minutes on first run)

```
ssense-redis                    | Ready to accept connections
ssense-slm-server-cpu          | 🔍 [Boot] Verifying AI weights and indices...
ssense-slm-server-cpu          | 📥 [Boot] Downloading Qwen2.5-7B-Instruct → /app/models/base/...
ssense-slm-server-cpu          | Fetching: model-00001-of-00004.safetensors: 100%|████| 4.98G/4.98G
ssense-slm-server-cpu          | 📥 [Boot] Downloading Ssense LoRAs & RAG from PRiyanshu0-1/DPDP-SSense...
ssense-slm-server-cpu          | ✅ [Boot] All AI weights verified.
ssense-slm-server-cpu          | ✅ [AuditStore] Persistent cache initialised → /app/data/ssense_audit_cache.db
ssense-slm-server-cpu          | ✅ Ssense SLM Server ready.
ssense-nginx-proxy-cpu         | nginx: the configuration file nginx.conf syntax is ok
```

### Check that all containers are healthy

```powershell
docker compose ps

# Expected output (all should show "healthy"):
# NAME                     STATUS           PORTS
# ssense-redis             Up (healthy)
# ssense-slm-server-cpu   Up (healthy)
# ssense-nginx-proxy-cpu  Up (healthy)
```

If the slm-server shows "(health: starting)" for up to 3 minutes, that is
normal — the CPU profile healthcheck has a 180-second start period.

### If HuggingFace requires a token (private models)

```powershell
# If you see "401 Unauthorized" or "Repository not found" in logs:
# 1. Create a free HuggingFace account at huggingface.co
# 2. Go to Settings → Access Tokens → New token (read permission)
# 3. Add HF_TOKEN to your .env file:

Add-Content -Path .env -Value "HF_TOKEN=hf_yourTokenHere"

# Then restart the server container:
docker compose --profile cpu up -d --force-recreate slm-server-cpu
```

---

## Phase 3 — Verify server endpoints (no extension needed yet)

All tests below use the direct FastAPI port `:8000` (bypasses Nginx),
which skips HMAC verification for requests from localhost. This is the
fastest way to verify the server is working before wiring up the extension.

### 3a. Health check

```powershell
curl.exe http://localhost:8000/health

# Expected JSON response:
# {
#   "status": "online",
#   "backend": "vllm",
#   "active_jobs": 0,
#   "max_queue": 5000,
#   "rag_ready": true,
#   "audit_cache": {
#     "total_cached_domains": 0,
#     "expired_pending_prune": 0,
#     "ttl_days": 90,
#     "db_path": "/app/data/ssense_audit_cache.db"
#   },
#   "timestamp": 1726742400
# }
```

### 3b. Audit by URL (primary endpoint — server fetches policy itself)

```powershell
# Use Invoke-RestMethod for cleaner PowerShell JSON handling
$body = @{
    domain       = "amazon.in"
    policyUrl    = "https://www.amazon.in/gp/help/customer/display.html?nodeId=200545940"
    force_refresh = $false
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://localhost:8000/v1/audit/by-url" `
    -Method POST `
    -ContentType "application/json" `
    -Headers @{ "X-Ssense-API-Key" = "xK8mP2nQrT5vW9yZ3aB6cE0fH4jL7oN1" } `
    -Body $body

# Expected response (first call — takes 30-120s on CPU, subsequent calls instant):
# source      : inference
# data        : @{dpdp_trust_score=61; subtlety_score=74; violations=System.Object[]; global_legal_reasoning=...}
# cached_at   :
# age_days    :
# policy_url  : https://www.amazon.in/gp/help/customer/display.html?nodeId=200545940
```

### 3c. Retrieve cached audit (instant after 3b completes)

```powershell
Invoke-RestMethod `
    -Uri "http://localhost:8000/v1/audit/amazon.in" `
    -Method GET `
    -Headers @{ "X-Ssense-API-Key" = "xK8mP2nQrT5vW9yZ3aB6cE0fH4jL7oN1" }

# Expected response:
# source    : hot_cache          ← served from in-memory hot layer
# data      : @{dpdp_trust_score=61; ...}
# cached_at : 1726742400
# age_days  : 0

# Run it again after 5 min and source will be "persistent_cache"
# (hot-layer TTL expired, served from SQLite)
```

### 3d. Chat stream (gated on completed audit)

The chat endpoint returns Server-Sent Events. Test it with a simple
Python script since PowerShell SSE handling is verbose:

```powershell
# Save this as test_chat.py in apps\slm-server\
@"
import urllib.request, json, sys

API_KEY = "xK8mP2nQrT5vW9yZ3aB6cE0fH4jL7oN1"  # your key
URL     = "http://localhost:8000/v1/chat/stream"

payload = json.dumps({
    "domain":       "amazon.in",
    "userPrompt":   "Does this site share my data with third parties?",
    "responseMode": "concise"
}).encode("utf-8")

req = urllib.request.Request(URL, data=payload, method="POST")
req.add_header("Content-Type", "application/json")
req.add_header("X-Ssense-API-Key", API_KEY)

print("Streaming response:")
with urllib.request.urlopen(req) as resp:
    for raw_line in resp:
        line = raw_line.decode("utf-8").strip()
        if line.startswith("data:"):
            chunk = line[5:].strip()
            try:
                event = json.loads(chunk)
                if event.get("event") == "token":
                    print(event["data"], end="", flush=True)
                elif event.get("event") == "done":
                    print("\n[stream complete]")
            except json.JSONDecodeError:
                pass
"@ | Out-File -FilePath test_chat.py -Encoding utf8

python test_chat.py

# Expected output:
# Streaming response:
# Based on Amazon.in's privacy policy, yes — the site shares personal
# data with third-party sellers and advertising partners. This raises
# concerns under Section 8(4) of the DPDP Act regarding data sharing
# without granular consent.
# [stream complete]
```

### 3e. Test that chat is blocked without an audit

```powershell
$body = @{
    domain       = "site-never-audited.example.com"
    userPrompt   = "What data do they collect?"
    responseMode = "concise"
} | ConvertTo-Json

# This should return "Please run an Audit on this site before chatting."
python -c "
import urllib.request, json
req = urllib.request.Request('http://localhost:8000/v1/chat/stream',
    data=b'$($body -replace \"'\",\"''\")',
    method='POST')
req.add_header('Content-Type', 'application/json')
req.add_header('X-Ssense-API-Key', 'xK8mP2nQrT5vW9yZ3aB6cE0fH4jL7oN1')
with urllib.request.urlopen(req) as r:
    print(r.read(500).decode())
"
```

### 3f. Force-refresh an audit

```powershell
$body = @{
    domain        = "amazon.in"
    policyUrl     = "https://www.amazon.in/gp/help/customer/display.html?nodeId=200545940"
    force_refresh = $true    # bypasses all 3 cache tiers, re-runs inference
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://localhost:8000/v1/audit/by-url" `
    -Method POST `
    -ContentType "application/json" `
    -Headers @{ "X-Ssense-API-Key" = "xK8mP2nQrT5vW9yZ3aB6cE0fH4jL7oN1" } `
    -Body $body

# source will be "inference" again (fresh run, not served from cache)
```

### 3g. Prometheus metrics

```powershell
curl.exe http://localhost:8000/metrics | Select-String "http_requests_total"

# Expected (some lines):
# http_requests_total{handler="/v1/audit/by-url",method="POST",status="2xx"} 2.0
# http_requests_total{handler="/v1/audit/{domain}",method="GET",status="2xx"} 3.0
```

---

## Phase 4 — Test full HMAC auth (through Nginx on port 443)

When the extension talks to the server, it goes through Nginx on port 443
with full HMAC-SHA256 signatures. Test this layer explicitly:

```powershell
# Save as test_hmac.py
@"
import hmac, hashlib, time, uuid, json, urllib.request, ssl

API_KEY     = "xK8mP2nQrT5vW9yZ3aB6cE0fH4jL7oN1"
HMAC_SECRET = "dF2gH5jK8mN1pQ4rS7tV0wX3yA6bC9eG2hJ5kL8nP1qR4s"
BASE_URL    = "https://localhost"   # through Nginx TLS

# The same signing algorithm used by api-client.ts
def sign(method, path, timestamp, nonce):
    payload = f"{method.upper()}:{path}:{timestamp}:{nonce}"
    return hmac.new(HMAC_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()

# Hit health endpoint (no HMAC needed — it's unauthenticated)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(f"{BASE_URL}/health")
with urllib.request.urlopen(req, context=ctx) as r:
    print("Health (no HMAC):", json.loads(r.read()))

# Hit audit endpoint with full HMAC
endpoint   = "/v1/audit/amazon.in"
ts         = str(int(time.time() * 1000))
nonce      = str(uuid.uuid4())
sig        = sign("GET", endpoint, ts, nonce)

req = urllib.request.Request(f"{BASE_URL}{endpoint}")
req.add_header("X-Ssense-API-Key",   API_KEY)
req.add_header("X-Ssense-Signature", sig)
req.add_header("X-Ssense-Timestamp", ts)
req.add_header("X-Ssense-Nonce",     nonce)

with urllib.request.urlopen(req, context=ctx) as r:
    data = json.loads(r.read())
    print(f"Audit (HMAC signed): trust_score={data['data']['dpdp_trust_score']}, source={data['source']}")

# Tampered signature test — must return 401
req2 = urllib.request.Request(f"{BASE_URL}{endpoint}")
req2.add_header("X-Ssense-API-Key",   API_KEY)
req2.add_header("X-Ssense-Signature", "invaliddeadbeef")
req2.add_header("X-Ssense-Timestamp", ts)
req2.add_header("X-Ssense-Nonce",     str(uuid.uuid4()))
try:
    urllib.request.urlopen(req2, context=ctx)
    print("ERROR: tampered sig should have been rejected!")
except urllib.error.HTTPError as e:
    print(f"Tampered signature correctly rejected: HTTP {e.code}")
"@ | Out-File -FilePath test_hmac.py -Encoding utf8

python test_hmac.py

# Expected output:
# Health (no HMAC): {'status': 'online', 'backend': 'vllm', ...}
# Audit (HMAC signed): trust_score=61, source=persistent_cache
# Tampered signature correctly rejected: HTTP 401
```

---

## Phase 5 — Build the extension

```powershell
# Navigate to extension directory
cd C:\Projects\Ssense\apps\extension

# Install dependencies
npm install
# Expected: added NNN packages in Ns

# Create .env.production — paste YOUR generated values
@"
VITE_SSENSE_SERVER_URL=https://localhost
VITE_SSENSE_API_KEY=xK8mP2nQrT5vW9yZ3aB6cE0fH4jL7oN1
VITE_SSENSE_HMAC_SECRET=dF2gH5jK8mN1pQ4rS7tV0wX3yA6bC9eG2hJ5kL8nP1qR4s
"@ | Out-File -FilePath .env.production -Encoding utf8

# Build the extension
npm run build

# Expected output:
# vite v5.x.x building for production...
# ✓ built in 890ms
# dist\background\service-worker.js
# dist\content\extractor.js
# dist\content\api-spoof.js
# dist\content\dark-pattern-blocker.js
# dist\content\chat-widget.js
# dist\popup.html
# dist\sidepanel.html
# dist\options.html

# Confirm dist folder was created
ls dist\
```

### Run the offline extractor test suite (no server, no npm extra installs)

```powershell
# Node 22 can run TypeScript directly with --experimental-strip-types
node --experimental-strip-types --test src\content\extractor.test.ts 2>&1

# Expected:
# ✔ WordPress: rel=privacy-policy in <head> wins over any footer link (2ms)
# ✔ meta[name=privacy-policy] authoritative discovery (0ms)
# ✔ Shopify-style /policies/ link found via footer scan (1ms)
# ✔ OneTrust-style cookie-banner noise does not shadow the real footer link (0ms)
# ... (14 more)
# ✔ link discovery succeeds on >= 90% of known-archetype fixtures (2ms)
# tests 18
# pass  18
# fail  0
```

---

## Phase 6 — Load the extension in Chrome

```powershell
# Open Chrome to the extensions page
Start-Process "chrome" "chrome://extensions"
```

In Chrome:

1. Toggle **Developer mode** ON (top-right corner)
2. Click **Load unpacked**
3. Select this folder: `C:\Projects\Ssense\apps\extension\dist`
4. Ssense shield icon appears in toolbar
5. **Note the Extension ID** shown under the Ssense card, e.g.:
   `abcdefghijklmnopqrstuvwxyzabcdef`

Now tighten CORS to only accept requests from this specific extension:

```powershell
# Update .env on the server with the real extension ID
cd C:\Projects\Ssense\apps\slm-server

# Replace * with your actual extension ID
$extensionId = "abcdefghijklmnopqrstuvwxyzabcdef"  # paste yours here
(Get-Content .env) -replace "SSENSE_ALLOWED_ORIGINS=\*", "SSENSE_ALLOWED_ORIGINS=chrome-extension://$extensionId" |
    Set-Content .env

# Restart server to pick up new CORS setting
docker compose --profile cpu up -d --force-recreate slm-server-cpu
```

---

## Phase 7 — End-to-end browser test

### 7a. Verify the extension connects

1. Click the Ssense shield icon in Chrome toolbar
2. Popup opens — you should see:

   ```
   🟢 Ssense AI — Connected
   Active on: (no active tab yet)
   [Open Privacy Panel]   [⚙️ Settings]
   ```

   If you see 🔴 or "unconfigured", jump to Troubleshooting §8.

### 7b. Trigger an audit in the browser

1. Navigate to `https://www.amazon.in` in Chrome
2. Wait 3–5 seconds
3. Click the Ssense shield icon → **Open Privacy Panel**
4. The Side Panel opens. After 5–30 seconds (CPU inference is slower than GPU):

   ```
   amazon.in     ⚠️ 61  Caution
   [History] [Policy] [Settings]  [Detailed] [Audit]  [🛡️ Shield]

   ⚠️ 3 Violations Found  ∨

   Trust Score    Subtlety Score
     61 / 100      74 / 100        [Export]

   "...Amazon shares your data with third-party sellers..."
   3. Unlawful Data Sharing  (Ref: Section 8(4) DPDP Act)
      [Click quote to highlight in page]
   ```

5. Type in the chat box:
   ```
   Is my location data being shared?
   ```
6. The AI responds in 5–20 seconds (CPU):
   ```
   Ssense AI
   Based on the audit of Amazon.in's policy, location data is shared with
   logistics partners and advertising vendors. Under Section 7(b) of the
   DPDP Act, granular consent is required before collecting location data...
   ```

### 7c. Verify local cache was populated

```powershell
# In a new PowerShell window
Invoke-RestMethod `
    -Uri "http://localhost:8000/v1/audit/amazon.in" `
    -Method GET `
    -Headers @{ "X-Ssense-API-Key" = "xK8mP2nQrT5vW9yZ3aB6cE0fH4jL7oN1" }

# Should show source = "hot_cache" or "persistent_cache"
# trust_score, violations all populated
```

In Chrome DevTools (F12 on any tab):

```javascript
// Paste into DevTools Console to see local cache
chrome.storage.local.get(null, (all) => {
    const auditKeys = Object.keys(all).filter(k => k.startsWith('audit:'));
    auditKeys.forEach(k => console.log(k, all[k].trust_score, all[k].violation_count + ' violations'));
});
// Expected:
// audit:amazon.in  61  3 violations
```

### 7d. Offline cache test

1. In Docker Desktop, stop the `ssense-slm-server-cpu` container
2. Revisit `amazon.in` in Chrome
3. Open Side Panel
4. The audit report still shows **from local cache** — score, all violations, legal reasoning
5. Restart the container: `docker compose --profile cpu up -d`

---

## Phase 8 — Troubleshooting

### Problem: Popup shows "AI service unavailable" or "Not configured"

```powershell
# 1. Check that the server is actually running
docker compose ps
# All should show "healthy"

# 2. Check if the server URL in the extension build matches
# (open dist\background\service-worker.js and search for "localhost")
Select-String -Path dist\background\service-worker.js -Pattern "localhost"

# 3. If you changed .env.production after the build, rebuild
npm run build

# 4. Reload the extension: chrome://extensions → Ssense → circular arrow icon
```

### Problem: "401 Unauthorized" when testing endpoints

```powershell
# Confirm the API key in your request matches what's in .env
cat C:\Projects\Ssense\apps\slm-server\.env | Select-String "SSENSE_API_KEYS"

# If you're testing through Nginx (:443), you ALSO need the HMAC signature
# Use test_hmac.py from Phase 4 as the reference
```

### Problem: `docker compose --profile cpu up` hangs at "Pulling"

```powershell
# Confirm Docker Desktop is running and WSL2 is enabled
docker info | Select-String "Server Version"

# Try pulling the base image manually first
docker pull redis:7.4-alpine
```

### Problem: Model download fails (network error inside container)

```powershell
# Check Docker's DNS and internet access
docker run --rm alpine wget -q https://huggingface.co -O /dev/null && echo "OK"

# If you're behind a corporate proxy, configure Docker Desktop:
# Settings → Resources → Proxies → set HTTP/HTTPS proxy
```

### Problem: `ollama` or `cuda` errors on CPU profile

```powershell
# CPU profile uses vLLM's CPU backend, NOT ollama. These errors mean the
# wrong profile was started. Verify:
docker compose ps --format "table {{.Name}}\t{{.Status}}"
# Should show: ssense-slm-server-CPU, not -gpu or -jetson

# If the wrong profile is running, stop everything and restart correctly:
docker compose --profile gpu  down  2>$null
docker compose --profile cpu  down  2>$null
docker compose --profile cpu  up -d
```

### Problem: Side panel opens but audit never completes

```powershell
# 1. Check service worker logs in Chrome:
#    chrome://extensions → Ssense → "service worker" link → Console tab

# 2. Check server logs for the incoming request:
docker compose logs slm-server-cpu --tail 50

# 3. Try a manual audit via the Audit button (toolbar) — this forces a fresh
#    FOUND_POLICY_URL → service worker → server flow

# 4. Check if the extension can reach localhost:
# In DevTools Console on any http page:
fetch("http://localhost:8000/health").then(r => r.json()).then(console.log)
# If CORS error: rebuild extension with VITE_SSENSE_SERVER_URL=http://localhost:8000
# (direct, bypassing Nginx) for development
```

### Problem: "No privacy policy link found" for a specific site

Some sites dynamically insert their footer (React/Next.js) and the policy
link is not in the DOM when `extractor.ts` runs at `document_idle`. Fix:

1. Navigate to the site's actual privacy policy page directly
2. Click **Audit** in the toolbar — the URL is the policy page itself
3. The extractor finds the canonical URL via `<link rel="privacy-policy">` in `<head>`, if present

---

## Phase 9 — Run the server security test suite

```powershell
cd C:\Projects\Ssense

# Run the unit tests (these run inside Python, no Docker needed)
# They test HMAC, Shannon entropy, schema repair, anti-extraction guard
python -m unittest apps\slm-server\tests\test_server_security.py -v

# Expected output:
# test_anti_extraction_guard ... ok
# test_hallucination_gate ... ok
# test_hmac_signature_valid ... ok
# test_hmac_timestamp_expired ... ok
# test_hmac_wrong_key ... ok
# test_schema_auto_repair ... ok
# test_shannon_entropy_high_input_blocked ... ok
# test_shannon_entropy_normal_input_passes ... ok
# Ran 8 tests in 0.007s
# OK
```

---

## Phase 10 — GPU testing (only if you have an NVIDIA GPU)

```powershell
# Confirm NVIDIA driver is visible to Docker
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
# Should show your GPU name and VRAM

# Stop CPU profile first
cd C:\Projects\Ssense\apps\slm-server
docker compose --profile cpu down

# Start GPU profile
docker compose --profile gpu up --build -d

# Wait for healthy (faster than CPU — model fits on VRAM)
docker compose ps

# GPU inference is 5-10x faster than CPU:
# - Audit: ~5 seconds vs ~60 seconds
# - Chat:  ~3 seconds vs ~20 seconds
```

---

## Quick reference — all commands

```powershell
# ── Server ──────────────────────────────────────────────────────────────────
cd C:\Projects\Ssense\apps\slm-server

docker compose --profile cpu up --build -d       # Start (CPU, first run downloads models)
docker compose --profile cpu up -d               # Start (subsequent runs, no rebuild)
docker compose --profile gpu up --build -d       # Start (GPU)
docker compose logs -f                           # Watch all logs
docker compose logs -f slm-server-cpu            # Server logs only
docker compose ps                                # Status of all containers
docker compose --profile cpu down                # Stop and remove containers (data safe)

# Health (no auth)
curl.exe http://localhost:8000/health

# Get cached audit (API key only, no HMAC needed on :8000 from localhost)
Invoke-RestMethod http://localhost:8000/v1/audit/amazon.in `
    -Headers @{ "X-Ssense-API-Key" = "YOUR_API_KEY" }

# Force new audit
Invoke-RestMethod http://localhost:8000/v1/audit/by-url -Method POST `
    -ContentType application/json `
    -Headers @{ "X-Ssense-API-Key" = "YOUR_API_KEY" } `
    -Body '{"domain":"amazon.in","policyUrl":"https://www.amazon.in/gp/help/customer/display.html?nodeId=200545940","force_refresh":true}'

# ── Extension ────────────────────────────────────────────────────────────────
cd C:\Projects\Ssense\apps\extension

npm install                                      # Install deps (once)
npm run build                                    # Build to dist\
node --experimental-strip-types --test src\content\extractor.test.ts  # Run tests

# ── Checks ───────────────────────────────────────────────────────────────────
python -m unittest apps\slm-server\tests\test_server_security.py -v
python test_hmac.py        # Full HMAC auth test through Nginx
python test_chat.py        # Chat streaming test
```

---

## Summary of what each test confirms

| Test | What it proves |
|------|---------------|
| `curl http://localhost:8000/health` | Server is up, vLLM loaded, RAG ready, SQLite cache open |
| Phase 3b — audit by URL | `policy_fetcher.py` can fetch + parse a real policy; vLLM inference runs; result stored in SQLite |
| Phase 3c — retrieve cached | SQLite 90-day cache works; hot-layer returns sub-ms on repeat calls |
| Phase 3d — chat stream | Chat is gated on audit; RAG retrieves DPDP law chunks; SSE streams token-by-token |
| Phase 3e — chat blocked | Audit gate correctly refuses chat for unknown domains |
| Phase 4 — HMAC test | Full HMAC-SHA256 signing works; tampered signatures are rejected; Nginx TLS terminates correctly |
| Phase 5 — `npm run build` | Extension TypeScript compiles clean; no type errors |
| Phase 5 — extractor tests | All 18 URL-discovery cases pass; language filter works; parse <50ms |
| Phase 6 — extension loaded | Extension connects to server via baked credentials; popup shows Connected |
| Phase 7a–7c — browser audit | Full end-to-end: extractor → FOUND_POLICY_URL → server → audit → local cache → UI |
| Phase 7d — offline cache | `audit-cache.ts` (chrome.storage.local) survives server being down |
| Phase 9 — security tests | HMAC verification, entropy filter, schema repair, anti-extraction guard all pass |
