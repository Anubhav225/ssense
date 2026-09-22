// apps/extension/src/background/site-session.ts
//
// Chat-thread identity, decoupled from "whichever tab is active".
//
// Design (per product spec):
//   - Each site the user has chatted with (or audited) becomes a queued
//     "thread", tagged by domain. Threads are never merged — chat-store.ts
//     already keeps them fully separate per domain, and stays that way.
//   - Exactly ONE thread can be ACTIVE (selectable for composing) at a time.
//   - Selecting a new thread while another is active is REJECTED — the
//     caller must explicitly deselect first. This is enforced here, not
//     just in the UI, so a race (e.g. a stale message from an old tab)
//     can't silently steal the active slot.
//   - Opening a new site never deletes or overlaps an existing thread — it
//     just joins the queue, unselected, until the user explicitly picks it.
//   - Bounded queue: LRU eviction automatically caps unpinned inactive threads
//     at MAX_QUEUE_ENTRIES (50), preventing unbounded session growth over months.
//
// Persisted to chrome.storage.session (Chrome 112+): survives MV3
// service-worker recycling (the previous module-level-variable approach
// reset on every ~30s idle kill), but clears when the browser closes, so a
// stale "active site" is never silently carried into a new browsing
// session.

import { normaliseDomain } from '../utils/domain';

const ACTIVE_KEY = 'ssense_active_site';
const QUEUE_KEY  = 'ssense_site_queue';

/** Maximum unpinned queue entries allowed in the session before LRU eviction. */
export const MAX_QUEUE_ENTRIES = 50;

export interface QueuedSite {
  domain:       string;
  lastActiveAt: number;
  pinned:       boolean;
  /** Set when a background (non-active) thread received a new AI message
   *  the user hasn't seen yet — drives the unread dot in the queue UI. */
  unread:       boolean;
}

async function getQueueRaw(): Promise<QueuedSite[]> {
  const d = await chrome.storage.session.get(QUEUE_KEY);
  return (d[QUEUE_KEY] as QueuedSite[]) ?? [];
}

/** Prunes oldest unpinned entries if queue exceeds MAX_QUEUE_ENTRIES. */
async function setQueueRaw(q: QueuedSite[]): Promise<void> {
  let toSave = q;
  if (toSave.length > MAX_QUEUE_ENTRIES) {
    const active = await getActiveSite();
    const evictable = toSave
      .filter(s => !s.pinned && s.domain !== active)
      .sort((a, b) => a.lastActiveAt - b.lastActiveAt);

    const excess = toSave.length - MAX_QUEUE_ENTRIES;
    const evictDomains = new Set(evictable.slice(0, excess).map(s => s.domain));
    toSave = toSave.filter(s => !evictDomains.has(s.domain));
  }
  await chrome.storage.session.set({ [QUEUE_KEY]: toSave });
}

export async function getActiveSite(): Promise<string | null> {
  const d = await chrome.storage.session.get(ACTIVE_KEY);
  return (d[ACTIVE_KEY] as string) ?? null;
}

export async function getQueue(): Promise<QueuedSite[]> {
  return (await getQueueRaw()).sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    return b.lastActiveAt - a.lastActiveAt;
  });
}

/** Add a site to the queue if it isn't already there. Does NOT select it. */
export async function ensureQueued(domain: string): Promise<void> {
  const norm = normaliseDomain(domain);
  if (!norm) return;
  const q = await getQueueRaw();
  if (!q.find(s => s.domain === norm)) {
    q.push({ domain: norm, lastActiveAt: Date.now(), pinned: false, unread: false });
    await setQueueRaw(q);
  }
}

/**
 * Explicit select. Fails closed if another site is already active — the
 * caller (UI) must call deselectSite() first. This is the single choke
 * point that makes "one active thread at a time" a real invariant instead
 * of a UI convention.
 */
export async function selectSite(domain: string): Promise<{ ok: boolean; error?: string }> {
  const norm = normaliseDomain(domain);
  if (!norm) return { ok: false, error: 'Invalid domain.' };
  const current = await getActiveSite();
  if (current && current !== norm) {
    return { ok: false, error: `"${current}" is still selected — deselect it before switching.` };
  }
  await ensureQueued(norm);
  const q = await getQueueRaw();
  const entry = q.find(s => s.domain === norm);
  if (entry) { entry.lastActiveAt = Date.now(); entry.unread = false; }
  await setQueueRaw(q);
  await chrome.storage.session.set({ [ACTIVE_KEY]: norm });
  return { ok: true };
}

export async function deselectSite(): Promise<void> {
  await chrome.storage.session.remove(ACTIVE_KEY);
}

/** Removes a thread from the queue entirely (paired with deleting its
 *  chat history). Auto-deselects if it was the active one. */
export async function removeFromQueue(domain: string): Promise<void> {
  const norm = normaliseDomain(domain);
  const q = (await getQueueRaw()).filter(s => s.domain !== norm);
  await setQueueRaw(q);
  const active = await getActiveSite();
  if (active === norm) await deselectSite();
}

export async function togglePin(domain: string): Promise<void> {
  const norm = normaliseDomain(domain);
  const q = await getQueueRaw();
  const entry = q.find(s => s.domain === norm);
  if (entry) entry.pinned = !entry.pinned;
  await setQueueRaw(q);
}

/** Mark a background (non-active) thread as having a new unread AI reply.
 *  No-op for the currently active thread (it's visible, not "unread"). */
export async function markUnread(domain: string): Promise<void> {
  const norm = normaliseDomain(domain);
  const active = await getActiveSite();
  if (active === norm) return;
  const q = await getQueueRaw();
  const entry = q.find(s => s.domain === norm);
  if (entry) { entry.unread = true; await setQueueRaw(q); }
}
