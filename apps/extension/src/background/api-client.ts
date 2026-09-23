// apps/extension/src/background/api-client.ts
//
// Cloud-only client — no native daemon, no policy text in transit.
// Primary audit path: extension sends {domain, policyUrl}; server fetches
// and extracts the policy text itself.

import type { AuditReport, AuditServerResponse, ChatResponseMode, ServiceResponse, RateLimitInfo } from '../types/server-protocol';

// ─── Default (shared) install credentials ──────────────────────────────────
// Baked in at build time from apps/extension/.env.production (see
// .env.production.example) — every install of this extension talks to the
// SAME centrally-hosted server by default, with the SAME shared credentials,
// so a regular user never has to see or paste in a key (see docs/SECURITY.md
// "Shared install credentials" for why a value baked into a publicly
// distributed extension can't be a real secret, and why that's an accepted,
// standard trade-off here — the server keys traffic on (api_key + client IP)
// specifically so this sharing doesn't collapse everyone into one rate-limit
// bucket).
//
// import.meta.env.VITE_* is statically replaced by Vite at build time — it
// is NOT read at runtime, so these fall back to the dev defaults below
// whenever a var isn't set (e.g. a `vite dev`/`vite build` run with no
// .env.production), which is what you want for local development against
// `scripts/run.sh`'s auto-generated server .env.
const BAKED_SERVER_URL:   string = import.meta.env.VITE_SSENSE_SERVER_URL  || 'http://localhost:8000';
const BAKED_API_KEY:      string = import.meta.env.VITE_SSENSE_API_KEY     || '';
const BAKED_HMAC_SECRET:  string = import.meta.env.VITE_SSENSE_HMAC_SECRET || '';

export interface ServerConfig { url: string; apiKey: string; hmacSecret: string; configured: boolean; isOverride: boolean; }

/**
 * Resolves the active server config. `chrome.storage.local` values are an
 * ADVANCED, opt-in override for people who want to point this extension at
 * their own self-hosted server (see Options.tsx's "Use a different server"
 * section) — an ordinary user never sets these, and the extension works
 * fully configured out of the box against the baked-in shared server.
 */
export async function getServerConfig(): Promise<ServerConfig> {
  const d = await chrome.storage.local.get([
    'ssense_override_enabled',
    'ssense_server_url',
    'ssense_api_key',
    'ssense_hmac_secret',
    'ssense_device_id',
    'ssense_user_name',
    'ssense_user_email',
  ]);

  // Active server URL: explicit override > storage custom > environment variable (BAKED_SERVER_URL)
  const effectiveUrl = (d.ssense_override_enabled && d.ssense_server_url)
    ? d.ssense_server_url.trim().replace(/\/$/, '')
    : (d.ssense_server_url?.trim().replace(/\/$/, '') || BAKED_SERVER_URL.trim().replace(/\/$/, ''));

  // Active credentials: dynamic issued credentials in storage > baked environment credentials
  const apiKey = (d.ssense_api_key && d.ssense_api_key.trim()) || BAKED_API_KEY;
  const hmacSecret = (d.ssense_hmac_secret && d.ssense_hmac_secret.trim()) || BAKED_HMAC_SECRET;

  return {
    url: effectiveUrl,
    apiKey,
    hmacSecret,
    configured: Boolean(apiKey && hmacSecret),
    isOverride: Boolean(d.ssense_override_enabled),
  };
}
export { getServerConfig as getRouterConfig };  // legacy alias

let _cachedUserId: string | null = null;
export async function getOrCreateUserId(): Promise<string> {
  if (_cachedUserId) return _cachedUserId;
  try {
    const d = await chrome.storage.local.get('ssense_user_id');
    if (d.ssense_user_id) {
      _cachedUserId = d.ssense_user_id;
      return _cachedUserId!;
    }
  } catch {}
  _cachedUserId = crypto.randomUUID();
  try {
    await chrome.storage.local.set({ ssense_user_id: _cachedUserId });
  } catch {}
  return _cachedUserId!;
}

