// apps/extension/src/content/dark-pattern-blocker.ts
import type { DpdpAuditReport, NetworkAction, Violation } from '../types/server-protocol';
import { isFirstPartyDomain } from '../utils/domain';

declare global {
  interface Window {
    __ssenseObserverAttached?: boolean;
    __ssenseDarkPatternBlockerLoaded?: boolean;
    __ssenseActiveObserver?: MutationObserver;
    __ssenseActiveFingerprint?: string;
  }
}

// Guard the ENTIRE file body against re-injection into an already-loaded page
// realm. Chrome re-runs a matching content script into a tab's *existing* JS
// realm (not a fresh one) whenever the extension reloads — a dev rebuild, or
// Chrome auto-updating the extension — while that tab is already open and
// hasn't navigated since. Without this guard, the second run's top-level
// `const`/`let` (e.g. MAX_DESCENDANTS_FOR_TEXT_SCAN below) collides with the
// binding the first run already created in that realm and throws "Identifier
// '...' has already been declared", aborting the whole script before it can
// attach its listener — which is exactly the error being reported.
if (!window.__ssenseDarkPatternBlockerLoaded) {
window.__ssenseDarkPatternBlockerLoaded = true;

console.log('[Ssense] DOM Enforcer injected and listening.');

let activeStyleElement: HTMLStyleElement | null = null;

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === 'ENFORCE_DPDP_RULES' && message.report) {
    executeNetworkActions(message.report);
  } else if (message.type === 'DISABLE_DPDP_RULES') {
    teardownRules();
  } else if (message.type === 'HIGHLIGHT_IN_DOM' && message.quote) {
    highlightAndScrollToQuote(message.quote);
  }
});

// Bootstrapping: Query background immediately for active shield rules
try {
  if (typeof chrome !== 'undefined' && chrome.runtime?.sendMessage) {
    chrome.runtime.sendMessage(
      { type: 'GET_ACTIVE_SHIELD_RULES', domain: window.location.hostname },
      (res) => {
        if (chrome.runtime?.lastError) return;
        if (res?.success && res.report) {
          executeNetworkActions(res.report);
        }
      }
    );
  }
} catch {}

function teardownRules() {
  if (window.__ssenseActiveObserver) {
    try { window.__ssenseActiveObserver.disconnect(); } catch {}
    window.__ssenseActiveObserver = undefined;
  }
  window.__ssenseActiveFingerprint = undefined;

  if (activeStyleElement) {
    try { activeStyleElement.remove(); } catch {}
    activeStyleElement = null;
  }

  try {
    document.querySelectorAll('.ssense-blocked-element').forEach((el) => {
      el.classList.remove('ssense-blocked-element');
    });
    document.querySelectorAll('.ssense-highlight-violation').forEach((el) => {
      el.classList.remove('ssense-highlight-violation');
      el.removeAttribute('title');
    });
  } catch {}

  document.dispatchEvent(
    new CustomEvent('__ssense_shield_update__', {
      detail: {
        badDomains: [],
        stripTelemetry: false,
        spoofHardware: false,
        injectGPC: false,
      },
    })
  );

  try {
    const script = document.createElement('script');
    script.textContent = `window.__ssenseBlockedDomains = []; window.__ssenseStripTelemetry = false;`;
    (document.head || document.documentElement).appendChild(script);
    script.remove();
  } catch {}

  console.log('[Ssense] DPDP Shield stood down for this page.');
}

function showToastNotice(msg: string) {
  try {
    const id = '__ssense_toast_notice';
    document.getElementById(id)?.remove();
    const toast = document.createElement('div');
    toast.id = id;
    toast.style.cssText = `
      position: fixed; top: 18px; left: 50%; transform: translateX(-50%);
      background: #09090b; color: #f4f4f5; padding: 10px 18px; border-radius: 10px;
      border: 1px solid rgba(6, 182, 212, 0.4); box-shadow: 0 8px 30px rgba(0,0,0,0.6);
      font-size: 12.5px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-weight: 500; z-index: 2147483647; display: flex; align-items: center; gap: 8px;
      transition: opacity 0.3s ease; pointer-events: none;
    `;
    toast.innerHTML = `<span style="color:#06b6d4;font-weight:700;">Ssense:</span> ${msg}`;
    (document.body || document.documentElement).appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 400);
    }, 4500);
  } catch {}
}

