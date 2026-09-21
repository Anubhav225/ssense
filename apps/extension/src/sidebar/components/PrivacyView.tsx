// apps/extension/src/sidebar/components/PrivacyView.tsx
//
// Renamed from "Privacy" to "Report" view.  Now shows the full structured
// audit report from the local cache — no policy text is stored or displayed.
// Policy text is fetched, used server-side, and discarded.

import React, { useState, useEffect } from 'react';
import type { LocalAuditEntry } from '../../background/audit-cache';

const linkStyle: React.CSSProperties = { color:'var(--ssense-accent-cyan)', fontSize:11, wordBreak:'break-all' };
const muted: React.CSSProperties = { color:'var(--ssense-text-muted)', fontSize:11 };
const card: React.CSSProperties = { background:'var(--ssense-bg-surface)', border:'1px solid var(--ssense-border)', borderRadius:10, padding:12, display:'flex', flexDirection:'column', gap:8 };

const SCORE_COLOR = (s:number) => s>=80?'var(--ssense-accent-emerald)':s>=50?'var(--ssense-accent-amber)':'var(--ssense-accent-rose)';

export const AuditReportView: React.FC<{ domain: string; onBack: () => void }> = ({ domain, onBack }) => {
  const [entry, setEntry] = useState<LocalAuditEntry|null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState('');

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
    <button
      onClick={onBack}
      style={{ background: 'none', border: 'none', color: 'var(--ssense-text-secondary)', cursor: 'pointer', fontSize: 16, padding: '2px 4px', alignSelf: 'flex-start' }}
      title="Back"
    >
      ←
    </button>
  );

  if (loading) return <div style={{ padding:20, display:'flex', flexDirection:'column', gap:12 }}>{backButton}<div style={{ color:'var(--ssense-text-muted)', fontSize:12 }}>Loading…</div></div>;
  if (error)   return <div style={{ padding:20, display:'flex', flexDirection:'column', gap:12 }}>{backButton}<div style={{ color:'var(--ssense-text-muted)', fontSize:12 }}>{error}</div></div>;
  if (!entry)  return <div style={{ padding:20 }}>{backButton}</div>;

  const color = SCORE_COLOR(entry.trust_score);

  return (
    <div style={{ padding:'16px 20px', display:'flex', flexDirection:'column', gap:14, overflowY:'auto', flex:1 }}
         className="ssense-scroll">

      {backButton}

      {/* Score header */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        <div>
          <div style={{ fontSize:10, color:'var(--ssense-text-muted)', marginBottom:2 }}>DPDP Trust Score</div>
          <div style={{ fontSize:28, fontWeight:800, color, lineHeight:1 }}>{entry.trust_score}<span style={{ fontSize:14, fontWeight:500, color:'var(--ssense-text-muted)', marginLeft:2 }}>/100</span></div>
        </div>
        <div style={{ textAlign:'right' }}>
          <div style={{ fontSize:10, color:'var(--ssense-text-muted)', marginBottom:2 }}>Subtlety Score</div>
          <div style={{ fontSize:28, fontWeight:800, color:'var(--ssense-accent-violet)', lineHeight:1 }}>{entry.subtlety_score}<span style={{ fontSize:14, fontWeight:500, color:'var(--ssense-text-muted)', marginLeft:2 }}>/100</span></div>
        </div>
      </div>

      {/* Meta row */}
      <div style={{ fontSize:10, color:'var(--ssense-text-muted)', display:'flex', flexWrap:'wrap', gap:'6px 16px' }}>
        <span>Audited: {new Date(entry.audited_at).toLocaleString()}</span>
        <span>Source: {entry.source}</span>
        {entry.age_days > 0 && <span>{entry.age_days}d old</span>}
        {entry.policy_url && (
          <a href={entry.policy_url} target="_blank" rel="noreferrer" style={linkStyle}>
            Policy Source ↗
          </a>
        )}
      </div>

      {/* Legal reasoning */}
      {entry.global_legal_reasoning && (
        <div style={{ background:'rgba(6,182,212,0.04)', border:'1px solid rgba(6,182,212,0.12)', borderRadius:8, padding:10, fontSize:12, lineHeight:1.6, color:'var(--ssense-text-secondary)', fontStyle:'italic' }}>
          {entry.global_legal_reasoning}
        </div>
      )}

      {/* Violations */}
      <div style={{ fontSize:12, fontWeight:700, color:'var(--ssense-text-primary)' }}>
        {entry.violation_count === 0 ? '✅ No violations found' : `⚠️ ${entry.violation_count} Violation${entry.violation_count!==1?'s':''}`}
      </div>

      {entry.violations.map((v, i) => (
        <div key={i} style={card}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:8 }}>
            <span style={{ background:'rgba(244,63,94,0.1)', color:'var(--ssense-accent-rose)', fontSize:10, fontWeight:700, padding:'3px 7px', borderRadius:6, textTransform:'uppercase', letterSpacing:'.04em', flexShrink:0 }}>
              {v.violation_type.replace(/_/g,' ')}
            </span>
            <span style={{ ...muted, fontSize:10, textAlign:'right' }}>{v.network_action.replace(/_/g,' ')}</span>
          </div>

          <div style={{ fontSize:11, color:'var(--ssense-text-muted)' }}>
            <strong style={{ color:'var(--ssense-text-secondary)' }}>Ref:</strong> {v.statute_reference}
          </div>

          {v.evidence_quote && (
            <blockquote style={{ margin:0, padding:'6px 10px', borderLeft:'2px solid var(--ssense-accent-rose)', background:'rgba(244,63,94,0.04)', borderRadius:'0 6px 6px 0', fontSize:11.5, lineHeight:1.55, fontStyle:'italic', color:'var(--ssense-text-secondary)' }}>
              "{v.evidence_quote}"
            </blockquote>
          )}

          {v.offending_entities?.length > 0 && (
            <div style={{ display:'flex', flexWrap:'wrap', gap:5 }}>
              {v.offending_entities.map((e,j) => (
                <span key={j} style={{ fontSize:10, fontFamily:'monospace', padding:'2px 6px', borderRadius:4, background:'var(--ssense-bg-elevated)', color:'var(--ssense-text-secondary)', border:'1px solid var(--ssense-border)' }}>{e}</span>
              ))}
            </div>
          )}
        </div>
      ))}

      {entry.violation_count === 0 && (
        <div style={{ textAlign:'center', padding:'24px 0', color:'var(--ssense-text-muted)', fontSize:12 }}>
          This site's policy appears compliant with DPDP Act 2023 based on the audited text.
        </div>
      )}
    </div>
  );
};

// Keep legacy export name so App.tsx doesn't need updating
export default AuditReportView;