// ─── HMAC signing ─────────────────────────────────────────────────────────────
async function signedHeaders(cfg: ServerConfig, method: string, endpoint: string) {
  const ts    = Date.now().toString();
  const nonce = crypto.randomUUID();
  const userId = await getOrCreateUserId();
  const key   = await crypto.subtle.importKey('raw', new TextEncoder().encode(cfg.hmacSecret),
    { name:'HMAC', hash:'SHA-256' }, false, ['sign']);
  const sig   = await crypto.subtle.sign('HMAC', key,
    new TextEncoder().encode(`${method.toUpperCase()}:${endpoint}:${ts}:${nonce}`));
  const hex   = Array.from(new Uint8Array(sig)).map(b=>b.toString(16).padStart(2,'0')).join('');
  return {
    'Content-Type':       'application/json',
    'X-Ssense-API-Key':   cfg.apiKey,
    'X-Ssense-Signature': hex,
    'X-Ssense-Timestamp': ts,
    'X-Ssense-Nonce':     nonce,
    'X-Ssense-User-Id':   userId,
  };
}

// ─── Error types ──────────────────────────────────────────────────────────────
export type ErrKind = 'network'|'server'|'auth'|'timeout'|'parse'|'unknown';
export class SsenseError extends Error {
  rateLimit?: RateLimitInfo;
  constructor(msg: string, public kind: ErrKind='unknown', public retryable=false, public status?: number) {
    super(msg); this.name = 'SsenseError';
  }
}
function classify(status: number, body: string): SsenseError {
  const bLower = body.toLowerCase();
  if (status===401||status===403) {
    if (bLower.includes('temporal') || bLower.includes('timestamp') || bLower.includes('clock') || bLower.includes('replay attack')) {
      return new SsenseError(
        'Request rejected: your device clock appears out of sync. Please check your system date & time settings.',
        'auth',
        false,
        status,
      );
    }
    return new SsenseError('Authentication failed. Check Settings.','auth',false,status);
  }
  if (status===429) return new SsenseError('Chat rate limit reached. Audits are not rate-limited.','server',false,status);
  if (status>=500)  return new SsenseError('AI service temporarily unavailable.','server',true,status);
  return new SsenseError(body||`HTTP ${status}`,'unknown',false,status);
}
function wrap(e: unknown, fb: string): SsenseError {
  if (e instanceof SsenseError) return e;
  const m = (e as any)?.message || '';
  if ((e as any)?.name==='AbortError') return new SsenseError('Request timed out.','timeout',true);
  if (m.includes('Failed to fetch')) return new SsenseError('Cannot reach server. Check Settings.','network',true);
  return new SsenseError(m||fb,'unknown',false);
}

// ─── Shared fetch helpers ──────────────────────────────────────────────────────
async function fetchJSON<T>(endpoint: string, method: 'GET'|'POST', body: any, cfg: ServerConfig, retries=2, timeoutMs=120_000): Promise<T> {
  if (!navigator.onLine) throw new SsenseError('No internet connection.','network',true);
  const url = `${cfg.url.replace(/\/$/,'')}${endpoint}`;
  for (let i=0; i<=retries; i++) {
    const ctrl = new AbortController();
    const tid  = setTimeout(()=>ctrl.abort(), timeoutMs);
    try {
      const r = await fetch(url, { method, headers: await signedHeaders(cfg,method,endpoint),
        body: body?JSON.stringify(body):undefined, signal:ctrl.signal, credentials:'omit' });
      clearTimeout(tid);
      if (!r.ok) {
        const txt = await r.text().catch(()=>'');
        // Fail-fast on 429: do NOT waste retry quota or keep the user waiting
        if (r.status === 429) {
          throw classify(r.status, txt);
        }
        if (r.status >= 500 && i < retries) {
          await _delay(2**i * 500);
          continue;
        }
        throw classify(r.status, txt);
      }
      return r.json() as Promise<T>;
    } catch(e: any) {
      clearTimeout(tid);
      if (i<retries&&(e.name==='AbortError'||e.message?.includes('Failed to fetch'))) { await _delay(2**i*500); continue; }
      throw wrap(e,'Request failed.');
    }
  }
  throw new SsenseError('Failed after retries.','server',true);
}

