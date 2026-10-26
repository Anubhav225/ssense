# Ssense — Hardware Detection, Docker Hardening & Rate Limiting Upgrade

> **Historical changelog.** Section 1 below concerns `apps/native-daemon`,
> which has since been removed from the project entirely. It is retained
> as a record of what changed at the time, not as current documentation.
> See `docs/DEPLOYMENT.md` for the live setup.

## 1. Native daemon: build-time hardware detection (`apps/native-daemon/scripts/build.sh`)

GPU support (`llama-cpp-2`'s `cublas`/`metal` Cargo features) was already
correctly *implemented*, but nothing chose the feature for you — you had to
know your own hardware and remember `--features cublas`. `build.sh` now:

- Detects an NVIDIA GPU via `nvidia-smi` (and verifies it actually responds,
  not just that the binary exists), or Apple Silicon via `uname -m`.
- Confirms a CUDA Toolkit (`nvcc`) is present before attempting a `cublas`
  build — falls back to CPU-only with a clear warning instead of a confusing
  compile failure if the toolkit is missing.
- Checks total system RAM against the daemon's real requirements (5100MB
  hard floor, matching `hardware_profiler.rs`'s `MIN_REQUIRED_RAM_MB`; 9600MB
  recommended for keeping both GGUF models warm) and **warns, never
  hard-fails** — consistent with `hardware_profiler.rs`'s own philosophy of
  letting mmap page rather than blocking install on marginal hardware.
- Supports `--force-cpu` / `--force-cublas` / `--force-metal` for CI or
  cross-compilation scenarios where auto-detection is wrong (e.g. building on
  a CPU-only CI runner for a GPU target host).

`hardware_profiler.rs`'s `has_gpu_acceleration` is still a `cfg!(feature=...)`
check — that's correct and unchanged; the fix was upstream of it, at build
time.

## 2. SLM server: CUDA-version-matched Torch installer (`apps/slm-server/scripts/install_torch.sh`)

For the two cases where no base image pins Torch for you (bare-metal/VM
GPU installs outside Docker, or reusing the CPU requirements path on a GPU
host by mistake):

1. Detects the GPU driver's **max supported CUDA runtime** by parsing
   `nvidia-smi`'s own banner (works even without a CUDA Toolkit installed).
2. Maps that to the newest PyTorch `cuXXX` wheel tag the driver can actually
   run (CUDA is backwards-compatible — never picks a tag newer than the
   driver supports).
3. Installs the pinned Torch version against that index; falls back cleanly
   to the CPU wheel if no GPU/driver is found or the version can't be parsed.
4. Runs a post-install sanity check (`torch.cuda.is_available()`).

