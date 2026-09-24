import { describe, expect, it } from 'vitest';
import { severityOf, groupBySeverity } from './severity';
import { siteStatus, isScannableHost, formatRelative } from './status';
import { sanitizePrefs, isIgnored, DEFAULT_PREFS } from '../background/prefs';
import { mergeEntries, type SiteHistoryEntry } from '../background/history-store';
import { buildRows, summarize } from './rows';

const entry = (o: Partial<SiteHistoryEntry> = {}): SiteHistoryEntry => ({
  domain: 'a.com', firstVisit: 100, lastVisit: 200, visitCount: 0, totalTimeMs: 0,
  lastScore: null, lastReport: null, lastAuditAt: null, updatedAt: 200, ...o,
});
const report = (score: number, types: string[] = []) => ({
  dpdp_trust_score: score, subtlety_score: 10, global_legal_reasoning: '',
  violations: types.map((t) => ({ violation_type: t, statute_reference: 'S4', evidence_quote: '', network_action: 'WARN_USER_ONLY', offending_entities: [] })),
});

describe('severity', () => {
  it('ranks consent/child/security as high, notice as low, unknown as medium', () => {
    expect(severityOf({ violation_type: 'CONSENT_NOT_FREE_OR_SPECIFIC', network_action: 'WARN_USER_ONLY' })).toBe('high');
    expect(severityOf({ violation_type: 'NOTICE_INADEQUATE', network_action: 'WARN_USER_ONLY' })).toBe('low');
    expect(severityOf({ violation_type: 'NOTICE_INADEQUATE', network_action: 'BLOCK_THIRD_PARTY' })).toBe('medium');
    expect(severityOf({ violation_type: 'SOMETHING_NEW', network_action: 'X' })).toBe('medium');
  });
  it('groups', () => {
    const g = groupBySeverity([{ violation_type: 'CHILD_CONSENT_VIOLATION', network_action: '' }, { violation_type: 'NOTICE_INADEQUATE', network_action: '' }]);
    expect(g.high.length).toBe(1); expect(g.low.length).toBe(1);
  });
});

describe('status', () => {
  it('derives status from scan state + score', () => {
    expect(siteStatus({ scanState: 'scanning', hasAudit: true, score: 90 })).toBe('scanning');
    expect(siteStatus({ hasAudit: true, score: 90, highCount: 0 })).toBe('compliant');
    expect(siteStatus({ hasAudit: true, score: 90, highCount: 1 })).toBe('review');
    expect(siteStatus({ hasAudit: true, score: 30 })).toBe('risk');
    expect(siteStatus({ hasAudit: false, scanState: 'nopolicy' })).toBe('nopolicy');
    expect(siteStatus({ hasAudit: false })).toBe('unscanned');
  });
  it('filters unscannable hosts', () => {
    for (const h of ['localhost', '192.168.1.1', 'intranet', 'x.local', '[::1]']) expect(isScannableHost(h)).toBe(false);
    expect(isScannableHost('example.com')).toBe(true);
  });
  it('formats relative time', () => { expect(formatRelative(null)).toBe('never'); expect(formatRelative(Date.now() - 3 * 3600_000)).toBe('3h ago'); });
});

describe('prefs', () => {
  it('sanitises and clamps', () => {
    const p = sanitizePrefs({ rescanAfterDays: 9999, lowScoreThreshold: -4, theme: 'neon' as any, ignoredDomains: ['https://WWW.Foo.com/x', 'foo.com', ''] });
    expect(p.rescanAfterDays).toBe(90); expect(p.lowScoreThreshold).toBe(5); expect(p.theme).toBe('system'); expect(p.ignoredDomains).toEqual(['foo.com']);
  });
  it('matches ignored subdomains', () => {
    const p = { ...DEFAULT_PREFS, ignoredDomains: ['bank.com'] };
    expect(isIgnored(p, 'login.bank.com')).toBe(true); expect(isIgnored(p, 'notbank.com')).toBe(false);
  });
});

describe('multi-device merge', () => {
  it('sums per-device time/visits, keeps newest audit', () => {
    const local = entry({ visitsByDevice: { pc: 3 }, timeByDevice: { pc: 1000 }, lastScore: 60, lastReport: report(60), lastAuditAt: 500, updatedAt: 500 });
    const remote = entry({ visitsByDevice: { phone: 2 }, timeByDevice: { phone: 400 }, lastScore: 80, lastReport: report(80), lastAuditAt: 900, updatedAt: 900, firstVisit: 50 });
    const m = mergeEntries(local, remote, 'pc');
    expect(m.visitCount).toBe(5); expect(m.totalTimeMs).toBe(1400);
    expect(m.lastScore).toBe(80); expect(m.firstVisit).toBe(50); expect(m.updatedAt).toBe(900);
  });
  it('is idempotent and never double counts the same device', () => {
    const a = entry({ visitsByDevice: { pc: 3 }, timeByDevice: { pc: 1000 } });
    const m1 = mergeEntries(a, a, 'pc'); const m2 = mergeEntries(m1, a, 'pc');
    expect(m2.visitCount).toBe(3); expect(m2.totalTimeMs).toBe(1000);
  });
  it('unions score history', () => {
    const a = entry({ scoreHistory: [{ timestamp: 1, score: 10 }, { timestamp: 3, score: 30 }] });
    const b = entry({ scoreHistory: [{ timestamp: 2, score: 20 }, { timestamp: 3, score: 30 }] });
    expect(mergeEntries(a, b, 'pc').scoreHistory!.map((p) => p.timestamp)).toEqual([1, 2, 3]);
  });
});

describe('rows', () => {
  it('shows live scanning over persisted state and summarises', () => {
    const rows = buildRows(
      [entry({ domain: 'a.com', lastScore: 90, lastReport: report(90) }), entry({ domain: 'b.com', lastScore: 20, lastReport: report(20, ['CHILD_CONSENT_VIOLATION']) }), entry({ domain: 'c.com', scanState: 'nopolicy' })],
      { 'a.com': { state: 'scanning', at: 1 } }, [],
    );
    expect(rows.map((r) => r.status)).toEqual(['scanning', 'risk', 'nopolicy']);
    const s = summarize(rows);
    expect(s.total).toBe(3); expect(s.violations).toBe(1); expect(s.avgScore).toBe(55);
  });
});
