// apps/extension/src/sidebar/components/HistoryView.tsx
//
// Complete redesign with collapsible per-site audit cards, full violation
// descriptions, statute references, evidence quotes, and live report links.

import React, { useEffect, useMemo, useState } from 'react';
import type { SiteHistoryEntry } from '../../background/history-store';

type SortKey = 'recent' | 'time' | 'violations' | 'score';

function formatDuration(ms: number): string {
  const totalSec = Math.round(ms / 1000);
  if (totalSec < 60) return `${totalSec}s`;
  const min = Math.floor(totalSec / 60);
  if (min < 60) return `${min}m`;
  const hr = Math.floor(min / 60);
  return `${hr}h ${min % 60}m`;
}

function formatRelativeTime(ms: number): string {
  const diff = Date.now() - ms;
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return 'just now';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  return `${day}d ago`;
}

function scoreColor(score: number | null): string {
  if (score === null) return 'var(--ssense-text-muted)';
  if (score >= 80) return 'var(--ssense-accent-emerald)';
  if (score >= 50) return 'var(--ssense-accent-amber)';
  return 'var(--ssense-accent-rose)';
}

const AUDIT_TTL_DAYS = 90;
function auditFreshness(lastAuditAt: number | null): { label: string; stale: boolean } | null {
  if (lastAuditAt === null) return null;
  const daysSince = (Date.now() - lastAuditAt) / (1000 * 60 * 60 * 24);
  const daysLeft = Math.ceil(AUDIT_TTL_DAYS - daysSince);
  if (daysLeft <= 0) return { label: 'Audit will refresh on your next visit', stale: true };
  if (daysLeft <= 7) return { label: `Refreshes automatically in ${daysLeft}d`, stale: true };
  return { label: `Valid for ${daysLeft}d`, stale: false };
}

