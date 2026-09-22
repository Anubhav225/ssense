#!/usr/bin/env python3
"""
db_sync.py — Automatic export/import/sync for the local audit-cache SQLite DB.

Problem this solves: `scripts/migrate_db.sh` / `backup_db.sh` (see docs) are
correct but manual — someone has to remember to run them before decommissioning
an instance. This module makes the same underlying operation (a WAL-safe
`VACUUM INTO` snapshot) automatic and bidirectional:

  1. IMPORT ON BOOT — if this instance's local DB (SSENSE_AUDIT_DB_PATH) is
     missing or empty (a brand-new instance / fresh volume) AND a prior export
     exists at SSENSE_DB_EXPORT_PATH (a second mount — NFS share, network
     block volume, S3-backed FUSE mount, or just another host directory you
     rsync elsewhere), the export is imported automatically before the server
     starts serving traffic. This is what makes "spin up a new instance" and
     "it already has the cached audits" the same event with no manual step.

  2. PERIODIC EXPORT — a background task snapshots the local DB out to
     SSENSE_DB_EXPORT_PATH on an interval (SSENSE_DB_SYNC_INTERVAL_SECONDS,
     default 15 min) plus once more on graceful shutdown. The snapshot is
     content-hashed so an unchanged DB (e.g. an idle CPU-profile instance
     with no new audits) doesn't re-write the export target every interval.

  Both directions use the same safety rules:
    - Snapshots are taken with `VACUUM INTO`, which is safe against a live
      WAL-mode writer (a raw file copy is NOT — see backup_db.sh's docstring)
      and produces a compact, single-file, non-WAL output — exactly what you
      want for a portable export.
    - Writes to the export target are atomic: write to `<name>.tmp-<pid>`,
      fsync, then os.replace() into the final name. A reader (another
      instance's import step, or a human `scp`) never observes a
      half-written file.
    - A sidecar `<name>.sha256` is written alongside the export and checked
      on import — a truncated/corrupted transfer (network share hiccup,
      power loss mid-write on some OTHER instance that was exporting) is
      detected and refused rather than imported silently.
    - Import NEVER overwrites an existing non-empty local DB. If the local
      file already has data, this instance is not "new" by definition, and
      auto-overwriting a running instance's cache with a possibly-older
      export would silently discard real (if cache) data. In that case we
      only log that a newer/different export exists so a human can decide
      to run `scripts/migrate_db.sh` deliberately, and continue booting.

Config (all optional; the whole subsystem is a no-op if
SSENSE_DB_EXPORT_PATH is unset — nothing changes for anyone not using it):

  SSENSE_DB_EXPORT_PATH             Directory to export into / import from.
                                     e.g. a second bind mount pointed at
                                     network storage. Unset = disabled.
  SSENSE_DB_SYNC_INTERVAL_SECONDS   Export interval. Default 900 (15 min).
  SSENSE_DB_EXPORT_RETAIN           How many timestamped snapshots to keep
                                     in <export_path>/history/ in addition to
                                     the one canonical "latest" file. Default
                                     5. Set to 0 to keep only "latest".
"""

import asyncio
import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional

DB_FILENAME = "ssense_audit_cache.db"


def _export_enabled() -> bool:
    return bool(os.getenv("SSENSE_DB_EXPORT_PATH", "").strip())


def _export_dir() -> Optional[Path]:
    raw = os.getenv("SSENSE_DB_EXPORT_PATH", "").strip()
    return Path(raw) if raw else None


def _sync_interval_s() -> float:
    return float(os.getenv("SSENSE_DB_SYNC_INTERVAL_SECONDS", "900"))


def _retain_count() -> int:
    return int(os.getenv("SSENSE_DB_EXPORT_RETAIN", "5"))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_copy(src: Path, dst: Path) -> None:
    """Copy src -> dst without a reader ever observing a partial dst."""
    tmp = dst.with_suffix(dst.suffix + f".tmp-{os.getpid()}")
    shutil.copyfile(src, tmp)
    with open(tmp, "rb") as f:
        os.fsync(f.fileno())
    os.replace(tmp, dst)  # atomic on the same filesystem (POSIX rename semantics)


def _snapshot_via_vacuum_into(live_db_path: Path, out_path: Path) -> None:
    """WAL-safe point-in-time snapshot of a live SQLite DB. Writes to a temp
    file first (VACUUM INTO refuses to overwrite an existing file) then
    atomically replaces out_path."""
    import sqlite3
    tmp = out_path.with_suffix(out_path.suffix + f".vacuum-{os.getpid()}")
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(live_db_path))
    try:
        conn.execute(f"VACUUM INTO '{tmp.as_posix()}'")
    finally:
        conn.close()
    with open(tmp, "rb") as f:
        os.fsync(f.fileno())
    os.replace(tmp, out_path)