async function fetchSSE(endpoint: string, body: any, cfg: ServerConfig, onChunk?: (t:string,done:boolean)=>void): Promise<{text:string;error?:string;rateLimit?:RateLimitInfo}> {
  if (!navigator.onLine) throw new SsenseError('No internet connection.','network',true);
  const url = `${cfg.url.replace(/\/$/,'')}${endpoint}`;
  const ctrl = new AbortController();
  const tid  = setTimeout(()=>ctrl.abort(), 240_000);
  try {
    const r = await fetch(url, { method:'POST', headers: await signedHeaders(cfg,'POST',endpoint),
      body:JSON.stringify(body), signal:ctrl.signal, credentials:'omit' });
    const rateLimit = parseRateLimitHeaders(r.headers);
    if (!r.ok||!r.body) {
      const t=await r.text().catch(()=>'');
      const err = classify(r.status,t);
      (err as any).rateLimit = rateLimit;
      throw err;
    }
    const reader=r.body.getReader(); const dec=new TextDecoder();
    let buf='',acc='',streamErr:string|undefined;
    while(true) {
      const {done,value}=await reader.read();
      if(done) break;
      buf+=dec.decode(value,{stream:true});
      const events=buf.split('\n\n'); buf=events.pop()||'';
      for(const raw of events) {
        const line=raw.split('\n').map(l=>l.trim()).find(l=>l.startsWith('data:'));
        if(!line) continue;
        const payload=line.slice(5).trim();
        if(payload==='[DONE]'){onChunk?.('',true);continue;}
        let p: any; try{p=JSON.parse(payload);}catch{continue;}
        if(p.event==='error'||p.status==='error'){streamErr=p.message||p.data;continue;}
        if(p.event==='done'){onChunk?.('',true);continue;}
        if(p.event==='citations') continue;
        const delta=typeof p.data==='string'?p.data:p?.choices?.[0]?.delta?.content;
        if(typeof delta==='string'){acc+=delta;onChunk?.(delta,false);}
      }
    }
    clearTimeout(tid); onChunk?.('',true);
    return {text:acc,error:streamErr,rateLimit};
  } catch(e:any) { clearTimeout(tid); throw wrap(e,'Stream failed.'); }
}

// ─── Rate limit info (chat only — audits are never rate-limited) ──────────────
function parseRateLimitHeaders(h: Headers): RateLimitInfo | undefined {
  const limit = h.get('X-RateLimit-Limit');
  const remaining = h.get('X-RateLimit-Remaining');
  const windowSeconds = h.get('X-RateLimit-Window');
  if (limit==null || remaining==null) return undefined;
  return { limit: Number(limit), remaining: Number(remaining), windowSeconds: Number(windowSeconds ?? 60) };
}

const _delay = (ms: number) => new Promise(r => setTimeout(r, ms));

// ─── Public API ───────────────────────────────────────────────────────────────
export async function executeHealthCheck(requestId: string): Promise<ServiceResponse> {
  const cfg = await getServerConfig();
  if (!cfg.configured) return {type:'ERROR',requestId,success:false,error:'Server not configured. Open Settings.',errorKind:'auth',retryable:false};
  try {
    let d: any;
    try {
      d = await fetchJSON<any>('/v1/status', 'GET', null, cfg, 0);
    } catch {
      d = await fetchJSON<any>('/health', 'GET', null, cfg, 1);
    }
    const isOnline = (d.status === 'online' || d.online === true);
    const modelOk  = d.rag_ready !== false && d.model_loaded !== false;
    return {
      type: 'HEALTH_CHECK_RESULT',
      requestId,
      success: isOnline && modelOk,
      modelLoaded: modelOk,
      cacheSize: d.audit_cache?.total_cached_domains ?? d.cached_domains ?? 0,
      totalInferences: 0,
      avgTokensPerSecond: 120,
      hasGpuAcceleration: false,
    };
  } catch(e) {
    const err=wrap(e,'Health check failed.');
    return {type:'ERROR',requestId,success:false,error:err.message,errorKind:err.kind,retryable:err.retryable};
  }
}

