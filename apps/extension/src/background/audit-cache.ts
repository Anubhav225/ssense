// apps/extension/src/background/audit-cache.ts
//
// Local audit result cache using chrome.storage.local.
//
// Stores only the structured audit result for each domain — no policy text,
// no HTML, no raw content.  The server fetches and discards policy text;
// the extension never sees it.
//
// Why chrome.storage.local instead of IndexedDB:
//   - Simple key-value access, no schema or transaction boilerplate
//   - Synchronous-feeling async API (single await)
//   - 10 MB default capacity — more than enough for thousands of audits
//     (each entry is ~2–4 KB of JSON)
//   - Survives service-worker restarts automatically

import type { AuditReport } from '../types/server-protocol';

export interface LocalAuditEntry {
  domain:          string;
  trust_score:     number;
  subtlety_score:  number;
  violation_count: number;
  violations:      AuditReport['violations'];
  global_legal_reasoning: string;
  policy_url:      string;
  audited_at:      number;   // Unix ms
  age_days:        number;
  source:          string;
}

const KEY_PREFIX = 'audit:';
const ALL_DOMAINS_KEY = 'audit_domains';  // sorted set of domain names for listing

function domainKey(domain: string): string {
  return KEY_PREFIX + domain.toLowerCase().replace(/^www\./, '');
}

// ── Write ─────────────────────────────────────────────────────────────────────
export async function saveAudit(
  domain: string,
  report: AuditReport,
  meta: { policy_url?: string; source?: string; age_days?: number },
): Promise<void> {
  const entry: LocalAuditEntry = {
    domain,
    trust_score:     report.dpdp_trust_score,
    subtlety_score:  report.subtlety_score,
    violation_count: report.violations?.length ?? 0,
    violations:      report.violations ?? [],
    global_legal_reasoning: report.global_legal_reasoning ?? '',
    policy_url:  meta.policy_url ?? '',
    audited_at:  Date.now(),
    age_days:    meta.age_days ?? 0,
    source:      meta.source ?? 'inference',
  };
  const normDomain = entry.domain.toLowerCase().replace(/^www\./, '');

  // Maintain the domains index so getAllAudits() can list without scanning keys
  const { [ALL_DOMAINS_KEY]: existing } = await chrome.storage.local.get(ALL_DOMAINS_KEY);
  const domains: string[] = existing ?? [];
  if (!domains.includes(normDomain)) domains.push(normDomain);

  await chrome.storage.local.set({
    [domainKey(domain)]: entry,
    [ALL_DOMAINS_KEY]:   domains,
  });
}

// ── Read one ──────────────────────────────────────────────────────────────────
export async function getAudit(domain: string): Promise<LocalAuditEntry | null> {
  const key = domainKey(domain);
  const result = await chrome.storage.local.get(key);
  return (result[key] as LocalAuditEntry) ?? null;
}

// ── Read all (for history view) ───────────────────────────────────────────────
export async function getAllAudits(): Promise<LocalAuditEntry[]> {
  const { [ALL_DOMAINS_KEY]: domains } = await chrome.storage.local.get(ALL_DOMAINS_KEY);
  if (!domains?.length) return [];
  const keys    = (domains as string[]).map(d => domainKey(d));
  const results = await chrome.storage.local.get(keys);
  return keys
    .map(k => results[k] as LocalAuditEntry)
    .filter(Boolean)
    .sort((a, b) => b.audited_at - a.audited_at);
}

// ── Remove one ────────────────────────────────────────────────────────────────
export async function removeAudit(domain: string): Promise<void> {
  const norm = domain.toLowerCase().replace(/^www\./, '');
  const { [ALL_DOMAINS_KEY]: domains } = await chrome.storage.local.get(ALL_DOMAINS_KEY);
  const filtered = ((domains as string[]) ?? []).filter(d => d !== norm);
  await chrome.storage.local.remove(domainKey(domain));
  await chrome.storage.local.set({ [ALL_DOMAINS_KEY]: filtered });
}

// ── Clear all ─────────────────────────────────────────────────────────────────
export async function clearAllAudits(): Promise<void> {
  const { [ALL_DOMAINS_KEY]: domains } = await chrome.storage.local.get(ALL_DOMAINS_KEY);
  const keys = ((domains as string[]) ?? []).map(d => domainKey(d));
  await chrome.storage.local.remove([...keys, ALL_DOMAINS_KEY]);
}
