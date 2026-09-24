// apps/extension/src/sidebar/components/HistoryView.tsx
//
// Audit history — every site in one place.
//   • summary strip + status bar for the whole portfolio
//   • filter chips (by status), search, sort, expand/collapse all
//   • sites grouped by status (when sorted by attention); each group and each site collapses
//   • inside a site: usage stats, actions, score trend, legal reasoning,
//     and violations grouped by impact — each one collapsible with its evidence.
// Updates live as scans complete or another device syncs.

import React, { useEffect, useMemo, useRef, useState } from 'react';
import '../history.css';
import { Collapsible, ConfirmButton, DomainTile, Icon, ScoreRing, Spinner, StatusPill, Toast, ViolationGroups, useOpenSet, useToast } from '../../ui/components';
import { highlightOnPage, send, useAuth, useSites, useSyncState } from '../../ui/hooks';
import { byAttention, summarize, type SiteRow } from '../../utils/rows';
import { STATUS_META, formatDuration, formatRelative, type SiteStatus } from '../../utils/status';
import { prettyViolationType } from '../../utils/severity';

type SortKey = 'attention' | 'recent' | 'score' | 'violations' | 'time';
type Filter = 'all' | 'risk' | 'review' | 'compliant' | 'scanning' | 'issues';

const SEG: Record<string, string> = { risk: 'var(--ssense-accent-rose)', review: 'var(--ssense-accent-amber)', compliant: 'var(--ssense-accent-emerald)', scanning: 'var(--ssense-info)' };
const GROUPS: { key: string; title: string; match: SiteStatus[] }[] = [
  { key: 'risk', title: 'Non-compliant', match: ['risk'] },
  { key: 'review', title: 'Needs review', match: ['review'] },
  { key: 'scanning', title: 'Scanning now', match: ['scanning'] },
  { key: 'compliant', title: 'Compliant', match: ['compliant'] },
  { key: 'issues', title: 'Couldn’t scan', match: ['error', 'nopolicy'] },
  { key: 'other', title: 'Not scanned', match: ['unscanned', 'paused', 'skipped'] },
];
const AUDIT_TTL_DAYS = 90;

// ─── helpers ─────────────────────────────────────────────────────────────────
const Trend: React.FC<{ points?: { timestamp: number; score: number }[] }> = ({ points }) => {
  if (!points || points.length < 2) return <div className="sx-muted" style={{ fontSize: 12 }}>Trend appears after a second audit.</div>;
  const W = 300, H = 56, pad = 6;
  const xs = points.map((_, i) => pad + (i / (points.length - 1)) * (W - pad * 2));
  const ys = points.map((p) => H - pad - (p.score / 100) * (H - pad * 2));
  const d = xs.map((x, i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' ');
  const last = points[points.length - 1], first = points[0];
  const delta = last.score - first.score;
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" role="img" aria-label={`Score changed from ${first.score} to ${last.score}`}>
        <line x1={pad} x2={W - pad} y1={H - pad - 0.8 * (H - pad * 2)} y2={H - pad - 0.8 * (H - pad * 2)} stroke="var(--ssense-border-strong)" strokeDasharray="2 4" />
        <path d={d} fill="none" stroke="var(--ssense-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        {xs.map((x, i) => <circle key={i} cx={x} cy={ys[i]} r={i === xs.length - 1 ? 3.5 : 2} fill="var(--ssense-accent)" />)}
      </svg>
      <div className="sx-muted" style={{ fontSize: 11, display: 'flex', justifyContent: 'space-between' }}>
        <span>{points.length} audits · since {new Date(first.timestamp).toLocaleDateString()}</span>
        <b style={{ color: delta >= 0 ? 'var(--ssense-accent-emerald)' : 'var(--ssense-accent-rose)' }}>{delta >= 0 ? '+' : ''}{delta} pts</b>
      </div>
    </div>
  );
};

function freshness(lastAuditAt: number | null): string | null {
  if (!lastAuditAt) return null;
  const left = Math.ceil(AUDIT_TTL_DAYS - (Date.now() - lastAuditAt) / 86_400_000);
  return left <= 0 ? 'Refreshes on your next visit' : `Valid for ${left} more day${left === 1 ? '' : 's'}`;
}