# ── Import (boot-time) ──────────────────────────────────────────────────────
def import_if_new(local_db_path: Path) -> None:
    """
    Call once at boot, BEFORE audit_store.initialize() opens the local DB.
    If the local DB is missing/empty and a valid export exists, copies the
    export in. Otherwise does nothing (safe to call unconditionally).
    """
    if not _export_enabled():
        return

    export_dir = _export_dir()
    export_db = export_dir / DB_FILENAME
    export_sha = export_dir / f"{DB_FILENAME}.sha256"
    export_meta = export_dir / f"{DB_FILENAME}.meta.json"

    local_is_empty = (not local_db_path.exists()) or local_db_path.stat().st_size == 0

    if not export_db.exists():
        print(f"ℹ️  [DBSync] No export found at {export_db} yet — nothing to import "
              f"(this is expected the very first time export is enabled anywhere).")
        return

    if not local_is_empty:
        # This instance already has data of its own. Never silently overwrite it.
        try:
            meta = json.loads(export_meta.read_text()) if export_meta.exists() else {}
            print(f"ℹ️  [DBSync] Local DB already has data — skipping auto-import. "
                  f"An export exists at {export_db} (last synced by "
                  f"{meta.get('source_host', 'unknown')} at {meta.get('exported_at', 'unknown')}). "
                  f"If you intended to replace this instance's cache with that export, "
                  f"run scripts/migrate_db.sh manually instead of relying on auto-import.")
        except Exception:
            print(f"ℹ️  [DBSync] Local DB already has data — skipping auto-import "
                  f"(an export exists at {export_db} but was not applied).")
        return

    # ── Genuinely a new/empty instance: safe to auto-import ─────────────────
    if export_sha.exists():
        expected = export_sha.read_text().strip().split()[0]
        actual = _sha256_file(export_db)
        if expected != actual:
            print(f"⚠️  [DBSync] Export at {export_db} FAILED checksum verification "
                  f"(expected {expected[:12]}…, got {actual[:12]}…) — refusing to import "
                  f"a possibly-corrupt/truncated file. Starting with a fresh empty cache instead.")
            return
    else:
        print(f"⚠️  [DBSync] Export at {export_db} has no .sha256 sidecar to verify against "
              f"— importing anyway, but this export wasn't written by this module's own "
              f"export path (or the sidecar was deleted). Proceed with awareness.")

    local_db_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"📥 [DBSync] New/empty instance detected — auto-importing cached audits from {export_db}...")
    _atomic_copy(export_db, local_db_path)
    # Also bring across the -wal/-shm sidecars if a previous export step
    # happened to leave any (VACUUM INTO output never has them, but be safe).
    for suffix in ("-wal", "-shm"):
        sidecar = export_db.with_name(export_db.name + suffix)
        if sidecar.exists():
            _atomic_copy(sidecar, local_db_path.with_name(local_db_path.name + suffix))
    print(f"✅ [DBSync] Import complete → {local_db_path} "
          f"({local_db_path.stat().st_size / 1024:.0f} KB). This instance now has the shared cache.")


# ── Export (periodic + shutdown) ────────────────────────────────────────────
_last_exported_hash: Optional[str] = None


def _do_export(local_db_path: Path) -> bool:
    """Returns True if a new export was written, False if skipped (unchanged
    or source missing)."""
    global _last_exported_hash

    if not local_db_path.exists() or local_db_path.stat().st_size == 0:
        return False

    export_dir = _export_dir()
    export_dir.mkdir(parents=True, exist_ok=True)
    export_db = export_dir / DB_FILENAME
    export_sha = export_dir / f"{DB_FILENAME}.sha256"
    export_meta = export_dir / f"{DB_FILENAME}.meta.json"

    # Snapshot to a private scratch location first so we can hash it before
    # deciding whether it's worth touching the shared export target at all.
    scratch = export_dir / f".scratch-{DB_FILENAME}-{os.getpid()}"
    try:
        _snapshot_via_vacuum_into(local_db_path, scratch)
        new_hash = _sha256_file(scratch)

        if new_hash == _last_exported_hash:
            scratch.unlink(missing_ok=True)
            return False  # nothing changed since the last export — skip the write

        os.replace(scratch, export_db)
        export_sha.write_text(f"{new_hash}  {DB_FILENAME}\n")
        export_meta.write_text(json.dumps({
            "exported_at": int(time.time()),
            "source_host": os.getenv("HOSTNAME", "unknown"),
            "sha256": new_hash,
            "size_bytes": export_db.stat().st_size,
        }, indent=2))

        if _retain_count() > 0:
            _write_history_snapshot(export_dir, export_db)

        _last_exported_hash = new_hash
        return True
    finally:
        if scratch.exists():
            scratch.unlink(missing_ok=True)


def _write_history_snapshot(export_dir: Path, export_db: Path) -> None:
    """Optional timestamped copies in <export_path>/history/, retention-pruned.
    The canonical `latest` file (export_db itself) is what import_if_new()
    reads — history/ is purely for "restore from 3 syncs ago" recovery."""
    history_dir = export_dir / "history"
    history_dir.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    dest = history_dir / f"{stamp}_{DB_FILENAME}"
    shutil.copyfile(export_db, dest)

    snapshots = sorted(history_dir.glob(f"*_{DB_FILENAME}"))
    excess = len(snapshots) - _retain_count()
    for old in snapshots[:max(0, excess)]:
        old.unlink(missing_ok=True)


async def periodic_export_task(local_db_path: Path) -> None:
    """Background asyncio task: export on an interval, forever, until cancelled."""
    if not _export_enabled():
        return
    interval = _sync_interval_s()
    print(f"🔁 [DBSync] Periodic export enabled → {_export_dir()} every {interval:.0f}s")
    while True:
        try:
            await asyncio.sleep(interval)
            wrote = await asyncio.to_thread(_do_export, local_db_path)
            if wrote:
                print(f"📤 [DBSync] Exported updated audit cache → {_export_dir() / DB_FILENAME}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"⚠️  [DBSync] Periodic export failed (will retry next interval): {e}")


async def final_export(local_db_path: Path) -> None:
    """Call once at shutdown so the export target never lags more than one
    sync interval behind — best-effort, never raises (shutdown must proceed
    even if the export target is unreachable, e.g. a network mount that's
    already gone)."""
    if not _export_enabled():
        return
    try:
        wrote = await asyncio.to_thread(_do_export, local_db_path)
        if wrote:
            print(f"📤 [DBSync] Final export on shutdown → {_export_dir() / DB_FILENAME}")
    except Exception as e:
        print(f"⚠️  [DBSync] Final export on shutdown failed (non-fatal): {e}")
