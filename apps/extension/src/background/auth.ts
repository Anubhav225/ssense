// apps/extension/src/background/auth.ts
//
// Google sign-in for the extension.
//
//   1. Obtain a Google access token from the browser
//        - Chrome:  chrome.identity.getAuthToken   (uses manifest oauth2.client_id)
//        - Others:  chrome.identity.launchWebAuthFlow (needs VITE_GOOGLE_WEB_CLIENT_ID)
//   2. Send it to POST /v1/auth/google. The server verifies it with Google and
//      returns this account's API key + HMAC secret.
//
// The e-mail is never taken from the client, so it can't be spoofed.

import { getServerConfig } from './api-client';
import * as historyStore from './history-store';
import * as auditCache from './audit-cache';

export type AuthProvider = 'google' | 'custom' | null;

export interface AuthState {
  signedIn: boolean;
  provider: AuthProvider;
  name: string;
  email: string;
  avatarUrl: string;
  userId: string;
}

const WEB_CLIENT_ID: string = (import.meta.env.VITE_GOOGLE_WEB_CLIENT_ID as string) || '';

export async function getAuthState(): Promise<AuthState> {
  const d = await chrome.storage.local.get([
    'ssense_auth_provider', 'ssense_api_key', 'ssense_hmac_secret', 'ssense_override_enabled',
    'ssense_user_name', 'ssense_user_email', 'ssense_avatar_url', 'ssense_user_id',
  ]);
  const hasCreds = Boolean(d.ssense_api_key && d.ssense_hmac_secret);
  let provider: AuthProvider = null;
  if (hasCreds && d.ssense_auth_provider === 'google') provider = 'google';
  else if (hasCreds && d.ssense_override_enabled) provider = 'custom'; // self-hosted operators use their own keys
  return {
    signedIn: provider !== null,
    provider,
    name: d.ssense_user_name || '',
    email: d.ssense_user_email || '',
    avatarUrl: d.ssense_avatar_url || '',
    userId: d.ssense_user_id || '',
  };
}

// ─── Getting a token from the browser ─────────────────────────────────────────
async function tokenViaGetAuthToken(interactive: boolean): Promise<string | null> {
  const id: any = chrome.identity;
  if (!id?.getAuthToken) return null;
  try {
    const r = await id.getAuthToken({ interactive });
    const token = typeof r === 'string' ? r : r?.token;
    return token || null;
  } catch (e: any) {
    const msg = String(e?.message || e);
    if (/user did not approve|canceled|cancelled|closed/i.test(msg)) throw new Error('Sign-in was cancelled.');
    // getAuthToken is unsupported (non-Chrome) or misconfigured → try the web flow.
    return null;
  }
}

