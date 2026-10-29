// apps/extension/src/utils/domain.ts
//
// Canonical domain normalization and first-party domain validation shared
// across all extension stores, background workers, and content scripts.

export const DOMAIN_PREFIXES = ['www.', 'en.', 'm.', 'app.'] as const;

/**
 * Normalizes a domain or URL string to a clean, canonical domain key:
 * - Strips protocol ('https://', 'http://')
 * - Strips ports, query strings, and paths
 * - Strips leading subdomains in DOMAIN_PREFIXES ('www.', 'en.', 'm.', 'app.')
 */
export function normaliseDomain(domain: string): string {
  if (!domain) return '';
  let low = domain.trim().toLowerCase();
  for (const prefix of ['https://', 'http://']) {
    if (low.startsWith(prefix)) {
      low = low.slice(prefix.length);
    }
  }
  low = low.split('/')[0].split('?')[0].split(':')[0];
  for (const pfx of DOMAIN_PREFIXES) {
    if (low.startsWith(pfx)) {
      low = low.slice(pfx.length);
    }
  }
  return low;
}

/** Known related fiduciary domain families (CDNs, asset hosts, subsidiaries) */
export const RELATED_FIDUCIARY_DOMAINS: string[][] = [
  // Wikimedia / Wikipedia
  ['wikipedia.org', 'wikimedia.org', 'wikidata.org', 'wiktionary.org', 'wikinews.org', 'wikiquote.org', 'wikisource.org', 'wikiversity.org', 'wikivoyage.org', 'mediawiki.org'],
  // Reddit
  ['reddit.com', 'redd.it', 'redditmedia.com', 'redditstatic.com'],
  // Google / YouTube
  ['google.com', 'google.co.in', 'gstatic.com', 'googleapis.com', 'googleusercontent.com', 'googlevideo.com', 'ytimg.com', 'youtube.com'],
  // Amazon
  ['amazon.com', 'amazon.in', 'media-amazon.com', 'ssl-images-amazon.com', 'assoc-amazon.com', 'a2z.com'],
  // Twitter / X
  ['twitter.com', 'x.com', 'twimg.com', 't.co'],
  // GitHub
  ['github.com', 'githubusercontent.com', 'githubassets.com', 'github.io'],
  // Stack Overflow / Stack Exchange
  ['stackoverflow.com', 'stackexchange.com', 'sstatic.net', 'superuser.com', 'serverfault.com', 'askubuntu.com'],
  // Microsoft
  ['microsoft.com', 'azure.com', 'live.com', 'office.com', 'microsoftonline.com', 's-microsoft.com', 'msecnd.net', 'bing.com'],
  // Apple
  ['apple.com', 'cdn-apple.com', 'icloud.com', 'mzstatic.com'],
  // Meta
  ['facebook.com', 'instagram.com', 'fbcdn.net', 'cdninstagram.com', 'threads.net', 'meta.com'],
  // Swiggy
  ['swiggy.com', 'swiggy.in'],
  // Zomato
  ['zomato.com', 'zmtcdn.com'],
  // Flipkart
  ['flipkart.com', 'flixcart.com'],
];

/** Check if an entity belongs to the first-party domain or its CDN family to prevent self-blocking */
export function isFirstPartyDomain(entity: string, host: string): boolean {
  if (!entity || !host) return false;
  const cleanEntity = entity.toLowerCase().trim().replace(/^https?:\/\//, '').split('/')[0].split(':')[0];
  const cleanHost = host.toLowerCase().trim().replace(/^https?:\/\//, '').split('/')[0].split(':')[0];
  if (!cleanEntity || !cleanHost) return false;
  if (cleanEntity === cleanHost) return true;
  if (cleanHost.endsWith('.' + cleanEntity)) return true;
  if (cleanEntity.endsWith('.' + cleanHost)) return true;

  const getBase = (d: string) => {
    const parts = d.split('.');
    if (parts.length <= 2) return d;
    const special = ['co.in', 'com.au', 'co.uk', 'org.in', 'net.in', 'gov.in'];
    const lastTwo = parts.slice(-2).join('.');
    if (special.includes(lastTwo) && parts.length >= 3) {
      return parts.slice(-3).join('.');
    }
    return parts.slice(-2).join('.');
  };

  const baseEntity = getBase(cleanEntity);
  const baseHost = getBase(cleanHost);
  if (baseEntity === baseHost) return true;

  // Check related fiduciary families (e.g. upload.wikimedia.org on en.wikipedia.org)
  for (const family of RELATED_FIDUCIARY_DOMAINS) {
    const inFamilyEntity = family.some((f) => baseEntity === f || baseEntity.endsWith('.' + f));
    const inFamilyHost = family.some((f) => baseHost === f || baseHost.endsWith('.' + f));
    if (inFamilyEntity && inFamilyHost) return true;
  }

  return false;
}