The `gpu` Docker profile is unaffected — it correctly inherits Torch from
`vllm/vllm-openai:v0.27.1`, which is already CUDA-matched by NVIDIA/vLLM
upstream and must not be overwritten (this is called out in
`requirements.txt`'s existing "do NOT uncomment" note).

## 3. Docker hardening

- Added `.dockerignore` (keeps `.env`, certs, models, caches, and dev
  artifacts out of build context/images).
- All three server Dockerfiles (`gpu`, `cpu`, `jetson`) now create and switch
  to a non-root `ssense` user before `CMD` runs. GPU/device access is via
  group/world-readable device nodes passed through by the container runtime,
  not root ownership, so this doesn't affect acceleration — flagged with a
  fallback note on the Jetson file specifically, since L4T device-node
  permissions vary more by image/JetPack version than desktop/DGX Linux.

## 4. Rate limiting: Redis-backed, Nginx-fronted, defense in depth

Three independent layers now exist, each catching what the others don't:

| Layer | Scope | Granularity | Survives restart? |
|---|---|---|---|
| Nginx `limit_req`/`limit_conn` | Network edge, before the app | Per-IP **and** per-API-key (new `map`-based zone) | No (in-memory to Nginx, but cheap/fast) |
| Nginx `/v1/audit`-specific zone | The one endpoint that triggers a full LLM generation | Per-IP, `2r/s` | No |
| App-level sliding window (`security.py` → `memory_orchestrator.py`) | Per API-key + IP combo | Exact request counting, 60/min default | **Yes, if Redis is configured** |

The app-level limiter was previously correct but strictly per-process
in-memory (fine for the single `--workers 1` vLLM process, but resets on
every restart and can't be shared if you ever run multiple `slm-server`
replicas behind Nginx for horizontal scaling). New `redis_limiter.py`:

- Implements the exact same sliding-window semantics as a single atomic Lua
  script (`ZADD`/`ZREMRANGEBYSCORE`/`ZCARD` in one round trip — no
  check-then-act race under concurrent load).
- Activates automatically when `SSENSE_REDIS_URL` is set; the app **pings
  Redis once at startup** (`memory_orchestrator.verify_rate_limiter_backend`)
  and falls back to the in-memory limiter with a loud warning if it's
  unreachable, rather than silently degrading on the first request.
- Ships as its own `redis` Compose service (`redis:7.4-alpine`,
  `--appendonly yes` for persistence across restarts, capped at 256MB with
  `allkeys-lru` eviction so it can never become the resource bottleneck) with
  a health-checked `depends_on` on every profile (gpu/cpu/jetson).
- `get_client_ip()` in `security.py` now only trusts `X-Forwarded-For` when
  the direct TCP peer is on a private/Docker network range or loopback —
  previously any client could spoof this header and defeat every IP-keyed
  limit, at both the Nginx and app layers.

**Nothing about this requires a domain.** All three Nginx configs still use
`server_name _;` with a self-signed cert (`nginx/certs/`), which works
correctly for any hostname or bare IP. When a real domain is bought/decided,
the only change needed is swapping `ssl_certificate`/`ssl_certificate_key` to
a CA-issued cert (e.g. via certbot) and, optionally, replacing `server_name
_;` with the actual domain to reject requests for other Host headers — the
rate limiting, headers, and routing above don't need to change at all.

## 5. Other SOTA features worth integrating next

Roughly in priority order:

1. **Grafana dashboard on top of the existing `/metrics`.** Correction after
   double-checking `main.py`: `Instrumentator().instrument(app).expose(app,
   endpoint="/metrics")` and the circuit breaker (`check_circuit_breaker` /
   `increment_jobs` / `decrement_jobs` around both the audit and chat
   handlers) are **already wired up** — that groundwork is done. What's
   missing is the visualization/alerting layer: add a Prometheus + Grafana
   pair to `docker-compose.yml` (or point at an existing org-wide
   Prometheus) scraping `/metrics` behind the same API-key auth, and put a
   dashboard on `total_inferences`/`avg_tokens_per_second`-equivalent
   histograms, `active_jobs_count` vs `SSENSE_MAX_QUEUE_DEPTH`, and Redis
   rate-limit rejection rate. Also worth exposing vLLM's own internal
   `/metrics` (queue depth, KV cache utilization, LoRA swap latency) behind
   the same auth for full-stack visibility.
2. **Structured JSON logging** in the SLM server (currently `print()`
   throughout `main.py`/`engine.py`/`memory_orchestrator.py`). Swap for
   `structlog` or stdlib `logging` with a JSON formatter so logs are
   queryable once you have more than one replica — directly useful once
   Redis-backed rate limiting makes multi-replica deployment realistic.
3. **API key scoping / tiers.** `ENTERPRISE_API_KEYS` already exists as a
   distinct set in `security.py` but isn't yet used to grant a different
   rate limit or model priority — an easy next step given the Redis limiter
   now supports per-key limits natively (just look up the tier's limit
   before calling `check_rate_limit`).
4. **Blue/green or canary LoRA rollout.** Since LoRAs are hot-swapped
   per-request already (`self.lora_requests` dict in `engine.py`), versioning
   adapter paths (`audit_lora_v2`) and routing a small % of traffic to a new
   adapter before full rollout is a small change with real production value
   once you're iterating on the LoRAs post-launch.
5. **Automated cert renewal** once a real domain exists — a small
   `certbot` sidecar container (webroot or DNS-01 challenge depending on
   whether ports 80/443 stay public) rather than a manual cert swap, so
   the current self-signed setup can flip to a real cert without re-touching
   Nginx config by hand each renewal.
6. **WAF / fail2ban-style IP banning** in front of Nginx for sustained
   abusers that blow through `limit_req` repeatedly (e.g. `fail2ban` tailing
   Nginx's access log for repeated 429s, or Cloudflare/similar once a domain
   exists) — the current setup rate-limits but never *bans*, so a persistent
   attacker just gets throttled forever rather than blocked.
