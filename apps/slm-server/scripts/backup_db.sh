#!/usr/bin/env bash
# backup_db.sh — Live, non-downtime backup of both Ssense SQLite databases:
#   - ssense_audit_cache.db  (90-day audit cache)
#   - ssense_users.db        (user/device/IP registry)
#
# Both DBs use WAL mode, so a raw cp while the server is running can produce
# a torn/inconsistent snapshot. SQLite VACUUM INTO creates a clean,
# fully-checkpointed copy safe to run against a live database with no
# reader/writer blocking.
#
# Usage:
#   ./scripts/backup_db.sh [output_dir]
#
# Suggested cron (nightly):
#   0 3 * * * /opt/ssense/apps/slm-server/scripts/backup_db.sh /opt/ssense-backups

set -euo pipefail

cd "$(dirname "$0")/.."

OUT_DIR="${1:-./data/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "${OUT_DIR}"

backup_db() {
  local DB_FILE="$1"
  local LABEL="$2"
  local OUT_FILE="${OUT_DIR}/${LABEL}_${TIMESTAMP}.db"

  if [ ! -f "${DB_FILE}" ]; then
    echo "  No DB file found at ${DB_FILE} -- skipping." >&2
    return 0
  fi

  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "${DB_FILE}" "VACUUM INTO '${OUT_FILE}';"
  else
    python3 - "${DB_FILE}" "${OUT_FILE}" <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1])
src.execute(f"VACUUM INTO '{sys.argv[2]}'")
src.close()
PY
  fi

  echo "  Backup written to ${OUT_FILE} ($(du -h "${OUT_FILE}" | cut -f1))"
  # Keep the last 30 daily backups, prune older ones.
  find "${OUT_DIR}" -name "${LABEL}_*.db" -mtime +30 -delete
}

echo "==> Taking live, WAL-safe backup snapshots..."
backup_db "./data/db/ssense_audit_cache.db" "ssense_audit_cache"
backup_db "./data/db/ssense_users.db"       "ssense_users"
echo "==> Pruned backups older than 30 days in ${OUT_DIR}"
