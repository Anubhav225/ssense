// apps/extension/src/background/service-worker.ts
//
// Cloud-only, no native daemon, no PROXY_FETCH, no policy text storage.
// Primary audit trigger: FOUND_POLICY_URL from extractor.ts → server fetches
// and extracts → result saved to local audit-cache (IndexedDB).
//
// R5 upgrades:
//   - Per-domain chat serialization queue (Map<domain, Promise>)
//   - Long-lived port relay for real-time SSE token streaming
//   - SWR offline-first audit resolution & cache pre-warming
//   - MAX_CONCURRENT_AUDITS semaphore gate
//   - Dynamic action badge reflecting live DPDP trust scores

import { executeAuditByUrl, executeFetchCachedAudit, executeChat, executeHealthCheck, getServerConfig } from './api-client';
import * as auditCache from './audit-cache';
import * as historyStore from './history-store';
import * as chatStore from './chat-store';
import * as offlineCacheManager from './offline-cache-manager';
import * as siteSession from './site-session';
import type { ServiceResponse } from '../types/server-protocol';

console.log('[Ssense] Service Worker v6.1 — multi-user scale, streaming chat, offline-first cache.');

// Pre-warm top domains in the background
offlineCacheManager.warmTopDomainCaches().catch(() => {});

// ─── Notifications ─────────────────────────────────────────────────────────────
function notify(id: string, title: string, message: string) {
  chrome.notifications.create(id, { type:'basic', iconUrl:'icons/icon128.png', title, message, priority:1 }, () => void chrome.runtime.lastError);
}
chrome.notifications.onClicked.addListener(id => { if (id.startsWith('ssense-')) chrome.action.openPopup?.().catch(()=>{}); });

// ─── Action Badge Management ──────────────────────────────────────────────────
async function updateActionBadge(domain: string | null) {
  if (!domain) {
    chrome.action.setBadgeText({ text: '' }).catch(() => {});
    return;
  }
  try {
    const entry = await auditCache.getAudit(domain);
    if (!entry) {
      chrome.action.setBadgeText({ text: '?' }).catch(() => {});
      chrome.action.setBadgeBackgroundColor({ color: '#71717A' }).catch(() => {});
      return;
    }
    const score = entry.trust_score;
    chrome.action.setBadgeText({ text: String(score) }).catch(() => {});
    const color = score >= 80 ? '#10B981' : score >= 50 ? '#F59E0B' : '#F43F5E';
    chrome.action.setBadgeBackgroundColor({ color }).catch(() => {});
  } catch {}
}

// ─── Time-on-site tracking ─────────────────────────────────────────────────────
let _domain: string|null=null, _since: number|null=null, _focused=true;
function hostnameOf(url?: string) { try { return url?.startsWith('http') ? new URL(url).hostname : null; } catch { return null; } }
async function flush() { if (_domain&&_since) await historyStore.addTime(_domain, Date.now()-_since); _since=null; }
async function startTracking(d: string|null) { await flush(); _domain=d; _since=(d&&_focused)?Date.now():null; }
async function syncTab() {
  const [tab]=await chrome.tabs.query({active:true,lastFocusedWindow:true}).catch(()=>[]);
  const d=hostnameOf(tab?.url);
  if (d!==_domain) {
    if (d) await historyStore.recordVisit(d);
    await startTracking(d);
  }
  updateActionBadge(d).catch(() => {});
}
chrome.tabs.onActivated.addListener(()=>syncTab());
chrome.tabs.onUpdated.addListener((_,i,t)=>{ if (i.status==='complete'&&t.active) syncTab(); });
chrome.windows.onFocusChanged.addListener(async wid=>{
  _focused=wid!==chrome.windows.WINDOW_ID_NONE;
  _focused ? syncTab() : flush();
});
setInterval(()=>{ flush().then(()=>{ _since=(_domain&&_focused)?Date.now():null; }); }, 20_000);
syncTab();

// ─── Chat Queue per domain ────────────────────────────────────────────────────
const _chatQueues = new Map<string, Promise<any>>();
async function enqueueChat<T>(domain: string, task: () => Promise<T>): Promise<T> {
  const norm = auditCache.normaliseDomain(domain);
  const prev = _chatQueues.get(norm) || Promise.resolve();
  const current = prev.catch(() => {}).then(task);
  _chatQueues.set(norm, current);
  try {
    return await current;
  } finally {
    if (_chatQueues.get(norm) === current) {
      _chatQueues.delete(norm);
    }
  }
}

