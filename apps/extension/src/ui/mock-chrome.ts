// apps/extension/src/ui/mock-chrome.ts
//
// In-browser mock for Chrome Extension APIs.
// When running in a standard browser tab (e.g. `npm run dev` or `vite preview`),
// this provides an in-memory & localStorage-backed extension environment so all
// 4 surfaces (welcome, popup, sidepanel, options) can be tested locally.
// Inside an actual Chrome extension, native chrome.* APIs exist and this does nothing.

if (typeof window !== 'undefined') {
  const w = window as any;
  if (!w.chrome) w.chrome = {};

  const isExtension = Boolean(w.chrome.runtime?.id && w.chrome.runtime?.getManifest);

  if (!isExtension) {
    console.info('[Ssense Dev] Initializing local in-browser Chrome API mocks for testing.');

    // ── LocalStorage-backed chrome.storage.local ───────────────────────────
    const storageKey = (k: string) => `ssense_dev_${k}`;
    const storage = {
      get: (keys: string | string[] | Record<string, any> | null): Promise<Record<string, any>> => {
        return new Promise((resolve) => {
          const res: Record<string, any> = {};
          if (keys === null) {
            for (let i = 0; i < localStorage.length; i++) {
              const k = localStorage.key(i);
              if (k?.startsWith('ssense_dev_')) {
                const raw = localStorage.getItem(k);
                try { res[k.replace('ssense_dev_', '')] = JSON.parse(raw!); } catch { res[k.replace('ssense_dev_', '')] = raw; }
              }
            }
          } else {
            const list = Array.isArray(keys) ? keys : typeof keys === 'string' ? [keys] : Object.keys(keys || {});
            for (const k of list) {
              const raw = localStorage.getItem(storageKey(k));
              if (raw !== null) {
                try { res[k] = JSON.parse(raw); } catch { res[k] = raw; }
              } else if (typeof keys === 'object' && !Array.isArray(keys) && keys[k] !== undefined) {
                res[k] = keys[k];
              }
            }
          }
          resolve(res);
        });
      },
      set: (items: Record<string, any>): Promise<void> => {
        return new Promise((resolve) => {
          for (const [k, v] of Object.entries(items)) {
            localStorage.setItem(storageKey(k), JSON.stringify(v));
          }
          resolve();
        });
      },
      remove: (keys: string | string[]): Promise<void> => {
        return new Promise((resolve) => {
          const list = Array.isArray(keys) ? keys : [keys];
          for (const k of list) localStorage.removeItem(storageKey(k));
          resolve();
        });
      },
      clear: (): Promise<void> => {
        return new Promise((resolve) => {
          for (let i = localStorage.length - 1; i >= 0; i--) {
            const k = localStorage.key(i);
            if (k?.startsWith('ssense_dev_')) localStorage.removeItem(k);
          }
          resolve();
        });
      },
    };

    const storageListeners = new Set<(changes: any, area: string) => void>();
    w.chrome.storage = {
      local: storage,
      sync: storage,
      onChanged: {
        addListener: (fn: any) => storageListeners.add(fn),
        removeListener: (fn: any) => storageListeners.delete(fn),
      },
    };

    if (!w.IntersectionObserver) {
      w.IntersectionObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
      };
    }

    // ── Mock Datasets ───────────────────────────────────────────────────────
    const mockSites = [
      {
        domain: 'zomato.com',
        firstVisit: Date.now() - 86400000 * 3,
        lastVisit: Date.now() - 3600000,
        visitCount: 14,
        totalTimeMs: 1420000,
        lastScore: 82,
        scanState: 'done',
        lastScanAt: Date.now() - 3600000,
        policyUrl: 'https://zomato.com/privacy',
        lastReport: {
          dpdp_trust_score: 82,
          summary: 'Policy broadly aligns with the DPDP Act 2023. Notice of purpose and data processing principles are clearly stated.',
          reasoning: 'Zomato explicitly identifies Data Fiduciaries and lists personal data categories collected for order fulfillment. Minor gaps identified regarding retention periods.',
          violations: [
            {
              type: 'DATA_RETENTION_SPECIFICATION',
              severity: 'Medium',
              statute_section: 'DPDP Act 2023 § 8(7)',
              description: 'Policy retains transaction logs indefinitely without clear criteria for scheduled erasure after delivery.',
              evidence: 'We retain your personal data for as long as necessary for the purposes set forth in this Policy.',
            },
            {
              type: 'NOTICE_CONSENT_SPECIFICATION',
              severity: 'Low',
              statute_section: 'DPDP Act 2023 § 5(1)',
              description: 'Consent notice does not list regional language availability.',
              evidence: 'By using our services, you consent to our privacy practices in English.',
            },
          ],
        },
        scoreHistory: [
          { timestamp: Date.now() - 86400000 * 2, score: 76, delta: 0 },
          { timestamp: Date.now() - 86400000, score: 80, delta: 4 },
          { timestamp: Date.now() - 3600000, score: 82, delta: 2 },
        ],
      },
      {
        domain: 'swiggy.com',
        firstVisit: Date.now() - 86400000 * 5,
        lastVisit: Date.now() - 7200000,
        visitCount: 22,
        totalTimeMs: 2580000,
        lastScore: 48,
        scanState: 'done',
        lastScanAt: Date.now() - 7200000,
        policyUrl: 'https://swiggy.com/privacy-policy',
        lastReport: {
          dpdp_trust_score: 48,
          summary: 'High compliance risk. Missing verifiable parental consent mechanisms and ambiguous data sharing terms.',
          reasoning: 'Critical gaps found under DPDP Act Section 9 (Processing of Personal Data of Children) and Section 8 (General Obligations of Data Fiduciary).',
          violations: [
            {
              type: 'CHILD_DATA_PROTECTION',
              severity: 'High',
              statute_section: 'DPDP Act 2023 § 9(1)',
              description: 'Platform collects delivery contact data of minors without parental verification mechanisms.',
              evidence: 'Users under the age of 18 may use the platform with the guidance of a parent or guardian.',
            },
            {
              type: 'GRIEVANCE_REDRESSAL_MECHANISM',
              severity: 'Medium',
              statute_section: 'DPDP Act 2023 § 8(10)',
              description: 'No Data Protection Officer or DPDP grievance redressal SLA published.',
              evidence: 'For any questions, reach out via the in-app support chat.',
            },
          ],
        },
        scoreHistory: [
          { timestamp: Date.now() - 86400000 * 3, score: 52, delta: 0 },
          { timestamp: Date.now() - 7200000, score: 48, delta: -4 },
        ],
      },
      {
        domain: 'zerodha.com',
        firstVisit: Date.now() - 86400000 * 7,
        lastVisit: Date.now() - 1800000,
        visitCount: 38,
        totalTimeMs: 4200000,
        lastScore: 94,
        scanState: 'done',
        lastScanAt: Date.now() - 1800000,
        policyUrl: 'https://zerodha.com/privacy',
        lastReport: {
          dpdp_trust_score: 94,
          summary: 'Exemplary compliance. Rigorous purpose limitation, explicit consent notices, and designated DPO contact published.',
          reasoning: 'Meets DPDP Act 2023 standards with full transparency on SEBI regulatory data requirements.',
          violations: [],
        },
        scoreHistory: [
          { timestamp: Date.now() - 86400000 * 4, score: 92, delta: 0 },
          { timestamp: Date.now() - 1800000, score: 94, delta: 2 },
        ],
      },
    ];

    const messageListeners = new Set<(msg: any, sender: any, sendResponse: any) => void>();

    // ── chrome.runtime ──────────────────────────────────────────────────────
    w.chrome.runtime = {
      id: 'ssense-dev-mock-id',
      getURL: (path: string) => path,
      getManifest: () => ({
        name: 'Ssense — DPDP Privacy Shield (Dev Mode)',
        version: '1.0.0',
        manifest_version: 3,
      }),
      onMessage: {
        addListener: (fn: any) => messageListeners.add(fn),
        removeListener: (fn: any) => messageListeners.delete(fn),
      },
      sendMessage: async (msg: any): Promise<any> => {
        const type = msg?.type;
        switch (type) {
          case 'GET_AUTH_STATE':
            return {
              signedIn: true,
              provider: 'google',
              name: 'Anubhav Das',
              email: 'anubhavdas11c05@gmail.com',
              avatarUrl: 'https://lh3.googleusercontent.com/a/default-user',
              userId: 'usr_dev_sample_id_102',
            };

          case 'GET_PREFS': {
            const raw = localStorage.getItem(storageKey('ssense_prefs'));
            const prefs = raw ? JSON.parse(raw) : {
              autoScan: true,
              showBadge: true,
              rescanHours: 24,
              blockDarkPatterns: true,
              notifyOnRisk: true,
              theme: 'system',
              ignoredDomains: ['internal.corp', 'localhost'],
            };
            return { prefs };
          }

          case 'SET_PREFS': {
            const current = (await w.chrome.runtime.sendMessage({ type: 'GET_PREFS' })).prefs;
            const updated = { ...current, ...(msg.patch || {}) };
            localStorage.setItem(storageKey('ssense_prefs'), JSON.stringify(updated));
            return { success: true, prefs: updated };
          }

          case 'GET_SYNC_STATE':
            return {
              state: {
                status: 'idle',
                lastSyncAt: Date.now() - 15 * 60 * 1000,
                siteCount: mockSites.length,
                pendingCount: 0,
                error: undefined,
              },
            };

          case 'SYNC_NOW':
            return {
              state: {
                status: 'idle',
                lastSyncAt: Date.now(),
                siteCount: mockSites.length,
                pendingCount: 0,
              },
            };

          case 'GET_OVERVIEW':
            return {
              success: true,
              entries: mockSites,
              records: {
                'zomato.com': { state: 'done', updatedAt: Date.now() - 3600000 },
                'swiggy.com': { state: 'done', updatedAt: Date.now() - 7200000 },
                'zerodha.com': { state: 'done', updatedAt: Date.now() - 1800000 },
              },
              ignored: ['internal.corp', 'localhost'],
            };

          case 'GET_SITE_HISTORY': {
            const site = mockSites.find((s) => s.domain === msg.domain);
            return { success: true, entry: site || null };
          }

          case 'GET_ENGINE_CONFIG':
            return {
              url: 'http://localhost:8000',
              configured: true,
            };

          case 'HEALTH_CHECK':
            return { success: true, status: 'online' };

          case 'GET_USER_PROFILE':
            return {
              success: true,
              profile: {
                user_id: 'usr_dev_sample_id_102',
                email: 'anubhavdas11c05@gmail.com',
                display_name: 'Anubhav Das',
                devices: [
                  {
                    device_id: 'dev_laptop_win',
                    device_name: 'Workstation (Windows)',
                    platform: 'Win32',
                    last_seen_at: Date.now() - 120000,
                  },
                  {
                    device_id: 'dev_pixel_phone',
                    device_name: 'Pixel 8 (Kiwi)',
                    platform: 'Linux armv8l',
                    last_seen_at: Date.now() - 86400000,
                  },
                ],
              },
            };

          case 'GET_LATEST_AUDIT': {
            const target = mockSites.find((s) => s.domain === msg.domain) || mockSites[0];
            return {
              success: true,
              report: target.lastReport,
              trust_score: target.lastScore,
              cached: true,
              domain: target.domain,
            };
          }

          default:
            return { success: true };
        }
      },
    };

    // ── chrome.tabs ─────────────────────────────────────────────────────────
    const tabListeners = new Set<(activeInfo: { tabId: number; windowId: number }) => void>();
    w.chrome.tabs = {
      query: async (_queryInfo?: any) => {
        return [
          {
            id: 101,
            active: true,
            url: 'https://zomato.com/privacy',
            title: 'Zomato Privacy Policy',
          },
        ];
      },
      onActivated: {
        addListener: (fn: any) => tabListeners.add(fn),
        removeListener: (fn: any) => tabListeners.delete(fn),
      },
      onUpdated: {
        addListener: () => {},
        removeListener: () => {},
      },
      create: (props: any) => {
        if (props.url) window.open(props.url, '_blank');
      },
      sendMessage: async () => ({ success: true }),
    };

    // ── chrome.identity ─────────────────────────────────────────────────────
    w.chrome.identity = {
      getAuthToken: (_opts: any, cb: (token: string) => void) => {
        setTimeout(() => cb('mock_google_oauth2_token_dev'), 300);
      },
      removeCachedAuthToken: (_opts: any, cb: () => void) => {
        setTimeout(cb, 100);
      },
    };

    // ── chrome.action ───────────────────────────────────────────────────────
    w.chrome.action = {
      setBadgeText: () => Promise.resolve(),
      setBadgeBackgroundColor: () => Promise.resolve(),
      openPopup: () => Promise.resolve(),
    };
  }
}

export {};
