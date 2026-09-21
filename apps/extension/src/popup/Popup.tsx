// apps/extension/src/popup/Popup.tsx — release build (cloud-only)
import React, { useEffect, useState, useCallback } from 'react';
import { getServerConfig } from '../background/api-client';

type ServiceStatus = 'checking' | 'online' | 'offline' | 'unconfigured';

const css = `
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: #09090B; color: #FAFAFA; min-width: 280px; }
  .popup { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
  .header { display: flex; align-items: center; gap: 10px; }
  .logo { width: 28px; height: 28px; border-radius: 7px; background: linear-gradient(135deg,#06B6D4,#8B5CF6); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .title { font-size: 14px; font-weight: 700; }
  .subtitle { font-size: 10px; color: #71717A; margin-top: 1px; }
  .status-row { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 8px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06); font-size: 11px; }
  .dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .btn { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 9px 14px; border-radius: 9px; font-size: 12px; font-weight: 600; cursor: pointer; border: none; transition: opacity 0.15s; width: 100%; }
  .btn:hover { opacity: 0.85; }
  .btn-primary { background: linear-gradient(135deg,#06B6D4,#8B5CF6); color: #fff; }
  .btn-ghost { background: rgba(255,255,255,0.05); color: #A1A1AA; border: 1px solid rgba(255,255,255,0.08); }
  .domain-chip { font-size: 10px; color: #71717A; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
`;

function statusColor(s: ServiceStatus) {
  if (s === 'online') return '#10B981';
  if (s === 'checking') return '#F59E0B';
  return '#F43F5E';
}
function statusLabel(s: ServiceStatus) {
  if (s === 'online') return 'Ssense AI — Connected';
  if (s === 'checking') return 'Checking connection…';
  if (s === 'unconfigured') return 'Not configured — open Settings';
  return 'AI service unavailable';
}

export const Popup: React.FC = () => {
  const [status, setStatus] = useState<ServiceStatus>('checking');
  const [domain, setDomain] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      // BUG FIX: this used to read the raw ssense_api_key/ssense_hmac_secret
      // storage keys directly and show "Not configured" whenever they were
      // empty - which, now that credentials are baked into the build rather
      // than typed in by the user, is *always* true for a normal install.
      // getServerConfig() resolves the baked-in default (or an explicit
      // self-host override), matching what api-client.ts actually uses.
      const cfg = await getServerConfig();
      if (!cfg.configured) { setStatus('unconfigured'); return; }
      try {
        const res = await chrome.runtime.sendMessage({ type: 'HEALTH_CHECK', requestId: crypto.randomUUID() });
        setStatus(res?.success ? 'online' : 'offline');
      } catch { setStatus('offline'); }
    })();
    chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
      try { if (tabs[0]?.url?.startsWith('http')) setDomain(new URL(tabs[0].url).hostname); } catch { /* noop */ }
    });
  }, []);

  const openPanel = useCallback(async () => {
    const [win] = await chrome.windows.getAll({ populate: false });
    if (win?.id !== undefined) {
      await chrome.sidePanel.open({ windowId: win.id });
      window.close();
    }
  }, []);

  return (
    <>
      <style>{css}</style>
      <div className="popup">
        <div className="header">
          <div className="logo"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg></div>
          <div><div className="title">Ssense Privacy Shield</div><div className="subtitle">DPDP Act 2023 Compliance</div></div>
        </div>

        <div className="status-row">
          <div className="dot" style={{ background: statusColor(status), boxShadow: status === 'online' ? '0 0 6px #10B981' : undefined }} />
          <span style={{ color: status === 'online' ? '#10B981' : status === 'checking' ? '#F59E0B' : '#F43F5E' }}>{statusLabel(status)}</span>
        </div>

        {domain && <div className="domain-chip">Active on: {domain}</div>}

        <button className="btn btn-primary" onClick={openPanel}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          Open Privacy Panel
        </button>

        <button className="btn btn-ghost" onClick={() => chrome.runtime.openOptionsPage()}>
          ⚙️ Settings
        </button>
      </div>
    </>
  );
};