// ─── Streaming Chat Relay (Long-lived port) ───────────────────────────────────
chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== 'ssense-chat-stream') return;

  // MV3 Keepalive: ping client and platformInfo every 10s to prevent service worker termination
  const keepAlive = setInterval(() => {
    try {
      port.postMessage({ type: 'PING' });
      chrome.runtime.getPlatformInfo().catch(() => {});
    } catch {
      clearInterval(keepAlive);
    }
  }, 10_000);

  port.onDisconnect.addListener(() => {
    clearInterval(keepAlive);
  });

  port.onMessage.addListener(async (msg) => {
    if (msg.type === 'START_CHAT') {
      const { domain, userPrompt, responseMode, requestId } = msg;
      if (!domain || !userPrompt) {
        port.postMessage({ type: 'ERROR', error: 'Missing domain or userPrompt' });
        return;
      }

      // Source of truth for "which thread is this message for" is the
      // background's own active-site record, NOT whatever the sender
      // claims — this is what makes cross-thread bleed structurally
      // impossible instead of merely unlikely. A stale UI (e.g. a port
      // opened just before the user deselected) gets rejected here.
      const active = await siteSession.getActiveSite();
      if (!active) {
        port.postMessage({ type: 'ERROR', error: 'No site is selected for chat. Select a site first.', errorKind: 'no_active_site' });
        return;
      }
      if (auditCache.normaliseDomain(domain) !== active) {
        port.postMessage({ type: 'ERROR', error: `"${active}" is the selected thread — this message was for a different site and was not sent.`, errorKind: 'stale_thread' });
        return;
      }

      await enqueueChat(domain, async () => {
        try {
          const res = await executeChat(
            domain,
            userPrompt,
            requestId || crypto.randomUUID(),
            (delta, done) => {
              try {
                port.postMessage({ type: 'CHUNK', delta, done, domain });
              } catch {}
            },
            responseMode || 'concise'
          );

          if (res.type === 'CHAT_RESULT' && res.success) {
            await chatStore.addMessage(domain, 'user', userPrompt);
            await chatStore.addMessage(domain, 'ai', res.message);
            // If the user switched the active thread away while this
            // request was in flight, the reply still lands correctly in
            // storage (keyed by `domain`, not by "whatever's on screen"),
            // and the now-background thread is flagged unread instead of
            // being lost or misrouted.
            const stillActive = await siteSession.getActiveSite();
            if (stillActive !== auditCache.normaliseDomain(domain)) {
              await siteSession.markUnread(domain);
            }
            port.postMessage({ type: 'DONE', fullText: res.message, rateLimit: res.rateLimit });
          } else {
            const errRes = res as any;
            port.postMessage({
              type: 'ERROR',
              error: errRes.error || 'Chat request failed',
              errorKind: errRes.errorKind,
              retryable: errRes.retryable,
              rateLimit: errRes.rateLimit,
            });
          }
        } catch (err: any) {
          port.postMessage({ type: 'ERROR', error: err?.message || 'Chat stream failed' });
        }
      });
    }
  });
});

// ─── In-flight deduplication (30-min LRU) & Audit Concurrency Gate ───────────
const _active  = new Map<string,Promise<ServiceResponse>>();
const _lru     = new Map<string,{ts:number;resp:ServiceResponse}>();
const LRU_TTL  = 30*60*1000;
const MAX_CONCURRENT_AUDITS = 3;
let _concurrentAudits = 0;

async function domainKey(domain: string, suffix='') {
  const buf=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(`${domain}${suffix}`));
  return Array.from(new Uint8Array(buf)).map(b=>b.toString(16).padStart(2,'0')).join('');
}

// ─── Message handler ───────────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  handleMessage(msg, sender)
    .then(r=>{ try{sendResponse(r);}catch{} })
    .catch(e=>{ try{sendResponse({success:false,error:e.message});}catch{} });
  return true;
});