const Sparkline = ({ points }: { points?: { score: number }[] }) => {
  if (!points || points.length < 2) return null;
  const scores = points.map(p => p.score);
  const min = Math.min(...scores, 0);
  const max = Math.max(...scores, 100);
  const range = max - min || 1;
  const w = 48, h = 16;
  const coords = scores.map((s, i) => {
    const x = (i / (scores.length - 1)) * w;
    const y = h - ((s - min) / range) * (h - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const lastScore = scores[scores.length - 1];
  const strokeColor = lastScore >= 80 ? 'var(--ssense-accent-emerald)' : lastScore >= 50 ? 'var(--ssense-accent-amber)' : 'var(--ssense-accent-rose)';
  return (
    <svg width={w} height={h} style={{ overflow: 'visible', verticalAlign: 'middle', flexShrink: 0 }}>
      <title>Score trend over visits</title>
      <polyline fill="none" stroke={strokeColor} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" points={coords} />
    </svg>
  );
};

export const HistoryView: React.FC<{ onBack: () => void; onOpenPrivacy?: (domain: string) => void }> = ({ onBack, onOpenPrivacy }) => {
  const [entries, setEntries] = useState<SiteHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>('recent');
  const [filter, setFilter] = useState('');
  const [expandedDomains, setExpandedDomains] = useState<Set<string>>(new Set());

  const loadHistory = async () => {
    setLoading(true);
    try {
      const res = await chrome.runtime.sendMessage({ type: 'GET_HISTORY' });
      setEntries(res?.entries || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadHistory(); }, []);

  const toggleExpand = (domain: string) => {
    setExpandedDomains(prev => {
      const next = new Set(prev);
      if (next.has(domain)) next.delete(domain);
      else next.add(domain);
      return next;
    });
  };

  const handleClear = async () => {
    if (!confirm('Clear all browsing and audit history? This cannot be undone.')) return;
    await chrome.runtime.sendMessage({ type: 'CLEAR_HISTORY' });
    await loadHistory();
  };

  const handleExportAll = () => {
    if (!entries.length) return;
    const escapeCsv = (str: string) => `"${str.replace(/"/g, '""')}"`;

    const headers = [
      'Domain',
      'Visits',
      'Total Time Spent',
      'Trust Score',
      'Subtlety Score',
      'Violations Count',
      'Statute References',
      'Global Legal Reasoning',
      'First Visit',
      'Last Visit',
      'Last Audit',
    ];

    const rows = [
      headers.join(','),
      ...entries.map(e => {
        const violations = e.lastReport?.violations || [];
        const statuteRefs = violations.map(v => v.statute_reference).filter(Boolean).join('; ');
        const reasoning = e.lastReport?.global_legal_reasoning || '';
        const subtlety = e.lastReport?.subtlety_score ?? 'N/A';

        return [
          escapeCsv(e.domain),
          e.visitCount,
          escapeCsv(formatDuration(e.totalTimeMs)),
          e.lastScore ?? 'N/A',
          subtlety,
          violations.length,
          escapeCsv(statuteRefs || 'None'),
          escapeCsv(reasoning),
          escapeCsv(new Date(e.firstVisit).toISOString()),
          escapeCsv(new Date(e.lastVisit).toISOString()),
          e.lastAuditAt ? escapeCsv(new Date(e.lastAuditAt).toISOString()) : 'N/A',
        ].join(',');
      }),
    ];

    const csvContent = rows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement('a'), {
      href: url,
      download: `ssense_dpdp_audit_history_${new Date().toISOString().split('T')[0]}.csv`,
    });
    a.click();
    URL.revokeObjectURL(url);
  };

  const visible = useMemo(() => {
    let list = entries;
    if (filter.trim()) {
      const q = filter.toLowerCase();
      list = list.filter((e) => e.domain.toLowerCase().includes(q));
    }
    const sorted = [...list];
    if (sortKey === 'recent') sorted.sort((a, b) => b.lastVisit - a.lastVisit);
    if (sortKey === 'time') sorted.sort((a, b) => b.totalTimeMs - a.totalTimeMs);
    if (sortKey === 'violations') {
      sorted.sort((a, b) => (b.lastReport?.violations.length || 0) - (a.lastReport?.violations.length || 0));
    }
    if (sortKey === 'score') {
      sorted.sort((a, b) => (a.lastScore ?? 999) - (b.lastScore ?? 999));
    }
    return sorted;
  }, [entries, sortKey, filter]);

  return (
    <div className="ssense-root">
      {/* Header */}
      <header className="ssense-header" style={{ paddingBottom: 10 }}>
        <div className="ssense-header-top">
          <div className="ssense-header-left">
            <button
              onClick={onBack}
              style={{
                background: 'var(--ssense-bg-elevated)',
                border: '1px solid var(--ssense-border)',
                color: 'var(--ssense-text-primary)',
                cursor: 'pointer',
                fontSize: 14,
                padding: '5px 9px',
                borderRadius: 7,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              title="Back to Co-Pilot"
            >
              ←
            </button>
            <div className="ssense-header-info">
              <div className="ssense-domain" style={{ fontSize: 14 }}>Compliance &amp; History</div>
              <div style={{ fontSize: 11, color: 'var(--ssense-text-muted)' }}>
                {entries.length} site{entries.length === 1 ? '' : 's'} tracked
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
            <button
              onClick={handleExportAll}
              disabled={entries.length === 0}
              style={{
                background: 'var(--ssense-bg-elevated)',
                border: '1px solid var(--ssense-border)',
                color: 'var(--ssense-text-primary)',
                fontSize: 11,
                fontWeight: 600,
                padding: '5px 9px',
                borderRadius: 7,
                cursor: entries.length === 0 ? 'not-allowed' : 'pointer',
                opacity: entries.length === 0 ? 0.5 : 1,
              }}
              title="Export complete compliance report as CSV"
            >
              Export CSV
            </button>
            <button
              onClick={handleClear}
              disabled={entries.length === 0}
              style={{
                background: 'rgba(244,63,94,0.1)',
                border: '1px solid rgba(244,63,94,0.25)',
                color: 'var(--ssense-accent-rose)',
                fontSize: 11,
                fontWeight: 600,
                padding: '5px 9px',
                borderRadius: 7,
                cursor: entries.length === 0 ? 'not-allowed' : 'pointer',
                opacity: entries.length === 0 ? 0.5 : 1,
              }}
              title="Clear all stored site history"
            >
              Clear
            </button>
          </div>
        </div>
      </header>

      {/* Filter and Sort bar */}
      <div style={{ padding: '10px 14px', display: 'flex', gap: 8, borderBottom: '1px solid var(--ssense-border)', background: 'var(--ssense-bg-surface)' }}>
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by domain…"
          style={{
            flex: 1,
            background: 'var(--ssense-bg-elevated)',
            border: '1px solid var(--ssense-border)',
            borderRadius: 8,
            color: 'var(--ssense-text-primary)',
            fontSize: 12,
            padding: '6px 10px',
            outline: 'none',
          }}
        />
        <select
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as SortKey)}
          style={{
            background: 'var(--ssense-bg-elevated)',
            border: '1px solid var(--ssense-border)',
            borderRadius: 8,
            color: 'var(--ssense-text-primary)',
            fontSize: 11.5,
            padding: '6px 8px',
            outline: 'none',
            cursor: 'pointer',
          }}
        >
          <option value="recent">Most recent</option>
          <option value="violations">Most violations</option>
          <option value="score">Lowest score (risk)</option>
          <option value="time">Most time spent</option>
        </select>
      </div>

      {/* Audit TTL explanation hint */}
      <div style={{ margin: '8px 14px 0', padding: '7px 10px', borderRadius: 8, background: 'var(--ssense-bg-elevated)', border: '1px solid var(--ssense-border)', fontSize: 10.5, color: 'var(--ssense-text-muted)', lineHeight: 1.45 }}>
        Audits are preserved for {AUDIT_TTL_DAYS} days before automatically re-auditing on your next visit. Click any card below to view detailed violations.
      </div>

      {/* Site Cards List */}
      <div className="ssense-scroll" style={{ flex: 1, overflowY: 'auto', padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {loading && (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--ssense-text-muted)', fontSize: 12 }}>
            Loading audit history…
          </div>
        )}

        {!loading && visible.length === 0 && (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--ssense-text-muted)', fontSize: 12 }}>
            {entries.length === 0
              ? 'No sites tracked yet. Browse normally — Ssense records visits and audits automatically.'
              : 'No sites match this filter query.'}
          </div>
        )}

        {visible.map((entry) => {
          const isExpanded = expandedDomains.has(entry.domain);
          const report = entry.lastReport;
          const violationCount = report?.violations.length ?? 0;
          const score = entry.lastScore;
          const color = scoreColor(score);
          const fresh = auditFreshness(entry.lastAuditAt);

          return (
            <div
              key={entry.domain}
              className="ssense-animate-in"
              style={{
                background: 'var(--ssense-bg-surface)',
                border: `1px solid ${isExpanded ? 'var(--ssense-border-strong)' : 'var(--ssense-border)'}`,
                borderRadius: 12,
                overflow: 'hidden',
                transition: 'border-color 0.2s, box-shadow 0.2s',
                boxShadow: isExpanded ? 'var(--ssense-shadow-ambient)' : 'none',
              }}
            >
              {/* Collapsed Header / Trigger */}
              <div
                onClick={() => toggleExpand(entry.domain)}
                style={{
                  padding: '12px 14px',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                  userSelect: 'none',
                }}
              >
                {/* Top Row: Domain & Score with Sparkline */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--ssense-text-primary)' }}>
                      {entry.domain}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                    <Sparkline points={entry.scoreHistory} />
                    <div
                      style={{
                        fontSize: 14,
                        fontWeight: 800,
                        fontFamily: "'JetBrains Mono', monospace",
                        color,
                        minWidth: 28,
                        textAlign: 'right',
                      }}
                      title={score !== null ? `DPDP Trust Score: ${score}/100` : 'Not yet audited'}
                    >
                      {score !== null ? score : '—'}
                    </div>
                    {/* Chevron Indicator */}
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      style={{
                        transform: isExpanded ? 'rotate(180deg)' : 'none',
                        transition: 'transform 0.2s ease',
                        color: 'var(--ssense-text-muted)',
                      }}
                    >
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </div>
                </div>

                {/* Sub Row: Meta stats & Violation badge pill */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <div style={{ fontSize: 11, color: 'var(--ssense-text-muted)' }}>
                    {formatRelativeTime(entry.lastVisit)} · {entry.visitCount} visit{entry.visitCount === 1 ? '' : 's'} · {formatDuration(entry.totalTimeMs)}
                  </div>

                  <div>
                    {score === null ? (
                      <span style={{ fontSize: 9.5, fontWeight: 600, color: 'var(--ssense-text-muted)', background: 'var(--ssense-bg-elevated)', padding: '2px 7px', borderRadius: 10, border: '1px solid var(--ssense-border)' }}>
                        Not Audited
                      </span>
                    ) : violationCount > 0 ? (
                      <span style={{ fontSize: 9.5, fontWeight: 700, color: 'var(--ssense-accent-rose)', background: 'rgba(244,63,94,0.12)', border: '1px solid rgba(244,63,94,0.25)', padding: '2px 7px', borderRadius: 10 }}>
                        ⚠️ {violationCount} Violation{violationCount > 1 ? 's' : ''}
                      </span>
                    ) : (
                      <span style={{ fontSize: 9.5, fontWeight: 700, color: 'var(--ssense-accent-emerald)', background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.25)', padding: '2px 7px', borderRadius: 10 }}>
                        ✓ Compliant
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Expanded Card Body */}
              {isExpanded && (
                <div
                  style={{
                    padding: '12px 14px',
                    borderTop: '1px solid var(--ssense-border)',
                    background: 'var(--ssense-bg-elevated)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 12,
                  }}
                  className="ssense-animate-in"
                >
                  {/* Scores overview */}
                  {report && (
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        background: 'var(--ssense-bg-surface)',
                        padding: '8px 12px',
                        borderRadius: 8,
                        border: '1px solid var(--ssense-border)',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 9.5, color: 'var(--ssense-text-muted)', textTransform: 'uppercase', letterSpacing: '.04em' }}>Trust Score</div>
                        <div style={{ fontSize: 16, fontWeight: 800, color: scoreColor(report.dpdp_trust_score), lineHeight: 1.2 }}>
                          {report.dpdp_trust_score}<span style={{ fontSize: 11, fontWeight: 500, color: 'var(--ssense-text-muted)' }}>/100</span>
                        </div>
                      </div>

                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: 9.5, color: 'var(--ssense-text-muted)', textTransform: 'uppercase', letterSpacing: '.04em' }}>Subtlety / Obfuscation</div>
                        <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--ssense-accent-violet)', lineHeight: 1.2 }}>
                          {report.subtlety_score}<span style={{ fontSize: 11, fontWeight: 500, color: 'var(--ssense-text-muted)' }}>/100</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Global Legal Reasoning */}
                  {report?.global_legal_reasoning ? (
                    <div
                      style={{
                        background: 'rgba(6,182,212,0.04)',
                        border: '1px solid rgba(6,182,212,0.15)',
                        borderRadius: 8,
                        padding: '10px 12px',
                        fontSize: 11.5,
                        lineHeight: 1.55,
                        color: 'var(--ssense-text-secondary)',
                        fontStyle: 'italic',
                      }}
                    >
                      "{report.global_legal_reasoning}"
                    </div>
                  ) : score === null ? (
                    <div style={{ fontSize: 11, color: 'var(--ssense-text-muted)', fontStyle: 'italic' }}>
                      No policy audit recorded for this site yet. Visit this site to trigger an automatic scan.
                    </div>
                  ) : null}

                  {/* Violations Section */}
                  {report && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ssense-text-primary)', display: 'flex', justifyContent: 'space-between' }}>
                        <span>Detected Violations</span>
                        <span style={{ fontSize: 10, color: 'var(--ssense-text-muted)', fontWeight: 500 }}>
                          {violationCount} item{violationCount === 1 ? '' : 's'}
                        </span>
                      </div>

                      {violationCount === 0 ? (
                        <div
                          style={{
                            padding: '10px 12px',
                            background: 'rgba(16,185,129,0.06)',
                            border: '1px solid rgba(16,185,129,0.2)',
                            borderRadius: 8,
                            fontSize: 11,
                            color: 'var(--ssense-accent-emerald)',
                            fontWeight: 500,
                          }}
                        >
                          ✅ DPDP Act 2023 compliant. No unlawful tracking or consent violations detected.
                        </div>
                      ) : (
                        report.violations.map((v, i) => (
                          <div
                            key={i}
                            style={{
                              background: 'var(--ssense-bg-surface)',
                              border: '1px solid var(--ssense-border)',
                              borderRadius: 8,
                              padding: 10,
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 6,
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                              <span
                                style={{
                                  background: 'rgba(244,63,94,0.12)',
                                  color: 'var(--ssense-accent-rose)',
                                  fontSize: 9.5,
                                  fontWeight: 700,
                                  padding: '2px 6px',
                                  borderRadius: 5,
                                  textTransform: 'uppercase',
                                  letterSpacing: '.04em',
                                }}
                              >
                                {v.violation_type.replace(/_/g, ' ')}
                              </span>
                              <span style={{ fontSize: 10, color: 'var(--ssense-text-muted)' }}>
                                {v.network_action.replace(/_/g, ' ')}
                              </span>
                            </div>

                            <div style={{ fontSize: 10.5, color: 'var(--ssense-text-muted)' }}>
                              <strong style={{ color: 'var(--ssense-text-secondary)' }}>Statute:</strong>{' '}
                              <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{v.statute_reference}</span>
                            </div>

                            {v.evidence_quote && (
                              <blockquote
                                style={{
                                  margin: 0,
                                  padding: '6px 9px',
                                  borderLeft: '2px solid var(--ssense-accent-rose)',
                                  background: 'rgba(244,63,94,0.04)',
                                  borderRadius: '0 6px 6px 0',
                                  fontSize: 11,
                                  lineHeight: 1.5,
                                  fontStyle: 'italic',
                                  color: 'var(--ssense-text-secondary)',
                                }}
                              >
                                "{v.evidence_quote}"
                              </blockquote>
                            )}

                            {v.offending_entities?.length > 0 && (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 2 }}>
                                {v.offending_entities.map((e, j) => (
                                  <span
                                    key={j}
                                    style={{
                                      fontSize: 9.5,
                                      fontFamily: "'JetBrains Mono', monospace",
                                      padding: '1px 5px',
                                      borderRadius: 4,
                                      background: 'var(--ssense-bg-elevated)',
                                      color: 'var(--ssense-text-secondary)',
                                      border: '1px solid var(--ssense-border)',
                                    }}
                                  >
                                    {e}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  )}

                  {/* Audit Freshness & Action buttons */}
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: 8,
                      paddingTop: 4,
                      borderTop: '1px solid var(--ssense-border)',
                      flexWrap: 'wrap',
                    }}
                  >
                    <div style={{ fontSize: 10, color: 'var(--ssense-text-muted)' }}>
                      {entry.lastAuditAt ? (
                        <>
                          <span>Audited {new Date(entry.lastAuditAt).toLocaleDateString()}</span>
                          {fresh && (
                            <span style={{ marginLeft: 6, fontWeight: 600, color: fresh.stale ? 'var(--ssense-accent-amber)' : 'var(--ssense-accent-emerald)' }}>
                              · {fresh.label}
                            </span>
                          )}
                        </>
                      ) : (
                        'No audit on file'
                      )}
                    </div>

                    {onOpenPrivacy && (
                      <button
                        onClick={() => onOpenPrivacy(entry.domain)}
                        style={{
                          background: 'var(--ssense-bg-surface)',
                          border: '1px solid var(--ssense-border-strong)',
                          color: 'var(--ssense-accent-cyan)',
                          fontSize: 10.5,
                          fontWeight: 600,
                          padding: '4px 8px',
                          borderRadius: 6,
                          cursor: 'pointer',
                        }}
                      >
                        View live report ↗
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
