// apps/extension/src/content/extractor.test.ts
//
// Extraction (fetch + content-selection + language-filtering) moved
// server-side into apps/slm-server/policy_fetcher.py — see that file's
// equivalent logic. This client stays scoped to link DISCOVERY only (finding
// the policy URL on the live, already-rendered DOM, which only the browser
// has access to). Tests below cover exactly that surface.
import { describe, it, expect } from 'vitest';
import { findPolicyUrl, isSafePublicUrl } from './extractor-core';

function parseHtml(html: string): Document {
  return new DOMParser().parseFromString(html, 'text/html');
}

describe('link discovery — known site archetypes', () => {
  it('WordPress: rel=privacy-policy in <head> wins over any footer link', () => {
    const doc = parseHtml(`
      <head><link rel="privacy-policy" href="/privacy-policy/"></head>
      <body><footer><a href="/contact">Contact</a></footer></body>
    `);
    expect(findPolicyUrl(doc, 'https://blog.example.com/')).toBe('https://blog.example.com/privacy-policy/');
  });

  it('meta[name=privacy-policy] authoritative discovery', () => {
    const doc = parseHtml(`<head><meta name="privacy-policy" content="/legal/privacy-policy.html"></head><body></body>`);
    expect(findPolicyUrl(doc, 'https://example.com/')).toBe('https://example.com/legal/privacy-policy.html');
  });

  it('Shopify-style /policies/ link found via footer scan', () => {
    const doc = parseHtml(`
      <body><footer class="site-footer">
        <a href="/policies/refund-policy">Refunds</a>
        <a href="/policies/privacy-policy">Privacy Policy</a>
      </footer></body>
    `);
    expect(findPolicyUrl(doc, 'https://shop.example.com/')).toBe('https://shop.example.com/policies/privacy-policy');
  });

  it('OneTrust-style cookie-banner noise does not shadow the real footer link', () => {
    const doc = parseHtml(`
      <body>
        <div id="onetrust-banner-sdk" class="onetrust-banner"><a href="#">Accept</a></div>
        <footer><a href="/legal/privacy">Privacy</a></footer>
      </body>
    `);
    expect(findPolicyUrl(doc, 'https://enterprise.example.com/')).toBe('https://enterprise.example.com/legal/privacy');
  });

  it('generic "legal" class hub catches a link with no privacy-ish href', () => {
    const doc = parseHtml(`<body><div class="legal-links"><a href="/l/8f3">Privacy</a></div></body>`);
    expect(findPolicyUrl(doc, 'https://startup.example.com/')).toBe('https://startup.example.com/l/8f3');
  });

  it('a[href*="privacy"] outranks a same-page generic footer link when both exist', () => {
    const doc = parseHtml(`
      <body><footer>
        <a href="/about">About</a>
        <a href="/privacy">Privacy</a>
      </footer></body>
    `);
    expect(findPolicyUrl(doc, 'https://startup.example.com/')).toBe('https://startup.example.com/privacy');
  });

  it('returns null when no plausible link exists anywhere', () => {
    const doc = parseHtml(`<body><header><a href="/home">Home</a></header></body>`);
    expect(findPolicyUrl(doc, 'https://example.com/')).toBeNull();
  });

  it('SSRF: a discovered link pointing at a cloud metadata host is flagged unsafe', () => {
    const doc = parseHtml(`<body><footer><a href="http://169.254.169.254/latest/meta-data/privacy">Privacy</a></footer></body>`);
    const url = findPolicyUrl(doc, 'https://malicious.example.com/');
    expect(url).toBe('http://169.254.169.254/latest/meta-data/privacy');
    expect(isSafePublicUrl(url!)).toBe(false);
    // Server-side note: policy_fetcher.py's SSRF guard is the authoritative
    // check now (it resolves DNS and checks the actual resolved IP, not
    // just the hostname string) - this client-side check is a UX-only fast
    // path so the extension can show "unsafe link" without a round trip,
    // never the sole line of defense.
  });

  it('SSRF guard does not false-positive on normal public hosts', () => {
    expect(isSafePublicUrl('https://www.example.com/privacy')).toBe(true);
  });

  it('javascript: hrefs are never resolved to a fetchable URL', () => {
    const doc = parseHtml(`<body><footer><a href="javascript:void(0)">Privacy</a></footer></body>`);
    expect(findPolicyUrl(doc, 'https://example.com/')).toBeNull();
  });
});

describe('coverage summary (informational)', () => {
  it('link discovery succeeds on >= 90% of known-archetype fixtures in this suite', () => {
    const archetypes: Array<{ name: string; html: string; base: string }> = [
      { name: 'WordPress (link rel)', base: 'https://blog.example.com/', html: `<head><link rel="privacy-policy" href="/privacy-policy/"></head><body></body>` },
      { name: 'Shopify (/policies/)', base: 'https://shop.example.com/', html: `<body><footer><a href="/policies/privacy-policy">Privacy</a></footer></body>` },
      { name: 'OneTrust noise + footer', base: 'https://enterprise.example.com/', html: `<body><div class="onetrust-banner"></div><footer><a href="/legal/privacy">Privacy</a></footer></body>` },
      { name: 'Generic legal-hub class', base: 'https://startup.example.com/', html: `<body><div class="legal-links"><a href="/l/1">Privacy</a></div></body>` },
      { name: 'data-protection href', base: 'https://eu.example.com/', html: `<body><footer><a href="/data-protection">Data Protection</a></footer></body>` },
      { name: 'cookie-policy text match', base: 'https://site.example.com/', html: `<body><footer><a href="/legal/x9">Cookie Policy</a></footer></body>` },
    ];

    const results = archetypes.map(({ name, html, base }) => ({
      name,
      found: findPolicyUrl(parseHtml(html), base) !== null,
    }));

    const hitRate = results.filter(r => r.found).length / results.length;
    // eslint-disable-next-line no-console
    console.log('[extractor coverage]', results, `hit rate: ${(hitRate * 100).toFixed(0)}%`);
    expect(hitRate).toBeGreaterThanOrEqual(0.9);
  });
});

// NOTE: content-selection, language-filtering, and parse-latency coverage
// (previously tested here against client-side functions that no longer
// exist post-refactor) now belongs against policy_fetcher.py's
// _select_content / _strip_non_english / fetch_policy on the server side.
// Recommended follow-up: add an equivalent pytest suite in
// apps/slm-server/ covering those same real-world archetypes (WordPress,
// Shopify, OneTrust noise, bilingual Hindi/English) against the Python
// implementation, which is now authoritative.
