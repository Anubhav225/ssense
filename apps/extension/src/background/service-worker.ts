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

import {
  executeAuditByUrl,
  executeAuditPolicy,
  executeFetchCachedAudit,
  executeChat,
  executeHealthCheck,
  getServerConfig,
  fetchServerPing,
  registerDevice,
  sendHeartbeat,
  fetchUserProfile,
} from './api-client';
import * as auditCache from './audit-cache';
import * as historyStore from './history-store';
import * as chatStore from './chat-store';
import * as offlineCacheManager from './offline-cache-manager';
import * as siteSession from './site-session';
import * as auth from './auth';
import * as prefsStore from './prefs';
import * as scans from './scan-manager';
import * as sync from './sync-manager';
import { isScannableHost } from '../utils/status';
import type { ServiceResponse, AuditReport } from '../types/server-protocol';

console.log('[Ssense] Service Worker v1.0 — verified sign-in, auto-scan, cross-device sync.');

// ─── Install / startup ─────────────────────────────────────────────────────────
// Content scripts only attach to pages loaded AFTER install, so we inject the
// extractor into tabs that are already open — otherwise the first minutes after
// sign-in would look like "nothing is being scanned".
async function scanOpenTabs(limit = 12) {
  const prefs = await prefsStore.getPrefs();
  if (!prefs.autoScan) return;
  const tabs = await chrome.tabs.query({ url: ['http://*/*', 'https://*/*'] }).catch(() => []);
  let n = 0;
  for (const t of tabs) {
    if (n >= limit) break;
    const host = hostnameOf(t.url);
    if (!t.id || !host || !isScannableHost(host) || prefsStore.isIgnored(prefs, host)) continue;
    n++;
    chrome.scripting.executeScript({ target: { tabId: t.id }, files: ['content/extractor.js'] }).catch(() => {});
  }
}

chrome.runtime.onInstalled.addListener(async (details) => {
  console.log('[Ssense] Extension installed / updated. Reason:', details?.reason);
  sync.registerSyncAlarms();
  await applyToolbarActionConfig().catch(() => {});
  if (details?.reason === 'install') {
    // First run: full-page welcome with Google sign-in (a popup can't stay open through the OAuth window).
    chrome.tabs.create({ url: chrome.runtime.getURL('welcome.html') });
  }
  try {
    const st = await auth.getAuthState();
    if (st.signedIn) sync.syncNow('installed').catch(() => {});
    scanOpenTabs().catch(() => {});
  } catch (err) {
    console.warn('[Ssense] Post-install check deferred:', err);
  }
});

chrome.runtime.onStartup.addListener(() => {
  sync.registerSyncAlarms();
  applyToolbarActionConfig().catch(() => {});
  sync.syncNow('startup').catch(() => {});
});

chrome.alarms.onAlarm.addListener((a) => {
  if (a.name === 'ssense-sync-periodic' || a.name === 'ssense-sync-soon') sync.syncNow(a.name).catch(() => {});
});

// Sync again as soon as the network returns.
self.addEventListener('online', () => { sync.syncNow('online').catch(() => {}); });

// Pre-warm top domains in the background
offlineCacheManager.warmTopDomainCaches().catch(() => {});

// ─── Toolbar Action Management ────────────────────────────────────────────────
export async function applyToolbarActionConfig() {
  try {
    const prefs = await prefsStore.getPrefs();
    const action = prefs.toolbarAction || 'sidepanel';
    if (action === 'sidepanel') {
      await chrome.action.setPopup({ popup: '' });
      if (chrome.sidePanel?.setPanelBehavior) {
        await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
      }
    } else if (action === 'tab') {
      await chrome.action.setPopup({ popup: '' });
      if (chrome.sidePanel?.setPanelBehavior) {
        await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false }).catch(() => {});
      }
    } else {
      if (chrome.sidePanel?.setPanelBehavior) {
        await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false }).catch(() => {});
      }
      await chrome.action.setPopup({ popup: 'popup.html' });
    }
  } catch (err) {
    console.warn('[Ssense] Failed to apply toolbar action config:', err);
  }
}
applyToolbarActionConfig().catch(() => {});

