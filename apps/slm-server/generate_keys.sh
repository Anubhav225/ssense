#!/usr/bin/env bash
# ==============================================================================
# generate_keys.sh — Ssense SLM Server Cryptographic Key Generator (Wrapper)
#
# Convenient wrapper to run scripts/generate_keys.sh from the slm-server root.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/scripts/generate_keys.sh" "$@"
