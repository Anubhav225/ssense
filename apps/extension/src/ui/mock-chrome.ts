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

    // ── LocalStorage-backed chrome.storage.local (with memory fallback) ──
    const memStore: Record<string, string> = {};
    const safeStore = {
      getItem: (k: string): string | null => {
        try {
          if (typeof localStorage !== 'undefined' && localStorage && typeof localStorage.getItem === 'function') {
            return localStorage.getItem(k);
          }
        } catch {}
        return memStore[k] ?? null;
      },
      setItem: (k: string, v: string): void => {
        try {
          if (typeof localStorage !== 'undefined' && localStorage && typeof localStorage.setItem === 'function') {
            localStorage.setItem(k, v);
            return;
          }
        } catch {}
        memStore[k] = v;
      },
      removeItem: (k: string): void => {
        try {
          if (typeof localStorage !== 'undefined' && localStorage && typeof localStorage.removeItem === 'function') {
            localStorage.removeItem(k);
            return;
          }
        } catch {}
        delete memStore[k];
      },
      key: (i: number): string | null => {
        try {
          if (typeof localStorage !== 'undefined' && localStorage && typeof localStorage.key === 'function') {
            return localStorage.key(i);
          }
        } catch {}
        return Object.keys(memStore)[i] ?? null;
      },
      get length(): number {
        try {
          if (typeof localStorage !== 'undefined' && localStorage) {
            return localStorage.length;
          }
        } catch {}
        return Object.keys(memStore).length;
      }
    };

    const storageKey = (k: string) => `ssense_dev_${k}`;
    const storage = {
      get: (keys: string | string[] | Record<string, any> | null): Promise<Record<string, any>> => {
        return new Promise((resolve) => {
          const res: Record<string, any> = {};
          if (keys === null) {
            for (let i = 0; i < safeStore.length; i++) {
              const k = safeStore.key(i);
              if (k?.startsWith('ssense_dev_')) {
                const raw = safeStore.getItem(k);
                try { res[k.replace('ssense_dev_', '')] = JSON.parse(raw!); } catch { res[k.replace('ssense_dev_', '')] = raw; }
              }
            }
          } else {
            const list = Array.isArray(keys) ? keys : typeof keys === 'string' ? [keys] : Object.keys(keys || {});
            for (const k of list) {
              const raw = safeStore.getItem(storageKey(k));
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
            safeStore.setItem(storageKey(k), JSON.stringify(v));
          }
          resolve();
        });
      },
      remove: (keys: string | string[]): Promise<void> => {
        return new Promise((resolve) => {
          const list = Array.isArray(keys) ? keys : [keys];
          for (const k of list) safeStore.removeItem(storageKey(k));
          resolve();
        });
      },
      clear: (): Promise<void> => {
        return new Promise((resolve) => {
          for (let i = safeStore.length - 1; i >= 0; i--) {
            const k = safeStore.key(i);
            if (k?.startsWith('ssense_dev_')) safeStore.removeItem(k);
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
        domain: 'paytm.com',
        firstVisit: Date.now() - 86400000 * 12,
        lastVisit: Date.now() - 900000,
        visitCount: 64,
        totalTimeMs: 5800000,
        lastScore: 100,
        scanState: 'done',
        lastScanAt: Date.now() - 900000,
        policyUrl: 'https://paytm.com/privacy',
        lastReport: {
          dpdp_trust_score: 100,
          subtlety_score: 0.05,
          summary: 'Exemplary statutory compliance. Explicit consent notices, transparent retention under PMLA 2002 safe harbors, and designated Grievance Officer.',
          reasoning: 'Clean statutory compliance under DPDP Act 2023 § 8(7) provisos and Section 17 exemptions. Mandatory financial transaction records maintained in strict adherence to RBI/PMLA regulations without indefinite retention clauses. Dedicated Resident Indian DPO published.',
          global_legal_reasoning: 'Full compliance across all 18 DPDP statutory verification axes. Section 8(7) erasure obligations properly integrated with PMLA safe harbor exceptions.',
          violations: [],
        },
        scoreHistory: [
          { timestamp: Date.now() - 86400000 * 8, score: 98, delta: 0 },
          { timestamp: Date.now() - 86400000 * 3, score: 100, delta: 2 },
          { timestamp: Date.now() - 900000, score: 100, delta: 0 },
        ],
      },
      {
        domain: 'goodhealth.org',
        firstVisit: Date.now() - 86400000 * 10,
        lastVisit: Date.now() - 1400000,
        visitCount: 19,
        totalTimeMs: 1950000,
        lastScore: 100,
        scanState: 'done',
        lastScanAt: Date.now() - 1400000,
        policyUrl: 'https://goodhealth.org/privacy-charter',
        lastReport: {
          dpdp_trust_score: 100,
          subtlety_score: 0.02,
          summary: 'Clean statutory safe harbor. Non-profit healthcare research fiduciary operating under DPDP Section 7(g) and Section 17 exemptions.',
          reasoning: 'Zero commercial profiling, strict purpose limitation, and affirmative anonymization protocol. Full compliance with medical research exemptions under Section 7 and 17.',
          global_legal_reasoning: 'Exemplary healthcare privacy architecture with zero third-party telemetry, unbundled consent, and robust grievance redressal.',
          violations: [],
        },
        scoreHistory: [
          { timestamp: Date.now() - 86400000 * 6, score: 100, delta: 0 },
          { timestamp: Date.now() - 1400000, score: 100, delta: 0 },
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
          subtlety_score: 0.08,
          summary: 'Exemplary compliance. Rigorous purpose limitation, explicit consent notices, and designated DPO contact published.',
          reasoning: 'Meets DPDP Act 2023 standards with full transparency on SEBI regulatory data requirements.',
          global_legal_reasoning: 'Exemplary compliance. Purpose limitation and consent notices explicitly published with SEBI regulatory alignment.',
          violations: [],
        },
        scoreHistory: [
          { timestamp: Date.now() - 86400000 * 4, score: 92, delta: 0 },
          { timestamp: Date.now() - 1800000, score: 94, delta: 2 },
        ],
      },
      {
        domain: 'redbus.in',
        firstVisit: Date.now() - 86400000 * 4,
        lastVisit: Date.now() - 2400000,
        visitCount: 16,
        totalTimeMs: 1680000,
        lastScore: 85,
        scanState: 'done',
        lastScanAt: Date.now() - 2400000,
        policyUrl: 'https://redbus.in/info/privacypolicy',
        lastReport: {
          dpdp_trust_score: 85,
          subtlety_score: 0.35,
          summary: 'Broadly compliant transport booking platform. Strong notice specifications with minor friction in consent revocation.',
          reasoning: 'Meets Section 5 notice and Section 8 security requirements. Minor consent withdrawal friction under Section 6(4).',
          global_legal_reasoning: 'Compliant transport booking platform with transparent itemized notice. Minor asymmetry in consent revocation procedure.',
          violations: [
            {
              violation_type: 'CONSENT_WITHDRAWAL_ASYMMETRY',
              type: 'CONSENT_WITHDRAWAL_ASYMMETRY',
              severity: 'Medium',
              network_action: 'WARN_USER_ONLY',
              statute_reference: 'DPDP Act 2023 § 6(4)',
              statute_section: 'DPDP Act 2023 § 6(4)',
              description: 'Consent withdrawal requires submitting an email request rather than an automated single-click toggle.',
              evidence: 'Users desiring to withdraw processing consent must send a registered email request to the customer support team.',
              evidence_quote: 'Users desiring to withdraw processing consent must send a registered email request to the customer support team.',
              offending_entities: ['redbus.in'],
            },
          ],
        },
        scoreHistory: [
          { timestamp: Date.now() - 86400000 * 3, score: 81, delta: 0 },
          { timestamp: Date.now() - 2400000, score: 85, delta: 4 },
        ],
      },
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
          subtlety_score: 0.42,
          summary: 'Policy broadly aligns with the DPDP Act 2023. Notice of purpose and data processing principles are clearly stated.',
          reasoning: 'Zomato explicitly identifies Data Fiduciaries and lists personal data categories collected for order fulfillment. Minor gaps identified regarding retention periods and regional language notice.',
          global_legal_reasoning: 'Broadly compliant food delivery fiduciary. Retention period lacks deterministic sunset clauses under Section 8(7).',
          violations: [
            {
              violation_type: 'DATA_RETENTION_SPECIFICATION',
              type: 'DATA_RETENTION_SPECIFICATION',
              severity: 'High',
              network_action: 'WARN_USER_ONLY',
              statute_reference: 'DPDP Act 2023 § 8(7)',
              statute_section: 'DPDP Act 2023 § 8(7)',
              description: 'Policy retains transaction logs indefinitely without clear criteria for scheduled erasure after delivery.',
              evidence: 'We retain your personal data for as long as necessary for the purposes set forth in this Policy.',
              evidence_quote: 'We retain your personal data for as long as necessary for the purposes set forth in this Policy.',
              offending_entities: ['zomato.com'],
            },
            {
              violation_type: 'NOTICE_INADEQUATE',
              type: 'NOTICE_INADEQUATE',
              severity: 'Low',
              network_action: 'WARN_USER_ONLY',
              statute_reference: 'DPDP Act 2023 § 5(3)',
              statute_section: 'DPDP Act 2023 § 5(3)',
              description: 'Consent notice does not list Eighth Schedule Indian regional language availability.',
              evidence: 'By using our services, you consent to our privacy practices in English.',
              evidence_quote: 'By using our services, you consent to our privacy practices in English.',
              offending_entities: ['zomato.com'],
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
        domain: 'makemytrip.com',
        firstVisit: Date.now() - 86400000 * 6,
        lastVisit: Date.now() - 5400000,
        visitCount: 21,
        totalTimeMs: 2100000,
        lastScore: 75,
        scanState: 'done',
        lastScanAt: Date.now() - 5400000,
        policyUrl: 'https://makemytrip.com/legal/privacy_policy.html',
        lastReport: {
          dpdp_trust_score: 75,
          subtlety_score: 0.58,
          summary: 'Online travel agency with multi-fiduciary partnerships. Ambiguous cross-border transfer and commercial marketing clauses.',
          reasoning: 'Gaps identified under Section 16 regarding non-notified territory transfer disclosures and Section 6 unbundled consent.',
          global_legal_reasoning: 'Moderate compliance risk. Third-party partner data sharing terms do not guarantee equivalent safeguards under DPDP Rules.',
          violations: [
            {
              violation_type: 'CROSS_BORDER_TRANSFER_VIOLATION',
              type: 'CROSS_BORDER_TRANSFER_VIOLATION',
              severity: 'High',
              network_action: 'WARN_USER_ONLY',
              statute_reference: 'DPDP Act 2023 § 16',
              statute_section: 'DPDP Act 2023 § 16',
              description: 'Cross-border transfer terms lack specific destination disclosures and security parity guarantees.',
              evidence: 'Your information may be transferred to and maintained on computers located outside India without geographical restriction.',
              evidence_quote: 'Your information may be transferred to and maintained on computers located outside India without geographical restriction.',
              offending_entities: ['makemytrip.com'],
            },
            {
              violation_type: 'PURPOSE_LIMITATION_VIOLATION',
              type: 'PURPOSE_LIMITATION_VIOLATION',
              severity: 'Medium',
              network_action: 'WARN_USER_ONLY',
              statute_reference: 'DPDP Act 2023 § 6(1)',
              statute_section: 'DPDP Act 2023 § 6(1)',
              description: 'Broad promotional marketing purposes bundled with travel itinerary reservation.',
              evidence: 'We share your personal profile with affiliated travel partners for marketing and promotional offers.',
              evidence_quote: 'We share your personal profile with affiliated travel partners for marketing and promotional offers.',
              offending_entities: ['makemytrip.com'],
            },
          ],
        },
        scoreHistory: [
          { timestamp: Date.now() - 86400000 * 5, score: 71, delta: 0 },
          { timestamp: Date.now() - 5400000, score: 75, delta: 4 },
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
          subtlety_score: 0.65,
          summary: 'High compliance risk. Missing verifiable parental consent mechanisms and ambiguous data sharing terms.',
          reasoning: 'Critical gaps found under DPDP Act Section 9 (Processing of Personal Data of Children) and Section 13 (Grievance Redressal Mechanism).',
          global_legal_reasoning: 'High risk compliance profile. Non-compliant child data handling and missing formal grievance officer details.',
          violations: [
            {
              violation_type: 'CHILD_CONSENT_VIOLATION',
              type: 'CHILD_CONSENT_VIOLATION',
              severity: 'High',
              network_action: 'BLOCK_THIRD_PARTY',
              statute_reference: 'DPDP Act 2023 § 9(1)',
              statute_section: 'DPDP Act 2023 § 9(1)',
              description: 'Platform collects delivery contact data of minors without parental verification mechanisms.',
              evidence: 'Users under the age of 18 may use the platform with the guidance of a parent or guardian.',
              evidence_quote: 'Users under the age of 18 may use the platform with the guidance of a parent or guardian.',
              offending_entities: ['swiggy.com'],
            },
            {
              violation_type: 'GRIEVANCE_REDRESSAL_INADEQUATE',
              type: 'GRIEVANCE_REDRESSAL_INADEQUATE',
              severity: 'Low',
              network_action: 'WARN_USER_ONLY',
              statute_reference: 'DPDP Act 2023 § 13',
              statute_section: 'DPDP Act 2023 § 13',
              description: 'No formal Data Protection Officer or DPDP grievance redressal SLA published.',
              evidence: 'For any questions, reach out via the in-app support chat.',
              evidence_quote: 'For any questions, reach out via the in-app support chat.',
              offending_entities: ['swiggy.com'],
            },
          ],
        },
        scoreHistory: [
          { timestamp: Date.now() - 86400000 * 3, score: 52, delta: 0 },
          { timestamp: Date.now() - 7200000, score: 48, delta: -4 },
        ],
      },
      {
        domain: 'badtracker.in',
        firstVisit: Date.now() - 86400000 * 2,
        lastVisit: Date.now() - 1200000,
        visitCount: 5,
        totalTimeMs: 450000,
        lastScore: 25,
        scanState: 'done',
        lastScanAt: Date.now() - 1200000,
        policyUrl: 'https://badtracker.in/privacy',
        lastReport: {
          dpdp_trust_score: 25,
          subtlety_score: 0.92,
          summary: 'Critical non-compliance. Systemic dark patterns, unauthorized child tracking, perpetual retention, and unbundled consent.',
          reasoning: 'Blatant violations across Section 6, Section 8(7), Section 9(2)-(3), and Section 13. Automatic blocking of tracking scripts engaged.',
          global_legal_reasoning: 'Severe non-compliance. Aggressive behavioral tracking, perpetual retention, and absence of statutory grievance channels.',
          violations: [
            {
              violation_type: 'CHILD_CONSENT_VIOLATION',
              type: 'CHILD_CONSENT_VIOLATION',
              severity: 'High',
              network_action: 'BLOCK_THIRD_PARTY',
              statute_reference: 'DPDP Act 2023 § 9(3)',
              statute_section: 'DPDP Act 2023 § 9(3)',
              description: 'Targeted tracking and behavioral monitoring of minor profiles detected.',
              evidence: 'We track user activity across devices to serve personalized behavioral advertisements to all visitors.',
              evidence_quote: 'We track user activity across devices to serve personalized behavioral advertisements to all visitors.',
              offending_entities: ['badtracker.in', 'adserver.badtracker.in'],
            },
            {
              violation_type: 'CONSENT_NOT_FREE_OR_SPECIFIC',
              type: 'CONSENT_NOT_FREE_OR_SPECIFIC',
              severity: 'High',
              network_action: 'BLOCK_THIRD_PARTY',
              statute_reference: 'DPDP Act 2023 § 6(1)',
              statute_section: 'DPDP Act 2023 § 6(1)',
              description: 'Bundled consent forced as mandatory prerequisite for access to basic service features.',
              evidence: 'Access to this service is conditioned upon unreserved agreement to all terms and affiliate tracking.',
              evidence_quote: 'Access to this service is conditioned upon unreserved agreement to all terms and affiliate tracking.',
              offending_entities: ['badtracker.in'],
            },
            {
              violation_type: 'DATA_RETENTION_SPECIFICATION',
              type: 'DATA_RETENTION_SPECIFICATION',
              severity: 'High',
              network_action: 'WARN_USER_ONLY',
              statute_reference: 'DPDP Act 2023 § 8(7)',
              statute_section: 'DPDP Act 2023 § 8(7)',
              description: 'Perpetual retention of personal identifiers without erasure schedule or purpose limitation.',
              evidence: 'We retain all collected personal data indefinitely for archive and analytical purposes.',
              evidence_quote: 'We retain all collected personal data indefinitely for archive and analytical purposes.',
              offending_entities: ['badtracker.in'],
            },
          ],
        },
        scoreHistory: [
          { timestamp: Date.now() - 86400000 * 2, score: 25, delta: 0 },
          { timestamp: Date.now() - 1200000, score: 25, delta: 0 },
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
            const raw = safeStore.getItem(storageKey('ssense_prefs'));
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
            safeStore.setItem(storageKey('ssense_prefs'), JSON.stringify(updated));
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
              records: Object.fromEntries(mockSites.map((s) => [s.domain, { state: 'done', updatedAt: s.lastScanAt }])),
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
