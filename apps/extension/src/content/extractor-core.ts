// apps/extension/src/content/extractor-core.ts
//
// URL DISCOVERY ONLY.
//
// HTML fetching, DOM parsing, text extraction, and language filtering have
// all moved to apps/slm-server/policy_fetcher.py.  The extension no longer
// handles policy text at all — it sends a URL to the server and receives a
// structured audit result back.
//
// This file retains only the two functions that genuinely require DOM access:
//   findPolicyUrl  — scans the live page DOM for a privacy policy link
//   isSafePublicUrl — SSRF guard run before the URL is ever sent off-device

// ─── URL resolution ────────────────────────────────────────────────────────────
export function resolveUrl(path: string, baseURI: string): string | null {
  try {
    const resolved = new URL(path, baseURI).href;
    return resolved.startsWith('http://') || resolved.startsWith('https://')
      ? resolved : null;
  } catch { return null; }
}

// ─── SSRF guard ────────────────────────────────────────────────────────────────
const _BLOCKED = [
  /^localhost$/i, /^127\./, /^0\.0\.0\.0$/, /^10\./,
  /^172\.(1[6-9]|2\d|3[01])\./, /^192\.168\./, /^169\.254\./,
  /^\[?::1\]?$/, /^\[?fe80:/i, /^\[?fc[0-9a-f]{2}:/i,
];
export function isSafePublicUrl(url: string): boolean {
  try {
    return !_BLOCKED.some(p => p.test(new URL(url).hostname));
  } catch { return false; }
}

// ─── Authoritative head-tag discovery ──────────────────────────────────────────
export function findAuthoritativePolicyUrl(doc: Document, baseURI: string): string | null {
  const link = doc.querySelector('link[rel~="privacy-policy"]');
  if (link) { const h = (link as HTMLLinkElement).getAttribute('href'); if (h) return resolveUrl(h, baseURI); }
  const meta = doc.querySelector('meta[name="privacy-policy"]');
  if (meta) { const c = meta.getAttribute('content'); if (c) return resolveUrl(c, baseURI); }
  return null;
}

// ─── Fallback DOM scan ──────────────────────────────────────────────────────────
const _HREF_SELECTORS = [
  'a[href*="privacy"]', 'a[href*="data-protection"]', 'a[href*="legal/privacy"]',
  'a[href*="data-policy"]', 'a[href*="/policies/"]', 'a[href*="datenschutz"]',
  'a[href*="confidentialite"]', 'a[href*="privacidad"]',
  'a[href*="iubenda.com"]', 'a[href*="termly.io"]', 'a[href*="privacypolicies.com"]',
  'a[href*="onetrust.com"]', 'a[href*="/legal"]', 'a[href*="/trust"]',
  // Modern compliance URL patterns
  'a[href*="privacy-notice"]', 'a[href*="privacy-choices"]',
  'a[href*="your-privacy"]', 'a[href*="privacy-rights"]',
  'a[href*="trust-center"]', 'a[href*="do-not-sell"]',
  'a[href*="ccpa"]', 'a[href*="gdpr"]',
  'a[href*="privacy-center"]', 'a[href*="data-processing"]',
  'footer a', '[class*="footer"] a', '[class*="legal"] a', '[id*="footer"] a',
];
const _COMBINED = _HREF_SELECTORS.join(', ');

const _URL_PATTERNS = [
  /privacy/i, /data[-\s]?protection/i, /cookie[-\s]?policy/i,
  /data[-\s]?policy/i, /datenschutz/i, /confidentialite/i,
  /privacidad/i, /iubenda\.com/i, /termly\.io/i,
  // Modern compliance URL fragments
  /privacy[-_]?notice/i, /privacy[-_]?choices/i, /privacy[-_]?rights/i,
  /trust[-_]?center/i, /do[-_]?not[-_]?sell/i, /\bccpa\b/i,
  /your[-_]?privacy/i, /privacy[-_]?center/i, /data[-_]?processing/i,
  /\bgdpr\b/i, /legal[-_]?notice/i, /privacy[-_]?statement/i,
];
const _TEXT_PATTERNS = [
  'privacy', 'data protection', 'cookie policy', 'data policy',
  'datenschutz', 'confidentialité', 'privacidad',
  // Modern compliance link text (US/EU standard terminology)
  'privacy notice', 'privacy choices', 'your privacy rights',
  'privacy center', 'trust center', 'do not sell',
  'do not share', 'legal notice',
  'privacy statement', 'data processing', 'manage cookies',
  'your california privacy', 'privacy & cookies',
];
const _WORD_TEXT_PATTERNS = [
  /\bccpa\b/i, /\bgdpr\b/i,
];

export function findFallbackPolicyUrl(doc: Document, baseURI: string): string | null {
  const anchors = doc.querySelectorAll<HTMLAnchorElement>(_COMBINED);
  if (!anchors.length) return null;

  const seen  = new Set<HTMLAnchorElement>();
  const buckets: HTMLAnchorElement[][] = _HREF_SELECTORS.map(() => []);
  anchors.forEach(a => {
    if (seen.has(a)) return; seen.add(a);
    for (let i = 0; i < _HREF_SELECTORS.length; i++) {
      if (a.matches(_HREF_SELECTORS[i])) { buckets[i].push(a); break; }
    }
  });

  for (const bucket of buckets) {
    for (const a of bucket) {
      const href = a.getAttribute('href');
      const text = (a.textContent || '').toLowerCase();
      if (!href || href.startsWith('#') || href.startsWith('javascript:')) continue;
      const abs = resolveUrl(href, baseURI);
      if (!abs) continue;
      if (
        _URL_PATTERNS.some(p => p.test(abs)) ||
        _TEXT_PATTERNS.some(t => text.includes(t)) ||
        _WORD_TEXT_PATTERNS.some(p => p.test(text))
      )
        return abs;
    }
  }
  return null;
}

export function findPolicyUrl(doc: Document, baseURI: string): string | null {
  return findAuthoritativePolicyUrl(doc, baseURI) || findFallbackPolicyUrl(doc, baseURI);
}
