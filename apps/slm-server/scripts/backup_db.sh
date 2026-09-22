#!/usr/bin/env bash
# backup_db.sh — Live, non-downtime backup of the audit-cache SQLite DB.
#
# Because audit_store.py opens the DB with `PRAGMA journal_mode = WAL`, a
# raw `cp` of ssense_audit_cache.db while the server is running can copy a
# torn/inconsistent snapshot (WAL mode keeps recent writes in a separate
# -wal file, replayed into the main file lazily). Use SQLite's own online
# backup API (`.backup` / `VACUUM INTO`) instead, which is safe to run
# against a live database with no reader/writer blocking.
#
# Usage:
#   ./scripts/backup_db.sh [output_dir]
#
# Suggested cron (nightly, in addition to the 90-day in-app TTL prune):
#   0 3 * * * /opt/ssense/apps/slm-server/scripts/backup_db.sh /opt/ssense-backups

set -euo pipefail

cd "$(dirname "$0")/.."

DB_FILE="./data/db/ssense_audit_cache.db"
OUT_DIR="${1:-./data/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="${OUT_DIR}/ssense_audit_cache_${TIMESTAMP}.db"

mkdir -p "${OUT_DIR}"

if [ ! -f "${DB_FILE}" ]; then
  echo "No DB file found at ${DB_FILE} — nothing to back up." >&2
  exit 1
fi

echo "==> Taking a live, WAL-safe backup snapshot..."
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

echo "==> Backup written to ${OUT_FILE} ($(du -h "${OUT_FILE}" | cut -f1))"

# Keep the last 30 daily backups, prune older ones.
find "${OUT_DIR}" -name 'ssense_audit_cache_*.db' -mtime +30 -delete
echo "==> Pruned backups older than 30 days in ${OUT_DIR}"