async function handleMessage(msg: any, sender: chrome.runtime.MessageSender): Promise<any> {
  const requestId = crypto.randomUUID();
  const tabId     = sender.tab?.id;

  switch (msg.type) {

    // ── Primary audit trigger — extractor found the policy URL ─────────────
    case 'FOUND_POLICY_URL': {
      if (!msg.domain||!msg.policyUrl) return {success:false,error:'Missing domain or policyUrl.'};
      return _triggerAudit(msg.domain, msg.policyUrl, requestId, tabId, false);
    }

    // ── Manual re-audit (Audit button, force_refresh) ──────────────────────
    case 'AUDIT_BY_URL': {
      if (!msg.domain||!msg.policyUrl) return {success:false,error:'Missing domain or policyUrl.'};
      return _triggerAudit(msg.domain, msg.policyUrl, requestId, tabId, Boolean(msg.forceRefresh));
    }

    // ── Retry: re-inject extractor into active tab ─────────────────────────
    case 'RETRY_EXTRACTION': {
      const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
      if (!tab?.id) return {success:false,error:'No active tab.'};
      try {
        await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>{(window as any).__ssenseExtractorLoaded=false;}});
        await chrome.scripting.executeScript({target:{tabId:tab.id},files:['content/extractor.js']});
        return {success:true};
      } catch(e:any) { return {success:false,error:e?.message||'Re-injection failed.'}; }
    }

    // ── Extraction failed (no URL found) ──────────────────────────────────
    case 'EXTRACTION_FAILED': {
      chrome.runtime.sendMessage({type:'AUDIT_ERROR',domain:msg.domain,
        error:msg.reason||"Could not find a privacy policy on this page.",
        errorKind:'extraction',retryable:true}).catch(()=>{});
      return {success:true};
    }

    // ── Fetch server-cached audit (no URL needed — domain only) ───────────
    case 'FETCH_CACHED_AUDIT': {
      const r=await executeFetchCachedAudit(String(msg.domain||''),requestId);
      if (r.type==='AUDIT_POLICY_RESULT'&&r.success) {
        await auditCache.saveAudit(msg.domain,r.report,{source:'persistent_cache'} as any);
        updateActionBadge(msg.domain).catch(() => {});
      }
      return r;
    }

    // ── Health check ──────────────────────────────────────────────────────
    case 'HEALTH_CHECK': return executeHealthCheck(requestId);

    // ── Audit cache reads (with SWR support) ──────────────────────────────
    case 'GET_LOCAL_AUDIT': {
      const entry=await auditCache.getAudit(String(msg.domain||''));
      return {success:true,entry:entry??null};
    }
    case 'GET_LOCAL_AUDIT_WITH_META': {
      const meta = await offlineCacheManager.getAuditSWR(String(msg.domain || ''), msg.policyUrl);
      return { success: true, ...meta };
    }
    case 'GET_ALL_AUDITS': {
      const entries=await auditCache.getAllAudits();
      return {success:true,entries};
    }
    case 'CLEAR_AUDITS': {
      await auditCache.clearAllAudits();
      updateActionBadge(null).catch(() => {});
      return {success:true};
    }

    // ── Trust score (from local cache) ────────────────────────────────────
    case 'GET_TRUST_SCORE': {
      const e=await auditCache.getAudit(String(msg.domain||''));
      return {type:'TRUST_SCORE_RESULT',requestId,success:true,score:e?.trust_score??null};
    }

    // ── History ───────────────────────────────────────────────────────────
    case 'GET_HISTORY': {
      const entries=await historyStore.getAllEntries();
      entries.sort((a:any,b:any)=>b.lastVisit-a.lastVisit);
      return {success:true,entries};
    }
    case 'CLEAR_HISTORY': { await historyStore.clearAllEntries(); return {success:true}; }
    case 'GET_SITE_HISTORY': {
      const e=await historyStore.getEntry(String(msg.domain||''));
      return {success:true,entry:e??null};
    }

    // ── Chat (Serialized per-domain, gated to the active thread) ───────────
    case 'CHAT': {
      const active = await siteSession.getActiveSite();
      if (!active) return { success:false, error:'No site is selected for chat. Select a site first.', errorKind:'no_active_site' };
      if (auditCache.normaliseDomain(msg.domain) !== active) {
        return { success:false, error:`"${active}" is the selected thread.`, errorKind:'stale_thread' };
      }
      return enqueueChat(msg.domain, async () => {
        const r=await executeChat(msg.domain,msg.userPrompt,requestId,undefined,msg.responseMode);
        if (r.type==='CHAT_RESULT'&&r.success) {
          await chatStore.addMessage(msg.domain,'user',msg.userPrompt);
          await chatStore.addMessage(msg.domain,'ai',r.message);
          const stillActive = await siteSession.getActiveSite();
          if (stillActive !== auditCache.normaliseDomain(msg.domain)) {
            await siteSession.markUnread(msg.domain);
          }
        }
        return r;
      });
    }
    case 'GET_CHAT_HISTORY': return {success:true,messages:await chatStore.getMessagesForDomain(msg.domain)};
    case 'CLEAR_CHAT_HISTORY': {
      await chatStore.clearMessagesForDomain(msg.domain);
      await siteSession.removeFromQueue(msg.domain);
      return {success:true};
    }

    // ── Site-thread queue: single active thread, explicit select/deselect ──
    case 'GET_SITE_QUEUE': return { success:true, queue: await siteSession.getQueue(), active: await siteSession.getActiveSite() };
    case 'SELECT_SITE_THREAD': {
      if (!msg.domain) return { success:false, error:'Missing domain.' };
      const r = await siteSession.selectSite(msg.domain);
      return { success: r.ok, error: r.error };
    }
    case 'DESELECT_SITE_THREAD': { await siteSession.deselectSite(); return { success:true }; }
    case 'REMOVE_SITE_THREAD': {
      if (!msg.domain) return { success:false, error:'Missing domain.' };
      await chatStore.clearMessagesForDomain(msg.domain);
      await siteSession.removeFromQueue(msg.domain);
      return { success:true };
    }
    case 'TOGGLE_PIN_SITE_THREAD': {
      if (!msg.domain) return { success:false, error:'Missing domain.' };
      await siteSession.togglePin(msg.domain);
      return { success:true, queue: await siteSession.getQueue() };
    }

    // ── Engine config ─────────────────────────────────────────────────────
    case 'GET_ENGINE_CONFIG': {
      const cfg = await getServerConfig();
      return { configured: cfg.configured, url: cfg.url, isOverride: cfg.isOverride };
    }
    case 'CLEAR_INFERENCE_CACHE': { _lru.clear(); return {success:true}; }

    // ── UI ────────────────────────────────────────────────────────────────
    case 'OPEN_SIDE_PANEL': {
      const wid=sender.tab?.windowId;
      if (wid===undefined) return {success:false,error:'No window context.'};
      try { await chrome.sidePanel.open({windowId:wid}); return {success:true}; }
      catch(e:any) { return {success:false,error:e?.message||'Could not open side panel.'}; }
    }
    case 'OPEN_OPTIONS_PAGE': { chrome.runtime.openOptionsPage(); return {success:true}; }

    default: throw new Error(`Unknown message type: ${msg.type}`);
  }
}