/** PRIMARY: server fetches and extracts the policy URL itself. */
export async function executeAuditByUrl(
  domain: string, policyUrl: string, requestId: string, forceRefresh=false,
): Promise<ServiceResponse> {
  const cfg = await getServerConfig();
  if (!cfg.configured) return {type:'ERROR',requestId,success:false,error:'Server not configured. Open Settings.',errorKind:'auth',retryable:false};
  try {
    const d = await fetchJSON<AuditServerResponse>('/v1/audit/by-url','POST',
      {domain, policyUrl, force_refresh:forceRefresh}, cfg, 0, 240_000);
    const report = d?.data ?? (d as any)?.report ?? d;
    if (!report||!Array.isArray(report.violations)) throw new SsenseError('Server returned invalid audit report.','parse',false);
    return {type:'AUDIT_POLICY_RESULT',requestId,success:true,report:report as AuditReport,
      cached:d.source!=='inference'};
  } catch(e) {
    const err=wrap(e,'Audit failed.'); return {type:'ERROR',requestId,success:false,error:err.message,errorKind:err.kind,retryable:err.retryable};
  }
}

/** LEGACY: extension sends pre-extracted text (kept for manual retry flows). */
export async function executeAuditPolicy(
  domain: string, policyText: string, requestId: string, forceRefresh=false,
): Promise<ServiceResponse> {
  const cfg = await getServerConfig();
  if (!cfg.configured) return {type:'ERROR',requestId,success:false,error:'Server not configured.',errorKind:'auth',retryable:false};
  try {
    const d = await fetchJSON<AuditServerResponse>('/v1/audit','POST',
      {domain,policyText,force_refresh:forceRefresh},cfg, 0, 240_000);
    const report = d?.data ?? (d as any)?.report ?? d;
    if (!report||!Array.isArray(report.violations)) throw new SsenseError('Invalid audit report.','parse',false);
    return {type:'AUDIT_POLICY_RESULT',requestId,success:true,report:report as AuditReport,cached:d.source!=='inference'};
  } catch(e) {
    const err=wrap(e,'Audit failed.'); return {type:'ERROR',requestId,success:false,error:err.message,errorKind:err.kind,retryable:err.retryable};
  }
}

export async function executeFetchCachedAudit(domain: string, requestId: string): Promise<ServiceResponse> {
  const cfg = await getServerConfig();
  if (!cfg.configured) return {type:'ERROR',requestId,success:false,error:'Server not configured.',errorKind:'auth',retryable:false};
  try {
    const d = await fetchJSON<AuditServerResponse>(`/v1/audit/${encodeURIComponent(domain)}`,'GET',null,cfg);
    const report = d?.data;
    if (!report||!Array.isArray(report.violations)) throw new SsenseError('No cached audit found.','parse',false);
    return {type:'AUDIT_POLICY_RESULT',requestId,success:true,report,cached:true};
  } catch(e) {
    const err=wrap(e,'Cached audit fetch failed.'); return {type:'ERROR',requestId,success:false,error:err.message,errorKind:err.kind,retryable:err.retryable};
  }
}

export async function executeChat(
  domain: string, userPrompt: string, requestId: string,
  onChunk?: (t:string,done:boolean)=>void, responseMode: ChatResponseMode='concise',
): Promise<ServiceResponse> {
  const cfg = await getServerConfig();
  if (!cfg.configured) {
    onChunk?.('',true);
    return {type:'ERROR',requestId,success:false,error:'Server not configured. Open Settings.',errorKind:'auth',retryable:false};
  }
  try {
    const r = await fetchSSE('/v1/chat/stream',{domain,userPrompt,responseMode},cfg,onChunk);
    if (r.error) { const e = new SsenseError(r.error,'server',true); e.rateLimit = r.rateLimit; throw e; }
    if (!r.text.trim()) throw new SsenseError('AI returned empty response.','server',true);
    return {type:'CHAT_RESULT',requestId,success:true,message:r.text,rateLimit:r.rateLimit};
  } catch(e) {
    const err=wrap(e,'Chat failed.'); onChunk?.('',true);
    return {type:'ERROR',requestId,success:false,error:err.message,errorKind:err.kind,retryable:err.retryable,rateLimit:(e as SsenseError)?.rateLimit};
  }
}

// ─── Handshake & Authentication Discovery ──────────────────────────────────
export interface ServerPingResult {
  online: boolean;
  service?: string;
  version?: string;
  authRequired?: boolean;
  registrationOpen?: boolean;
  requiresInvite?: boolean;
  publicUrl?: string;
  error?: string;
}

