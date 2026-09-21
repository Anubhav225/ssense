#!/usr/bin/env bash
# ==============================================================================
# docker-entrypoint.sh — Fix bind-mount ownership, then drop to non-root.
#
# THIS IS THE FIX FOR:
#   PermissionError: [Errno 13] Permission denied: '/app/models/base'
#
# Root cause: docker-compose.yml bind-mounts a HOST directory into the
# container (../../ml/models:/app/models:rw). That host directory is owned
# by whatever user/UID ran `docker compose up` (often root), NOT by the
# container's non-root `ssense` user. `USER ssense` in the Dockerfile makes
# the uvicorn process run as that non-root user from the very first
# instruction — so the moment ensure_models_exist() tries to
# `os.mkdir('/app/models/base')` to start downloading the base model, it
# hits a bind-mounted directory it doesn't own and can't write to. This is a
# "works in `docker build`, breaks in `docker compose up`" class of bug:
# there's no bind mount during a plain build, so it never surfaces there.
#
# Fix: the Dockerfiles now start the container AS ROOT (no `USER` directive
# at the end — see each Dockerfile), this entrypoint runs first as root,
# chowns just the writable data directories to `ssense`, and THEN drops to
# `ssense` via `gosu` before exec'ing the real command. The server process
# itself still never runs as root.
# ==============================================================================
set -euo pipefail

export PYTHONPATH="/app:${PYTHONPATH:-}"

if [ -f "/app/sitecustomize.py" ]; then
    cp /app/sitecustomize.py /usr/local/lib/python3.11/site-packages/sitecustomize.py 2>/dev/null || true
fi

for dir in "/app/models" "/app/.cache/huggingface" "/app/.cache/vllm" "/app/data"; do
    mkdir -p "$dir"
    current_owner="$(stat -c '%u' "$dir")"
    ssense_uid="$(id -u ssense)"
    if [ "$current_owner" != "$ssense_uid" ]; then
        echo "[entrypoint] Fixing ownership of $dir for non-root 'ssense' user (was uid $current_owner)..."
        chown -R ssense:ssense "$dir"
    fi
done

# OMP_NUM_THREADS: libgomp treats an EMPTY value as invalid ("libgomp:
# Invalid value for environment variable OMP_NUM_THREADS") — it needs either
# a real positive integer or to not be set at all. docker-compose.yml can't
# conditionally omit an env var (${SSENSE_CPU_THREADS:-} always expands to
# *something*, even if that something is ""), so that check has to happen
# here instead: only export OMP_NUM_THREADS when the operator actually gave
# us a value. Otherwise leave it unset so libgomp/vLLM fall back to their
# own core-count auto-detection.
if [ -n "${SSENSE_CPU_THREADS:-}" ]; then
    export OMP_NUM_THREADS="$SSENSE_CPU_THREADS"
    echo "[entrypoint] OMP_NUM_THREADS=$OMP_NUM_THREADS (from SSENSE_CPU_THREADS)"
else
    unset OMP_NUM_THREADS
fi

# ── Hardware Auto-Detection & Platform Configuration ───────────────────────────
echo "[entrypoint] Probing hardware environment for compute capabilities..."
DETECTED_HW="cpu"
if python3 -c "import torch; exit(0 if torch.cuda.is_available() and torch.cuda.device_count() > 0 else 1)" 2>/dev/null; then
    DETECTED_HW="gpu"
    if [ -f "/etc/nv_tegra_release" ] || [ -d "/sys/devices/soc0/family" ]; then
        DETECTED_HW="jetson"
    fi
fi

REQUESTED_PROFILE="${SSENSE_COMPUTE_PROFILE:-auto}"

if [ "$REQUESTED_PROFILE" = "auto" ] || [ -z "$REQUESTED_PROFILE" ]; then
    RESOLVED_PROFILE="$DETECTED_HW"
    echo "[entrypoint] Auto-detected hardware: $RESOLVED_PROFILE"
elif [ "$REQUESTED_PROFILE" = "gpu" ] && [ "$DETECTED_HW" = "cpu" ]; then
    echo "[entrypoint] ⚠️ Requested profile 'gpu', but no functional CUDA runtime was detected in container."
    echo "[entrypoint] ⚠️ Gracefully falling back to 'cpu' to prevent container startup crash."
    RESOLVED_PROFILE="cpu"
else
    RESOLVED_PROFILE="$REQUESTED_PROFILE"
fi

export SSENSE_COMPUTE_PROFILE="$RESOLVED_PROFILE"

if [ "$RESOLVED_PROFILE" = "cpu" ]; then
    export VLLM_TARGET_DEVICE="cpu"
    export VLLM_USE_V1=0
    echo "[entrypoint] ✅ Profile configured: CPU (VLLM_TARGET_DEVICE=cpu, VLLM_USE_V1=0)"
elif [ "$RESOLVED_PROFILE" = "jetson" ]; then
    export VLLM_TARGET_DEVICE="cuda"
    echo "[entrypoint] ✅ Profile configured: JETSON (VLLM_TARGET_DEVICE=cuda)"
else
    export VLLM_TARGET_DEVICE="cuda"
    echo "[entrypoint] ✅ Profile configured: GPU (VLLM_TARGET_DEVICE=cuda)"
fi

exec gosu ssense "$@"
