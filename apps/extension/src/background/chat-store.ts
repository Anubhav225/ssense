// apps/extension/src/background/chat-store.ts
//
// Persists chatbot conversation history, per domain. Lives in the SERVICE
// WORKER (extension origin), not in the content script that renders the
// widget. This matters: a content script's IndexedDB is scoped to the
// HOST PAGE's origin, not the extension's — writing chat history there
// would silently fragment it across every site's own storage and leak
// extension data into site storage. Routing every write through a
// background message keeps it in one place, under the extension's own
// origin, matching how history-store.ts already handles audit data.
//
// R5 changes:
//   - Domain normalization (strips www.) to match audit-cache.ts behaviour
//   - Per-domain message cap: only the last CHAT_HISTORY_LIMIT messages are
//     kept. Prevents unbounded growth on long-lived sessions.
//   - DB reconnect: if _dbPromise resolves to a broken connection (quota
//     eviction, version mismatch) the module resets and re-opens cleanly.
//   - addMessage returns the id of the inserted record for dedup tracking.

const DB_NAME    = 'ssense_chat_history';
const DB_VERSION = 1;
const STORE      = 'messages';

/** Maximum messages retained per domain. Oldest records are pruned on write. */
export const CHAT_HISTORY_LIMIT = 100;

export interface ChatMessage {
  id?:       number;   // autoIncrement primary key
  domain:    string;   // normalised (no www.)
  role:      'user' | 'ai';
  text:      string;
  timestamp: number;
}

let _dbPromise: Promise<IDBDatabase> | null = null;

import { normaliseDomain } from '../utils/domain';

function openDb(): Promise<IDBDatabase> {
  if (_dbPromise) return _dbPromise;
  _dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
        store.createIndex('domain',    'domain',    { unique: false });
        store.createIndex('domain_ts', ['domain','timestamp'], { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror  = () => {
      _dbPromise = null;   // allow retry on next call
      reject(req.error);
    };
  });
  return _dbPromise;
}

/** Get a live DB connection, resetting if the previous one was closed. */
async function getDb(): Promise<IDBDatabase> {
  try {
    const db = await openDb();
    // Chrome can mark a connection as closed after a force-kill; detect it.
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

// ── Write ──────────────────────────────────────────────────────────────────────
export async function addMessage(domain: string, role: 'user' | 'ai', text: string): Promise<void> {
  if (!domain || !text) return;
  const norm = normaliseDomain(domain);
  const db   = await getDb();

  await new Promise<void>((resolve, reject) => {
    const tx    = db.transaction(STORE, 'readwrite');
    const store = tx.objectStore(STORE);

    // 1. Insert the new message.
    store.add({ domain: norm, role, text, timestamp: Date.now() });

    // 2. After insert, prune oldest records beyond CHAT_HISTORY_LIMIT.
    //    We do this in the same transaction to avoid a race between
    //    concurrent addMessage calls inflating the count.
    const countReq = store.index('domain').count(IDBKeyRange.only(norm));
    countReq.onsuccess = () => {
      const count = countReq.result;
      if (count > CHAT_HISTORY_LIMIT) {
        // Fetch the oldest (count - CHAT_HISTORY_LIMIT) records to delete.
        const toPrune = count - CHAT_HISTORY_LIMIT;
        const cursorReq = store.index('domain_ts').openCursor(
          IDBKeyRange.bound([norm, 0], [norm, Infinity])
        );
        let pruned = 0;
        cursorReq.onsuccess = () => {
          const cursor = cursorReq.result;
          if (cursor && pruned < toPrune) {
            cursor.delete();
            pruned++;
            cursor.continue();
          }
        };
      }
    };

    tx.oncomplete = () => resolve();
    tx.onerror   = () => reject(tx.error);
  });
}

// ── Read ───────────────────────────────────────────────────────────────────────
export async function getMessagesForDomain(domain: string): Promise<ChatMessage[]> {
  const norm = normaliseDomain(domain);
  const db   = await getDb();
  return new Promise((resolve, reject) => {
    const tx  = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).index('domain').getAll(IDBKeyRange.only(norm));
    req.onsuccess = () => {
      const results = (req.result || []) as ChatMessage[];
      results.sort((a, b) => a.timestamp - b.timestamp);
      // Honour the cap on read too — in case legacy records exceed it.
      resolve(results.slice(-CHAT_HISTORY_LIMIT));
    };
    req.onerror = () => reject(req.error);
  });
}

// ── Clear ──────────────────────────────────────────────────────────────────────
export async function clearMessagesForDomain(domain: string): Promise<void> {
  const norm = normaliseDomain(domain);
  const db   = await getDb();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction(STORE, 'readwrite');
    const index = tx.objectStore(STORE).index('domain');
    const req   = index.openCursor(IDBKeyRange.only(norm));
    req.onsuccess = () => {
      const cursor = req.result;
      if (cursor) { cursor.delete(); cursor.continue(); }
    };
    tx.oncomplete = () => resolve();
    tx.onerror   = () => reject(tx.error);
  });
}

export async function clearAllMessages(): Promise<void> {
  const db = await getDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).clear();
    tx.oncomplete = () => resolve();
    tx.onerror   = () => reject(tx.error);
  });
}