function highlightAndScrollToQuote(quote: string) {
  try {
    const cleanQuote = quote.toLowerCase().replace(/\s+/g, ' ').trim();
    if (!cleanQuote) return;

    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node: Node | null = null;
    let found = false;
    while ((node = walker.nextNode())) {
      const text = (node.nodeValue || '').toLowerCase().replace(/\s+/g, ' ');
      if (text.includes(cleanQuote) && node.parentElement) {
        found = true;
        const el = node.parentElement;
        el.classList.add('ssense-highlight-violation');
        el.style.outline = '3px solid #06B6D4';
        el.style.backgroundColor = 'rgba(244, 63, 94, 0.25)';
        el.style.transition = 'all 0.4s ease';
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        setTimeout(() => {
          el.style.outline = '';
          el.style.backgroundColor = '';
        }, 4000);
        break;
      }
    }
    if (!found) {
      showToastNotice('Notice: Quote belongs to the site’s Privacy Policy and was not found in this active page view.');
    }
  } catch (err) {
    console.error('[Ssense] Error locating quote in page:', err);
  }
}

function matchesBlockedDomain(urlStr: string, badDomains: string[]): boolean {
  if (!urlStr || !badDomains.length) return false;
  try {
    const parsed = new URL(urlStr, window.location.href);
    const host = parsed.hostname.toLowerCase();
    return badDomains.some((d) => {
      const target = d.toLowerCase().trim();
      return host === target || host.endsWith('.' + target);
    });
  } catch {
    const lower = urlStr.toLowerCase();
    return badDomains.some((d) => lower.includes(d.toLowerCase()));
  }
}

