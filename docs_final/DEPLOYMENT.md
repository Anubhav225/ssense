# Ssense — Deployment & Operations Guide

This is the real, in-order sequence to stand up the SLM server and connect
the extension to it. Written for whoever runs the server (your "friend" /
ops person), not end users — see `USER_MANUAL.md` for that.

> This file previously described a different, older architecture (separate
> `vllm-engine` / `slm-gateway` / `redis-queue` / `qdrant-db` containers). The
> server has since been consolidated into a **single unified FastAPI
> container per hardware profile** (vLLM runs in-process — see
> `SLM_Server_Architecture.md`), fronted by Nginx, with one shared Redis
> instance used only for the chat rate limiter. This revision matches that
> actual `docker-compose.yml`.

---

## 1. Prerequisites

- A machine matching one of the three supported profiles:
  - **gpu** — a discrete NVIDIA GPU. The engine self-caps at 32GB of usage
    regardless of card size (see `engine.py::TARGET_TOTAL_MEMORY_GB`), so
    24GB+ VRAM is the practical minimum.
  - **jetson** — an NVIDIA Jetson AGX-class device (Orin/Spark). GPU+CPU
    share one unified memory pool; the jetson profile budgets for that
    conservatively (see `engine.py::_build_jetson_args`).
  - **cpu** — no GPU at all, using vLLM's native CPU backend. Needs a CPU
    with AVX512-BF16/AMX support (modern Intel Xeon Scalable, Sapphire
    Rapids+) for realistic bfloat16 throughput — vLLM raises a clear error
    at boot on unsupported CPUs rather than silently downgrading precision.
- Docker + Docker Compose. For `gpu`/`jetson`, the NVIDIA Container Toolkit
  (`nvidia-ctk`) must be installed and configured as the Docker daemon's
  default runtime — standard on JetPack for Jetson, install separately for
  a discrete-GPU host.
- A domain name pointed at this machine, if deploying to production
  (self-signed certs work for local/dev only — see §3).

---

## 2. First-time setup

```bash
cd apps/slm-server
cp .env.example .env
```

Generate the two required secrets — **the server refuses to boot in
production (`SSENSE_ENV=production`) without real values here**:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # → SSENSE_API_KEYS
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # → SSENSE_HMAC_SECRET
```

Edit `.env` (see `.env.example` for the full list with explanations):
```ini
SSENSE_ENV=production
SSENSE_API_KEYS=<generated value>
SSENSE_ENTERPRISE_API_KEYS=          # optional; currently unused by the code
                                      # (no priority-queue logic exists yet)
SSENSE_HMAC_SECRET=<generated value>
SSENSE_ALLOWED_ORIGINS=              # restrict to chrome-extension://<id>
```

**These are real secrets — set them directly on the server (this `.env`
file, read by Docker Compose) and nowhere else.** Never commit them, never
send them over any network path other than however you deploy this `.env`
itself (SSH, a systemd `EnvironmentFile`, or your CI/CD's own secrets
store). See `docs/SECURITY.md` for why this matters more than it might
seem for a project whose extension is public.

The **same** generated values also go into `apps/extension/.env.production`
(copy `.env.production.example`) so they're baked into the extension build
— see `docs/SECURITY.md` "Two different things that both get called 'the
secret'" for why that's a deliberate, different trust model from the copy
that lives here, not an oversight. Ordinary users of the published
extension never see or enter these values themselves.

Alternatively, `scripts/run.sh` will auto-generate a starter `.env` (with
fresh, cryptographically random keys, and automatic key rotation every ~10
months) the first time you run it — but it still leaves
`SSENSE_ALLOWED_ORIGINS=*`, which you should tighten before real production
traffic.

---

## 3. TLS certificates

See `apps/slm-server/nginx/certs/README.md` for the full instructions.
Short version:

**Local/dev (self-signed):**
```bash
cd apps/slm-server/nginx/certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssense.key -out ssense.crt -subj "/CN=localhost"
```

**Production:** use Let's Encrypt or your org's CA — place the issued
files at `ssense.crt` / `ssense.key` in that same directory, and set up
automatic renewal (Let's Encrypt certs expire every 90 days). There is no
`SSENSE_DOMAIN` env var to set: `nginx/nginx.*.conf` use a catch-all
`server_name _;`, so Nginx doesn't need your domain name — it just needs
DNS pointed at the host and a matching certificate in place.

---

## 4. Bring the stack up

Pick the profile that matches your hardware and pass it explicitly —
`docker compose` builds/starts nothing by default without one:

```bash
cd apps/slm-server

