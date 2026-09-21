// apps/extension/src/background/service-worker.ts
//
// Cloud-only, no native daemon, no PROXY_FETCH, no policy text storage.
// Primary audit trigger: FOUND_POLICY_URL from extractor.ts → server fetches
// and extracts → result saved to local audit-cache (chrome.storage.local).

import { executeAuditByUrl, executeFetchCachedAudit, executeChat, executeHealthCheck, getServerConfig } from './api-client';
import * as auditCache from './audit-cache';
import * as historyStore from './history-store';
import * as chatStore from './chat-store';
import type { ServiceResponse } from '../types/server-protocol';

console.log('[Ssense] Service Worker v6 — cloud-only, server-side extraction.');

// ─── Notifications ─────────────────────────────────────────────────────────────
function notify(id: string, title: string, message: string) {
  chrome.notifications.create(id, { type:'basic', iconUrl:'icons/icon128.png', title, message, priority:1 }, () => void chrome.runtime.lastError);
}
chrome.notifications.onClicked.addListener(id => { if (id.startsWith('ssense-')) chrome.action.openPopup?.().catch(()=>{}); });

// ─── Time-on-site tracking ─────────────────────────────────────────────────────
let _domain: string|null=null, _since: number|null=null, _focused=true;
function hostnameOf(url?: string) { try { return url?.startsWith('http') ? new URL(url).hostname : null; } catch { return null; } }
async function flush() { if (_domain&&_since) await historyStore.addTime(_domain, Date.now()-_since); _since=null; }
async function startTracking(d: string|null) { await flush(); _domain=d; _since=(d&&_focused)?Date.now():null; }
async function syncTab() {
  const [tab]=await chrome.tabs.query({active:true,lastFocusedWindow:true}).catch(()=>[]);
  const d=hostnameOf(tab?.url);
  if (d!==_domain) { if (d) await historyStore.recordVisit(d); await startTracking(d); }
}
chrome.tabs.onActivated.addListener(()=>syncTab());
chrome.tabs.onUpdated.addListener((_,i,t)=>{ if (i.status==='complete'&&t.active) syncTab(); });
chrome.windows.onFocusChanged.addListener(async wid=>{
  _focused=wid!==chrome.windows.WINDOW_ID_NONE;
  _focused ? syncTab() : flush();
});
setInterval(()=>{ flush().then(()=>{ _since=(_domain&&_focused)?Date.now():null; }); }, 20_000);
syncTab();

// ─── In-flight deduplication (30-min LRU) ─────────────────────────────────────
const _active  = new Map<string,Promise<ServiceResponse>>();
const _lru     = new Map<string,{ts:number;resp:ServiceResponse}>();
const LRU_TTL  = 30*60*1000;
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
        await auditCache.saveAudit(msg.domain,r.report,{source:'persistent_cache',cached:true} as any);
      }
      return r;
    }

    // ── Health check ──────────────────────────────────────────────────────
    case 'HEALTH_CHECK': return executeHealthCheck(requestId);

    // ── Audit cache reads ─────────────────────────────────────────────────
    case 'GET_LOCAL_AUDIT': {
      const entry=await auditCache.getAudit(String(msg.domain||''));
      return {success:true,entry:entry??null};
    }
    case 'GET_ALL_AUDITS': {
      const entries=await auditCache.getAllAudits();
      return {success:true,entries};
    }
    case 'CLEAR_AUDITS': { await auditCache.clearAllAudits(); return {success:true}; }

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

    // ── Chat ──────────────────────────────────────────────────────────────
    case 'CHAT': {
      const r=await executeChat(msg.domain,msg.userPrompt,requestId,undefined,msg.responseMode);
      if (r.type==='CHAT_RESULT'&&r.success) {
        await chatStore.addMessage(msg.domain,'user',msg.userPrompt);
        await chatStore.addMessage(msg.domain,'ai',r.message);
      }
      return r;
    }
    case 'GET_CHAT_HISTORY': return {success:true,messages:await chatStore.getMessagesForDomain(msg.domain)};
    case 'CLEAR_CHAT_HISTORY': { await chatStore.clearMessagesForDomain(msg.domain); return {success:true}; }

    // ── Engine config ─────────────────────────────────────────────────────
    // BUG FIX: this used to return the full ServerConfig object — including
    // the plaintext apiKey/hmacSecret — to whatever caller asked, but the
    // only caller (chat-widget.ts, a content script) only ever reads
    // `.configured`. Redact the secret fields; nothing needs them outside
    // api-client.ts itself, which reads them straight from getServerConfig()
    // rather than round-tripping through a message.
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
      if (r.type==='AUDIT_POLICY_RESULT'&&r.success&&tabId)
        chrome.tabs.sendMessage(tabId,{type:'ENFORCE_DPDP_RULES',report:r.report}).catch(()=>{});
      return r;
    }
    const inflight=_active.get(ck);
    if (inflight) return inflight;
  }

  const exec=(async()=>{
    try {
      const r=await executeAuditByUrl(domain,policyUrl,requestId,forceRefresh);

      if (r.type==='AUDIT_POLICY_RESULT'&&r.success) {
        // Save minimal entry to local cache (no policy text)
        await auditCache.saveAudit(domain,r.report,{
          policy_url: (r as any).policy_url||policyUrl,
          source:     (r as any).cached?'persistent_cache':'inference',
          age_days:   (r as any).age_days??0,
        });
        await historyStore.recordAudit(domain,r.report);

        if (!forceRefresh) _lru.set(ck,{ts:Date.now(),resp:r});

        chrome.runtime.sendMessage({type:'AUDIT_COMPLETE',domain,
          score:r.report.dpdp_trust_score,report:r.report}).catch(()=>{});

        if (r.report.dpdp_trust_score<40)
          notify(`ssense-${domain}`,`Low privacy score: ${domain}`,
            `Trust score ${r.report.dpdp_trust_score}/100 — open Ssense for details.`);

        if (tabId) chrome.tabs.sendMessage(tabId,{type:'ENFORCE_DPDP_RULES',report:r.report}).catch(()=>{});
      } else if (r.type==='ERROR') {
        chrome.runtime.sendMessage({type:'AUDIT_ERROR',domain,
          error:r.error,errorKind:r.errorKind,retryable:r.retryable}).catch(()=>{});
      }
      return r;
    } finally { _active.delete(ck); }
  })();

  if (!forceRefresh) _active.set(ck,exec);
  return exec;
}
