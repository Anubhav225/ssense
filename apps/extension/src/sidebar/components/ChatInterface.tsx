// apps/extension/src/sidebar/components/ChatInterface.tsx

import React, { useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react';
import type { AuditReport, RateLimitInfo } from '../../types/server-protocol';

function formatDuration(ms: number): string {
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

// ═══════════════════════════════════════════════════════════════
// DESIGN SYSTEM
// ═══════════════════════════════════════════════════════════════
export const DESIGN_SYSTEM_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  :root {
    --ssense-bg-deep: #09090B;
    --ssense-bg-surface: #18181B;
    --ssense-bg-elevated: #27272A;
    --ssense-border: rgba(255,255,255,0.06);
    --ssense-text-primary: #FAFAFA;
    --ssense-text-secondary: #A1A1AA;
    --ssense-text-muted: #71717A;
    --ssense-accent-cyan: #06B6D4;
    --ssense-accent-violet: #8B5CF6;
    --ssense-accent-emerald: #10B981;
    --ssense-accent-rose: #F43F5E;
    --ssense-accent-amber: #F59E0B;
    --ssense-gradient-ai: linear-gradient(135deg, var(--ssense-accent-cyan) 0%, var(--ssense-accent-violet) 100%);
    --ssense-glass: rgba(255,255,255,0.02);
  }

  .ssense-root { font-family:'Inter',sans-serif; background:var(--ssense-bg-deep); color:var(--ssense-text-primary); height:100vh; width:100%; display:flex; flex-direction:column; overflow:hidden; position:relative; -webkit-font-smoothing:antialiased; }
  .ssense-scroll::-webkit-scrollbar { width:6px; } .ssense-scroll::-webkit-scrollbar-track { background:transparent; } .ssense-scroll::-webkit-scrollbar-thumb { background:rgba(255,255,255,0.08); border-radius:3px; }
  @keyframes ssense-fade-in-up { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
  @keyframes ssense-pulse { 0%,100%{opacity:.4;transform:scale(.8)} 50%{opacity:1;transform:scale(1.2)} }
  .ssense-animate-in { animation:ssense-fade-in-up 0.3s cubic-bezier(0.16,1,0.3,1) forwards; }
  .ssense-gradient-text { background:var(--ssense-gradient-ai); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
  .ssense-thinking-dot { width:5px; height:5px; border-radius:50%; background:var(--ssense-accent-cyan); animation:ssense-pulse 1.4s infinite ease-in-out; }

  .ssense-header { padding:12px 16px 0; display:flex; flex-direction:column; gap:10px; border-bottom:1px solid var(--ssense-border); z-index:10; position:relative; background:rgba(9,9,11,0.8); backdrop-filter:blur(12px); }
  .ssense-header-top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
  .ssense-header-left { display:flex; align-items:center; gap:12px; flex:1; min-width:0; }
  .ssense-header-icon { width:32px; height:32px; border-radius:8px; flex-shrink:0; background:var(--ssense-gradient-ai); display:flex; align-items:center; justify-content:center; }
  .ssense-header-info { flex:1; min-width:0; }
  .ssense-domain { font-size:13px; font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .ssense-badge { display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:12px; background:rgba(255,255,255,0.05); margin-top:4px; }
  .ssense-badge-dot { width:6px; height:6px; border-radius:50%; }

  .ssense-toolbar { display:flex; flex-wrap:wrap; align-items:center; gap:6px; padding-bottom:10px; }
  .ssense-toolbar-btn { display:inline-flex; align-items:center; gap:5px; background:rgba(255,255,255,0.05); border:1px solid var(--ssense-border); color:var(--ssense-text-secondary); font-size:11px; font-weight:500; padding:5px 9px; border-radius:7px; cursor:pointer; transition:background .15s,color .15s,border-color .15s; white-space:nowrap; flex-shrink:0; }
  .ssense-toolbar-btn:hover { background:rgba(255,255,255,0.09); color:var(--ssense-text-primary); border-color:rgba(255,255,255,0.14); }
  .ssense-toolbar-btn:disabled { opacity:.4; cursor:default; }
  .ssense-toolbar-btn--active { background:rgba(6,182,212,0.16); color:var(--ssense-accent-cyan); border-color:rgba(6,182,212,0.35); }
  .ssense-toolbar-spacer { flex:1 1 auto; min-width:4px; }

  .ssense-audit-card { margin:16px 20px 0; border:1px solid var(--ssense-border); border-radius:12px; background:var(--ssense-glass); overflow:hidden; flex-shrink:0; z-index:10; position:relative; }
  .ssense-audit-header { padding:12px 16px; display:flex; align-items:center; justify-content:space-between; cursor:pointer; user-select:none; }
  .ssense-audit-header:hover { background:rgba(255,255,255,0.02); }
  .ssense-audit-body { padding:0 16px 16px; border-top:1px solid var(--ssense-border); animation:ssense-fade-in-up .2s ease; display:flex; flex-direction:column; gap:12px; max-height:40vh; overflow-y:auto; }
  .ssense-audit-body::-webkit-scrollbar { width:4px; } .ssense-audit-body::-webkit-scrollbar-thumb { background:rgba(255,255,255,0.1); border-radius:2px; }
  .ssense-audit-reasoning { font-size:12px; line-height:1.5; color:var(--ssense-text-secondary); margin:12px 0 0; font-style:italic; }

  .ssense-violation-card { background:var(--ssense-bg-surface); border:1px solid var(--ssense-border); border-radius:10px; padding:12px; display:flex; flex-direction:column; gap:8px; }
  .ssense-violation-top { display:flex; justify-content:space-between; align-items:center; }
  .ssense-violation-type { color:var(--ssense-accent-rose); font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.05em; padding:4px 8px; background:rgba(244,63,94,0.1); border-radius:6px; }
  .ssense-violation-action { color:var(--ssense-text-secondary); font-size:11px; font-weight:600; }
  .ssense-evidence { margin:0; padding:8px 12px; border-left:2px solid var(--ssense-accent-rose); background:rgba(244,63,94,0.04); border-radius:0 6px 6px 0; font-size:11.5px; line-height:1.5; font-style:italic; cursor:pointer; }
  .ssense-entities-list { display:flex; flex-wrap:wrap; gap:6px; margin-top:4px; }
  .ssense-entity-tag { font-size:10px; font-family:'JetBrains Mono',monospace; padding:2px 6px; border-radius:4px; background:var(--ssense-bg-elevated); color:var(--ssense-text-secondary); border:1px solid var(--ssense-border); }

  .ssense-stream { flex:1; overflow-y:auto; padding:24px 20px; display:flex; flex-direction:column; gap:24px; z-index:10; position:relative; }
  .ssense-empty-state { text-align:center; margin-top:15%; opacity:.9; }
  .ssense-quick-prompts { display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin-top:24px; }
  .ssense-quick-prompt { padding:8px 14px; border-radius:8px; font-size:12px; font-weight:500; color:var(--ssense-text-secondary); cursor:pointer; transition:all .2s; white-space:nowrap; border:1px solid var(--ssense-border); background:transparent; font-family:inherit; }
  .ssense-quick-prompt:hover { border-color:var(--ssense-accent-cyan); color:var(--ssense-text-primary); background:rgba(6,182,212,0.05); }

  .ssense-msg { display:flex; max-width:100%; }
  .ssense-msg-user { justify-content:flex-end; }
  .ssense-msg-bubble { padding:10px 16px; font-size:13.5px; line-height:1.6; max-width:85%; white-space:pre-wrap; word-break:break-word; }
  .ssense-msg-bubble.user { border-radius:16px 16px 4px 16px; background:var(--ssense-bg-elevated); }
  .ssense-msg-bubble.ai { border-radius:16px 16px 16px 4px; background:var(--ssense-glass); border:1px solid var(--ssense-border); }
  .ssense-msg-header { display:flex; align-items:center; gap:6px; margin-bottom:10px; font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:.05em; }
  .ssense-msg-header-dot { width:4px; height:4px; border-radius:50%; background:var(--ssense-accent-cyan); }
  .ssense-inline-code { background:rgba(255,255,255,.08); padding:2px 6px; border-radius:4px; font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--ssense-accent-cyan); }

  .ssense-input-dock { padding:16px 20px 24px; border-top:1px solid var(--ssense-border); z-index:10; position:relative; background:rgba(9,9,11,0.9); backdrop-filter:blur(12px); }
  .ssense-input-container { display:flex; align-items:center; padding:4px 4px 4px 20px; border-radius:16px; border:1px solid var(--ssense-border); background:var(--ssense-bg-surface); transition:border-color .2s,box-shadow .2s; }
  .ssense-input-container:focus-within { border-color:rgba(6,182,212,0.5); box-shadow:0 0 0 2px rgba(6,182,212,0.15); }
  .ssense-input-field { flex:1; background:transparent; border:none; outline:none; color:var(--ssense-text-primary); font-family:inherit; font-size:14px; padding:12px 0; }
  .ssense-input-field::placeholder { color:var(--ssense-text-muted); }
  .ssense-send-btn { width:36px; height:36px; border-radius:12px; border:none; flex-shrink:0; background:transparent; color:var(--ssense-text-muted); cursor:not-allowed; display:flex; align-items:center; justify-content:center; transition:all .2s; transform:scale(0.9); }
  .ssense-send-btn.active { background:var(--ssense-gradient-ai); color:#fff; cursor:pointer; transform:scale(1); }

  .ssense-service-banner { border-bottom:1px solid rgba(244,63,94,0.3); padding:10px 20px; display:flex; align-items:center; gap:10px; color:var(--ssense-accent-rose); font-size:12px; font-weight:500; z-index:20; background:rgba(244,63,94,0.07); }

  .ssense-shield-panel { border-bottom:1px solid var(--ssense-border); padding:12px 16px; font-size:11px; display:flex; flex-direction:column; gap:8px; background:var(--ssense-bg-surface); z-index:10; }
  .ssense-shield-row { display:flex; justify-content:space-between; align-items:center; cursor:pointer; color:var(--ssense-text-secondary); }
  .ssense-branding { text-align:center; margin-top:12px; font-size:10px; color:var(--ssense-text-muted); letter-spacing:.03em; }

  /* Regular / Thinking segmented control — a clear two-state switch rather
     than a single toggle button, so both modes are always visible and the
     active one is unambiguous at a glance. */
  .ssense-mode-switch { display:inline-flex; align-items:center; background:rgba(255,255,255,0.04); border:1px solid var(--ssense-border); border-radius:9px; padding:2px; gap:2px; flex-shrink:0; }
  .ssense-mode-option { display:inline-flex; align-items:center; gap:4px; border:none; background:transparent; color:var(--ssense-text-muted); font-size:10.5px; font-weight:600; padding:5px 9px; border-radius:7px; cursor:pointer; transition:background .15s,color .15s; white-space:nowrap; }
  .ssense-mode-option:hover { color:var(--ssense-text-secondary); }
  .ssense-mode-option--active { background:var(--ssense-bg-elevated); color:var(--ssense-text-primary); box-shadow:0 1px 2px rgba(0,0,0,0.3); }
  .ssense-mode-option--active.ssense-mode-thinking { color:var(--ssense-accent-violet); }
  .ssense-mode-option--active.ssense-mode-concise { color:var(--ssense-accent-cyan); }

  /* Chat quota chip — subtle by default, warns as it runs low. Never shown
     for audits, which are unlimited. */
  .ssense-quota-chip { font-size:9.5px; font-weight:600; color:var(--ssense-text-muted); padding:3px 8px; border-radius:10px; background:rgba(255,255,255,0.03); border:1px solid var(--ssense-border); white-space:nowrap; }
  .ssense-quota-chip--low { color:var(--ssense-accent-amber); background:rgba(245,158,11,0.08); border-color:rgba(245,158,11,0.25); }

  .ssense-cooldown-banner { margin:12px 20px 0; padding:12px 14px; border-radius:10px; border:1px solid rgba(245,158,11,0.25); background:rgba(245,158,11,0.06); display:flex; flex-direction:column; gap:4px; }
  .ssense-cooldown-title { display:flex; align-items:center; gap:8px; font-size:12px; font-weight:600; color:var(--ssense-accent-amber); }
  .ssense-cooldown-sub { font-size:11px; color:var(--ssense-text-secondary); line-height:1.5; }
`;

// ─── Markdown tokenizer (CSP-safe, no dangerouslySetInnerHTML) ───────────────
const parseMarkdown = (text: string): React.ReactNode[] =>
  text.split(/(`.*?`|\*\*.*?\*\*|\*.*?\*|\n)/g).map((part, i) => {
    if (part === '\n') return <br key={i} />;
    if (part.startsWith('`') && part.endsWith('`')) return <code key={i} className="ssense-inline-code">{part.slice(1,-1)}</code>;
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={i}>{part.slice(2,-2)}</strong>;
    if (part.startsWith('*') && part.endsWith('*')) return <em key={i}>{part.slice(1,-1)}</em>;
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });

// ─── Sub-components ───────────────────────────────────────────────────────────
const ComplianceBadge = ({ score, delta }: { score: number | null; delta?: number | null }) => {
  if (score === null) return (
    <div className="ssense-badge">
      <div className="ssense-badge-dot" style={{ background: 'var(--ssense-accent-amber)', animation: 'ssense-pulse 1.5s infinite' }} />
      <span style={{ fontSize:11, fontWeight:500, color:'var(--ssense-text-secondary)' }}>Scanning</span>
    </div>
  );
  const color = score >= 80 ? 'var(--ssense-accent-emerald)' : score >= 50 ? 'var(--ssense-accent-amber)' : 'var(--ssense-accent-rose)';
  const label = score >= 80 ? 'Compliant' : score >= 50 ? 'Caution' : 'Violations';
  return (
    <div className="ssense-badge">
      <div className="ssense-badge-dot" style={{ background: color }} />
      <span style={{ fontSize:11, fontWeight:600, color }}>{score}</span>
      <span style={{ fontSize:11, fontWeight:500, color:'var(--ssense-text-muted)' }}>{label}</span>
      {typeof delta === 'number' && delta !== 0 && (
        <span style={{
          fontSize: 10,
          fontWeight: 700,
          color: delta > 0 ? 'var(--ssense-accent-emerald)' : 'var(--ssense-accent-rose)',
          background: delta > 0 ? 'rgba(16,185,129,0.12)' : 'rgba(244,63,94,0.12)',
          padding: '1px 5px',
          borderRadius: 4,
          marginLeft: 2,
        }}>
          {delta > 0 ? `+${delta}` : delta}
        </span>
      )}
    </div>
  );
};

const MessageBubble = React.memo(({ msg }: { msg: { role: 'user' | 'ai'; text: string } }) => (
  <div className={`ssense-msg ssense-animate-in ${msg.role === 'user' ? 'ssense-msg-user' : 'ssense-msg-ai'}`}>
    <div className={`ssense-msg-bubble ${msg.role}`}>
      {msg.role === 'ai' && (
        <div className="ssense-msg-header">
          <div className="ssense-msg-header-dot" />
          <span className="ssense-gradient-text">Ssense AI</span>
        </div>
      )}
      {msg.role === 'ai' ? parseMarkdown(msg.text) : msg.text}
    </div>
  </div>
));

// ═══════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════
export const ChatInterface: React.FC<{ onOpenHistory?: () => void; onOpenPrivacy?: () => void }> = ({ onOpenHistory, onOpenPrivacy }) => {
  const [domain, setDomain]               = useState<string | null>(null);
  const [isSystemPage, setIsSystemPage]   = useState(false);
  const [trustScore, setTrustScore]       = useState<number | null>(null);
  const [scoreDelta, setScoreDelta]       = useState<number | null>(null);
  const [auditReport, setAuditReport]     = useState<AuditReport | null>(null);
  const [auditError, setAuditError]       = useState('');
  const [showAuditDetails, setShowAuditDetails] = useState(false);
  const [showExplainability, setShowExplainability] = useState(false);
  const [showShield, setShowShield]       = useState(false);
  const [messages, setMessages]           = useState<{ role: 'user' | 'ai'; text: string }[]>([]);
  const [input, setInput]                 = useState('');
  const [isAuditing, setIsAuditing]       = useState(false);
  const [isChatting, setIsChatting]       = useState(false);
  const [responseMode, setResponseMode]   = useState<'concise' | 'thinking'>('concise');
  const [loadingText, setLoadingText]     = useState('Connecting to Ssense AI...');
  const [serviceAvailable, setServiceAvailable] = useState(true);
  const [serviceError, setServiceError]   = useState('');
  const [siteHistory, setSiteHistory]     = useState<any | null>(null);
  const [shieldSettings, setShieldSettings] = useState({ blockTrackers: true, spoofHardware: true, injectGPC: true });
  const [cacheSource, setCacheSource]     = useState<string>('inference');
  const [cacheAgeDays, setCacheAgeDays]   = useState<number>(0);
  const [isOffline, setIsOffline]         = useState(typeof navigator !== 'undefined' ? !navigator.onLine : false);
  const [chatQuota, setChatQuota]         = useState<RateLimitInfo | null>(null);
  const [cooldownUntil, setCooldownUntil] = useState<number | null>(null);
  const [cooldownLeft, setCooldownLeft]   = useState(0);

  const scrollRef = useRef<HTMLDivElement>(null);
  const currentDomainRef = useRef<string | null>(null);

  // ── Load persisted shield settings ──────────────────────────
  useEffect(() => {
    chrome.storage.local.get('ssense_shield_settings').then(d => {
      if (d.ssense_shield_settings) setShieldSettings(d.ssense_shield_settings);
    }).catch(() => {});
  }, []);

  const toggleShield = (key: 'blockTrackers' | 'spoofHardware' | 'injectGPC') => {
    setShieldSettings(prev => {
      const next = { ...prev, [key]: !prev[key] };
      chrome.storage.local.set({ ssense_shield_settings: next }).catch(() => {});
      return next;
    });
  };

  // ── Export report ──────────────────────────────────────────
  const exportAuditReport = () => {
    if (!auditReport || !domain) return;
    const lines = [
      `# Ssense DPDP Audit Report`,
      `**Domain:** \`${domain}\`  |  **Score:** \`${auditReport.dpdp_trust_score}/100\`  |  **Date:** \`${new Date().toISOString()}\``,
      `## Global Reasoning`,
      auditReport.global_legal_reasoning,
      `## Violations (${auditReport.violations.length})`,
      ...auditReport.violations.map((v, i) => [
        `### ${i+1}. ${v.violation_type.replace(/_/g,' ')}`,
        `- **Statute:** ${v.statute_reference}`,
        `- **Action:** \`${v.network_action}\``,
        `- **Evidence:** "${v.evidence_quote}"`,
        v.offending_entities?.length ? `- **Entities:** ${v.offending_entities.join(', ')}` : '',
      ].filter(Boolean).join('\n')),
    ];
    const blob = new Blob([lines.join('\n\n')], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement('a'), { href: url, download: `ssense_${domain.replace(/\W/g,'_')}.md` });
    a.click();
    URL.revokeObjectURL(url);
  };

  // ── Adaptive Health check (visibility-aware + 2-min backoff) ─
  useEffect(() => {
    const ping = () => {
      if (document.hidden) return; // Skip if tab/panel is hidden
      chrome.runtime.sendMessage({ type: 'HEALTH_CHECK', requestId: crypto.randomUUID() })
        .then(res => {
          const ok = Boolean(res?.success) && res?.modelLoaded !== false;
          setServiceAvailable(ok);
          setServiceError(ok ? '' : res?.error || 'AI service unavailable. Check Settings.');
        })
        .catch(err => { setServiceAvailable(false); setServiceError(err?.message || 'Cannot reach Ssense server.'); });
    };

    ping();
    const id = setInterval(ping, 120_000); // 2-min backoff: reduces health traffic by 87%

    const onVis = () => { if (!document.hidden) ping(); };
    document.addEventListener('visibilitychange', onVis);

    const onOn = () => setIsOffline(false);
    const onOff = () => setIsOffline(true);
    window.addEventListener('online', onOn);
    window.addEventListener('offline', onOff);

    return () => {
      clearInterval(id);
      document.removeEventListener('visibilitychange', onVis);
      window.removeEventListener('online', onOn);
      window.removeEventListener('offline', onOff);
    };
  }, []);

  // ── Tab tracking & History loading on domain switch ────────
  useEffect(() => {
    const handleUrl = async (url: string | undefined) => {
      if (!url?.startsWith('http')) {
        setIsSystemPage(true); setDomain(null); currentDomainRef.current = null;
        setAuditReport(null); setAuditError(''); setMessages([]);
        return;
      }
      setIsSystemPage(false);
      const newDomain = new URL(url).hostname;
      if (newDomain === currentDomainRef.current) return;
      setDomain(newDomain); currentDomainRef.current = newDomain;
      setTrustScore(null); setScoreDelta(null); setAuditReport(null); setAuditError('');
      setShowAuditDetails(false); setSiteHistory(null);

      try {
        // Load local audit with SWR metadata, site history, and chat history concurrently
        const [localAudit, hist, chatHist] = await Promise.all([
          chrome.runtime.sendMessage({ type: 'GET_LOCAL_AUDIT_WITH_META', domain: newDomain }),
          chrome.runtime.sendMessage({ type: 'GET_SITE_HISTORY', domain: newDomain }),
          chrome.runtime.sendMessage({ type: 'GET_CHAT_HISTORY', domain: newDomain }),
        ]);

        if (localAudit?.success && localAudit.entry) {
          const e = localAudit.entry;
          setTrustScore(e.trust_score);
          setAuditReport({
            dpdp_trust_score: e.trust_score,
            subtlety_score: e.subtlety_score,
            violations: e.violations,
            global_legal_reasoning: e.global_legal_reasoning,
          });
          setCacheSource(localAudit.source || e.source || 'local_cache');
          setCacheAgeDays(localAudit.ageDays || e.age_days || 0);
          setShowAuditDetails(e.violation_count > 0);
        }

        if (hist?.success && hist.entry) {
          setSiteHistory(hist.entry);
          const historyArr = hist.entry.scoreHistory || [];
          if (historyArr.length >= 2) {
            const last = historyArr[historyArr.length - 1];
            const prev = historyArr[historyArr.length - 2];
            setScoreDelta(last.score - prev.score);
          }
        }

        if (chatHist?.success && Array.isArray(chatHist.messages)) {
          setMessages(chatHist.messages.map((m: any) => ({ role: m.role, text: m.text })));
        } else {
          setMessages([]);
        }
      } catch { /* non-fatal */ }
    };

    chrome.tabs.query({ active: true, currentWindow: true }, tabs => handleUrl(tabs[0]?.url));
    const onUpdate = (_: number, ci: chrome.tabs.TabChangeInfo, tab: chrome.tabs.Tab) => {
      if (tab.active && (ci.status === 'complete' || ci.url)) handleUrl(tab.url);
    };
    const onActivate = async (info: chrome.tabs.TabActiveInfo) => handleUrl((await chrome.tabs.get(info.tabId)).url);
    const onMsg = (msg: any) => {
      if (msg.type === 'AUDIT_COMPLETE' && msg.domain === currentDomainRef.current) {
        setTrustScore(msg.score); setAuditError(''); setServiceAvailable(true); setServiceError('');
        setIsAuditing(false);
        if (msg.previousScore != null) {
          setScoreDelta(msg.score - msg.previousScore);
        }
        if (msg.source) setCacheSource(msg.source);
        if (msg.report) { setAuditReport(msg.report); setShowAuditDetails(msg.report.violations.length > 0); }
        chrome.runtime.sendMessage({ type: 'GET_SITE_HISTORY', domain: msg.domain })
          .then(r => { if (r?.success) setSiteHistory(r.entry || null); }).catch(() => {});
      }
      if (msg.type === 'AUDIT_ERROR' && msg.domain === currentDomainRef.current) {
        setAuditError(msg.error || 'Audit could not be completed.');
        setIsAuditing(false);
      }
    };
    chrome.tabs.onUpdated.addListener(onUpdate);
    chrome.tabs.onActivated.addListener(onActivate);
    chrome.runtime.onMessage.addListener(onMsg);
    return () => {
      chrome.tabs.onUpdated.removeListener(onUpdate);
      chrome.tabs.onActivated.removeListener(onActivate);
      chrome.runtime.onMessage.removeListener(onMsg);
    };
  }, []);

  useLayoutEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, isChatting]);

  useEffect(() => {
    if (!isAuditing && !isChatting) return;
    const stages = isAuditing
      ? ['Scanning page DOM...', 'Checking DPDP compliance cache...', 'Forensic legal analysis...', 'Finalizing report...']
      : ['Connecting to Ssense AI...', 'Retrieving context...', 'Reasoning over DPDP Act...', 'Generating response...'];
    let i = 0; setLoadingText(stages[0]);
    const id = setInterval(() => { i = (i+1) % stages.length; setLoadingText(stages[i]); }, 3000);
    return () => clearInterval(id);
  }, [isAuditing, isChatting]);

  // ── Cooldown countdown (chat rate limit only — audits are unaffected) ──
  useEffect(() => {
    if (!cooldownUntil) { setCooldownLeft(0); return; }
    const tick = () => {
      const left = Math.max(0, Math.ceil((cooldownUntil - Date.now()) / 1000));
      setCooldownLeft(left);
      if (left <= 0) setCooldownUntil(null);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [cooldownUntil]);

  // ── Manual audit: re-inject extractor → finds URL → server does everything ─
  const runAudit = useCallback(async (forceRefresh = false) => {
    if (!domain || isAuditing) return;
    setIsAuditing(true); setAuditError('');
    try {
      if (!forceRefresh) {
        const local = await chrome.runtime.sendMessage({ type: 'GET_LOCAL_AUDIT_WITH_META', domain });
        if (local?.success && local.entry) {
          setTrustScore(local.entry.trust_score);
          setAuditReport({
            dpdp_trust_score: local.entry.trust_score,
            subtlety_score: local.entry.subtlety_score,
            violations: local.entry.violations,
            global_legal_reasoning: local.entry.global_legal_reasoning,
          });
          setCacheSource(local.source || 'local_cache');
          setCacheAgeDays(local.ageDays || 0);
          setShowAuditDetails(local.entry.violation_count > 0);
          setIsAuditing(false);
          return;
        }
      }
      const retry = await chrome.runtime.sendMessage({ type: 'RETRY_EXTRACTION' });
      if (!retry?.success) throw new Error(retry?.error || 'Could not scan this page for a privacy policy link.');
    } catch (err: any) {
      setAuditError(err.message || 'Audit failed.');
      setIsAuditing(false);
    }
  }, [domain, isAuditing]);

  // ── Chat (Streaming relay via port with fallback) ───────────
  const handleSend = useCallback(async (text?: string) => {
    const prompt = text || input;
    if (!prompt.trim() || isChatting || !domain || isSystemPage || !serviceAvailable || cooldownLeft > 0 || isOffline) return;

    setMessages(prev => [...prev, { role: 'user', text: prompt }]);
    setInput('');
    setIsChatting(true);

    try {
      const port = chrome.runtime.connect({ name: 'ssense-chat-stream' });
      let accumulatedAiText = '';
      let messageAppended = false;

      port.onMessage.addListener((streamMsg) => {
        if (streamMsg.type === 'CHUNK') {
          accumulatedAiText += streamMsg.delta || '';
          setMessages(prev => {
            if (!messageAppended) {
              messageAppended = true;
              return [...prev, { role: 'ai', text: accumulatedAiText }];
            }
            const updated = [...prev];
            updated[updated.length - 1] = { role: 'ai', text: accumulatedAiText };
            return updated;
          });
        } else if (streamMsg.type === 'DONE') {
          if (streamMsg.rateLimit) setChatQuota(streamMsg.rateLimit);
          setIsChatting(false);
          port.disconnect();
        } else if (streamMsg.type === 'ERROR') {
          const isRateLimited = streamMsg.errorKind === 'server' && /rate limit/i.test(streamMsg.error || '');
          if (isRateLimited) {
            setCooldownUntil(Date.now() + (streamMsg.rateLimit?.windowSeconds ?? 60) * 1000);
          } else {
            setMessages(prev => [...prev, { role: 'ai', text: `⚠️ ${streamMsg.error || 'Request failed.'}` }]);
          }
          setIsChatting(false);
          port.disconnect();
        }
      });

      port.postMessage({
        type: 'START_CHAT',
        domain,
        userPrompt: prompt,
        responseMode,
        requestId: crypto.randomUUID(),
      });
    } catch {
      // Fallback to standard message passing
      try {
        const res = await chrome.runtime.sendMessage({ type: 'CHAT', domain, userPrompt: prompt, responseMode });
        if (res?.rateLimit) setChatQuota(res.rateLimit);
        if (res?.success) {
          setMessages(prev => [...prev, { role: 'ai', text: res.message }]);
        } else {
          setMessages(prev => [...prev, { role: 'ai', text: `⚠️ ${res?.error || 'Request failed.'}` }]);
        }
      } catch (err: any) {
        setMessages(prev => [...prev, { role: 'ai', text: `⚠️ ${err?.message || 'Could not reach Ssense AI.'}` }]);
      } finally {
        setIsChatting(false);
      }
    }
  }, [input, isChatting, domain, isSystemPage, serviceAvailable, responseMode, cooldownLeft, isOffline]);

  const quickPrompts = domain
    ? [`Is ${domain} selling my data?`, 'Where is my data stored?', 'Explain the data retention policy.']
    : [];

  const chevronStyle: React.CSSProperties = { transform: showAuditDetails ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' };

  return (
    <div className="ssense-root">
      {/* Background glow */}
      <div style={{ position:'absolute', top:'-30%', left:'50%', transform:'translateX(-50%)', width:'120%', height:'60%', background:`radial-gradient(circle,${trustScore !== null && trustScore < 50 ? 'rgba(244,63,94,0.06)' : 'rgba(6,182,212,0.04)'} 0%,transparent 70%)`, pointerEvents:'none', zIndex:0, filter:'blur(40px)' }} />

      {/* Service unavailable banner */}
      {!serviceAvailable && (
        <div className="ssense-service-banner">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <span>{serviceError || 'Ssense AI is unavailable. Check Settings.'}</span>
          <button onClick={() => chrome.runtime.openOptionsPage()} style={{ marginLeft:'auto', background:'transparent', border:'1px solid rgba(244,63,94,0.4)', color:'var(--ssense-accent-rose)', borderRadius:6, padding:'3px 8px', fontSize:10, cursor:'pointer', flexShrink:0 }}>Settings</button>
        </div>
      )}

      {/* Header */}
      <header className="ssense-header">
        <div className="ssense-header-top">
          <div className="ssense-header-left">
            <div className="ssense-header-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            </div>
            <div className="ssense-header-info">
              <div className="ssense-domain">{isSystemPage ? 'System Page' : (domain || 'Detecting…')}</div>
              {!isSystemPage && <ComplianceBadge score={trustScore} delta={scoreDelta} />}
            </div>
          </div>
        </div>

        <nav className="ssense-toolbar">
          <button className="ssense-toolbar-btn" onClick={onOpenHistory} title="Past audits and browsing history"><span>🕘</span><span>History</span></button>
          <button className="ssense-toolbar-btn" onClick={onOpenPrivacy} title="View retrieved privacy policy text"><span>🔎</span><span>Policy</span></button>
          <button className="ssense-toolbar-btn" onClick={() => chrome.runtime.openOptionsPage()} title="Server configuration"><span>⚙️</span><span>Settings</span></button>
          <span className="ssense-toolbar-spacer" />
          {chatQuota && (
            <span
              className={`ssense-quota-chip${chatQuota.remaining <= 15 ? ' ssense-quota-chip--low' : ''}`}
              title="Chat messages remaining this minute. Audits are never limited."
            >
              💬 {chatQuota.remaining}/{chatQuota.limit}
            </span>
          )}
          <div className="ssense-mode-switch" role="radiogroup" aria-label="Response length">
            <button
              role="radio" aria-checked={responseMode === 'concise'}
              className={`ssense-mode-option ssense-mode-concise${responseMode === 'concise' ? ' ssense-mode-option--active' : ''}`}
              onClick={() => setResponseMode('concise')}
              title="Regular: short, direct answers"
            ><span>⚡</span><span>Regular</span></button>
            <button
              role="radio" aria-checked={responseMode === 'thinking'}
              className={`ssense-mode-option ssense-mode-thinking${responseMode === 'thinking' ? ' ssense-mode-option--active' : ''}`}
              onClick={() => setResponseMode('thinking')}
              title="Thinking: the model reasons through the DPDP provisions first — slower, more thorough"
            ><span>🧠</span><span>Thinking</span></button>
          </div>
          <button
            className="ssense-toolbar-btn"
            onClick={() => runAudit(true)}
            disabled={!domain || isAuditing || isSystemPage}
            title="Run a fresh audit of this site's privacy policy — audits are never rate-limited"
          ><span>{isAuditing ? '⏳' : '📋'}</span><span>{isAuditing ? 'Auditing…' : 'Audit'}</span></button>
          <button
            className={`ssense-toolbar-btn${showShield ? ' ssense-toolbar-btn--active' : ''}`}
            onClick={() => setShowShield(v => !v)}
            title="Active protection controls"
          ><span>🛡️</span><span>Shield</span></button>
        </nav>
      </header>

      {/* Chat cooldown — chat only; audits above remain fully available */}
      {cooldownLeft > 0 && (
        <div className="ssense-cooldown-banner ssense-animate-in">
          <div className="ssense-cooldown-title"><span>⏳</span><span>Chat is briefly cooling down — back in {cooldownLeft}s</span></div>
          <div className="ssense-cooldown-sub">
            You've reached the chat message limit for this minute. This only affects chat — running an Audit above works as normal.
          </div>
        </div>
      )}

      {/* Shield panel */}
      {showShield && (
        <div className="ssense-shield-panel">
          <div style={{ display:'flex', justifyContent:'space-between', fontWeight:600, color:'#fff' }}>
            <span>Active Protection</span>
            <span style={{ fontSize:10, color:'var(--ssense-accent-cyan)', cursor:'pointer' }} onClick={() => setShowShield(false)}>✕</span>
          </div>
          {([
            ['blockTrackers',  'Block Third-Party Trackers'],
            ['spoofHardware',  'Spoof Hardware APIs (Canvas / Audio)'],
            ['injectGPC',      'Inject Global Privacy Control (GPC)'],
          ] as const).map(([key, label]) => (
            <label key={key} className="ssense-shield-row">
              <span>{label}</span>
              <input type="checkbox" checked={shieldSettings[key]} onChange={() => toggleShield(key)} />
            </label>
          ))}
        </div>
      )}

      {/* Audit error */}
      {auditError && !isSystemPage && (
        <div style={{ margin:'10px 20px 0', padding:'10px 12px', borderRadius:9, border:'1px solid rgba(245,158,11,.25)', background:'rgba(245,158,11,.07)', color:'var(--ssense-accent-amber)', fontSize:10.5, lineHeight:1.5 }}>
          <strong>Audit unavailable.</strong> {auditError}
          <div style={{ marginTop:6, display:'flex', gap:8 }}>
            <button onClick={() => runAudit(false)} disabled={isAuditing} style={{ border:'1px solid rgba(245,158,11,.3)', background:'transparent', color:'var(--ssense-accent-amber)', borderRadius:6, padding:'4px 8px', fontSize:10, cursor:'pointer' }}>Retry</button>
            <button onClick={() => chrome.runtime.sendMessage({ type: 'RETRY_EXTRACTION' })} style={{ border:'1px solid rgba(245,158,11,.2)', background:'transparent', color:'var(--ssense-text-muted)', borderRadius:6, padding:'4px 8px', fontSize:10, cursor:'pointer' }}>Re-scan page</button>
          </div>
        </div>
      )}

      {/* Audit card */}
      {auditReport && !isSystemPage && (
        <div className="ssense-audit-card">
          <div className="ssense-audit-header" onClick={() => setShowAuditDetails(v => !v)}>
            <span className="ssense-gradient-text" style={{ fontWeight:600, fontSize:12 }}>
              {auditReport.violations.length === 0 ? '✅ Policy Compliant' : `⚠️ ${auditReport.violations.length} Violation${auditReport.violations.length !== 1 ? 's' : ''} Found`}
            </span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={chevronStyle}><polyline points="6 9 12 15 18 9"/></svg>
          </div>

          {showAuditDetails && (
            <div className="ssense-audit-body">
              {/* Cache & Offline metadata badges */}
              {cacheSource === 'offline_cache' && (
                <div style={{ fontSize:10, color:'var(--ssense-accent-amber)', padding:'4px 8px', background:'rgba(245,158,11,0.08)', borderRadius:6, border:'1px solid rgba(245,158,11,0.2)' }}>
                  📶 Offline Mode — Displaying cached audit ({cacheAgeDays}d old)
                </div>
              )}
              {cacheSource === 'persistent_cache' && cacheAgeDays > 0 && (
                <div style={{ fontSize:10, color:'var(--ssense-text-muted)', padding:'2px 4px' }}>
                  From cache · {cacheAgeDays} day{cacheAgeDays !== 1 ? 's' : ''} ago
                </div>
              )}

              {/* Score row */}
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', background:'rgba(255,255,255,0.03)', padding:8, borderRadius:6, border:'1px solid rgba(255,255,255,0.05)' }}>
                <div><div style={{ fontSize:10, color:'var(--ssense-text-muted)' }}>Trust Score</div><div style={{ fontSize:14, fontWeight:700, color:'var(--ssense-accent-cyan)' }}>{auditReport.dpdp_trust_score} / 100</div></div>
                <div><div style={{ fontSize:10, color:'var(--ssense-text-muted)' }}>Subtlety</div><div style={{ fontSize:14, fontWeight:700, color:'var(--ssense-accent-violet)' }} title="Legal obfuscation score — higher means more complex evasive language">{auditReport.subtlety_score} / 100</div></div>
                <button onClick={e => { e.stopPropagation(); exportAuditReport(); }} style={{ background:'var(--ssense-gradient-ai)', border:'none', color:'#000', fontWeight:600, fontSize:10, padding:'4px 10px', borderRadius:6, cursor:'pointer' }}>Export</button>
              </div>

              <p className="ssense-audit-reasoning">{auditReport.global_legal_reasoning}</p>

              {/* Explainability / history accordion */}
              {(auditReport.explainability || siteHistory) && (
                <div style={{ border:'1px solid var(--ssense-border)', borderRadius:8, padding:9, background:'rgba(6,182,212,0.025)' }}>
                  <button onClick={e => { e.stopPropagation(); setShowExplainability(v => !v); }} style={{ width:'100%', background:'transparent', border:0, color:'var(--ssense-text-primary)', cursor:'pointer', display:'flex', justifyContent:'space-between', fontSize:10.5, fontWeight:700, padding:0 }}>
                    <span>Why this score?</span><span>{showExplainability ? '−' : '+'}</span>
                  </button>
                  {showExplainability && (
                    <div style={{ marginTop:9 }}>
                      {siteHistory ? (
                        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:7 }}>
                          {([['Current score', siteHistory.lastScore != null ? `${siteHistory.lastScore}/100` : '—'],['Visits', String(siteHistory.visitCount)],['Time on site', formatDuration(siteHistory.totalTimeMs)],['Violations', String(siteHistory.lastReport?.violations?.length ?? 0)],['Last audit', siteHistory.lastAuditAt ? new Date(siteHistory.lastAuditAt).toLocaleString() : 'Never'],['First seen', new Date(siteHistory.firstVisit).toLocaleDateString()]] as [string,string][]).map(([label, val]) => (
                            <div key={label} style={{ padding:7, borderRadius:6, background:'rgba(255,255,255,0.035)', border:'1px solid rgba(255,255,255,0.05)' }}>
                              <div style={{ fontSize:8.5, color:'var(--ssense-text-muted)' }}>{label}</div>
                              <div style={{ fontSize:10, fontWeight:650, marginTop:2 }}>{val}</div>
                            </div>
                          ))}
                        </div>
                      ) : <div style={{ fontSize:9.5, color:'var(--ssense-text-muted)' }}>No local history for this site yet.</div>}
                    </div>
                  )}
                </div>
              )}

              {/* Violations */}
              {auditReport.violations.map((v, i) => (
                <div key={i} className="ssense-violation-card">
                  <div className="ssense-violation-top">
                    <span className="ssense-violation-type">{v.violation_type.replace(/_/g,' ')}</span>
                    <span className="ssense-violation-action">{v.network_action.replace(/_/g,' ')}</span>
                  </div>
                  {v.evidence_quote && (
                    <blockquote className="ssense-evidence" title="Click to highlight in page" onClick={() => chrome.tabs.query({ active:true, currentWindow:true }, tabs => { if (tabs[0]?.id) chrome.tabs.sendMessage(tabs[0].id, { type:'HIGHLIGHT_IN_DOM', quote:v.evidence_quote }).catch(()=>{}); })}>
                      "{v.evidence_quote}"
                      <div style={{ fontSize:9.5, color:'var(--ssense-accent-cyan)', marginTop:4, fontStyle:'normal' }}>🔍 Click to highlight in page</div>
                    </blockquote>
                  )}
                  {v.offending_entities?.length > 0 && (
                    <div className="ssense-entities-list">
                      {v.offending_entities.map((e, j) => <span key={j} className="ssense-entity-tag">{e}</span>)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Message stream */}
      <div ref={scrollRef} className="ssense-stream">
        {isSystemPage
          ? <div className="ssense-empty-state" style={{ marginTop:'30%', color:'var(--ssense-text-muted)' }}>Ssense AI is disabled on browser system pages.</div>
          : <>
              {messages.length === 0 && !isChatting && domain && (
                <div className="ssense-empty-state">
                  <h2 className="ssense-gradient-text" style={{ fontSize:22, fontWeight:700, margin:0, letterSpacing:'-0.02em' }}>Ssense Co-Pilot</h2>
                  <p style={{ color:'var(--ssense-text-secondary)', fontSize:13, marginTop:8, lineHeight:1.5 }}>Ask anything about this site's data practices.</p>
                  <div className="ssense-quick-prompts">
                    {quickPrompts.map((p, i) => <button key={i} className="ssense-quick-prompt" onClick={() => handleSend(p)}>{p}</button>)}
                  </div>
                </div>
              )}
              {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}
              {isChatting && (
                <div className="ssense-animate-in" style={{ display:'flex', alignItems:'center', gap:10, paddingLeft:4 }}>
                  <div className="ssense-thinking-dot" />
                  <div className="ssense-thinking-dot" style={{ animationDelay:'0.2s' }} />
                  <div className="ssense-thinking-dot" style={{ animationDelay:'0.4s' }} />
                  <span style={{ fontSize:12, color:'var(--ssense-text-muted)', marginLeft:4, fontWeight:500 }}>{loadingText}</span>
                </div>
              )}
            </>
        }
      </div>

      {/* Input dock */}
      <div className="ssense-input-dock">
        <div className="ssense-input-container">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder={isSystemPage ? 'Disabled on system pages' : isOffline ? 'Chat requires an internet connection' : cooldownLeft > 0 ? `Chat resumes in ${cooldownLeft}s…` : 'Ask about this site\'s privacy practices…'}
            className="ssense-input-field"
            disabled={isChatting || !domain || isSystemPage || !serviceAvailable || cooldownLeft > 0 || isOffline}
          />
          <button onClick={() => handleSend()} disabled={!input.trim() || isChatting || !domain || isSystemPage || !serviceAvailable || cooldownLeft > 0 || isOffline} className={`ssense-send-btn${input.trim() && !isChatting && cooldownLeft === 0 && !isOffline ? ' active' : ''}`}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>
        </div>
        <div className="ssense-branding">Powered by Ssense AI · DPDP Act 2023</div>
      </div>
    </div>
  );
};