chrome.action.onClicked?.addListener(async (tab) => {
  try {
    const prefs = await prefsStore.getPrefs();
    const action = prefs.toolbarAction || 'sidepanel';
    if (action === 'sidepanel') {
      if (tab?.windowId !== undefined && chrome.sidePanel?.open) {
        try {
          await chrome.sidePanel.open({ windowId: tab.windowId });
          return;
        } catch {}
      }
    }
    // Open full widescreen dashboard in a tab
    chrome.tabs.create({ url: chrome.runtime.getURL('sidepanel.html') });
  } catch {
    chrome.tabs.create({ url: chrome.runtime.getURL('sidepanel.html') });
  }
});

// ─── Notifications ─────────────────────────────────────────────────────────────
function notify(id: string, title: string, message: string) {
  chrome.notifications.create(id, { type:'basic', iconUrl:'icons/icon128.png', title, message, priority:1 }, () => void chrome.runtime.lastError);
}
chrome.notifications.onClicked.addListener(id => { if (id.startsWith('ssense-')) chrome.action.openPopup?.().catch(()=>{}); });

// ─── Action Badge Management ──────────────────────────────────────────────────
async function updateActionBadge(domain: string | null) {
  const setText = (text: string, color?: string) => {
    chrome.action.setBadgeText({ text }).catch(() => {});
    if (color) chrome.action.setBadgeBackgroundColor({ color }).catch(() => {});
  };
  try {
    const prefs = await prefsStore.getPrefs();
    if (!domain || !prefs.showBadge) return setText('');
    const rec = await scans.getScanRecord(domain);
    if (rec && (rec.state === 'scanning' || rec.state === 'queued')) return setText('…', '#0EA5E9');
    const entry = await auditCache.getAudit(domain);
    if (!entry) return setText(rec?.state === 'error' ? '!' : '', rec?.state === 'error' ? '#F59E0B' : undefined);
    const score = entry.trust_score;
    setText(String(score), score >= 80 ? '#10B981' : score >= 50 ? '#F59E0B' : '#F43F5E');
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
      return autoScan(msg.domain, msg.policyUrl, requestId, tabId);
    }

    // ── Manual re-audit (Audit button, force_refresh) ──────────────────────
    case 'AUDIT_BY_URL': {
      if (!msg.domain||!msg.policyUrl) return {success:false,error:'Missing domain or policyUrl.'};
      const gate = await requireSignIn(msg.domain);
      if (gate) return gate;
      return _triggerAudit(msg.domain, msg.policyUrl, requestId, tabId, Boolean(msg.forceRefresh));
    }

    // ── "Scan now" from popup / history: use the known policy URL, else re-extract ──
    case 'SCAN_NOW': {
      const domain = auditCache.normaliseDomain(String(msg.domain || ''));
      if (!domain) return {success:false,error:'Missing domain.'};
      const gate = await requireSignIn(domain);
      if (gate) return gate;
      const [known, hist] = await Promise.all([auditCache.getAudit(domain), historyStore.getEntry(domain)]);
      const policyUrl = msg.policyUrl || known?.policy_url || hist?.policyUrl;
      if (policyUrl) return _triggerAudit(domain, policyUrl, requestId, undefined, true);
      // Unknown policy URL → ask the page. Mark it forced so the freshness gate is bypassed.
      _forceNext.add(domain);
      await scans.setScan(domain, { state: 'queued' });
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab?.id && hostnameOf(tab.url) && auditCache.normaliseDomain(hostnameOf(tab.url)!) === domain) {
        try {
          await chrome.scripting.executeScript({ target:{tabId:tab.id}, func:()=>{(window as any).__ssenseExtractorLoaded=false;} });
          await chrome.scripting.executeScript({ target:{tabId:tab.id}, files:['content/extractor.js'] });
          return { success:true, started:true };
        } catch(e:any) { _forceNext.delete(domain); return {success:false,error:e?.message||'Could not read the page.'}; }
      }
      _forceNext.delete(domain);
      await scans.clearScans().catch(()=>{});
      return { success:false, error:'Open this site in a tab to scan it — its policy link is not known yet.', errorKind:'needs_page' };
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
      const domain = auditCache.normaliseDomain(String(msg.domain||''));
      if (!domain) return {success:true};
      const local = await auditCache.getAudit(domain);
      // Already audited before? A flaky page shouldn't overwrite a good result with "no policy".
      if (!local) {
        const reason = msg.reason || "Could not find a privacy policy on this page.";
        await scans.setScan(domain, { state:'nopolicy', error: reason });
        await historyStore.recordScanState(domain, 'nopolicy', reason);
        updateActionBadge(domain).catch(()=>{});
      }
      _forceNext.delete(domain);
      chrome.runtime.sendMessage({type:'AUDIT_ERROR',domain,
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
    case 'CLEAR_HISTORY': {
      await historyStore.clearAllEntries();
      await auditCache.clearAllAudits();
      await scans.clearScans();
      updateActionBadge(null).catch(()=>{});
      await chrome.storage.local.remove('ssense_sync_state'); // next sync re-pulls from the account if sync is on
      chrome.runtime.sendMessage({ type:'HISTORY_CHANGED' }).catch(()=>{});
      return {success:true};
    }
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

    // ── Handshake & User Management ──────────────────────────────────────
    case 'GET_SERVER_PING': {
      const res = await fetchServerPing(msg.url);
      return { success: res.online, ...res };
    }
    case 'REGISTER_DEVICE': {
      const res = await registerDevice(
        msg.name,
        msg.email,
        msg.deviceName,
        msg.inviteCode,
        msg.googleId,
        msg.avatarUrl,
      );
      return res;
    }
    case 'SEND_HEARTBEAT': {
      const ok = await sendHeartbeat();
      return { success: ok };
    }
    case 'GET_USER_PROFILE': {
      const profile = await fetchUserProfile();
      return { success: Boolean(profile), profile };
    }

    // ── Account ───────────────────────────────────────────────────────────
    case 'GET_AUTH_STATE': return { success:true, ...(await auth.getAuthState()) };
    case 'SIGN_IN_GOOGLE': {
      const r = await auth.signInWithGoogle();
      if (r.success) {
        chrome.runtime.sendMessage({ type:'AUTH_CHANGED', signedIn:true }).catch(()=>{});
        sync.registerSyncAlarms();
        sync.syncNow('sign-in').catch(()=>{});
        scanOpenTabs().catch(()=>{});
        syncTab().catch(()=>{});
        if (r.switchedAccount) chrome.runtime.sendMessage({ type:'HISTORY_CHANGED' }).catch(()=>{});
      }
      return r;
    }
    case 'SIGN_OUT': {
      await auth.signOut({ keepLocalData: Boolean(msg.keepLocalData) });
      await scans.clearScans();
      updateActionBadge(null).catch(()=>{});
      chrome.runtime.sendMessage({ type:'AUTH_CHANGED', signedIn:false }).catch(()=>{});
      return { success:true };
    }

    // ── Preferences ───────────────────────────────────────────────────────
    case 'GET_PREFS': return { success:true, prefs: await prefsStore.getPrefs() };
    case 'SET_PREFS': {
      const prefs = await prefsStore.setPrefs(msg.patch || {});
      if (msg.patch?.toolbarAction) applyToolbarActionConfig().catch(()=>{});
      chrome.runtime.sendMessage({ type:'PREFS_CHANGED', prefs }).catch(()=>{});
      if (prefs.syncEnabled) sync.scheduleSync();
      syncTab().catch(()=>{});
      if (msg.patch?.autoScan === true) scanOpenTabs().catch(()=>{});
      return { success:true, prefs };
    }

    // ── Scan status + combined overview for History / popup ───────────────
    case 'GET_SCAN_STATUS': return { success:true, records: await scans.getScanRecords() };
    case 'GET_OVERVIEW': {
      const [entries, records, prefs] = await Promise.all([historyStore.getAllEntries(), scans.getScanRecords(), prefsStore.getPrefs()]);
      entries.sort((a:any,b:any)=>b.lastVisit-a.lastVisit);
      return { success:true, entries, records, ignored: prefs.ignoredDomains };
    }
    case 'IGNORE_SITE': {
      const domain = auditCache.normaliseDomain(String(msg.domain||''));
      if (!domain) return {success:false,error:'Missing domain.'};
      const prefs = await prefsStore.getPrefs();
      const list = new Set(prefs.ignoredDomains);
      msg.ignore === false ? list.delete(domain) : list.add(domain);
      const next = await prefsStore.setPrefs({ ignoredDomains: [...list] });
      if (msg.ignore !== false) { await scans.setScan(domain,{state:'skipped'}); await historyStore.recordScanState(domain,'skipped'); }
      chrome.runtime.sendMessage({ type:'PREFS_CHANGED', prefs: next }).catch(()=>{});
      sync.scheduleSync();
      return { success:true, prefs: next };
    }
    case 'REMOVE_SITE_HISTORY': {
      await historyStore.removeEntry(String(msg.domain||''));
      await auditCache.removeAudit(String(msg.domain||''));
      chrome.runtime.sendMessage({ type:'HISTORY_CHANGED' }).catch(()=>{});
      return { success:true };
    }

    // ── Sync ──────────────────────────────────────────────────────────────
    case 'SYNC_NOW': return { success:true, state: await sync.syncNow('manual') };
    case 'GET_SYNC_STATE': return { success:true, state: await sync.getSyncState() };
    case 'DELETE_CLOUD_DATA': {
      try { await sync.deleteCloudData(); return { success:true }; }
      catch(e:any) { return { success:false, error:e?.message||'Could not delete synced data.' }; }
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

// ─── Auto-scan gate ────────────────────────────────────────────────────────────
const _forceNext = new Set<string>();

/** Guest mode is fully supported for local audits; returns null to proceed. */
async function requireSignIn(_domain: string): Promise<ServiceResponse | null> {
  return null;
}

function reportFromCache(e: auditCache.LocalAuditEntry): AuditReport {
  return { dpdp_trust_score:e.trust_score, subtlety_score:e.subtlety_score, violations:e.violations,
    global_legal_reasoning:e.global_legal_reasoning };
}

/**
 * Called whenever a page reports its policy URL (i.e. a site was opened).
 * Decides whether to scan, serve from the local cache, or skip entirely.
 */
async function autoScan(domain: string, policyUrl: string, requestId: string, tabId: number|undefined) {
  const norm = auditCache.normaliseDomain(domain);
  const forced = _forceNext.delete(norm);

  if (!isScannableHost(norm)) return { success:true, skipped:'unscannable' };

  const gate = await requireSignIn(norm);
  if (gate) return gate;

  const prefs = await prefsStore.getPrefs();
  if (!forced) {
    if (prefsStore.isIgnored(prefs, norm)) {
      await scans.setScan(norm, { state:'skipped' });
      updateActionBadge(norm).catch(()=>{});
      return { success:true, skipped:'ignored' };
    }
    if (!prefs.autoScan) {
      await scans.setScan(norm, { state:'paused' });
      return { success:true, skipped:'auto_scan_off' };
    }
    // Fresh enough? Serve locally: no network, no battery, and instant on mobile-class devices.
    const local = await auditCache.getAudit(norm);
    if (local) {
      const ageDays = (Date.now() - local.audited_at) / 86_400_000;
      if (ageDays < prefs.rescanAfterDays) {
        await scans.setScan(norm, { state:'done', via:'cache', policyUrl: local.policy_url });
        updateActionBadge(norm).catch(()=>{});
        if (tabId && prefs.enforceProtections) chrome.tabs.sendMessage(tabId,{type:'ENFORCE_DPDP_RULES',report:reportFromCache(local)}).catch(()=>{});
        return { success:true, cached:true, fromLocal:true };
      }
    }
  }
  return _triggerAudit(domain, policyUrl, requestId, tabId, forced);
}

// ─── Shared audit execution ────────────────────────────────────────────────────
async function _triggerAudit(
  domain: string, policyUrl: string, requestId: string,
  tabId: number|undefined, forceRefresh: boolean,
): Promise<ServiceResponse> {
  const norm = auditCache.normaliseDomain(domain);
  const ck = await domainKey(domain, forceRefresh?'force':'');
  const prefs = await prefsStore.getPrefs();

  // LRU dedup for non-force requests
  if (!forceRefresh) {
    const cached=_lru.get(ck);
    if (cached&&Date.now()-cached.ts<LRU_TTL) {
      const r=cached.resp;
      if (r.type==='AUDIT_POLICY_RESULT'&&r.success) {
        updateActionBadge(domain).catch(() => {});
        if (tabId && prefs.enforceProtections) chrome.tabs.sendMessage(tabId,{type:'ENFORCE_DPDP_RULES',report:r.report}).catch(()=>{});
      }
      return r;
    }
    const inflight=_active.get(ck);
    if (inflight) return inflight;
  }

  await scans.setScan(norm, { state:'scanning', policyUrl });
  updateActionBadge(norm).catch(()=>{});

  // Concurrency gate (a burst of restored tabs must not stampede the server)
  while (_concurrentAudits >= MAX_CONCURRENT_AUDITS) {
    await new Promise(r => setTimeout(r, 200));
  }

  _concurrentAudits++;
  const exec=(async()=>{
    const keepAlive = setInterval(() => {
      chrome.runtime.getPlatformInfo().catch(() => {});
    }, 15_000);
    try {
      let r = await executeAuditByUrl(domain, policyUrl, requestId, forceRefresh);

      // Resilient fallback for client-rendered SPAs or server scraping blockades:
      // If server returns extraction failure (HTTP 422), attempt live tab DOM extraction.
      if (r.type === 'ERROR' && (r.error?.includes('extract') || r.error?.includes('422') || r.error?.includes('No policy text'))) {
        try {
          const queryUrls = [policyUrl];
          try {
            const parsed = new URL(policyUrl);
            queryUrls.push(`${parsed.origin}/*`);
          } catch {}
          const matchedTabs = await chrome.tabs.query({ url: queryUrls });
          const candidateTab = matchedTabs[0] || (tabId ? await chrome.tabs.get(tabId).catch(() => null) : null);
          if (candidateTab?.id) {
            const injection = await chrome.scripting.executeScript({
              target: { tabId: candidateTab.id },
              func: () => {
                const main = document.querySelector('main, article, [role="main"], .policy-content, #content') || document.body;
                return main ? (main as HTMLElement).innerText || '' : '';
              },
            });
            const extractedText = injection?.[0]?.result;
            if (typeof extractedText === 'string' && extractedText.trim().length >= 400) {
              console.log(`[Ssense SW] Server URL fetch failed for ${domain}; falling back to client tab DOM extraction (${extractedText.length} chars)`);
              r = await executeAuditPolicy(domain, extractedText, requestId, forceRefresh);
            }
          }
        } catch (fbErr) {
          console.warn('[Ssense SW] Client DOM fallback attempt failed:', fbErr);
        }
      }

      if (r.type==='AUDIT_POLICY_RESULT'&&r.success) {
        const saved = await auditCache.saveAudit(domain,r.report,{
          policy_url: (r as any).policy_url||policyUrl,
          source:     (r as any).cached?'persistent_cache':'inference',
          age_days:   (r as any).age_days??0,
        });
        await historyStore.recordAudit(domain,r.report,(r as any).policy_url||policyUrl);
        await scans.setScan(norm, { state:'done', policyUrl, via:'server' });
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

        // Notify once when a site *crosses* into low-score territory, not on every re-scan.
        const score = r.report.dpdp_trust_score;
        const prev = saved.previous_trust_score;
        if (prefs.notifyOnLowScore && score < prefs.lowScoreThreshold && (prev == null || prev >= prefs.lowScoreThreshold))
          notify(`ssense-${domain}`,`Low privacy score: ${domain}`,
            `Trust score ${score}/100 — open Ssense for details.`);

        if (tabId && prefs.enforceProtections) chrome.tabs.sendMessage(tabId,{type:'ENFORCE_DPDP_RULES',report:r.report}).catch(()=>{});
        if (prefs.syncEnabled) sync.scheduleSync();
      } else if (r.type==='ERROR') {
        await scans.setScan(norm, { state:'error', error:r.error, errorKind:r.errorKind, policyUrl });
        await historyStore.recordScanState(norm, 'error', r.error);
        updateActionBadge(domain).catch(() => {});
        chrome.runtime.sendMessage({type:'AUDIT_ERROR',domain,
          error:r.error,errorKind:r.errorKind,retryable:r.retryable}).catch(()=>{});
      }
      return r;
    } catch (e: any) {
      const msg = e?.message || 'Scan failed unexpectedly.';
      await scans.setScan(norm, { state:'error', error:msg, policyUrl }).catch(()=>{});
      await historyStore.recordScanState(norm, 'error', msg).catch(()=>{});
      updateActionBadge(domain).catch(() => {});
      return { type:'ERROR', requestId, success:false, error:msg, retryable:true } as ServiceResponse;
    } finally {
      clearInterval(keepAlive);
      _concurrentAudits--;
      _active.delete(ck);
    }
  })();

  if (!forceRefresh) _active.set(ck,exec);
  return exec;
}
