// apps/extension/src/background/scan-manager.ts
//
// Live scan status for every site, shared by popup / side panel / options.
//
//   transient states (queued, scanning, needs_signin, paused) live in
//   chrome.storage.session — they mean nothing after the browser restarts.
//   terminal outcomes (done, error, nopolicy, skipped) are ALSO persisted on the
//   site's history entry by the caller, so History can show them later and they
//   sync across devices.

import type { ScanState } from '../utils/status';
import { normaliseDomain } from '../utils/domain';

const KEY = 'ssense_scan_status';
const MAX_TRACKED = 300;
const STALE_MS = 5 * 60_000;

export interface ScanRecord {
  state: ScanState;
  at: number;
  error?: string;
  errorKind?: string;
  policyUrl?: string;
  /** 'cache' when served from the local audit cache without a network scan. */
  via?: 'cache' | 'server';
}

let _chain: Promise<unknown> = Promise.resolve();
function serial<T>(fn: () => Promise<T>): Promise<T> {
  const run = _chain.then(fn, fn);
  _chain = run.catch(() => undefined);
  return run;
}

async function readAll(): Promise<Record<string, ScanRecord>> {
  try {
    const d = await chrome.storage.session.get(KEY);
    const all = (d[KEY] as Record<string, ScanRecord>) || {};
    // A "scanning" record older than this belongs to a request the service worker
    // lost (it was killed mid-flight) — don't show a spinner forever.
    const now = Date.now();
    for (const k of Object.keys(all)) {
      if ((all[k].state === 'scanning' || all[k].state === 'queued') && now - all[k].at > STALE_MS) delete all[k];
    }
    return all;
  } catch {
    return {};
  }
}

export async function getScanRecords(): Promise<Record<string, ScanRecord>> {
  return readAll();
}

export async function getScanRecord(domain: string): Promise<ScanRecord | null> {
  return (await readAll())[normaliseDomain(domain)] ?? null;
}

export async function setScan(domain: string, rec: Omit<ScanRecord, 'at'>): Promise<void> {
  const norm = normaliseDomain(domain);
  if (!norm) return;
  await serial(async () => {
    const all = await readAll();
    all[norm] = { ...rec, at: Date.now() };
    const keys = Object.keys(all);
    if (keys.length > MAX_TRACKED) {
      keys
        .sort((a, b) => all[a].at - all[b].at)
        .slice(0, keys.length - MAX_TRACKED)
        .forEach((k) => delete all[k]);
    }
    try { await chrome.storage.session.set({ [KEY]: all }); } catch {}
  });
  // Live-update any open popup / side panel. Nobody listening is fine.
  chrome.runtime.sendMessage({ type: 'SCAN_STATUS', domain: norm, state: rec.state, error: rec.error }).catch(() => {});
}

export async function clearScans(): Promise<void> {
  await serial(async () => { try { await chrome.storage.session.remove(KEY); } catch {} });
}
