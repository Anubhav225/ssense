#!/usr/bin/env bash
# ==============================================================================
# generate_keys.sh — Ssense SLM Server Cryptographic Key Generator
#
# Inspects apps/slm-server/.env and automatically generates cryptographically
# secure server-side keys (API Keys, HMAC Secret, Admin Token) if missing
# or empty. Preserves all existing configuration.
#
# Usage:
#   ./scripts/generate_keys.sh          # Generate missing keys in .env
#   ./scripts/generate_keys.sh --force  # Force-regenerate/rotate all keys
#   ./scripts/generate_keys.sh --show   # Show current keys without modifying
#   ./scripts/generate_keys.sh --help   # Show usage and options
# ==============================================================================
set -euo pipefail

# ANSI color codes
BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

# ── Parse Arguments ───────────────────────────────────────────────────────────
FORCE_REGEN=0
SHOW_ONLY=0
CUSTOM_ENV=""

print_help() {
  cat << EOF
Ssense SLM Server Key Generator

Usage:
  $(basename "$0") [options]

Options:
  -f, --force       Force re-generate / rotate all server-side keys in .env
  -s, --show        Display existing keys from .env without making any changes
  -e, --env <path>  Specify path to .env file (default: auto-detected in slm-server)
  -h, --help        Show this help message and exit

Keys Managed:
  • SSENSE_API_KEYS     - Pre-shared client API key (X-Ssense-API-Key)
  • SSENSE_HMAC_SECRET  - HMAC-SHA256 request signing secret (X-Ssense-Signature)
  • SSENSE_ADMIN_TOKEN  - Secret token for administrative access (/v1/admin/*)

EOF
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--force)
      FORCE_REGEN=1
      shift
      ;;
    -s|--show)
      SHOW_ONLY=1
      shift
      ;;
    -e|--env)
      CUSTOM_ENV="$2"
      shift 2
      ;;
    -h|--help)
      print_help
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      echo "Use --help for usage details."
      exit 1
      ;;
  esac
done

# ── Locate SLM Server Directory and .env ──────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/main.py" ]]; then
  SLM_DIR="$SCRIPT_DIR"
elif [[ -f "$SCRIPT_DIR/../main.py" ]]; then
  SLM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  SLM_DIR="$(pwd)"
fi

if [[ -n "$CUSTOM_ENV" ]]; then
  ENV_FILE="$CUSTOM_ENV"
else
  ENV_FILE="$SLM_DIR/.env"
fi
ENV_EXAMPLE="$SLM_DIR/.env.example"

# ── Python & Secrets Engine Detection ─────────────────────────────────────────
PYTHON_BIN=""
for candidate in python3 python python.exe python3.exe /c/Python*/python.exe /usr/bin/python3 /usr/local/bin/python3; do
  if [ -f "$candidate" ] || [ -x "$candidate" ] || command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c "import secrets; print('ok')" 2>/dev/null | grep -q "ok"; then
      PYTHON_BIN="$candidate"
      break
    fi
  fi
done

# Fallback generator in pure bash/openssl if python is unavailable
gen_token() {
  local num_bytes="$1"
  if [[ -n "$PYTHON_BIN" ]]; then
    "$PYTHON_BIN" -c "import secrets; print(secrets.token_urlsafe($num_bytes))"
  elif command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 "$num_bytes" 2>/dev/null | tr '+/' '-_' | tr -d '=\r\n'
  else
    # Minimal urandom fallback
    head -c "$num_bytes" /dev/urandom 2>/dev/null | base64 | tr '+/' '-_' | tr -d '=\r\n'
  fi
}

echo -e "${CYAN}==============================================================${NC}"
echo -e "${CYAN}${BOLD}       Ssense SLM Server — Cryptographic Key Generator        ${NC}"
echo -e "${CYAN}==============================================================${NC}"
echo -e "${GRAY}Target .env: ${ENV_FILE}${NC}\n"

# ── Step 1: Ensure .env Exists ────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  if [[ "$SHOW_ONLY" -eq 1 ]]; then
    echo -e "${RED}Error: .env file not found at ${ENV_FILE}${NC}"
    exit 1
  fi
  echo -e "${YELLOW}[!] .env not found. Creating from .env.example...${NC}"
  if [[ -f "$ENV_EXAMPLE" ]]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
  else
    cat << 'EOF' > "$ENV_FILE"
SSENSE_ENV=production
SSENSE_API_KEYS=
SSENSE_ENTERPRISE_API_KEYS=
SSENSE_HMAC_SECRET=
SSENSE_ADMIN_TOKEN=
SSENSE_ALLOWED_ORIGINS=*
SSENSE_MAX_QUEUE_DEPTH=5000
EOF
  fi
  echo -e "${GREEN}✓ Created starter .env at ${ENV_FILE}${NC}\n"
fi

# ── Step 2: Key Inspection & Generation ───────────────────────────────────────
# Known placeholder / leaked values from security.py that must be rotated
DUMMY_KEYS=("" "ssense_dev_key_2026" "ssense_prod_key_2026" "your-api-key" "your_api_key_here" "CHANGE_ME")
DUMMY_SECRETS=("" "ssense_secret_key_2026_prod" "your-hmac-secret" "your_secret_here" "CHANGE_ME")

is_dummy() {
  local val="$1"
  shift
  local dummy
  for dummy in "$@"; do
    if [[ "$val" == "$dummy" ]]; then
      return 0
    fi
  done
  return 1
}

# Function to read value from .env
get_env_val() {
  local key="$1"
  local line
  line=$(grep -E "^[[:space:]]*${key}=" "$ENV_FILE" | tail -n 1 || true)
  if [[ -n "$line" ]]; then
    local val="${line#*=}"
    # Strip surrounding quotes and whitespace
    val="${val#\"}"
    val="${val%\"}"
    val="${val#\'}"
    val="${val%\'}"
    echo "$val"
  else
    echo ""
  fi
}

# Function to update or append key in .env
set_env_val() {
  local key="$1"
  local val="$2"
  if grep -q -E "^[[:space:]]*${key}=" "$ENV_FILE"; then
    # Use python or sed for safe in-place replacement
    if [[ -n "$PYTHON_BIN" ]]; then
      "$PYTHON_BIN" -c "
import sys, re
key = sys.argv[1]
val = sys.argv[2]
path = sys.argv[3]
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()
pattern = re.compile(r'^[ \t]*' + re.escape(key) + r'=.*$', re.MULTILINE)
new_content = pattern.sub(f'{key}={val}', content)
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)
" "$key" "$val" "$ENV_FILE"
    else
      # sed fallback
      sed -i.bak -e "s|^[[:space:]]*${key}=.*|${key}=${val}|" "$ENV_FILE" && rm -f "${ENV_FILE}.bak"
    fi
  else
    # Append if not present
    echo "${key}=${val}" >> "$ENV_FILE"
  fi
}

CURRENT_API_KEY="$(get_env_val "SSENSE_API_KEYS")"
CURRENT_HMAC_SECRET="$(get_env_val "SSENSE_HMAC_SECRET")"
CURRENT_ADMIN_TOKEN="$(get_env_val "SSENSE_ADMIN_TOKEN")"

API_STATUS="EXISTING"
HMAC_STATUS="EXISTING"
ADMIN_STATUS="EXISTING"
MODIFIED=0

# ── API Key ───────────────────────────────────────────────────────────────────
if [[ "$FORCE_REGEN" -eq 1 ]] || is_dummy "$CURRENT_API_KEY" "${DUMMY_KEYS[@]}"; then
  if [[ "$SHOW_ONLY" -eq 1 ]]; then
    API_STATUS="MISSING/EMPTY"
  else
    CURRENT_API_KEY="$(gen_token 32)"
    set_env_val "SSENSE_API_KEYS" "$CURRENT_API_KEY"
    API_STATUS="GENERATED"
    MODIFIED=1
  fi
fi

# ── HMAC Secret ───────────────────────────────────────────────────────────────
if [[ "$FORCE_REGEN" -eq 1 ]] || is_dummy "$CURRENT_HMAC_SECRET" "${DUMMY_SECRETS[@]}"; then
  if [[ "$SHOW_ONLY" -eq 1 ]]; then
    HMAC_STATUS="MISSING/EMPTY"
  else
    CURRENT_HMAC_SECRET="$(gen_token 48)"
    set_env_val "SSENSE_HMAC_SECRET" "$CURRENT_HMAC_SECRET"
    HMAC_STATUS="GENERATED"
    MODIFIED=1
  fi
fi

# ── Admin Token ───────────────────────────────────────────────────────────────
if [[ "$FORCE_REGEN" -eq 1 ]] || [[ -z "$CURRENT_ADMIN_TOKEN" ]]; then
  if [[ "$SHOW_ONLY" -eq 1 ]]; then
    ADMIN_STATUS="MISSING/EMPTY"
  else
    CURRENT_ADMIN_TOKEN="$(gen_token 32)"
    set_env_val "SSENSE_ADMIN_TOKEN" "$CURRENT_ADMIN_TOKEN"
    ADMIN_STATUS="GENERATED"
    MODIFIED=1
  fi
fi

# ── Step 3: Display Results ───────────────────────────────────────────────────
fmt_status() {
  local st="$1"
  if [[ "$st" == "GENERATED" ]]; then
    echo -e "${GREEN}[NEWLY GENERATED]${NC}"
  elif [[ "$st" == "EXISTING" ]]; then
    echo -e "${CYAN}[EXISTING]${NC}"
  else
    echo -e "${RED}[${st}]${NC}"
  fi
}

echo -e "${BOLD}Current Server Keys in .env:${NC}"
echo -e "──────────────────────────────────────────────────────────────"
echo -e "${BOLD}1. SSENSE_API_KEYS:${NC} $(fmt_status "$API_STATUS")"
echo -e "   ${YELLOW}${CURRENT_API_KEY}${NC}"
echo ""
echo -e "${BOLD}2. SSENSE_HMAC_SECRET:${NC} $(fmt_status "$HMAC_STATUS")"
echo -e "   ${YELLOW}${CURRENT_HMAC_SECRET}${NC}"
echo ""
echo -e "${BOLD}3. SSENSE_ADMIN_TOKEN:${NC} $(fmt_status "$ADMIN_STATUS")"
echo -e "   ${YELLOW}${CURRENT_ADMIN_TOKEN}${NC}"
echo -e "──────────────────────────────────────────────────────────────"

if [[ "$MODIFIED" -eq 1 ]]; then
  echo -e "\n${GREEN}✅ Keys were successfully written to ${ENV_FILE}!${NC}"
else
  echo -e "\n${CYAN}ℹ All server keys are already configured and valid in .env.${NC}"
  echo -e "${GRAY}(Use --force to regenerate new keys if you need to rotate them)${NC}"
fi

# ── Step 4: Display Helpful Connection Info ───────────────────────────────────
echo -e "\n${BOLD}${CYAN}► HOW TO CONNECT THE CHROME EXTENSION:${NC}"
echo -e "  1. In the Ssense Chrome Extension, click ${BOLD}Settings (⚙)${NC}."
echo -e "  2. Go to ${BOLD}Server${NC} section and enable ${BOLD}'Use my own server'${NC}."
echo -e "  3. Enter the following values:"
echo -e "     • ${BOLD}Server URL:${NC}   http://localhost:8000  (or your server's IP/domain)"
echo -e "     • ${BOLD}API Key:${NC}      ${YELLOW}${CURRENT_API_KEY}${NC}"
echo -e "     • ${BOLD}HMAC Secret:${NC}  ${YELLOW}${CURRENT_HMAC_SECRET}${NC}"
echo -e "  4. Click ${BOLD}Save${NC} and then click ${BOLD}'Test connection'${NC}."

echo -e "\n${BOLD}${CYAN}► QUICK TEST VIA CURL:${NC}"
echo -e "  curl -s -H \"X-Ssense-API-Key: ${CURRENT_API_KEY}\" http://localhost:8000/v1/auth/ping\n"
