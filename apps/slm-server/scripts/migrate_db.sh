#!/usr/bin/env bash
# migrate_db.sh — Move the local audit-cache SQLite DB to a new server
# instance while the app stack stays otherwise stateless.
#
# Works because docker-compose.yml mounts the DB as a plain host bind mount
# (./data/db -> /app/data), not a Docker named volume, so the on-disk file
# is directly rsync-able. Nothing here talks to `docker volume`.
#
# Usage:
#   ./scripts/migrate_db.sh <profile> user@new-host:/path/to/ssense-main/apps/slm-server
#
# Example:
#   ./scripts/migrate_db.sh gpu deploy@10.0.4.12:/opt/ssense/apps/slm-server
#
# What it does:
#   1. Stops the local slm-server-<profile> container (keeps Redis/Nginx up
#      if they're shared, but usually you're moving the whole stack).
#   2. Forces a WAL checkpoint so ssense_audit_cache.db-wal is folded into
#      the main .db file before it travels (avoids shipping a dangling WAL
#      that a different SQLite/aiosqlite version has to reconcile).
#   3. rsyncs ./data/db/ to the same relative path on the destination host.
#   4. Leaves the source files in place — this is a copy, not a cutover.
#      Run `docker compose up -d --profile <profile>` on the new host, then
#      decommission the old one once you've verified it's serving traffic.

set -euo pipefail

PROFILE="${1:?Usage: migrate_db.sh <gpu|jetson|cpu> <user@host:/path>}"
DEST="${2:?Usage: migrate_db.sh <gpu|jetson|cpu> <user@host:/path>}"

cd "$(dirname "$0")/.."

echo "==> Stopping slm-server-${PROFILE} (keeps the DB file quiescent for a clean copy)..."
docker compose --profile "${PROFILE}" stop "slm-server-${PROFILE}"

DB_FILE="./data/db/ssense_audit_cache.db"
if [ -f "${DB_FILE}" ]; then
  echo "==> Forcing a WAL checkpoint so no writes are left in the -wal sidecar file..."
  # sqlite3 CLI if present; falls back to python's sqlite3 module otherwise.
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "${DB_FILE}" "PRAGMA wal_checkpoint(TRUNCATE);"
  else
    python3 - "${DB_FILE}" <<'PY'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
conn.close()
PY
  fi
else
  echo "==> No existing DB file at ${DB_FILE} — nothing to checkpoint (fresh install?)."
fi

echo "==> rsyncing ./data/db/ -> ${DEST}/data/db/ ..."
rsync -avz --progress ./data/db/ "${DEST}/data/db/"

echo "==> Done. On the destination host: docker compose --profile ${PROFILE} up -d"
echo "==> Source files were left in place — decommission this host only after verifying the new one."
