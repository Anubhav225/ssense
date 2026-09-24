// apps/extension/src/background/history-store.ts
//
// Durable per-site record: visits, time, latest audit, and scan status.
// IndexedDB (available in MV3 service workers) because this grows unbounded.
//
// Multi-device: every entry carries `updatedAt`, and visit/time counters are
// tracked *per device* (visitsByDevice / timeByDevice) so merging two devices'
// records adds their activity instead of overwriting one with the other.

import type { DpdpAuditReport } from '../types/server-protocol';
import type { ScanState } from '../utils/status';
import { normaliseDomain } from '../utils/domain';

const DB_NAME = 'ssense_history';
const DB_VERSION = 1;
const STORE = 'site_visits';
const MAX_SCORE_POINTS = 30;

export interface ScoreHistoryPoint {
  timestamp: number;
  score:     number;
  delta?:    number;
}

export interface SiteHistoryEntry {
  domain: string;
  firstVisit: number;
  lastVisit: number;
  visitCount: number;
  totalTimeMs: number;
  lastScore: number | null;
  lastReport: DpdpAuditReport | null;
  lastAuditAt: number | null;
  scoreHistory?: ScoreHistoryPoint[];

  // ── v1 additions (all optional so pre-v1 records keep loading) ──
  policyUrl?: string;
  scanState?: ScanState;
  scanError?: string;
  lastScanAt?: number;
  visitsByDevice?: Record<string, number>;
  timeByDevice?: Record<string, number>;
  /** Epoch ms of the last change; the sync conflict-resolution clock. */
  updatedAt?: number;
}

// ─── Device identity ──────────────────────────────────────────────────────────
let _deviceId: string | null = null;
export async function getDeviceId(): Promise<string> {
  if (_deviceId) return _deviceId;
  const d = await chrome.storage.local.get('ssense_device_id');
  if (d.ssense_device_id) return (_deviceId = d.ssense_device_id as string);
  const id = `dev_${crypto.randomUUID().slice(0, 12)}`;
  await chrome.storage.local.set({ ssense_device_id: id });
  return (_deviceId = id);
}

// ─── IndexedDB plumbing ───────────────────────────────────────────────────────
let _dbPromise: Promise<IDBDatabase> | null = null;

function openDb(): Promise<IDBDatabase> {
  if (_dbPromise) return _dbPromise;
  _dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: 'domain' });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => { _dbPromise = null; reject(req.error); };
  });
  return _dbPromise;
}

// Serialise read-modify-write cycles: without this, two quick events for the
// same domain (e.g. addTime + recordAudit) can each read the old row and the
// later put silently discards the earlier one.
let _chain: Promise<unknown> = Promise.resolve();
function serial<T>(fn: () => Promise<T>): Promise<T> {
  const run = _chain.then(fn, fn);
  _chain = run.catch(() => undefined);
  return run;
}

function sumValues(o?: Record<string, number>): number {
  return o ? Object.values(o).reduce((a, b) => a + (Number(b) || 0), 0) : 0;
}

/** Fills v1 fields on legacy rows and keeps totals consistent with per-device maps. */
export function normalizeEntry(e: SiteHistoryEntry, deviceId: string): SiteHistoryEntry {
  const out: SiteHistoryEntry = { ...e };
  if (!out.visitsByDevice) out.visitsByDevice = out.visitCount ? { [deviceId]: out.visitCount } : {};
  if (!out.timeByDevice) out.timeByDevice = out.totalTimeMs ? { [deviceId]: out.totalTimeMs } : {};
  out.visitCount = Math.max(sumValues(out.visitsByDevice), 0);
  out.totalTimeMs = Math.max(sumValues(out.timeByDevice), 0);
  if (!out.updatedAt) out.updatedAt = out.lastAuditAt || out.lastVisit || out.firstVisit || Date.now();
  return out;
}

async function rawGet(norm: string): Promise<SiteHistoryEntry | null> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, 'readonly').objectStore(STORE).get(norm);
    req.onsuccess = () => resolve((req.result as SiteHistoryEntry) ?? null);
    req.onerror = () => reject(req.error);
  });
}

async function rawPut(entry: SiteHistoryEntry): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put(entry);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

function blank(norm: string, now: number): SiteHistoryEntry {
  return {
    domain: norm, firstVisit: now, lastVisit: now,
    visitCount: 0, totalTimeMs: 0,
    lastScore: null, lastReport: null, lastAuditAt: null,
    scoreHistory: [], visitsByDevice: {}, timeByDevice: {}, updatedAt: now,
  };
}

async function mutate(
  domain: string,
  fn: (e: SiteHistoryEntry, now: number, deviceId: string) => boolean | void,
): Promise<SiteHistoryEntry | null> {
  const norm = normaliseDomain(domain);
  if (!norm) return null;
  return serial(async () => {
    const deviceId = await getDeviceId();
    const now = Date.now();
    const found = await rawGet(norm);
    const entry = normalizeEntry(found ?? blank(norm, now), deviceId);
    const touch = fn(entry, now, deviceId);
    entry.visitCount = sumValues(entry.visitsByDevice);
    entry.totalTimeMs = sumValues(entry.timeByDevice);
    if (touch !== false) entry.updatedAt = now;
    await rawPut(entry);
    return entry;
  });
}

// ─── Reads ────────────────────────────────────────────────────────────────────
export async function getEntry(domain: string): Promise<SiteHistoryEntry | null> {
  const norm = normaliseDomain(domain);
  if (!norm) return null;
  const e = await rawGet(norm);
  return e ? normalizeEntry(e, await getDeviceId()) : null;
}