docker compose --profile gpu    up --build -d   # discrete NVIDIA GPU
docker compose --profile jetson up --build -d   # Jetson AGX-class device
docker compose --profile cpu    up --build -d   # no GPU
```

Or use the interactive helper, which also handles first-run `.env`
generation and key rotation for you (GPU profile by default):
```bash
chmod +x scripts/run.sh   # first time only, Linux/macOS
./scripts/run.sh
```

```bash
docker compose ps
```
Everything should reach `healthy`, not just `running`. The `slm-server-*`
container's healthcheck allows a **90s start period** (`180s` on the `cpu`
profile) for the ~15GB base model + LoRA adapters to load — a long wait
here on first boot is normal, not a failure. `nginx-<profile>` won't report
healthy until `slm-server-<profile>` does (`depends_on: condition:
service_healthy`), and both depend on the shared `redis` service being
healthy first.

Watch first-boot model download/load progress:
```bash
docker compose logs -f slm-server-gpu   # or -cpu / -jetson
```

Confirm the whole path works end-to-end:
```bash
curl -k https://localhost/health
```
(`-k` skips cert validation, only needed against a self-signed dev cert.)

---

## 5. Tuning for your actual hardware

Every profile self-caps total model+KV-cache usage at **32GB**
(`engine.py::TARGET_TOTAL_MEMORY_GB`) regardless of the card/box's real
capacity — on a bigger GPU this leaves real headroom unused. To raise it:
edit `TARGET_TOTAL_MEMORY_GB` in `engine.py` and rebuild the image
(`docker compose --profile gpu up --build -d`); there's no env var for
this today.

`max_num_seqs` (the actual measured concurrency ceiling, i.e. how many
sequences vLLM runs on the GPU/CPU at once) is set per-profile directly in
`engine.py::_build_gpu_args` / `_build_jetson_args` / `_build_cpu_args` —
256 (gpu) / 16 (jetson) / 8 (cpu) as shipped. After first boot, watch
`docker compose logs -f slm-server-<profile>` for vLLM's own KV-cache
sizing output and for `Sequence group ... preempted` warnings under load —
that's vLLM telling you `max_num_seqs` is set too high for the real memory
available for that hardware. Adjust the constant down (and rebuild) if you
see that; raise it if you have consistent headroom and want more
throughput.

---

## 6. Operational notes

**Redis is internal-only, on purpose.** The `redis` service does not
publish a host port (only `expose: 6379`, reachable inside the Docker
compose network) — it backs the distributed chat rate limiter
(`redis_limiter.py`) and persists to a named volume so limits survive
restarts. Do not add a `ports:` mapping for it in production.

**Nginx is the only public entry point.** `slm-server-<profile>` itself has
no host port mapping either (only `expose: 8000`) — everything goes
through Nginx on 80/443. This gives you SSE-correct streaming
(`proxy_buffering off` on `/v1/chat/stream` and `/v1/audit` specifically),
TLS termination, and a first line of rate/connection limiting before
requests ever reach the app.

**"10,000 concurrent users" means held-open connections, not simultaneous
GPU-resident requests.** `SSENSE_MAX_QUEUE_DEPTH` (default 5000, in `.env`)
caps how many requests (audit + chat combined) can be in flight — held
open as async connections — before new ones get a 503; only `max_num_seqs`
(§5) are ever actually running against the GPU/CPU at once. This is
correct, deliberate design, not a shortfall — see
`docs/SLM_Server_Architecture.md` for the full math.

**Logs:**
```bash
docker compose logs -f slm-server-gpu   # app-level request handling, inference, security events
docker compose logs -f nginx-gpu        # proxy-level access/error logs
docker compose logs -f redis            # rate-limiter backend
```
(swap `-gpu` for `-cpu`/`-jetson` to match your profile)

**Restarting after a `.env` change:**
```bash
docker compose --profile gpu up -d --force-recreate slm-server-gpu
```

---

## 7. What's actually persisted, and how to migrate to a new server

**There is no separate "user database."** Auth is pre-shared API key +
HMAC secret (`SSENSE_API_KEYS`/`SSENSE_HMAC_SECRET` in `.env`) — there are
no user accounts to migrate. The stateful things that *do* exist:

| What | Where | Volume | Matters for migration? |
|---|---|---|---|
| Audit result cache (SQLite, 90-day TTL) | `/app/data/ssense_audit_cache.db` in the container | named volume `audit-data` | **Yes** — this is the thing worth carrying over |
| Chat rate-limit windows / replay nonces | Redis | named volume `redis-data` | No — safe to lose, just resets rate-limit counters |
| Base model + LoRA adapters + RAG embeddings | `../../ml/models` on the host | bind mount, not a Docker volume | Only if you don't want to re-download; these are also re-creatable via `ensure_models_exist()` on first boot |
| HuggingFace download cache | `~/.cache/huggingface` on the host | bind mount | No — pure re-download cache |

Both `audit-data` and `redis-data` were previously **not persisted at
all** — the audit cache in particular lived only in the container's
writable layer, so a plain `docker compose down` / `--force-recreate` /
image rebuild silently wiped 90 days of cached audits with no warning.
Fixed: `docker-compose.yml` now mounts both as named volumes, and each
`Dockerfile.*` creates `/app/data` with the correct non-root ownership
before the volume is ever mounted (a fresh named volume otherwise gets
created root-owned, which would make every write silently fail once the
app's `ssense` user tries to open the SQLite file for writing).

**To move to a new AWS instance / VPS:**

```bash
# On the OLD server — back up the two volumes to a single tarball:
docker run --rm \
  -v audit-data:/from-audit -v redis-data:/from-redis \
  -v "$(pwd)":/backup alpine \
  tar czf /backup/ssense-state-backup.tar.gz -C / from-audit from-redis

