#!/usr/bin/env bash
# ==============================================================================
# install_torch.sh — CUDA-Version-Aware Torch Installer
#
# The gpu profile inherits torch from the vllm/vllm-openai base image (already
# CUDA-matched by NVIDIA/vLLM upstream) and never runs this script. This
# script exists for two cases where NO base image pins torch for you:
#   1. Building slm-server OUTSIDE Docker directly on a bare-metal / VM GPU
#      host (e.g. a DGX box provisioned before containerization, or local dev).
#   2. The `cpu` profile's requirements-cpu.txt, which currently hardcodes
#      `--extra-index-url https://download.pytorch.org/whl/cpu` — fine for
#      CPU, but if this same requirements file/script is reused on a GPU host
#      it would silently install a CPU-only torch and disable acceleration.
#
# This script:
#   1. Detects whether an NVIDIA GPU + driver are present (nvidia-smi).
#   2. If present, reads the driver's MAX SUPPORTED CUDA runtime version
#      (nvidia-smi reports this even if no CUDA toolkit is installed).
#   3. Maps that to the newest PyTorch CUDA wheel index the driver can run
#      (PyTorch only ships a handful of cuXXX wheel tags at a time — this
#      picks the highest tag <= driver capability, never a tag the driver
#      can't support).
#   4. Installs the pinned torch version against that index. If no GPU is
#      found, installs the CPU wheel instead.
#
# Usage:
#   ./scripts/install_torch.sh                 # auto-detect
#   TORCH_VERSION=2.13.0 ./scripts/install_torch.sh   # override pinned version
# ==============================================================================
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'

TORCH_VERSION="${TORCH_VERSION:-2.13.0}"

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}   Ssense SLM Server — CUDA-Aware Torch Installer      ${NC}"
echo -e "${BLUE}======================================================${NC}\n"

# ------------------------------------------------------------------------------
# STEP 1: GPU + DRIVER DETECTION
# ------------------------------------------------------------------------------
if ! command -v nvidia-smi &>/dev/null; then
    echo -e "${YELLOW}[i] No nvidia-smi found — no NVIDIA GPU/driver present.${NC}"
    echo -e "${YELLOW}    Installing CPU-only torch build.${NC}"
    pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
        "torch==${TORCH_VERSION}"
    echo -e "\n${GREEN}[✓] Installed torch ${TORCH_VERSION} (CPU build).${NC}"
    exit 0
fi

if ! nvidia-smi &>/dev/null; then
    echo -e "${RED}[✗] nvidia-smi is present but returned an error — driver may be broken or GPU not attached.${NC}"
    echo -e "${YELLOW}    Falling back to CPU-only torch build so installation can proceed.${NC}"
    pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
        "torch==${TORCH_VERSION}"
    exit 0
fi

DRIVER_CUDA_VERSION="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)"
# nvidia-smi's top-right "CUDA Version:" banner reflects the MAX CUDA runtime
# the installed driver supports — parse it from the full text output since
# --query-gpu doesn't expose it directly.
MAX_CUDA="$(nvidia-smi | grep -oP 'CUDA Version:\s*\K[0-9]+\.[0-9]+' | head -1)"
GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"

echo -e "${GREEN}[✓] GPU detected:${NC} $GPU_NAME"
echo -e "${GREEN}[✓] Driver version:${NC} $DRIVER_CUDA_VERSION"
echo -e "${GREEN}[✓] Max supported CUDA runtime:${NC} $MAX_CUDA"

if [ -z "$MAX_CUDA" ]; then
    echo -e "${YELLOW}[!] Could not parse max CUDA version from nvidia-smi output.${NC}"
    echo -e "${YELLOW}    Falling back to CPU-only torch to avoid installing an incompatible wheel.${NC}"
    pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
        "torch==${TORCH_VERSION}"
    exit 0
fi

# ------------------------------------------------------------------------------
# STEP 2: MAP DRIVER CAPABILITY -> BEST AVAILABLE PYTORCH WHEEL TAG
#
# PyTorch publishes a small, discrete set of CUDA wheel tags per release
# (e.g. cu118, cu121, cu124, cu126, cu128...). Pick the HIGHEST tag the
# driver's max-supported CUDA version can still run (CUDA is
# backwards-compatible: a driver that supports CUDA 12.6 can run a cu121 or
# cu124 wheel, but never a cu128 wheel).
# ------------------------------------------------------------------------------
# Ordered oldest -> newest; keep in sync with whatever tags
# download.pytorch.org actually serves for TORCH_VERSION at deploy time.
CUDA_TAGS=("11.8:cu118" "12.1:cu121" "12.4:cu124" "12.6:cu126" "12.8:cu128")

BEST_TAG=""
for entry in "${CUDA_TAGS[@]}"; do
    tag_cuda="${entry%%:*}"
    tag_name="${entry##*:}"
    # Numeric comparison via sort -V so "12.10" > "12.8" is handled correctly.
    if [ "$(printf '%s\n%s\n' "$tag_cuda" "$MAX_CUDA" | sort -V | head -1)" == "$tag_cuda" ]; then
        BEST_TAG="$tag_name"
    fi
done

if [ -z "$BEST_TAG" ]; then
    echo -e "${RED}[✗] Driver's max CUDA ($MAX_CUDA) is older than the oldest wheel tag we support (11.8).${NC}"
    echo -e "${RED}    Update the NVIDIA driver before installing GPU torch. Falling back to CPU build.${NC}"
    pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
        "torch==${TORCH_VERSION}"
    exit 0
fi

echo -e "${BLUE}[i] Selected PyTorch wheel index: ${NC}${BEST_TAG}"

# ------------------------------------------------------------------------------
# STEP 3: INSTALL
# ------------------------------------------------------------------------------
pip install --no-cache-dir \
    --extra-index-url "https://download.pytorch.org/whl/${BEST_TAG}" \
    "torch==${TORCH_VERSION}"

echo -e "\n${GREEN}[✓] Installed torch ${TORCH_VERSION} (${BEST_TAG}) matched to driver max CUDA ${MAX_CUDA}.${NC}"

# ------------------------------------------------------------------------------
# STEP 4: SANITY CHECK
# ------------------------------------------------------------------------------
python3 -c "
import torch
print(f'[Verify] torch {torch.__version__} | cuda available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'[Verify] device: {torch.cuda.get_device_name(0)}')
" || echo -e "${YELLOW}[!] Post-install verification failed to import torch — check the log above.${NC}"