// ─── Shared audit execution ────────────────────────────────────────────────────
async function _triggerAudit(
  domain: string, policyUrl: string, requestId: string,
  tabId: number|undefined, forceRefresh: boolean,
): Promise<ServiceResponse> {
  const ck = await domainKey(domain, forceRefresh?'force':'');

  // LRU dedup for non-force requests
  if (!forceRefresh) {
    const cached=_lru.get(ck);
    if (cached&&Date.now()-cached.ts<LRU_TTL) {
      const r=cached.resp;
      if (r.type==='AUDIT_POLICY_RESULT'&&r.success) {
        updateActionBadge(domain).catch(() => {});
        if (tabId) chrome.tabs.sendMessage(tabId,{type:'ENFORCE_DPDP_RULES',report:r.report}).catch(()=>{});
      }
      return r;
    }
    const inflight=_active.get(ck);
    if (inflight) return inflight;
  }

  // Concurrency gate
  while (_concurrentAudits >= MAX_CONCURRENT_AUDITS) {
    await new Promise(r => setTimeout(r, 200));
  }

  _concurrentAudits++;
  const exec=(async()=>{
    const keepAlive = setInterval(() => {
      chrome.runtime.getPlatformInfo().catch(() => {});
    }, 15_000);
    try {
      const r=await executeAuditByUrl(domain,policyUrl,requestId,forceRefresh);

      if (r.type==='AUDIT_POLICY_RESULT'&&r.success) {
        // Save entry to IndexedDB local cache
        const saved = await auditCache.saveAudit(domain,r.report,{
          policy_url: (r as any).policy_url||policyUrl,
          source:     (r as any).cached?'persistent_cache':'inference',
          age_days:   (r as any).age_days??0,
        });
        await historyStore.recordAudit(domain,r.report);
        // Joins the site-thread queue (unselected) so it's pickable for
        // chat without forcing it to become the active thread.
        await siteSession.ensureQueued(domain);

        if (!forceRefresh) _lru.set(ck,{ts:Date.now(),resp:r});

        updateActionBadge(domain).catch(() => {});

        chrome.runtime.sendMessage({
          type:'AUDIT_COMPLETE',
          domain,
          score:r.report.dpdp_trust_score,
          report:r.report,
          source: saved.source,
          previousScore: saved.previous_trust_score,
        }).catch(()=>{});

        if (r.report.dpdp_trust_score<40)
          notify(`ssense-${domain}`,`Low privacy score: ${domain}`,
            `Trust score ${r.report.dpdp_trust_score}/100 — open Ssense for details.`);

        if (tabId) chrome.tabs.sendMessage(tabId,{type:'ENFORCE_DPDP_RULES',report:r.report}).catch(()=>{});
      } else if (r.type==='ERROR') {
        chrome.runtime.sendMessage({type:'AUDIT_ERROR',domain,
          error:r.error,errorKind:r.errorKind,retryable:r.retryable}).catch(()=>{});
      }
      return r;
    } finally {
      clearInterval(keepAlive);
      _concurrentAudits--;
      _active.delete(ck);
    }
  })();

  if (!forceRefresh) _active.set(ck,exec);
  return exec;
}
