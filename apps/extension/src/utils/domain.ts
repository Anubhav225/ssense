// apps/extension/src/utils/domain.ts
//
// Canonical domain normalization shared across all extension stores and components.
// Matches the server-side prefix stripping ('www.', 'en.', 'm.', 'app.') to guarantee
// complete client-server normalization parity without drift.

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