export async function fetchServerPing(targetUrl?: string): Promise<ServerPingResult> {
  const cfg = await getServerConfig();
  const baseUrl = targetUrl ? targetUrl.trim().replace(/\/$/, '') : cfg.url;
  try {
    const res = await fetch(`${baseUrl}/v1/auth/ping`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    });
    if (!res.ok) {
      return { online: false, error: `HTTP ${res.status}: ${res.statusText}` };
    }
    const data = await res.json();
    return {
      online: data.status === 'online',
      service: data.service,
      version: data.version,
      authRequired: data.auth_required,
      registrationOpen: data.registration_open,
      requiresInvite: data.requires_invite,
      publicUrl: data.public_url,
    };
  } catch (err: any) {
    return { online: false, error: err?.message || 'Failed to connect to server' };
  }
}

export interface RegisterResult {
  success: boolean;
  userId?: string;
  apiKey?: string;
  deviceId?: string;
  userName?: string;
  userEmail?: string;
  googleId?: string;
  avatarUrl?: string;
  error?: string;
}

export async function registerDevice(
  name?: string,
  email?: string,
  deviceName?: string,
  inviteCode?: string,
  googleId?: string,
  avatarUrl?: string,
): Promise<RegisterResult> {
  const cfg = await getServerConfig();
  const stored = await chrome.storage.local.get(['ssense_device_id']);
  const deviceId = stored.ssense_device_id || `dev_${crypto.randomUUID().slice(0, 12)}`;

  const payload = {
    name: name?.trim() || undefined,
    email: email?.trim() || undefined,
    google_id: googleId?.trim() || undefined,
    avatar_url: avatarUrl?.trim() || undefined,
    device_name: deviceName?.trim() || (typeof navigator !== 'undefined' && navigator.userAgent.includes('Windows') ? 'Windows Laptop' : 'Laptop Client'),
    device_id: deviceId,
    platform: typeof navigator !== 'undefined' ? navigator.userAgent.slice(0, 50) : 'Chrome Extension',
    invite_code: inviteCode?.trim() || undefined,
  };

  try {
    const res = await fetch(`${cfg.url}/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let errMsg = `Registration failed (HTTP ${res.status})`;
      try {
        const errJson = await res.json();
        if (errJson?.detail) errMsg = errJson.detail;
      } catch {}
      return { success: false, error: errMsg };
    }

    const data = await res.json();
    const finalName = data.display_name || name || 'Guest Reviewer';
    const finalEmail = data.email || email;
    const finalGoogleId = data.google_id || googleId;
    const finalAvatar = data.avatar_url || avatarUrl;

    await chrome.storage.local.set({
      ssense_api_key: data.api_key,
      ssense_hmac_secret: data.hmac_secret,
      ssense_user_id: data.user_id,
      ssense_device_id: data.device_id,
      ssense_user_name: finalName,
      ssense_user_email: finalEmail,
      ssense_google_id: finalGoogleId,
      ssense_avatar_url: finalAvatar,
      ssense_onboarded: true,
    });

    return {
      success: true,
      userId: data.user_id,
      apiKey: data.api_key,
      deviceId: data.device_id,
      userName: finalName,
      userEmail: finalEmail,
      googleId: finalGoogleId,
      avatarUrl: finalAvatar,
    };
  } catch (err: any) {
    return { success: false, error: err?.message || 'Network error during registration' };
  }
}

export async function sendHeartbeat(): Promise<boolean> {
  const cfg = await getServerConfig();
  if (!cfg.configured) return false;
  try {
    const headers = await signedHeaders(cfg, 'POST', '/v1/auth/heartbeat');
    const stored = await chrome.storage.local.get(['ssense_device_id']);
    const res = await fetch(`${cfg.url}/v1/auth/heartbeat`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ device_id: stored.ssense_device_id }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function fetchUserProfile(): Promise<any> {
  const cfg = await getServerConfig();
  if (!cfg.configured) return null;
  try {
    const headers = await signedHeaders(cfg, 'GET', '/v1/auth/me');
    const res = await fetch(`${cfg.url}/v1/auth/me`, {
      method: 'GET',
      headers,
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}
