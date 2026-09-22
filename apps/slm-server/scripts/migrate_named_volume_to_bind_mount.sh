#!/usr/bin/env bash
# migrate_named_volume_to_bind_mount.sh — ONE-TIME helper for deployments
# that were already running with the old `audit-data` Docker named volume
# (pre this change) and need their existing cached audits carried over to
# the new ./data/db host bind mount. Safe to run once; a no-op if the named
# volume doesn't exist.
#
# Usage: ./scripts/migrate_named_volume_to_bind_mount.sh

set -euo pipefail
cd "$(dirname "$0")/.."

VOLUME_NAME="$(basename "$(pwd)")_audit-data"
mkdir -p ./data/db

if ! docker volume inspect "${VOLUME_NAME}" >/dev/null 2>&1; then
  echo "No named volume '${VOLUME_NAME}' found — nothing to migrate (fresh install, or already migrated)."
  exit 0
fi

echo "==> Copying contents of named volume '${VOLUME_NAME}' into ./data/db ..."
docker run --rm \
  -v "${VOLUME_NAME}:/from:ro" \
  -v "$(pwd)/data/db:/to" \
  alpine sh -c "cp -av /from/. /to/"

echo "==> Done. Verify ./data/db/ssense_audit_cache.db exists, then bring the stack up normally."
echo "==> The old named volume was left untouched — remove it later with:"
echo "      docker volume rm ${VOLUME_NAME}"