function toCsv(rows: SiteRow[]): string {
  const q = (s: string) => `"${String(s).replace(/"/g, '""')}"`;
  const head = ['Domain', 'Status', 'Trust Score', 'Subtlety Score', 'High', 'Medium', 'Low', 'Violation Types', 'Statute References', 'Policy URL', 'Visits', 'Time Spent', 'First Visit', 'Last Visit', 'Last Audit'];
  const lines = rows.map((r) => {
    const e = r.entry;
    return [
      q(r.domain), q(STATUS_META[r.status].label), e.lastScore ?? '', e.lastReport?.subtlety_score ?? '',
      r.counts.high, r.counts.medium, r.counts.low,
      q(r.violations.map((v) => v.violation_type).join('; ')), q(r.violations.map((v) => v.statute_reference).filter(Boolean).join('; ')),
      q(r.policyUrl || ''), e.visitCount, q(formatDuration(e.totalTimeMs)),
      q(new Date(e.firstVisit).toISOString()), q(new Date(e.lastVisit).toISOString()), e.lastAuditAt ? q(new Date(e.lastAuditAt).toISOString()) : '',
    ].join(',');
  });
  return [head.join(','), ...lines].join('\n');
}

const Reasoning: React.FC<{ text?: string }> = ({ text }) => {
  const [open, setOpen] = useState(false);
  if (!text) return null;
  return (
    <Collapsible open={open} onToggle={() => setOpen((o) => !o)} className="sx-card" style={{ background: 'var(--ssense-bg-elevated)' }} headClassName=""
      header={<span style={{ padding: '9px 10px', fontSize: 12.5, fontWeight: 650, flex: 1 }}>Why this score? <span className="sx-muted" style={{ fontWeight: 500 }}>legal reasoning</span></span>}>
      <p style={{ margin: 0, padding: '0 12px 12px', fontSize: 12.5, lineHeight: 1.6, color: 'var(--ssense-text-secondary)' }}>{text}</p>
    </Collapsible>
  );
};

// ─── One site ────────────────────────────────────────────────────────────────
const SiteCard: React.FC<{
  row: SiteRow; open: boolean; onToggle: () => void; onChat: (d: string) => void; onReport: (d: string) => void; toast: (m: string) => void;
}> = ({ row, open, onToggle, onChat, onReport, toast }) => {
  const [busy, setBusy] = useState(false);
  const e = row.entry;
  const scanning = row.status === 'scanning';

  const rescan = async () => {
    setBusy(true);
    const r = await send<any>({ type: 'SCAN_NOW', domain: row.domain, policyUrl: row.policyUrl });
    setBusy(false);
    toast(r?.success === false ? r.error || 'Could not start the scan.' : 'Scan started');
  };
  const copy = async () => {
    const lines = [`${row.domain} — ${STATUS_META[row.status].label}${row.score != null ? `, trust score ${row.score}/100` : ''}`,
      ...row.violations.map((v) => `• ${prettyViolationType(v.violation_type)} (${v.statute_reference})${v.evidence_quote ? ` — “${v.evidence_quote}”` : ''}`)];
    try { await navigator.clipboard.writeText(lines.join('\n')); toast('Summary copied'); } catch { toast('Copy failed'); }
  };
  const headline = row.counts.total
    ? `${row.counts.total} issue${row.counts.total === 1 ? '' : 's'}${row.counts.high ? ` · ${row.counts.high} high` : ''}`
    : row.status === 'compliant' ? 'No violations' : STATUS_META[row.status].label;

  return (
    <Collapsible open={open} onToggle={onToggle} id={`site-${row.domain}`} className="sx-card hv-site" headClassName="hv-site-head"
      header={
        <>
          <DomainTile domain={row.domain} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="sx-trunc" style={{ fontSize: 13.5, fontWeight: 650 }}>{row.domain}</div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 4, flexWrap: 'wrap' }}>
              <StatusPill status={row.status} />
              <span className="sx-muted" style={{ fontSize: 11.5 }}>{headline} · {formatRelative(e.lastVisit)}</span>
            </div>
          </div>
          <ScoreRing score={row.score} size={42} scanning={scanning} />
        </>
      }>
      <div className="hv-site-body">
        <div className="hv-kv4">
          {([['Visits', String(e.visitCount)], ['Time', formatDuration(e.totalTimeMs)], ['Last audit', e.lastAuditAt ? formatRelative(e.lastAuditAt) : '—'], ['First seen', new Date(e.firstVisit).toLocaleDateString()]] as const).map(([k, v]) => (
            <div key={k} className="sx-kv"><span className="sx-eyebrow" style={{ fontSize: 9.5 }}>{k}</span><b>{v}</b></div>
          ))}
        </div>

        <div className="hv-actions">
          <button className="sx-btn sx-btn--primary sx-btn--sm" onClick={rescan} disabled={busy || scanning || row.ignored}>{busy || scanning ? <Spinner size={13} /> : <Icon name="refresh" size={13} />} {e.lastAuditAt ? 'Re-scan' : 'Scan'}</button>
          <button className="sx-btn sx-btn--sm" onClick={() => onChat(row.domain)}><Icon name="chat" size={13} /> Ask AI</button>
          {e.lastReport && <button className="sx-btn sx-btn--sm" onClick={() => onReport(row.domain)}>Full report</button>}
          <button className="sx-btn sx-btn--sm" onClick={() => chrome.tabs.create({ url: `https://${row.domain}` })}><Icon name="external" size={13} /> Visit</button>
          {row.policyUrl && <button className="sx-btn sx-btn--sm" onClick={() => chrome.tabs.create({ url: row.policyUrl! })}>Policy</button>}
          <button className="sx-btn sx-btn--sm" onClick={copy}>Copy</button>
          <button className="sx-btn sx-btn--sm" onClick={() => send({ type: 'IGNORE_SITE', domain: row.domain, ignore: !row.ignored })} aria-pressed={row.ignored}>
            <Icon name={row.ignored ? 'scan' : 'eyeOff'} size={13} /> {row.ignored ? 'Resume' : 'Ignore'}
          </button>
          <ConfirmButton size="sm" icon="trash" label="Remove" confirmLabel="Remove" onConfirm={() => send({ type: 'REMOVE_SITE_HISTORY', domain: row.domain })} />
        </div>

        {(row.status === 'error' || row.status === 'nopolicy') && row.error && (
          <div style={{ fontSize: 12, lineHeight: 1.5, padding: '9px 11px', borderRadius: 9, background: 'var(--ssense-bg-elevated)', color: 'var(--ssense-text-secondary)' }}>{row.error}</div>
        )}

        {e.lastReport && (
          <>
            <div className="hv-sect">
              <div className="sx-eyebrow">Violations · {row.counts.total}</div>
              <ViolationGroups violations={row.violations} compact onHighlight={highlightOnPage} defaultOpenHigh />
            </div>
            <Reasoning text={e.lastReport.global_legal_reasoning} />
            <div className="hv-sect">
              <div className="sx-eyebrow">Score trend</div>
              <Trend points={e.scoreHistory} />
              {freshness(e.lastAuditAt) && <div className="sx-muted" style={{ fontSize: 11 }}>{freshness(e.lastAuditAt)}</div>}
            </div>
          </>
        )}
      </div>
    </Collapsible>
  );
};

