// apps/extension/src/content/extractor.ts
//
// Minimal content script: finds the privacy-policy URL in the page DOM,
// validates it for safety, then hands it to the service worker.
// ALL fetching, parsing, and extraction now happens server-side in
// apps/slm-server/policy_fetcher.py — this script never reads policy text.

import { findPolicyUrl, isSafePublicUrl } from './extractor-core';

export {};
declare global { interface Window { __ssenseExtractorLoaded?: boolean; } }

if (!window.__ssenseExtractorLoaded) {
window.__ssenseExtractorLoaded = true;

function fail(reason: string) {
  chrome.runtime.sendMessage({
    type: 'EXTRACTION_FAILED',
    domain: window.location.hostname,
    reason,
  }).catch(() => {});
}

// Many sites (SPAs, consent-banner-gated footers) render their footer after
// document_idle. Try immediately, then twice more before giving up.
const RETRY_DELAYS_MS = [0, 2500, 6000];
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

(async () => {
  let policyUrl: string | null = null;
  for (const delay of RETRY_DELAYS_MS) {
    if (delay) await wait(delay);
    policyUrl = findPolicyUrl(document, document.baseURI);
    if (policyUrl) break;
  }
  if (!policyUrl) { fail('No privacy policy link found on this page.'); return; }
  if (!isSafePublicUrl(policyUrl)) { fail('Policy URL points to a private/internal host (SSRF guard).'); return; }

  await chrome.runtime.sendMessage({
    type:      'FOUND_POLICY_URL',
    domain:    window.location.hostname,
    pageUrl:   window.location.href,
    policyUrl,
  }).catch(() => {});
})();

} // end guard
