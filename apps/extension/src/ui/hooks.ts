// apps/extension/src/ui/hooks.ts — data hooks shared by every extension surface.
import './mock-chrome';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { SiteHistoryEntry } from '../background/history-store';
import type { ScanRecord } from '../background/scan-manager';
import type { Prefs } from '../background/prefs';
import type { SyncState } from '../background/sync-manager';
import type { AuthState } from '../background/auth';
import { buildRows, type SiteRow } from '../utils/rows';

const send = <T = any>(msg: Record<string, unknown>): Promise<T> =>
  chrome.runtime.sendMessage(msg).catch(() => ({ success: false })) as Promise<T>;
export { send };

/** Subscribe to runtime broadcasts of the given types. */
function useBroadcast(types: string[], handler: (msg: any) => void) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    const l = (m: any) => { if (m && types.includes(m.type)) ref.current(m); };
    chrome.runtime.onMessage.addListener(l);
    return () => chrome.runtime.onMessage.removeListener(l);
  }, [types.join('|')]); // eslint-disable-line react-hooks/exhaustive-deps
}

export function useAuth() {
  const [auth, setAuth] = useState<AuthState | null>(null);
  const reload = useCallback(async () => {
    const r = await send<any>({ type: 'GET_AUTH_STATE' });
    setAuth(r?.success === false ? { signedIn: false, provider: null, name: '', email: '', avatarUrl: '', userId: '' } : r);
  }, []);
  useEffect(() => { void reload(); }, [reload]);
  useBroadcast(['AUTH_CHANGED'], () => void reload());
  return { auth, reload };
}

export function usePrefs() {
  const [prefs, setPrefsState] = useState<Prefs | null>(null);
  useEffect(() => { void send<any>({ type: 'GET_PREFS' }).then((r) => r?.prefs && setPrefsState(r.prefs)); }, []);
  useBroadcast(['PREFS_CHANGED'], (m) => m.prefs && setPrefsState(m.prefs));
  const update = useCallback(async (patch: Partial<Prefs>) => {
    setPrefsState((p) => (p ? { ...p, ...patch } : p)); // optimistic
    const r = await send<any>({ type: 'SET_PREFS', patch });
    if (r?.prefs) setPrefsState(r.prefs);
  }, []);
  return { prefs, update };
}

export function useSyncState() {
  const [state, setState] = useState<SyncState | null>(null);
  useEffect(() => { void send<any>({ type: 'GET_SYNC_STATE' }).then((r) => r?.state && setState(r.state)); }, []);
  useBroadcast(['SYNC_STATE'], (m) => setState(m.state));
  const syncNow = useCallback(async () => {
    setState((s) => (s ? { ...s, status: 'syncing' } : s));
    const r = await send<any>({ type: 'SYNC_NOW' });
    if (r?.state) setState(r.state);
  }, []);
  return { state, syncNow };
}

/** All tracked sites joined with live scan status; refreshes as audits/scans/syncs land. */
export function useSites() {
  const [entries, setEntries] = useState<SiteHistoryEntry[]>([]);
  const [records, setRecords] = useState<Record<string, ScanRecord>>({});
  const [ignored, setIgnored] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const timer = useRef<number | undefined>(undefined);

  const reload = useCallback(async () => {
    const r = await send<any>({ type: 'GET_OVERVIEW' });
    if (r?.success) { setEntries(r.entries || []); setRecords(r.records || {}); setIgnored(r.ignored || []); }
    setLoading(false);
  }, []);
  const soon = useCallback(() => { window.clearTimeout(timer.current); timer.current = window.setTimeout(() => void reload(), 250); }, [reload]);

  useEffect(() => { void reload(); return () => window.clearTimeout(timer.current); }, [reload]);
  useBroadcast(['AUDIT_COMPLETE', 'AUDIT_ERROR', 'SCAN_STATUS', 'HISTORY_CHANGED', 'PREFS_CHANGED'], soon);

  const rows: SiteRow[] = useMemo(() => buildRows(entries, records, ignored), [entries, records, ignored]);
  return { rows, loading, reload };
}

export function useActiveTab() {
  const [tab, setTab] = useState<{ id?: number; url?: string; host: string | null }>({ host: null });
  useEffect(() => {
    const read = () => chrome.tabs.query({ active: true, currentWindow: true }).then(([t]) => {
      let host: string | null = null;
      try { if (t?.url?.startsWith('http')) host = new URL(t.url).hostname; } catch {}
      setTab({ id: t?.id, url: t?.url, host });
    }).catch(() => setTab({ host: null }));
    void read();
    chrome.tabs.onActivated.addListener(read);
    const upd = (_id: number, info: chrome.tabs.TabChangeInfo) => { if (info.status === 'complete' || info.url) void read(); };
    chrome.tabs.onUpdated.addListener(upd);
    return () => { chrome.tabs.onActivated.removeListener(read); chrome.tabs.onUpdated.removeListener(upd); };
  }, []);
  return tab;
}

/** Applies the user's theme choice (system/light/dark) to <html data-theme>. */
export function useTheme(theme: Prefs['theme'] | undefined) {
  useEffect(() => {
    const el = document.documentElement;
    if (!theme || theme === 'system') el.removeAttribute('data-theme');
    else el.setAttribute('data-theme', theme);
  }, [theme]);
}

export function highlightOnPage(quote: string) {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]?.id) chrome.tabs.sendMessage(tabs[0].id, { type: 'HIGHLIGHT_IN_DOM', quote }).catch(() => {});
  });
}

export async function openSidePanel(view: 'audit' | 'history' | 'privacy' = 'audit', focusDomain?: string) {
  await chrome.storage.local.set({ ssense_sidepanel_view: view, ssense_history_focus: focusDomain ?? null });
  try {
    const w = await chrome.windows.getCurrent();
    if (w?.id !== undefined) await chrome.sidePanel.open({ windowId: w.id });
  } catch { /* side panel unsupported (e.g. some Chromium forks) */ }
}
