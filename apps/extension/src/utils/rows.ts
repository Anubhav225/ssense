// apps/extension/src/utils/rows.ts — joins history entries + live scan records into view rows.

import type { SiteHistoryEntry } from '../background/history-store';
import type { ScanRecord } from '../background/scan-manager';
import type { Violation } from '../types/server-protocol';
import { groupBySeverity } from './severity';
import { siteStatus, type SiteStatus } from './status';

export interface SiteRow {
  domain: string;
  status: SiteStatus;
  score: number | null;
  violations: Violation[];
  counts: { high: number; medium: number; low: number; total: number };
  entry: SiteHistoryEntry;
  scan?: ScanRecord;
  ignored: boolean;
  error?: string;
  policyUrl?: string;
}

export function buildRows(entries: SiteHistoryEntry[], records: Record<string, ScanRecord>, ignored: string[]): SiteRow[] {
  const ign = new Set(ignored);
  return entries.map((entry) => {
    const scan = records[entry.domain];
    const violations = entry.lastReport?.violations ?? [];
    const g = groupBySeverity(violations);
    const isIgnored = ign.has(entry.domain);
    // Live record wins while a scan is in flight; otherwise the persisted outcome.
    const live = scan && (scan.state === 'scanning' || scan.state === 'queued' || scan.state === 'needs_signin' || scan.state === 'paused') ? scan.state : undefined;
    const state = live ?? (isIgnored ? 'skipped' : entry.scanState);
    const status = siteStatus({
      scanState: state,
      score: entry.lastScore,
      highCount: g.high.length,
      hasAudit: entry.lastReport !== null && entry.lastScore !== null,
    });
    return {
      domain: entry.domain, status, score: entry.lastScore, violations,
      counts: { high: g.high.length, medium: g.medium.length, low: g.low.length, total: violations.length },
      entry, scan, ignored: isIgnored,
      error: scan?.error || entry.scanError,
      policyUrl: entry.policyUrl || scan?.policyUrl,
    };
  });
}

/** Sites that most need the user's attention float to the top. */
const PRIORITY: Record<SiteStatus, number> = {
  scanning: 0, risk: 1, error: 2, review: 3, nopolicy: 4, compliant: 5, unscanned: 6, paused: 7, skipped: 8,
};
export const byAttention = (a: SiteRow, b: SiteRow) =>
  PRIORITY[a.status] - PRIORITY[b.status] || (a.score ?? 101) - (b.score ?? 101) || b.entry.lastVisit - a.entry.lastVisit;

export function summarize(rows: SiteRow[]) {
  const by: Record<SiteStatus, number> = { scanning: 0, compliant: 0, review: 0, risk: 0, nopolicy: 0, error: 0, skipped: 0, paused: 0, unscanned: 0 };
  let scored = 0, sum = 0, violations = 0;
  for (const r of rows) {
    by[r.status]++;
    violations += r.counts.total;
    if (typeof r.score === 'number') { scored++; sum += r.score; }
  }
  return { total: rows.length, byStatus: by, avgScore: scored ? Math.round(sum / scored) : null, violations, scored };
}
