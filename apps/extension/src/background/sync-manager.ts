// apps/extension/src/background/sync-manager.ts
//
// Cross-device sync for the signed-in account. Any browser where the user signs
// in with the same Google account converges to the same history and settings.
//
//   push:  local records changed since the last successful push
//   pull:  everything the server has after our cursor (cursor is a server-side
//          sequence number, so device clock drift can't cause missed updates)
//   merge: history-store.mergeEntries — audits/scan status: newest wins;
//          visit counts and time: summed per device.

import { getServerConfig, signedHeaders } from './api-client';
import { getAuthState } from './auth';
import * as historyStore from './history-store';
import * as auditCache from './audit-cache';
import { getPrefs, setPrefs, sanitizePrefs } from './prefs';

const STATE_KEY = 'ssense_sync_state';
const PUSH_BATCH = 25;

export interface SyncState {
  status: 'idle' | 'syncing' | 'error' | 'off';
  lastSyncAt: number | null;
  lastError: string | null;
  cursor: number;
  lastPushAt: number;
  pushed: number;
  pulled: number;
}

const EMPTY: SyncState = { status: 'idle', lastSyncAt: null, lastError: null, cursor: 0, lastPushAt: 0, pushed: 0, pulled: 0 };

export async function getSyncState(): Promise<SyncState> {
  const d = await chrome.storage.local.get(STATE_KEY);
  return { ...EMPTY, ...(d[STATE_KEY] || {}) };
}

async function patchState(p: Partial<SyncState>): Promise<SyncState> {
  const next = { ...(await getSyncState()), ...p };
  await chrome.storage.local.set({ [STATE_KEY]: next });
  chrome.runtime.sendMessage({ type: 'SYNC_STATE', state: next }).catch(() => {});
  return next;
}

async function api<T>(method: 'GET' | 'POST' | 'DELETE', endpointWithQuery: string, body?: unknown): Promise<T> {
  const cfg = await getServerConfig();
  if (!cfg.configured) throw new Error('Not signed in.');
  // The HMAC covers the path only, not the query string (matches server verify).
  const path = endpointWithQuery.split('?')[0];
  const r = await fetch(`${cfg.url}${endpointWithQuery}`, {
    method,
    headers: await signedHeaders(cfg, method, path),
    body: body ? JSON.stringify(body) : undefined,
    credentials: 'omit',
  });
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try { const j = await r.json(); if (typeof j?.detail === 'string') detail = j.detail; } catch {}
    throw new Error(detail);
  }
  return r.json() as Promise<T>;
}

let _running: Promise<SyncState> | null = null;

/** Push local changes, then pull remote ones. Concurrent callers share one run. */
export function syncNow(_reason = 'manual'): Promise<SyncState> {
  if (_running) return _running;
  _running = (async () => {
    try {
      const auth = await getAuthState();
      const prefs = await getPrefs();
      if (!auth.signedIn || auth.provider !== 'google' || !prefs.syncEnabled) {
        return await patchState({ status: 'off' });
      }
      if (typeof navigator !== 'undefined' && !navigator.onLine) {
        return await patchState({ status: 'error', lastError: 'You are offline. Will retry when you reconnect.' });
      }

      await patchState({ status: 'syncing', lastError: null });
      const startedAt = Date.now();
      const state = await getSyncState();

      // ── push ──
      const all = await historyStore.getAllEntries();
      const dirty = all.filter((e) => (e.updatedAt || 0) > state.lastPushAt);
      const prefsDirty = prefs._updatedAt > state.lastPushAt;
      let pushed = 0;
      for (let i = 0; i < dirty.length || (i === 0 && prefsDirty); i += PUSH_BATCH) {
        const batch = dirty.slice(i, i + PUSH_BATCH);
        await api('POST', '/v1/sync/push', {
          sites: batch.map((e) => ({ domain: e.domain, updated_at: e.updatedAt || Date.now(), data: e })),
          prefs: i === 0 && prefsDirty ? { updated_at: prefs._updatedAt, data: prefs } : undefined,
        });
        pushed += batch.length;
        if (dirty.length === 0) break;
      }

      // ── pull ──
      let cursor = state.cursor;
      let pulled = 0;
      for (let guard = 0; guard < 50; guard++) {
        const page = await api<{
          sites: { domain: string; updated_at: number; data: historyStore.SiteHistoryEntry }[];
          prefs: { updated_at: number; data: any } | null;
          cursor: number;
          has_more: boolean;
        }>('GET', `/v1/sync/pull?cursor=${cursor}&limit=200`);

        for (const s of page.sites) {
          const { merged, changed } = await historyStore.mergeRemote({ ...s.data, domain: s.domain, updatedAt: s.updated_at });
          if (changed) {
            pulled++;
            // Keep the fast local lookup (badge, popup, pre-fill) consistent with history.
            if (merged.lastReport && merged.lastAuditAt) {
              const cached = await auditCache.getAudit(merged.domain);
              if (!cached || cached.audited_at < merged.lastAuditAt) {
                await auditCache.saveAudit(merged.domain, merged.lastReport, {
                  policy_url: merged.policyUrl,
                  source: 'synced',
                  audited_at: merged.lastAuditAt,
                });
              }
            }
          }
        }
        if (page.prefs && page.prefs.updated_at > prefs._updatedAt) {
          await setPrefs(sanitizePrefs({ ...page.prefs.data, _updatedAt: page.prefs.updated_at }), { fromRemote: true });
        }
        cursor = page.cursor;
        if (!page.has_more) break;
      }

      const done = await patchState({
        status: 'idle', lastSyncAt: Date.now(), lastError: null,
        cursor, lastPushAt: startedAt, pushed, pulled,
      });
      if (pulled > 0) chrome.runtime.sendMessage({ type: 'HISTORY_CHANGED' }).catch(() => {});
      return done;
    } catch (e: any) {
      return await patchState({ status: 'error', lastError: e?.message || 'Sync failed.' });
    } finally {
      _running = null;
    }
  })();
  return _running;
}

/** Debounced "soon": survives service-worker restarts because it's an alarm. */
export function scheduleSync(): void {
  try { chrome.alarms.create('ssense-sync-soon', { delayInMinutes: 0.5 }); } catch {}
}

export function registerSyncAlarms(): void {
  try { chrome.alarms.create('ssense-sync-periodic', { periodInMinutes: 15, delayInMinutes: 1 }); } catch {}
}

/** Remove this account's synced copy from the server (local data untouched). */
export async function deleteCloudData(): Promise<void> {
  await api('DELETE', '/v1/sync/data');
  await patchState({ cursor: 0, lastPushAt: 0, lastSyncAt: null });
}

export async function resetSyncState(): Promise<void> {
  await chrome.storage.local.remove(STATE_KEY);
}
