// Ssense Native Messaging bridge.
// Download progress is an event, not the terminal response to the request.

import type { DaemonRequest, DaemonResponse } from '../types/native-protocol';

const NATIVE_HOST_NAME = 'com.ssense.daemon';
let port: chrome.runtime.Port | null = null;

type Pending = {
  resolve: (value: DaemonResponse) => void;
  reject: (reason: Error) => void;
  timeout: ReturnType<typeof setTimeout>;
};

const pendingRequests = new Map<string, Pending>();
const eventListeners = new Set<(message: DaemonResponse) => void>();

function getPort(): chrome.runtime.Port {
  if (!port) {
    port = chrome.runtime.connectNative(NATIVE_HOST_NAME);

    port.onMessage.addListener((message: DaemonResponse) => {
      // Progress/status events must never resolve the download promise.
      if (message.type === 'DOWNLOAD_PROGRESS') {
        for (const listener of eventListeners) {
          try { listener(message); } catch (e) { console.error('[Ssense] Native event listener:', e); }
        }
        return;
      }

      if (message.type === 'CHAT_STREAM_CHUNK') {
        for (const listener of eventListeners) {
          try { listener(message); } catch (e) { console.error('[Ssense] Native event listener:', e); }
        }
        // Intermediate token chunks stream to listeners without settling the final promise
        if (!message.is_final) {
          return;
        }
      }

      if (message.type === 'STATUS') {
        for (const listener of eventListeners) {
          try { listener(message); } catch (e) { console.error('[Ssense] Native event listener:', e); }
        }
        // STATUS is the terminal response for long-running operations such
        // as DOWNLOAD_MODELS, so it must also settle the matching promise.
      }

      const requestId = message.requestId;
      if (!requestId) return;

      const pending = pendingRequests.get(requestId);
      if (!pending) return;

      clearTimeout(pending.timeout);
      pendingRequests.delete(requestId);
      pending.resolve(message);
    });

    port.onDisconnect.addListener(() => {
      const error = chrome.runtime.lastError;
      const message = error?.message || 'Native host disconnected';
      console.error('[Ssense] Native host disconnected:', message);
      port = null;

      for (const [, pending] of pendingRequests) {
        clearTimeout(pending.timeout);
        pending.reject(new Error(message));
      }
      pendingRequests.clear();
      stopKeepaliveIfIdle();
    });
  }
  return port;
}

export function subscribeNativeEvents(listener: (message: DaemonResponse) => void): () => void {
  eventListeners.add(listener);
  return () => eventListeners.delete(listener);
}

// ── Service worker keepalive ──
// Chrome can terminate an MV3 service worker after ~30s of apparent idleness,
// even mid-native-messaging-request — CHAT and AUDIT_POLICY routinely take
// longer than that (cold-start model loading alone can take well over a
// minute). In addition to 5s setInterval ticks, we register a chrome.alarms
// heartbeat to prevent background worker eviction during long offline downloads.
let keepaliveInterval: ReturnType<typeof setInterval> | null = null;
const KEEPALIVE_ALARM = 'ssense_native_keepalive';

if (typeof chrome !== 'undefined' && chrome.alarms) {
  chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === KEEPALIVE_ALARM) {
      chrome.runtime.getPlatformInfo(() => { /* keepalive alarm tick */ });
    }
  });
}

function startKeepaliveIfNeeded() {
  if (keepaliveInterval) return;
  keepaliveInterval = setInterval(() => {
    chrome.runtime.getPlatformInfo(() => { /* no-op, just resets the idle clock */ });
  }, 5000);

  if (typeof chrome !== 'undefined' && chrome.alarms) {
    chrome.alarms.create(KEEPALIVE_ALARM, { periodInMinutes: 0.25 });
  }
}

function stopKeepaliveIfIdle() {
  if (pendingRequests.size === 0) {
    if (keepaliveInterval) {
      clearInterval(keepaliveInterval);
      keepaliveInterval = null;
    }
    if (typeof chrome !== 'undefined' && chrome.alarms) {
      chrome.alarms.clear(KEEPALIVE_ALARM);
    }
  }
}

export function sendToNativeDaemon(
  request: DaemonRequest,
  timeoutMs = request.type === 'DOWNLOAD_MODELS' ? 30 * 60 * 1000 : 180 * 1000
): Promise<DaemonResponse> {
  return new Promise((resolve, reject) => {
    startKeepaliveIfNeeded();

    const settle = (fn: (v: any) => void, value: any) => {
      fn(value);
      stopKeepaliveIfIdle();
    };

    const timeoutId = setTimeout(() => {
      if (pendingRequests.has(request.requestId)) {
        pendingRequests.delete(request.requestId);
        settle(reject, new Error('Native daemon request timed out.'));
      }
    }, timeoutMs);

    try {
      const p = getPort();
      pendingRequests.set(request.requestId, {
        resolve: (v) => settle(resolve, v),
        reject: (e) => settle(reject, e),
        timeout: timeoutId,
      });
      p.postMessage(request);
    } catch (err: any) {
      clearTimeout(timeoutId);
      pendingRequests.delete(request.requestId);
      try { port?.disconnect(); } catch { /* ignore */ }
      port = null;
      settle(reject, new Error(`Native IPC failed: ${err?.message || String(err)}`));
    }
  });
}

// Compatibility bridge used by api-client.ts.
export const nativeBridge = {
  sendRequest<T extends DaemonResponse>(request: DaemonRequest): Promise<T> {
    return sendToNativeDaemon(request) as Promise<T>;
  },

  async sendChatStream(
    request: DaemonRequest,
    onChunk: (token: string, isFinal: boolean) => void
  ): Promise<void> {
    const unsubscribe = subscribeNativeEvents((message: DaemonResponse) => {
      if (message.type === 'CHAT_STREAM_CHUNK' && message.requestId === request.requestId) {
        onChunk(message.token, message.is_final);
      }
    });

    try {
      const response = await sendToNativeDaemon(request);
      if (response.type === 'CHAT_STREAM_CHUNK') {
        if (response.token) {
          onChunk(response.token, response.is_final);
        }
      } else if (response.type === 'ERROR') {
        throw new Error(response.error || 'Local AI model failed to answer.');
      } else {
        throw new Error('Local AI returned an unexpected response.');
      }
    } finally {
      unsubscribe();
    }
  },

  subscribe: subscribeNativeEvents,
};