function executeNetworkActions(report: DpdpAuditReport) {
  const violationFingerprint = (report.violations || [])
    .map(v => `${v.violation_type}:${v.network_action}:${(v.offending_entities || []).slice().sort().join(',')}`)
    .sort()
    .join('|');
  const fingerprint = `${report.dpdp_trust_score}:${violationFingerprint}`;

  // If already enforcing identical rules on this page, avoid redundant sweeps
  if (window.__ssenseActiveFingerprint === fingerprint) return;
  window.__ssenseActiveFingerprint = fingerprint;

  // Disconnect previous observer if a re-audit brought updated violations
  if (window.__ssenseActiveObserver) {
    try { window.__ssenseActiveObserver.disconnect(); } catch {}
    window.__ssenseActiveObserver = undefined;
  }

  console.log(`[Ssense] Activating Real-Time Shield. Trust Score: ${report.dpdp_trust_score}`);

  const badDomains: string[] = [];
  const quotesToHighlight: string[] = [];
  let injectGPC = false;
  let spoofHardware = false;

  // 1. Parse Enforcement Directives, filtering out 1st-party domain from tracker blocking
  const currentHost = window.location.hostname;
  report.violations.forEach((violation: Violation) => {
    switch (violation.network_action as NetworkAction) {
      case 'BLOCK_THIRD_PARTY':
        if (violation.offending_entities) {
          const safeTrackers = violation.offending_entities
            .map((e) => e.toLowerCase().trim())
            .filter((e) => e && !isFirstPartyDomain(e, currentHost));
          badDomains.push(...safeTrackers);
        }
        break;
      case 'WARN_USER_ONLY':
      case 'STRIP_TELEMETRY_HEADER':
        if (violation.evidence_quote) {
          // Normalize whitespace for robust matching against dynamic DOM text
          quotesToHighlight.push(violation.evidence_quote.toLowerCase().replace(/\s+/g, ' ').trim().substring(0, 50));
        }
        break;
      case 'INJECT_GPC_SIGNAL':
        injectGPC = true;
        break;
      case 'SPOOF_HARDWARE_API':
        spoofHardware = true;
        break;
    }
  });

  // Inject CSS rules for instant visual hiding of blocked trackers
  if (badDomains.length > 0 && !activeStyleElement) {
    try {
      const style = document.createElement('style');
      style.textContent = `
        .ssense-blocked-element {
          display: none !important;
          opacity: 0 !important;
          pointer-events: none !important;
          visibility: hidden !important;
        }
      `;
      (document.head || document.documentElement).appendChild(style);
      activeStyleElement = style;
    } catch(e) {}
  }

  // 🚀 CSP-Safe Synchronization with MAIN world (api-spoof.ts)
  document.dispatchEvent(
    new CustomEvent('__ssense_shield_update__', {
      detail: {
        badDomains,
        stripTelemetry: badDomains.length > 0,
        spoofHardware,
        injectGPC,
      },
    })
  );

  // Fallback inline script execution for unconstrained contexts
  if (badDomains.length > 0) {
    try {
      const script = document.createElement('script');
      script.textContent = `window.__ssenseBlockedDomains = ${JSON.stringify(badDomains)}; window.__ssenseStripTelemetry = true;`;
      (document.head || document.documentElement).appendChild(script);
      script.remove();
    } catch(e) {}
  }
  if (injectGPC) injectGlobalPrivacyControl();
  if (spoofHardware) spoofHardwareAPIs();

  // 2. Initial Sweep (catch existing elements on page load)
  if (badDomains.length > 0) sweepAndBlock(document.body, badDomains);
  if (quotesToHighlight.length > 0) highlightViolationsInNodes([document.body], quotesToHighlight);

  // 3. Real-Time MutationObserver (Optimized for SPAs & Dynamic Injections)
  const observer = new MutationObserver((mutations) => {
    // OPTIMIZATION: use a Set instead of an array. On SPAs a single burst of
    // mutations frequently touches the same element more than once (e.g. an
    // added container plus one of its own descendants also reported, or an
    // attribute change on a node that childList already queued) — dedupe
    // once here instead of paying for the same textContent/src scan twice
    // downstream in blockElements/highlightViolationsInNodes.
    const elementsToCheck = new Set<Element>();

    for (const mutation of mutations) {
      if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            const el = node as Element;
            elementsToCheck.add(el);
            // Check descendants of the added node
            const descendants = el.querySelectorAll?.('iframe, script, img, p, span, div, li, h1, h2, h3, h4, h5, h6');
            descendants?.forEach(desc => elementsToCheck.add(desc));
          }
        });
      } 
      // 🚀 SOTA FIX: Catch dynamic SPA src/href changes on existing elements
      else if (mutation.type === 'attributes' && mutation.target) {
        elementsToCheck.add(mutation.target as Element);
      }
    }

    if (elementsToCheck.size > 0) {
      const batch = Array.from(elementsToCheck);
      requestAnimationFrame(() => {
        if (badDomains.length > 0) blockElements(batch, badDomains);
        if (quotesToHighlight.length > 0) highlightViolationsInNodes(batch, quotesToHighlight);
      });
    }
  });

  observer.observe(document.body, { 
    childList: true, 
    subtree: true,
    attributes: true,
    attributeFilter: ['src', 'href'], // 🚀 SOTA: Catches dynamic tracker injections
    attributeOldValue: false
  });
  window.__ssenseActiveObserver = observer;
  
  console.log('[Ssense] MutationObserver active. Shield is locked in.');
}

// ═══════════════════════════════════════════════════════════════
// 🚀 SOTA: MAIN WORLD INJECTIONS
// ═══════════════════════════════════════════════════════════════

function injectGlobalPrivacyControl() {
  try {
    const script = document.createElement('script');
    script.textContent = `
      try {
        Object.defineProperty(Navigator.prototype, 'globalPrivacyControl', {
          get: function() { return true; },
          configurable: false
        });
      } catch(e) { /* CSP blocked */ }
    `;
    (document.head || document.documentElement).appendChild(script);
    script.remove();
    console.log('[Ssense] Global Privacy Control (GPC) signal injected.');
  } catch (e) {
    console.warn('[Ssense] Failed to inject GPC:', e);
  }
}

