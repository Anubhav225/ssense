// apps/extension/src/sidebar/components/PrivacyView.tsx
//
// Shows the full structured audit report from the local cache.

import React, { useState, useEffect } from 'react';
import type { LocalAuditEntry } from '../../background/audit-cache';
import { ScoreRing, ViolationGroups, Collapsible, Icon } from '../../ui/components';
import { highlightOnPage } from '../../ui/hooks';

export const AuditReportView: React.FC<{ domain: string; onBack: () => void }> = ({ domain, onBack }) => {
  const [entry, setEntry] = useState<LocalAuditEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!domain) return;
    setLoading(true); setError(''); setEntry(null);
    chrome.runtime.sendMessage({ type: 'GET_LOCAL_AUDIT', domain })
      .then(r => {
        if (r?.success && r.entry) setEntry(r.entry);
        else setError('No audit on file for this site yet. Click Audit to run one.');
      })
      .catch(e => setError(e?.message || 'Could not load audit.'))
      .finally(() => setLoading(false));
  }, [domain]);

  const backButton = (
    <button onClick={onBack} className="sx-icon-btn" style={{ alignSelf: 'flex-start' }} title="Back" aria-label="Back">
      <Icon name="arrowLeft" size={18} />
    </button>
  );

  if (loading) return <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>{backButton}<div className="sx-muted">Loading…</div></div>;
  if (error) return <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>{backButton}<div className="sx-muted">{error}</div></div>;
  if (!entry) return <div style={{ padding: 20 }}>{backButton}</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '16px 20px 10px', display: 'flex', alignItems: 'center', gap: 12, borderBottom: '1px solid var(--ssense-border)' }}>
        {backButton}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="sx-display" style={{ fontSize: 18, lineHeight: 1.1 }}>Audit Report</div>
          <div className="sx-muted sx-trunc" style={{ fontSize: 12 }}>{entry.domain}</div>
        </div>
      </div>

      <div className="ssense-scroll" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 20, overflowY: 'auto', flex: 1 }}>
        {/* Scores */}
        <div style={{ display: 'flex', gap: 20, alignItems: 'center', background: 'var(--ssense-bg-surface)', padding: 16, borderRadius: 12, border: '1px solid var(--ssense-border)' }}>
          <ScoreRing score={entry.trust_score} size={64} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 650, color: 'var(--ssense-text-primary)' }}>DPDP Trust Score</div>
            <div style={{ fontSize: 11.5, color: 'var(--ssense-text-secondary)', marginTop: 4 }}>
              Subtlety Score: <strong style={{ color: 'var(--ssense-accent-violet)' }}>{entry.subtlety_score}/100</strong>
            </div>
            {entry.previous_trust_score != null && (
              <div style={{ fontSize: 11.5, color: 'var(--ssense-text-muted)', marginTop: 2 }}>
                Previous score: {entry.previous_trust_score}
              </div>
            )}
          </div>
        </div>

        {/* Timeline / Basic Info */}
        <div style={{ background: 'var(--ssense-bg-elevated)', padding: 14, borderRadius: 12, display: 'grid', gap: 10 }}>
          <div className="sx-eyebrow">Audit Timeline & Info</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px 24px' }}>
            <div className="sx-kv"><span className="sx-eyebrow" style={{ fontSize: 9.5 }}>Audited At</span><b>{new Date(entry.audited_at).toLocaleString()}</b></div>
            <div className="sx-kv"><span className="sx-eyebrow" style={{ fontSize: 9.5 }}>Source</span><b>{entry.source}</b></div>
            <div className="sx-kv"><span className="sx-eyebrow" style={{ fontSize: 9.5 }}>Age</span><b>{entry.age_days > 0 ? `${entry.age_days} days` : 'Fresh'}</b></div>
          </div>
          {entry.policy_url && (
            <div style={{ marginTop: 4 }}>
              <a href={entry.policy_url} target="_blank" rel="noreferrer" style={{ color: 'var(--ssense-accent-cyan)', fontSize: 11.5, textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <Icon name="external" size={12} /> View Privacy Policy Source
              </a>
            </div>
          )}
        </div>

        {/* Legal Reasoning */}
        {entry.global_legal_reasoning && (
          <Collapsible open={true} onToggle={() => {}} className="sx-card" style={{ background: 'var(--ssense-bg-surface)' }} headClassName=""
            header={<span style={{ padding: '9px 10px', fontSize: 13, fontWeight: 650, flex: 1 }}>Legal Reasoning</span>}>
            <p style={{ margin: 0, padding: '0 12px 12px', fontSize: 12.5, lineHeight: 1.6, color: 'var(--ssense-text-secondary)', fontStyle: 'italic' }}>
              {entry.global_legal_reasoning}
            </p>
          </Collapsible>
        )}

        {/* Explainability (XAI) */}
        {entry.explainability && entry.explainability.features && entry.explainability.features.length > 0 && (
          <Collapsible open={true} onToggle={() => {}} className="sx-card" style={{ background: 'var(--ssense-bg-surface)' }} headClassName=""
            header={<span style={{ padding: '9px 10px', fontSize: 13, fontWeight: 650, flex: 1, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Icon name="sparkle" size={14} style={{ color: 'var(--ssense-accent-violet)' }} /> Explainable AI ({entry.explainability.method})
            </span>}>
            <div style={{ padding: '0 12px 12px' }}>
              <div style={{ display: 'grid', gap: 10 }}>
                {entry.explainability.features.map((f, i) => (
                  <div key={i} style={{ background: 'rgba(255,255,255,0.03)', padding: 10, borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: f.evidence ? 6 : 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ssense-text-primary)' }}>{f.feature}</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: typeof f.shap_value === 'number' ? (f.shap_value > 0 ? 'var(--ssense-accent-red)' : 'var(--ssense-accent-green)') : 'var(--ssense-text-primary)' }}>
                        {typeof f.shap_value === 'number' ? (f.shap_value > 0 ? '+' : '') + f.shap_value.toFixed(2) : f.shap_value}
                      </div>
                    </div>
                    {f.evidence && (
                      <div style={{ fontSize: 11.5, color: 'var(--ssense-text-secondary)', fontStyle: 'italic', paddingLeft: 8, borderLeft: '2px solid var(--ssense-border)' }}>
                        "{f.evidence}"
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </Collapsible>
        )}

        {/* Violations */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <div className="sx-eyebrow" style={{ fontSize: 12 }}>Violations · {entry.violation_count}</div>
          </div>
          <ViolationGroups violations={entry.violations} onHighlight={highlightOnPage} defaultOpenHigh={true} />
        </div>
      </div>
    </div>
  );
};

export default AuditReportView;
