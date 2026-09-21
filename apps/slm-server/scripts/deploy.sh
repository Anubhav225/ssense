#!/usr/bin/env bash
# ==============================================================================
# deploy.sh — Auto-detect hardware, launch the matching compose profile.
#
# Picks, in order:
#   1. jetson  — running ON a Jetson/L4T device itself (aarch64 + Tegra release
#                file present). Not "GPU present" in general — specifically
#                Jetson, since that has its own Dockerfile/base image.
#   2. gpu     — a real NVIDIA GPU that Docker can actually hand to a
#                container (checked with a real `--gpus all` test container,
#                not just "does nvidia-smi exist on the host" — those are two
#                different things: the host driver can be fine while the
#                NVIDIA Container Toolkit isn't installed/configured, which
#                is a very common way "we have a GPU" deploys still silently
#                end up running the gpu profile with no GPU passthrough and
#                failing confusingly later instead of just using cpu).
#   3. cpu     — fallback, always works.
#
# Usage:
#   ./scripts/deploy.sh              # detect + up -d (detached)
#   ./scripts/deploy.sh --logs       # detect + up (attached, streaming logs)
#   ./scripts/deploy.sh --force-cpu  # skip detection, always use cpu
#   ./scripts/deploy.sh --force-gpu  # skip detection, always use gpu
#
# Windows/Docker Desktop note: run this from WSL or Git Bash, not raw
# PowerShell (PowerShell can't execute .sh directly). From PowerShell:
#     wsl bash ./scripts/deploy.sh
# ==============================================================================
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."   # apps/slm-server — where docker-compose.yml lives

DETACHED="-d"
FORCE_PROFILE=""
for arg in "$@"; do
    case "$arg" in
        --logs)       DETACHED="" ;;
        --force-cpu)  FORCE_PROFILE="cpu" ;;
        --force-gpu)  FORCE_PROFILE="gpu" ;;
        --force-jetson) FORCE_PROFILE="jetson" ;;
        *) echo -e "${RED}Unknown argument: $arg${NC}"; exit 1 ;;
    esac
done

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}   Ssense SLM Server — Auto-Detecting Deploy Target    ${NC}"
echo -e "${BLUE}======================================================${NC}\n"

# ------------------------------------------------------------------------------
# Detection
# ------------------------------------------------------------------------------
is_jetson() {
    [ "$(uname -m)" == "aarch64" ] && [ -f /etc/nv_tegra_release ]
}

docker_can_use_gpu() {
    # The real test: can Docker actually attach a GPU to a container right
    # now? `nvidia-smi` existing on the host only proves the driver is
    # there — it says nothing about whether the NVIDIA Container Toolkit is
    # installed and Docker's daemon is configured to use it, which is the
    # actual requirement for `deploy.resources.reservations.devices` in
    # docker-compose.yml to work. Using a tiny existing-locally-or-cheap
    # image keeps this fast and offline-friendly.
    command -v docker &>/dev/null || return 1
    docker run --rm --gpus all alpine:3.20 sh -c 'exit 0' &>/dev/null
}

PROFILE=""
REASON=""

if [ -n "$FORCE_PROFILE" ]; then
    PROFILE="$FORCE_PROFILE"
    REASON="forced via command-line flag"
elif is_jetson; then
    PROFILE="jetson"
    REASON="Jetson/L4T device detected (aarch64 + /etc/nv_tegra_release)"
elif docker_can_use_gpu; then
    PROFILE="gpu"
    GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)"
    REASON="Docker can attach an NVIDIA GPU (${GPU_NAME:-detected})"
else
    PROFILE="cpu"
    if command -v nvidia-smi &>/dev/null; then
        REASON="NVIDIA driver found, but Docker cannot use it — is the NVIDIA Container Toolkit installed? Falling back to CPU"
    else
        REASON="no usable GPU detected"
    fi
fi

echo -e "${GREEN}[✓] Selected profile: ${NC}${PROFILE}"
echo -e "${BLUE}[i] Reason: ${NC}${REASON}\n"

if [ "$PROFILE" == "cpu" ] && [ -z "$FORCE_PROFILE" ] && command -v nvidia-smi &>/dev/null; then
    echo -e "${YELLOW}[!] You have an NVIDIA GPU but Docker can't reach it — running on CPU will work but be much slower.${NC}"
    echo -e "${YELLOW}    Install the NVIDIA Container Toolkit (https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html),${NC}"
    echo -e "${YELLOW}    restart Docker, then re-run this script — or pass --force-gpu once that's done.${NC}\n"
fi

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}[!] No .env found — run.sh normally generates one with a fresh SSENSE_SERVER_KEY.${NC}"
    echo -e "${YELLOW}    Continuing with docker-compose.yml's built-in defaults; set up .env before real deployment.${NC}\n"
fi

# ------------------------------------------------------------------------------
# Launch
# ------------------------------------------------------------------------------
echo -e "${BLUE}[i] Running: docker compose --profile ${PROFILE} up --build ${DETACHED}${NC}\n"
# shellcheck disable=SC2086
docker compose --profile "$PROFILE" up --build $DETACHED

if [ -n "$DETACHED" ]; then
    echo -e "\n${GREEN}[✓] Started in background. Follow logs with:${NC}"
    echo -e "    docker compose logs -f slm-server-${PROFILE}"
    echo -e "${GREEN}[✓] Check health with:${NC}"
    echo -e "    docker compose ps"
fi