async function tokenViaWebAuthFlow(): Promise<string | null> {
  if (!WEB_CLIENT_ID || !chrome.identity?.launchWebAuthFlow) return null;
  const redirect = chrome.identity.getRedirectURL();
  const url =
    'https://accounts.google.com/o/oauth2/v2/auth?' +
    new URLSearchParams({
      client_id: WEB_CLIENT_ID,
      response_type: 'token',
      redirect_uri: redirect,
      scope: 'openid email profile',
      prompt: 'select_account',
    }).toString();
  try {
    const result: string | undefined = await new Promise((resolve, reject) =>
      chrome.identity.launchWebAuthFlow({ url, interactive: true }, (r) =>
        chrome.runtime.lastError ? reject(new Error(chrome.runtime.lastError.message)) : resolve(r),
      ),
    );
    if (!result) return null;
    const hash = new URL(result).hash.replace(/^#/, '');
    return new URLSearchParams(hash).get('access_token');
  } catch (e: any) {
    if (/user did not approve|canceled|cancelled|closed/i.test(String(e?.message))) throw new Error('Sign-in was cancelled.');
    throw e;
  }
}

function describeDevice(): string {
  const ua = typeof navigator !== 'undefined' ? navigator.userAgent : '';
  const os = /Android/i.test(ua) ? 'Android'
    : /iPhone|iPad/i.test(ua) ? 'iOS'
    : /Windows/i.test(ua) ? 'Windows'
    : /Mac OS X/i.test(ua) ? 'macOS'
    : /CrOS/i.test(ua) ? 'ChromeOS'
    : /Linux/i.test(ua) ? 'Linux' : 'Device';
  const br = /Edg\//.test(ua) ? 'Edge' : /OPR\//.test(ua) ? 'Opera' : /Brave/i.test(ua) ? 'Brave' : 'Chrome';
  return `${br} on ${os}`;
}

// ─── Public API ───────────────────────────────────────────────────────────────
export async function signInWithGoogle(): Promise<{ success: boolean; error?: string; state?: AuthState; switchedAccount?: boolean }> {
  let token: string | null = null;
  try {
    token = (await tokenViaGetAuthToken(true)) || (await tokenViaWebAuthFlow());
  } catch (e: any) {
    return { success: false, error: e?.message || 'Sign-in was cancelled.' };
  }
  if (!token) {
    return {
      success: false,
      error: 'Google sign-in is not available in this browser build. Use Chrome, or ask the publisher to enable the web sign-in client.',
    };
  }

  const cfg = await getServerConfig();
  const stored = await chrome.storage.local.get(['ssense_device_id', 'ssense_history_owner']);
  const deviceId = stored.ssense_device_id || (await historyStore.getDeviceId());

  let res: Response;
  try {
    res = await fetch(`${cfg.url}/v1/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        token,
        token_type: 'access_token',
        device_id: deviceId,
        device_name: describeDevice(),
        platform: typeof navigator !== 'undefined' ? navigator.userAgent.slice(0, 50) : 'Chrome Extension',
      }),
    });
  } catch {
    return { success: false, error: 'Cannot reach the Ssense server. Check your connection and try again.' };
  }

  if (!res.ok) {
    let msg = `Sign-in failed (HTTP ${res.status}).`;
    try { const j = await res.json(); if (typeof j?.detail === 'string') msg = j.detail; } catch {}
    // A cached token Google no longer accepts must be dropped or every retry fails the same way.
    if (res.status === 401) await dropCachedToken(token);
    return { success: false, error: msg };
  }

  const data = await res.json();

  // Different Google account than last time on this browser → don't let the previous
  // person's history leak into (and sync to) this account.
  let switchedAccount = false;
  if (stored.ssense_history_owner && stored.ssense_history_owner !== data.user_id) {
    await historyStore.clearAllEntries();
    await auditCache.clearAllAudits();
    await chrome.storage.local.remove(['ssense_sync_state', 'ssense_prefs']);
    switchedAccount = true;
  }

  await chrome.storage.local.set({
    ssense_api_key: data.api_key,
    ssense_hmac_secret: data.hmac_secret,
    ssense_user_id: data.user_id,
    ssense_device_id: data.device_id,
    ssense_user_name: data.display_name,
    ssense_user_email: data.email,
    ssense_google_id: data.google_id || '',
    ssense_avatar_url: data.avatar_url || '',
    ssense_auth_provider: 'google',
    ssense_history_owner: data.user_id,
    ssense_onboarded: true,
  });

  return { success: true, state: await getAuthState(), switchedAccount };
}

async function dropCachedToken(token: string) {
  try { await (chrome.identity as any).removeCachedAuthToken?.({ token }); } catch {}
}

export async function signOut(opts: { keepLocalData?: boolean } = {}): Promise<void> {
  try {
    const r: any = await (chrome.identity as any).getAuthToken?.({ interactive: false });
    const token = typeof r === 'string' ? r : r?.token;
    if (token) {
      await dropCachedToken(token);
      // Best-effort revoke so the grant doesn't linger on Google's side.
      fetch(`https://oauth2.googleapis.com/revoke?token=${encodeURIComponent(token)}`, { method: 'POST' }).catch(() => {});
    }
  } catch {}

  await chrome.storage.local.remove([
    'ssense_api_key', 'ssense_hmac_secret', 'ssense_user_id', 'ssense_user_name',
    'ssense_user_email', 'ssense_google_id', 'ssense_avatar_url', 'ssense_auth_provider',
    'ssense_onboarded', 'ssense_sync_state',
  ]);
  // ssense_history_owner is intentionally kept: if someone else signs in next we wipe local data.
  if (!opts.keepLocalData) {
    await historyStore.clearAllEntries();
    await auditCache.clearAllAudits();
  }
}
