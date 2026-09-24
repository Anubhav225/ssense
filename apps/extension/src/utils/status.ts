// apps/extension/src/utils/status.ts
//
// One place that decides what "status" a site shows in every surface
// (popup, history, options). Combines the live/persisted scan state with the
// latest audit result.

export type ScanState =
  | 'queued'
  | 'scanning'
  | 'done'
  | 'error'
  | 'nopolicy'
  | 'skipped'
  | 'paused'
  | 'needs_signin';

export type SiteStatus =
  | 'scanning'
  | 'compliant'
  | 'review'
  | 'risk'
  | 'nopolicy'
  | 'error'
  | 'skipped'
  | 'paused'
  | 'unscanned';

export interface StatusInput {
  scanState?: ScanState | null;
  score?: number | null;
  highCount?: number;
  hasAudit: boolean;
}

export function siteStatus(i: StatusInput): SiteStatus {
  if (i.scanState === 'scanning' || i.scanState === 'queued') return 'scanning';
  if (i.hasAudit && typeof i.score === 'number') {
    if (i.score >= 80 && !(i.highCount && i.highCount > 0)) return 'compliant';
    if (i.score >= 50) return 'review';
    return 'risk';
  }
  if (i.scanState === 'error') return 'error';
  if (i.scanState === 'nopolicy') return 'nopolicy';
  if (i.scanState === 'skipped') return 'skipped';
  if (i.scanState === 'paused' || i.scanState === 'needs_signin') return 'paused';
  return 'unscanned';
}

export const STATUS_META: Record<SiteStatus, { label: string; tone: 'ok' | 'warn' | 'bad' | 'info' | 'muted'; hint: string }> = {
  scanning:  { label: 'Scanning',        tone: 'info',  hint: 'Reading the privacy policy now' },
  compliant: { label: 'Compliant',       tone: 'ok',    hint: 'No serious DPDP issues found' },
  review:    { label: 'Needs review',    tone: 'warn',  hint: 'Some DPDP concerns found' },
  risk:      { label: 'Non-compliant',   tone: 'bad',   hint: 'Serious DPDP concerns found' },
  nopolicy:  { label: 'No policy found', tone: 'muted', hint: 'No privacy policy link was found on the page' },
  error:     { label: 'Scan failed',     tone: 'bad',   hint: 'The scan could not be completed' },
  skipped:   { label: 'Ignored',         tone: 'muted', hint: 'You excluded this site from scanning' },
  paused:    { label: 'Not scanned',     tone: 'muted', hint: 'Auto-scan is off or you are signed out' },
  unscanned: { label: 'Not scanned',     tone: 'muted', hint: 'Visited, but not audited yet' },
};

export function scoreTone(score: number | null | undefined): 'ok' | 'warn' | 'bad' | 'muted' {
  if (typeof score !== 'number') return 'muted';
  return score >= 80 ? 'ok' : score >= 50 ? 'warn' : 'bad';
}

/** Hosts we never scan: local/dev/private/internal or non-domain targets. */
export function isScannableHost(host: string | null | undefined): boolean {
  if (!host) return false;
  const h = host.toLowerCase();
  if (h === 'localhost' || h.endsWith('.local') || h.endsWith('.internal') || h.endsWith('.localhost')) return false;
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(h)) return false; // bare IPv4
  if (h.includes(':') || h.startsWith('[')) return false; // IPv6
  if (!h.includes('.')) return false; // intranet single-label
  return true;
}

export function formatRelative(ms: number | null | undefined, now = Date.now()): string {
  if (!ms) return 'never';
  const sec = Math.max(0, Math.floor((now - ms) / 1000));
  if (sec < 45) return 'just now';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${Math.max(1, min)}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  return new Date(ms).toLocaleDateString();
}

export function formatDuration(ms: number): string {
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}