scp ssense-state-backup.tar.gz you@new-server:/path/to/apps/slm-server/
```

```bash
# On the NEW server — create the (empty) named volumes once, then restore into them:
cd apps/slm-server
docker compose --profile <gpu|cpu|jetson> up -d   # creates the named volumes on first boot
docker compose --profile <gpu|cpu|jetson> down     # stop before overwriting their contents

docker run --rm \
  -v audit-data:/to-audit -v redis-data:/to-redis \
  -v "$(pwd)":/backup alpine \
  tar xzf /backup/ssense-state-backup.tar.gz -C /

docker compose --profile <gpu|cpu|jetson> up -d   # back online, with the old audit cache intact
```

Everything else — the repo checkout itself (including `ml/models` if you
want to skip re-downloading), your `.env` secrets, and your TLS certs in
`nginx/certs/` — just needs a normal file copy (`rsync`/`scp`/`git clone`
+ re-adding the secrets) to the new box; none of it is tied to the old
host's IP or hostname.

## 8. Full request lifecycle (for reference)

1. Extension content script extracts the privacy-policy URL (or, on the
   legacy path, the extracted text) from the current page.
2. Sent to the background service worker, which signs the request
   (HMAC-SHA256 + nonce + timestamp) and posts it to Nginx over HTTPS.
3. Nginx terminates TLS, applies coarse rate/connection limiting (with a
   separate, stricter zone just for the heavy `/v1/audit` endpoint), and
   proxies to `slm-server-<profile>:8000` with buffering disabled for the
   SSE routes.
4. `main.py` (FastAPI) verifies the API key + HMAC signature + nonce
   (replay-checked, Redis-backed when `SSENSE_REDIS_URL` is reachable),
   checks for prompt-injection/extraction patterns (`security.py`), then
   either serves a cached audit or runs inference in-process via
   `engine.py`'s `AsyncLLMEngine` (vLLM, multi-LoRA: audit vs chatbot
   adapter).
5. For chat, the request is gated on a completed audit existing for that
   domain, augmented with retrieved DPDP statute context
   (`rag_engine.py`, hybrid BM25 + BGE dense search), and streamed back as
   Server-Sent Events; identical concurrent requests are coalesced onto a
   single in-flight generation (`memory_orchestrator.py`).
6. The extension's SSE client consumes the stream, and the result is
   persisted locally (audit → `audit-cache.ts`, chat → `chat-store.ts`) and
   shown in the UI.
