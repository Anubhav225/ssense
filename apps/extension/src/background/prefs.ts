// apps/extension/src/background/prefs.ts
//
// User preferences. Stored locally, and synced across the user's devices by
// sync-manager (last-writer-wins on `_updatedAt`).

import { normaliseDomain } from '../utils/domain';

export interface Prefs {
  /** Scan a site's privacy policy automatically when it is opened. */
  autoScan: boolean;
  /** Re-scan a site only when its last audit is older than this many days. */
  rescanAfterDays: number;
  /** Domains that are never scanned. */
  ignoredDomains: string[];
  /** Apply the protections (tracker blocking, GPC, fingerprint masking) an audit recommends. */
  enforceProtections: boolean;
  /** Desktop notification when a site scores below the threshold. */
  notifyOnLowScore: boolean;
  lowScoreThreshold: number;
  /** Show the trust score on the toolbar icon. */
  showBadge: boolean;
  /** Sync history and settings to the signed-in account. */
  syncEnabled: boolean;
  theme: 'system' | 'light' | 'dark';
  _updatedAt: number;
}

export const DEFAULT_PREFS: Prefs = {
  autoScan: true,
  rescanAfterDays: 30,
  ignoredDomains: [],
  enforceProtections: true,
  notifyOnLowScore: true,
  lowScoreThreshold: 40,
  showBadge: true,
  syncEnabled: true,
  theme: 'system',
  _updatedAt: 0,
};

const KEY = 'ssense_prefs';

export function sanitizePrefs(input: Partial<Prefs> | null | undefined): Prefs {
  const p = { ...DEFAULT_PREFS, ...(input || {}) };
  const clamp = (n: unknown, lo: number, hi: number, d: number) => {
    const v = Number(n);
    return Number.isFinite(v) ? Math.min(hi, Math.max(lo, Math.round(v))) : d;
  };
  return {
    autoScan: Boolean(p.autoScan),
    rescanAfterDays: clamp(p.rescanAfterDays, 1, 90, DEFAULT_PREFS.rescanAfterDays),
    ignoredDomains: Array.from(
      new Set((Array.isArray(p.ignoredDomains) ? p.ignoredDomains : []).map((d) => normaliseDomain(String(d))).filter(Boolean)),
    ).slice(0, 500),
    enforceProtections: Boolean(p.enforceProtections),
    notifyOnLowScore: Boolean(p.notifyOnLowScore),
    lowScoreThreshold: clamp(p.lowScoreThreshold, 5, 95, DEFAULT_PREFS.lowScoreThreshold),
    showBadge: Boolean(p.showBadge),
    syncEnabled: Boolean(p.syncEnabled),
    theme: (['system', 'light', 'dark'] as const).includes(p.theme as any) ? p.theme : 'system',
    _updatedAt: Number(p._updatedAt) || 0,
  };
}

export function isIgnored(prefs: Prefs, domain: string): boolean {
  const d = normaliseDomain(domain);
  return prefs.ignoredDomains.some((x) => d === x || d.endsWith(`.${x}`));
}

export async function getPrefs(): Promise<Prefs> {
  const d = await chrome.storage.local.get(KEY);
  return sanitizePrefs(d[KEY]);
}

export async function setPrefs(patch: Partial<Prefs>, opts: { fromRemote?: boolean } = {}): Promise<Prefs> {
  const cur = await getPrefs();
  const next = sanitizePrefs({
    ...cur,
    ...patch,
    _updatedAt: opts.fromRemote ? Number(patch._updatedAt) || Date.now() : Date.now(),
  });
  await chrome.storage.local.set({ [KEY]: next });
  return next;
}