export async function getAllEntries(): Promise<SiteHistoryEntry[]> {
  const db = await openDb();
  const deviceId = await getDeviceId();
  const rows: SiteHistoryEntry[] = await new Promise((resolve, reject) => {
    const req = db.transaction(STORE, 'readonly').objectStore(STORE).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
  return rows.map((r) => normalizeEntry(r, deviceId));
}

// ─── Writes ───────────────────────────────────────────────────────────────────
/** Once per navigation to a domain. */
export async function recordVisit(domain: string): Promise<void> {
  await mutate(domain, (e, now, dev) => {
    e.visitsByDevice![dev] = (e.visitsByDevice![dev] || 0) + 1;
    e.lastVisit = now;
  });
}

/** Active-tab time. Called every ~20s, so it only bumps the sync clock occasionally. */
export async function addTime(domain: string, deltaMs: number): Promise<void> {
  if (deltaMs <= 0) return;
  await mutate(domain, (e, now, dev) => {
    e.timeByDevice![dev] = (e.timeByDevice![dev] || 0) + deltaMs;
    if (!e.visitsByDevice![dev]) e.visitsByDevice![dev] = 1;
    return now - (e.updatedAt || 0) > 10 * 60_000; // false → don't touch updatedAt
  });
}

export async function recordAudit(domain: string, report: DpdpAuditReport, policyUrl?: string): Promise<void> {
  await mutate(domain, (e, now) => {
    const prev = e.lastScore;
    const score = report.dpdp_trust_score;
    const hist = e.scoreHistory || [];
    hist.push({ timestamp: now, score, delta: prev !== null ? score - prev : 0 });
    if (hist.length > MAX_SCORE_POINTS) hist.splice(0, hist.length - MAX_SCORE_POINTS);
    e.scoreHistory = hist;
    e.lastScore = score;
    e.lastReport = report;
    e.lastAuditAt = now;
    e.scanState = 'done';
    e.scanError = undefined;
    e.lastScanAt = now;
    if (policyUrl) e.policyUrl = policyUrl;
  });
}

/** Persist a terminal scan outcome (error / no policy / skipped / …). */
export async function recordScanState(domain: string, state: ScanState, error?: string): Promise<void> {
  await mutate(domain, (e, now) => {
    e.scanState = state;
    e.scanError = error;
    e.lastScanAt = now;
  });
}

export async function removeEntry(domain: string): Promise<void> {
  const norm = normaliseDomain(domain);
  if (!norm) return;
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).delete(norm);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function clearAllEntries(): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).clear();
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

// ─── Multi-device merge (pure; unit-tested) ───────────────────────────────────
function maxMerge(a?: Record<string, number>, b?: Record<string, number>): Record<string, number> {
  const out: Record<string, number> = { ...(a || {}) };
  for (const [k, v] of Object.entries(b || {})) out[k] = Math.max(out[k] || 0, Number(v) || 0);
  return out;
}

export function mergeEntries(local: SiteHistoryEntry | null, remote: SiteHistoryEntry, deviceId: string): SiteHistoryEntry {
  const R = normalizeEntry(remote, 'remote');
  if (!local) return R;
  const L = normalizeEntry(local, deviceId);

  const auditFrom = (R.lastAuditAt || 0) > (L.lastAuditAt || 0) ? R : L;
  const scanFrom = (R.lastScanAt || 0) > (L.lastScanAt || 0) ? R : L;

  const seen = new Map<number, ScoreHistoryPoint>();
  for (const p of [...(L.scoreHistory || []), ...(R.scoreHistory || [])]) seen.set(p.timestamp, p);
  const scoreHistory = [...seen.values()].sort((a, b) => a.timestamp - b.timestamp).slice(-MAX_SCORE_POINTS);

  const visitsByDevice = maxMerge(L.visitsByDevice, R.visitsByDevice);
  const timeByDevice = maxMerge(L.timeByDevice, R.timeByDevice);

  return {
    domain: L.domain,
    firstVisit: Math.min(L.firstVisit, R.firstVisit),
    lastVisit: Math.max(L.lastVisit, R.lastVisit),
    visitsByDevice, timeByDevice,
    visitCount: sumValues(visitsByDevice),
    totalTimeMs: sumValues(timeByDevice),
    lastScore: auditFrom.lastScore,
    lastReport: auditFrom.lastReport,
    lastAuditAt: auditFrom.lastAuditAt,
    policyUrl: auditFrom.policyUrl || L.policyUrl || R.policyUrl,
    scanState: scanFrom.scanState,
    scanError: scanFrom.scanError,
    lastScanAt: scanFrom.lastScanAt,
    scoreHistory,
    updatedAt: Math.max(L.updatedAt || 0, R.updatedAt || 0),
  };
}

/** Apply a record pulled from the server. Does NOT bump updatedAt (avoids sync ping-pong). */
export async function mergeRemote(remote: SiteHistoryEntry): Promise<{ merged: SiteHistoryEntry; changed: boolean }> {
  const norm = normaliseDomain(remote.domain);
  return serial(async () => {
    const deviceId = await getDeviceId();
    const local = await rawGet(norm);
    const merged = mergeEntries(local, { ...remote, domain: norm }, deviceId);
    const changed = !local || JSON.stringify(normalizeEntry(local, deviceId)) !== JSON.stringify(merged);
    if (changed) await rawPut(merged);
    return { merged, changed };
  });
}