// ─── View ────────────────────────────────────────────────────────────────────
export const HistoryView: React.FC<{ onBack: () => void; onOpenPrivacy?: (domain: string) => void }> = ({ onBack, onOpenPrivacy }) => {
  const { rows, loading } = useSites();
  const { state: sync, syncNow } = useSyncState();
  const { auth } = useAuth();
  const [sort, setSort] = useState<SortKey>('attention');
  const [filter, setFilter] = useState<Filter>('all');
  const [q, setQ] = useState('');
  const sites = useOpenSet();
  const groupsClosed = useOpenSet();
  const { msg, show } = useToast();
  const listRef = useRef<HTMLDivElement>(null);

  // Deep-link from the popup: open + scroll to one site.
  useEffect(() => {
    const focus = async () => {
      const d = (await chrome.storage.local.get('ssense_history_focus')).ssense_history_focus as string | null;
      if (!d) return;
      await chrome.storage.local.remove('ssense_history_focus');
      sites.add(d);
      setTimeout(() => {
        const el = document.getElementById(`site-${d}`);
        el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el?.classList.add('hv-flash');
      }, 250);
    };
    void focus();
    const l = (c: Record<string, chrome.storage.StorageChange>, area: string) => { if (area === 'local' && c.ssense_history_focus?.newValue) void focus(); };
    chrome.storage.onChanged.addListener(l);
    return () => chrome.storage.onChanged.removeListener(l);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const summary = useMemo(() => summarize(rows), [rows]);
  const attention = summary.byStatus.risk + summary.byStatus.review + summary.byStatus.error;

  const chips: { id: Filter; label: string; n: number }[] = [
    { id: 'all', label: 'All', n: summary.total },
    { id: 'risk', label: 'Non-compliant', n: summary.byStatus.risk },
    { id: 'review', label: 'Review', n: summary.byStatus.review },
    { id: 'compliant', label: 'Compliant', n: summary.byStatus.compliant },
    { id: 'scanning', label: 'Scanning', n: summary.byStatus.scanning },
    { id: 'issues', label: 'Couldn’t scan', n: summary.byStatus.error + summary.byStatus.nopolicy },
  ];

  const visible = useMemo(() => {
    const term = q.trim().toLowerCase();
    let list = rows.filter((r) => {
      if (term && !r.domain.includes(term)) return false;
      if (filter === 'all') return true;
      if (filter === 'issues') return r.status === 'error' || r.status === 'nopolicy';
      return r.status === filter;
    });
    list = [...list];
    if (sort === 'attention') list.sort(byAttention);
    if (sort === 'recent') list.sort((a, b) => b.entry.lastVisit - a.entry.lastVisit);
    if (sort === 'score') list.sort((a, b) => (a.score ?? 999) - (b.score ?? 999));
    if (sort === 'violations') list.sort((a, b) => b.counts.total - a.counts.total || b.counts.high - a.counts.high);
    if (sort === 'time') list.sort((a, b) => b.entry.totalTimeMs - a.entry.totalTimeMs);
    return list;
  }, [rows, sort, filter, q]);

  const chat = async (domain: string) => {
    await send({ type: 'DESELECT_SITE_THREAD' });
    const r = await send<any>({ type: 'SELECT_SITE_THREAD', domain });
    if (r?.success) onBack(); else show(r?.error || 'Could not open chat.');
  };
  const exportCsv = () => {
    const url = URL.createObjectURL(new Blob([toCsv(rows)], { type: 'text/csv;charset=utf-8;' }));
    Object.assign(document.createElement('a'), { href: url, download: `ssense_dpdp_audit_${new Date().toISOString().slice(0, 10)}.csv` }).click();
    URL.revokeObjectURL(url);
  };

  const renderCard = (r: SiteRow) => (
    <SiteCard key={r.domain} row={r} open={sites.isOpen(r.domain)} onToggle={() => sites.toggle(r.domain)} onChat={chat}
      onReport={(d) => onOpenPrivacy?.(d)} toast={show} />
  );

  const grouped = sort === 'attention' && filter === 'all' && !q;
  const allOpen = visible.length > 0 && visible.every((r) => sites.isOpen(r.domain));

  return (
    <div className="hv">
      <div className="hv-top">
        <div className="hv-row">
          <button className="sx-icon-btn" onClick={onBack} title="Back" aria-label="Back"><Icon name="chevron" size={18} style={{ transform: 'rotate(180deg)' }} /></button>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="sx-display" style={{ fontSize: 18, lineHeight: 1.1 }}>Audit history</div>
            <div className="sx-muted sx-trunc" style={{ fontSize: 11.5 }}>
              {sync?.status === 'syncing' ? 'Syncing…' : sync?.lastSyncAt ? `Synced ${formatRelative(sync.lastSyncAt)}${auth?.email ? ` · ${auth.email}` : ''}` : auth?.email || 'This device'}
            </div>
          </div>
          <button className="sx-icon-btn" onClick={syncNow} title="Sync now" aria-label="Sync now" disabled={sync?.status === 'syncing'}><Icon name="sync" size={16} className={sync?.status === 'syncing' ? 'sx-ring-spin' : undefined} /></button>
          <button className="sx-icon-btn" onClick={exportCsv} disabled={!rows.length} title="Export CSV" aria-label="Export CSV"><Icon name="download" size={16} /></button>
          <ConfirmButton size="sm" icon="trash" label="Clear" confirmLabel="Clear all" disabled={!rows.length} onConfirm={async () => { await send({ type: 'CLEAR_HISTORY' }); show('History cleared on this device'); }} />
        </div>

        <div className="hv-kpis">
          <div className="hv-kpi"><b>{summary.total}</b><span>Sites</span></div>
          <div className="hv-kpi"><b style={{ color: summary.avgScore == null ? undefined : summary.avgScore >= 80 ? 'var(--ssense-accent-emerald)' : summary.avgScore >= 50 ? 'var(--ssense-accent-amber)' : 'var(--ssense-accent-rose)' }}>{summary.avgScore ?? '–'}</b><span>Avg score</span></div>
          <div className="hv-kpi"><b>{summary.violations}</b><span>Violations</span></div>
          <div className="hv-kpi"><b style={{ color: attention ? 'var(--ssense-accent-rose)' : undefined }}>{attention}</b><span>Need attention</span></div>
        </div>
        {summary.total > 0 && (
          <div className="hv-bar" role="img" aria-label="Sites by status">
            {(['risk', 'review', 'compliant', 'scanning'] as const).map((k) => summary.byStatus[k] > 0 && <span key={k} style={{ flex: summary.byStatus[k], background: SEG[k] }} />)}
            {summary.total - summary.byStatus.risk - summary.byStatus.review - summary.byStatus.compliant - summary.byStatus.scanning > 0 &&
              <span style={{ flex: summary.total - summary.byStatus.risk - summary.byStatus.review - summary.byStatus.compliant - summary.byStatus.scanning, background: 'var(--ssense-border-strong)' }} />}
          </div>
        )}
      </div>

      <div className="hv-tools">
        <div className="hv-row">
          <div style={{ position: 'relative', flex: 1 }}>
            <Icon name="search" size={14} style={{ position: 'absolute', left: 10, top: 11, color: 'var(--ssense-text-muted)' }} />
            <input className="sx-input" style={{ paddingLeft: 30 }} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search sites…" aria-label="Search sites" />
          </div>
          <select className="sx-input sx-select" style={{ width: 'auto' }} value={sort} onChange={(e) => setSort(e.target.value as SortKey)} aria-label="Sort">
            <option value="attention">Needs attention</option>
            <option value="recent">Most recent</option>
            <option value="score">Lowest score</option>
            <option value="violations">Most violations</option>
            <option value="time">Most time</option>
          </select>
          <button className="sx-icon-btn" onClick={() => (allOpen ? sites.clear() : sites.set(visible.map((r) => r.domain)))} title={allOpen ? 'Collapse all' : 'Expand all'} aria-label={allOpen ? 'Collapse all' : 'Expand all'}>
            <Icon name={allOpen ? 'collapse' : 'expand'} size={16} />
          </button>
        </div>
        <div className="hv-chips" role="group" aria-label="Filter by status">
          {chips.map((c) => <button key={c.id} className="hv-chip" aria-pressed={filter === c.id} onClick={() => setFilter(c.id)}>{c.label} <em>{c.n}</em></button>)}
        </div>
      </div>

      <div className="hv-list sx-scroll" ref={listRef}>
        {loading ? (
          <>{[0, 1, 2].map((i) => <div key={i} className="sx-skel" style={{ height: 66 }} />)}</>
        ) : rows.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '44px 16px', display: 'grid', gap: 8, justifyItems: 'center' }}>
            <div style={{ width: 48, height: 48, borderRadius: 15, display: 'grid', placeItems: 'center', background: 'var(--ssense-accent-soft)', color: 'var(--ssense-accent)' }}><Icon name="history" size={24} /></div>
            <div className="sx-display" style={{ fontSize: 19 }}>Nothing audited yet</div>
            <div style={{ fontSize: 12.5, lineHeight: 1.55, color: 'var(--ssense-text-secondary)', maxWidth: 300 }}>Browse normally. Each site you open is scanned automatically and appears here with its status and violations.</div>
          </div>
        ) : visible.length === 0 ? (
          <div className="sx-muted" style={{ textAlign: 'center', padding: 30, fontSize: 13 }}>No sites match this filter.</div>
        ) : grouped ? (
          GROUPS.map((g) => {
            const list = visible.filter((r) => g.match.includes(r.status));
            if (!list.length) return null;
            const isOpen = !groupsClosed.isOpen(g.key);
            return (
              <div key={g.key} style={{ display: 'grid', gap: 8 }}>
                <button className="hv-group-head sx-coll-head" onClick={() => groupsClosed.toggle(g.key)} aria-expanded={isOpen} style={{ width: '100%' }}>
                  <Icon name="chevron" size={13} style={{ transform: isOpen ? 'rotate(90deg)' : undefined, transition: 'transform .2s' }} />
                  {g.title} · {list.length}<span className="hv-line" />
                </button>
                {isOpen && list.map(renderCard)}
              </div>
            );
          })
        ) : visible.map(renderCard)}

        <div className="sx-muted" style={{ fontSize: 11, lineHeight: 1.5, textAlign: 'center', paddingTop: 6 }}>
          Audits stay valid for {AUDIT_TTL_DAYS} days{rows[0]?.entry.lastAuditAt ? ` · ${freshness(rows[0].entry.lastAuditAt)?.toLowerCase()} for the latest` : ''}.
        </div>
      </div>
      <Toast message={msg} />
    </div>
  );
};
