// apps/extension/src/background/audit-cache.ts
//
// Persistent local audit cache backed by IndexedDB with chrome.storage.local
// auto-migration and quota resilience.
//
// Why IndexedDB:
//   - chrome.storage.local has a strict ~10 MB quota that caps out at 2,500-3,000 domains.
//   - IndexedDB allows hundreds of MBs, indexed querying on audited_at,
//     and cursor-based iteration.
//   - Seamlessly migrates legacy chrome.storage.local entries on first run.

import type { AuditReport } from '../types/server-protocol';

export interface LocalAuditEntry {
  _v?:             number;   // schema version (1)
  domain:          string;   // normalized (no www.)
  trust_score:     number;
  subtlety_score:  number;
  violation_count: number;
  violations:      AuditReport['violations'];
  global_legal_reasoning: string;
  policy_url:      string;
  audited_at:      number;   // Unix ms
  age_days:        number;
  source:          string;
  previous_trust_score?: number | null;
  previous_audited_at?:  number | null;
}

const DB_NAME    = 'ssense_audit_cache';
const DB_VERSION = 1;
const STORE      = 'audits';
const SCHEMA_VERSION = 1;
const LEGACY_DOMAINS_KEY = 'audit_domains';
const LEGACY_PREFIX = 'audit:';

let _dbPromise: Promise<IDBDatabase> | null = null;
let _migrated = false;

import { normaliseDomain } from '../utils/domain';
export { normaliseDomain };

function openDb(): Promise<IDBDatabase> {
  if (_dbPromise) return _dbPromise;
  _dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: 'domain' });
        store.createIndex('audited_at', 'audited_at', { unique: false });
        store.createIndex('trust_score', 'trust_score', { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => {
      _dbPromise = null;
      reject(req.error);
    };
  });
  return _dbPromise;
}

async function getDb(): Promise<IDBDatabase> {
  try {
    const db = await openDb();
    if ((db as any).closePending || (db as any)._closed) {
      _dbPromise = null;
      return openDb();
    }
    return db;
  } catch {
    _dbPromise = null;
    return openDb();
  }
}

/** One-time migration from chrome.storage.local to IndexedDB. */
async function migrateLegacyStorage(): Promise<void> {
  if (_migrated) return;
  _migrated = true;
  try {
    const data = await chrome.storage.local.get(LEGACY_DOMAINS_KEY);
    const domains: string[] = data[LEGACY_DOMAINS_KEY];
    if (!Array.isArray(domains) || domains.length === 0) return;

    const keys = domains.map(d => `${LEGACY_PREFIX}${d}`);
    const records = await chrome.storage.local.get(keys);
    const db = await getDb();

    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      const store = tx.objectStore(STORE);
      for (const k of keys) {
        const entry = records[k];
        if (entry && entry.domain) {
          entry._v = SCHEMA_VERSION;
          entry.domain = normaliseDomain(entry.domain);
          store.put(entry);
        }
      }
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });

    // Clean up legacy chrome.storage keys to free quota
    await chrome.storage.local.remove([...keys, LEGACY_DOMAINS_KEY]);
    console.log(`[AuditCache] Migrated ${domains.length} cached audits from chrome.storage.local to IndexedDB.`);
  } catch (err) {
    console.warn('[AuditCache] Legacy migration check failed (non-fatal):', err);
  }
}

// ── Write ─────────────────────────────────────────────────────────────────────
export async function saveAudit(
  domain: string,
  report: AuditReport,
  meta: { policy_url?: string; source?: string; age_days?: number; audited_at?: number },
): Promise<LocalAuditEntry> {
  await migrateLegacyStorage();
  const norm = normaliseDomain(domain);
  const db   = await getDb();

  // Read prior entry to compute score diff
  const prior = await getAudit(norm);

  const entry: LocalAuditEntry = {
    _v:              SCHEMA_VERSION,
    domain:          norm,
    trust_score:     report.dpdp_trust_score,
    subtlety_score:  report.subtlety_score,
    violation_count: report.violations?.length ?? 0,
    violations:      report.violations ?? [],
    global_legal_reasoning: report.global_legal_reasoning ?? '',
    policy_url:      meta.policy_url ?? (prior?.policy_url || ''),
    audited_at:      meta.audited_at ?? Date.now(),
    age_days:        meta.age_days ?? 0,
    source:          meta.source ?? 'inference',
    previous_trust_score: prior ? prior.trust_score : null,
    previous_audited_at:  prior ? prior.audited_at : null,
  };

  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    const store = tx.objectStore(STORE);
    store.put(entry);
    tx.oncomplete = () => resolve(entry);
    tx.onerror = () => reject(tx.error);
  });
}

// ── Read one ──────────────────────────────────────────────────────────────────
export async function getAudit(domain: string): Promise<LocalAuditEntry | null> {
  await migrateLegacyStorage();
  const norm = normaliseDomain(domain);
  const db   = await getDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).get(norm);
    req.onsuccess = () => resolve((req.result as LocalAuditEntry) ?? null);
    req.onerror = () => reject(req.error);
  });
}

// ── Read all (sorted by audited_at DESC) ───────────────────────────────────────
export async function getAllAudits(): Promise<LocalAuditEntry[]> {
  await migrateLegacyStorage();
  const db = await getDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const index = tx.objectStore(STORE).index('audited_at');
    const results: LocalAuditEntry[] = [];
    const req = index.openCursor(null, 'prev'); // newest first
    req.onsuccess = () => {
      const cursor = req.result;
      if (cursor) {
        results.push(cursor.value);
        cursor.continue();
      } else {
        resolve(results);
      }
    };
    req.onerror = () => reject(req.error);
  });
}

// ── Remove one ────────────────────────────────────────────────────────────────
export async function removeAudit(domain: string): Promise<void> {
  await migrateLegacyStorage();
  const norm = normaliseDomain(domain);
  const db   = await getDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).delete(norm);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

// ── Clear all ─────────────────────────────────────────────────────────────────
export async function clearAllAudits(): Promise<void> {
  const db = await getDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).clear();
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}