function spoofHardwareAPIs() {
  try {
    const script = document.createElement('script');
    script.textContent = `
      try {
        // Spoof Canvas Fingerprinting by adding microscopic noise
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type) {
          if (type === 'image/png' || type === 'image/jpeg') {
            const ctx = this.getContext('2d');
            if (ctx) {
              const imageData = ctx.getImageData(0, 0, this.width, this.height);
              for (let i = 0; i < imageData.data.length; i += 16) {
                imageData.data[i] += Math.floor(Math.random() * 2); // Red channel noise
              }
              ctx.putImageData(imageData, 0, 0);
            }
          }
          return originalToDataURL.apply(this, arguments);
        };
      } catch(e) { /* CSP blocked */ }
    `;
    (document.head || document.documentElement).appendChild(script);
    script.remove();
    console.log('[Ssense] Hardware API fingerprinting spoofed.');
  } catch (e) {
    console.warn('[Ssense] Failed to spoof hardware APIs:', e);
  }
}

// ═══════════════════════════════════════════════════════════════
// DOM MANIPULATION (Optimized for 60fps)
// ═══════════════════════════════════════════════════════════════

function blockElements(elements: Element[], badDomains: string[]) {
  try {
    for (const el of elements) {
      if (el.classList.contains('ssense-blocked-element')) continue;

      const tag = el.tagName;
      if (tag === 'IFRAME' || tag === 'SCRIPT' || tag === 'IMG') {
        const src = (el as HTMLIFrameElement | HTMLScriptElement | HTMLImageElement).src;
        if (src && matchesBlockedDomain(src, badDomains)) {
          el.classList.add('ssense-blocked-element');
          el.removeAttribute('src');
          if (tag === 'SCRIPT' || tag === 'IFRAME') {
            el.remove();
          }
        }
      }
    }
  } catch (err) {
    console.error('[Ssense] Error blocking elements:', err);
  }
}

function sweepAndBlock(rootNode: HTMLElement, badDomains: string[]) {
  try {
    const elements = rootNode.querySelectorAll('iframe, script, img');
    blockElements(Array.from(elements), badDomains);
  } catch (err) {
    console.error('[Ssense] Error sweeping elements:', err);
  }
}

// OPTIMIZATION: cap how large a container's subtree we're willing to
// stringify via .textContent per call. When a big nested subtree is added
// (e.g. an SPA route render), the MutationObserver batch already includes
// each descendant individually — so also computing .textContent on their
// large ancestor containers re-walks the same text repeatedly (effectively
// O(depth) redundant work per insertion). Skipping large containers here
// relies on their smaller descendants being checked directly instead.
const MAX_DESCENDANTS_FOR_TEXT_SCAN = 200;

// 🚀 SOTA: Incremental Highlighting (Only scans provided nodes)
function highlightViolationsInNodes(nodes: Element[], quotes: string[]) {
  try {
    for (const el of nodes) {
      // Only process text-bearing elements to save CPU
      if (['P', 'SPAN', 'DIV', 'LI', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'TD', 'TH'].includes(el.tagName)) {
        if (el.classList.contains('ssense-highlight-violation')) continue;
        if (el.getElementsByTagName('*').length > MAX_DESCENDANTS_FOR_TEXT_SCAN) continue;

        const text = (el.textContent || '').toLowerCase().replace(/\s+/g, ' ');
        
        for (const quote of quotes) {
          if (text.includes(quote)) {
            el.classList.add('ssense-highlight-violation');
            el.setAttribute('title', '⚠️ Ssense: DPDP Violation Detected');
            break; // Only highlight once per element
          }
        }
      }
    }
  } catch (err) {
    console.error('[Ssense] Error highlighting violations:', err);
  }
}
} // end __ssenseDarkPatternBlockerLoaded guard