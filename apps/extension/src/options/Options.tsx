// apps/extension/src/options/Options.tsx — General Release Settings & Preferences

import { useEffect, useState } from 'react';

type TestState = 'idle' | 'testing' | 'ok' | 'fail';
type SavedState = 'idle' | 'saving' | 'saved' | 'error';
type ResetState = 'idle' | 'resetting' | 'done';

const OVERRIDE_KEYS = ['ssense_override_enabled', 'ssense_server_url', 'ssense_api_key', 'ssense_hmac_secret'] as const;

function isValidUrl(raw: string): boolean {
  try {
    const u = new URL(raw.trim());
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch {
    return false;
  }
}

export default function Options() {
  const [testState, setTestState] = useState<TestState>('idle');
  const [testDetail, setTestDetail] = useState('');

  const [overrideEnabled, setOverrideEnabled] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [serverUrl, setServerUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [hmacSecret, setHmacSecret] = useState('');
  const [showSecrets, setShowSecrets] = useState(false);
  const [saveState, setSaveState] = useState<SavedState>('idle');
  const [resetState, setResetState] = useState<ResetState>('idle');

  const [activeUrl, setActiveUrl] = useState('');
  const [userName, setUserName] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [googleId, setGoogleId] = useState('');
  const [avatarUrl, setAvatarUrl] = useState('');
  const [isOnboarded, setIsOnboarded] = useState(false);
  const [handshakeState, setHandshakeState] = useState<'idle' | 'registering' | 'done' | 'error'>('idle');

  const manifest = typeof chrome !== 'undefined' && chrome.runtime?.getManifest ? chrome.runtime.getManifest() : null;
  const version = manifest?.version || '1.0.0';

  useEffect(() => {
    const styleTag = document.createElement('style');
    styleTag.innerHTML = OPTIONS_CSS;
    document.head.appendChild(styleTag);
    return () => { document.head.removeChild(styleTag); };
  }, []);

  useEffect(() => {
    chrome.storage.local.get([
      ...OVERRIDE_KEYS,
      'ssense_user_name',
      'ssense_user_email',
      'ssense_google_id',
      'ssense_avatar_url',
      'ssense_onboarded',
    ], async (data) => {
      const enabled = Boolean(data.ssense_override_enabled);
      setOverrideEnabled(enabled);
      setShowAdvanced(enabled);
      if (data.ssense_server_url) setServerUrl(data.ssense_server_url);
      if (data.ssense_api_key) setApiKey(data.ssense_api_key);
      if (data.ssense_hmac_secret) setHmacSecret(data.ssense_hmac_secret);
      if (data.ssense_user_name) setUserName(data.ssense_user_name);
      if (data.ssense_user_email) setUserEmail(data.ssense_user_email);
      if (data.ssense_google_id) setGoogleId(data.ssense_google_id);
      if (data.ssense_avatar_url) setAvatarUrl(data.ssense_avatar_url);
      if (data.ssense_onboarded) setIsOnboarded(Boolean(data.ssense_onboarded));

      try {
        const cfgRes = await chrome.runtime.sendMessage({ type: 'GET_ENGINE_CONFIG' });
        if (cfgRes?.url) setActiveUrl(cfgRes.url);
      } catch {}
    });
  }, []);

  const overrideValid = !overrideEnabled || (isValidUrl(serverUrl) && apiKey.trim().length > 0 && hmacSecret.trim().length > 0);

  const handleTest = async () => {
    setTestState('testing');
    setTestDetail('');
    try {
      const res = await chrome.runtime.sendMessage({ type: 'HEALTH_CHECK' });
      if (res?.success) {
        setTestState('ok');
        setTestDetail('Connected to Ssense SLM Server.');
      } else {
        setTestState('fail');
        setTestDetail(res?.error || 'Could not reach the Ssense service right now.');
      }
    } catch {
      setTestState('fail');
      setTestDetail('Could not reach the Ssense service right now.');
    }
  };

  const handleSaveOverride = async () => {
    setSaveState('saving');
    try {
      if (overrideEnabled) {
        await chrome.storage.local.set({
          ssense_override_enabled: true,
          ssense_server_url: serverUrl.trim().replace(/\/$/, ''),
          ssense_api_key: apiKey.trim(),
          ssense_hmac_secret: hmacSecret.trim(),
        });
      } else {
        await chrome.storage.local.remove(OVERRIDE_KEYS as unknown as string[]);
      }
      setSaveState('saved');
      setTestState('idle');
      try {
        const cfgRes = await chrome.runtime.sendMessage({ type: 'GET_ENGINE_CONFIG' });
        if (cfgRes?.url) setActiveUrl(cfgRes.url);
      } catch {}
      setTimeout(() => setSaveState('idle'), 2000);
    } catch {
      setSaveState('error');
    }
  };

  const toggleOverride = (checked: boolean) => {
    setOverrideEnabled(checked);
    if (!checked) { setTestState('idle'); }
  };

  const handleRegister = async () => {
    setHandshakeState('registering');
    try {
      const res = await chrome.runtime.sendMessage({
        type: 'REGISTER_DEVICE',
        name: userName || undefined,
        email: userEmail || undefined,
        googleId: googleId || undefined,
        avatarUrl: avatarUrl || undefined,
      });
      if (res?.success) {
        setHandshakeState('done');
        const st = await chrome.storage.local.get([
          'ssense_user_name',
          'ssense_user_email',
          'ssense_google_id',
          'ssense_avatar_url',
          'ssense_api_key',
          'ssense_hmac_secret',
          'ssense_onboarded',
        ]);
        setUserName(st.ssense_user_name || 'Registered Reviewer');
        setUserEmail(st.ssense_user_email || '');
        if (st.ssense_google_id) setGoogleId(st.ssense_google_id);
        if (st.ssense_avatar_url) setAvatarUrl(st.ssense_avatar_url);
        if (st.ssense_onboarded) setIsOnboarded(true);
        if (st.ssense_api_key) setApiKey(st.ssense_api_key);
        if (st.ssense_hmac_secret) setHmacSecret(st.ssense_hmac_secret);
        await handleTest();
        setTimeout(() => setHandshakeState('idle'), 2500);
      } else {
        setHandshakeState('error');
        alert(res?.error || 'Registration failed');
      }
    } catch {
      setHandshakeState('error');
    }
  };

  const handleResetData = async () => {
    if (!confirm('Clear all local browsing history and cached DPDP audits? Your account linkage and settings will remain.')) {
      return;
    }
    setResetState('resetting');
    try {
      await chrome.runtime.sendMessage({ type: 'CLEAR_HISTORY' });
      await chrome.storage.local.remove(['ssense_recent_audits', 'ssense_sidepanel_view']);
      setResetState('done');
      setTimeout(() => setResetState('idle'), 2500);
    } catch {
      setResetState('idle');
    }
  };

  return (
    <div className="opt-page">
      <div className="opt-shell">
        {/* Header */}
        <header className="opt-masthead">
          <div className="opt-masthead-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <div>
            <div className="opt-title">Ssense Settings</div>
            <div className="opt-subtitle">DPDP Act 2023 Compliance &amp; Privacy Shield</div>
          </div>
        </header>

        {/* Section 1: Status & Connection */}
        <section className="opt-card">
          <div className="opt-card-head">
            <div className="opt-card-head-text">
              <div className="opt-eyebrow">Connection Status</div>
              <div className="opt-card-title">
                {isOnboarded ? 'Privacy Shield Active' : 'Setup Required'}
              </div>
            </div>
            <span className={`opt-badge ${isOnboarded ? 'opt-badge--active' : 'opt-badge--setup'}`}>
              <span className="opt-badge-dot" />
              {isOnboarded ? 'Connected' : 'Unregistered'}
            </span>
          </div>

          <p className="opt-plain">
            {isOnboarded
              ? 'Your browser is linked to Ssense. Audits run automatically as you browse, evaluating privacy policies against statutory requirements.'
              : 'Complete the 1-Click Handshake below to register this browser and unlock your free hourly AI co-pilot quota.'}
          </p>

          {/* Active Server Info */}
          <div style={{
            fontSize: '11.5px',
            color: 'var(--opt-cyan)',
            background: 'var(--opt-bg-elevated)',
            border: '1px solid var(--opt-border)',
            borderRadius: '8px',
            padding: '8px 12px',
            marginBottom: '14px',
            wordBreak: 'break-all',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
          }}>
            <div>
              <strong>Server:</strong> {overrideEnabled ? 'Custom Self-Hosted' : 'Ssense Cloud (Default)'}
              <div style={{ fontSize: '10.5px', color: 'var(--opt-text-muted)', marginTop: 2 }}>{activeUrl || 'Connecting…'}</div>
            </div>
            <span style={{ fontSize: '10px', background: 'var(--opt-bg-surface)', padding: '2px 6px', borderRadius: 4, border: '1px solid var(--opt-border)', color: 'var(--opt-text-secondary)', flexShrink: 0 }}>
              {overrideEnabled ? 'Override' : 'Cloud'}
            </span>
          </div>

          {/* Profile Card if linked */}
          {userName && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '10px',
              padding: '9px 12px',
              borderRadius: '9px',
              background: 'var(--opt-bg-elevated)',
              border: '1px solid var(--opt-border)',
              marginBottom: '14px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  background: 'var(--opt-gradient)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '12px',
                  fontWeight: 700,
                  color: '#fff',
                  overflow: 'hidden',
                  flexShrink: 0,
                }}>
                  {avatarUrl ? <img src={avatarUrl} alt={userName} style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : (userName || 'U')[0].toUpperCase()}
                </div>
                <div>
                  <div style={{ fontSize: '12.5px', fontWeight: 650, color: 'var(--opt-text-primary)' }}>{userName}</div>
                  <div style={{ fontSize: '10.5px', color: 'var(--opt-text-muted)' }}>{userEmail || 'Local Reviewer'}</div>
                </div>
              </div>

              {googleId || userEmail?.includes('@gmail.com') ? (
                <span style={{
                  fontSize: '10px',
                  fontWeight: 600,
                  color: 'var(--opt-green)',
                  background: 'rgba(16, 185, 129, 0.12)',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                  borderRadius: '6px',
                  padding: '3px 7px',
                  whiteSpace: 'nowrap',
                }}>
                  ✓ Google Linked
                </span>
              ) : null}
            </div>
          )}

          {/* Action Row */}
          <div className="opt-button-row">
            <button className="opt-btn opt-btn--secondary" disabled={testState === 'testing'} onClick={handleTest}>
              {testState === 'testing' ? 'Checking…' : 'Test connection'}
            </button>
            <button className="opt-btn opt-btn--primary" disabled={handshakeState === 'registering'} onClick={handleRegister}>
              {handshakeState === 'registering' ? 'Registering…' : handshakeState === 'done' ? '✓ Registered' : isOnboarded ? 'Refresh Handshake' : '1-Click Handshake'}
            </button>
          </div>

          {testState === 'ok' && (
            <div className="opt-status opt-status--ok">
              <span className="opt-status-icon">✓</span>
              <span>{testDetail}</span>
            </div>
          )}
          {testState === 'fail' && (
            <div className="opt-status opt-status--fail">
              <span className="opt-status-icon">!</span>
              <span>{testDetail} Try again in a moment, or verify your internet connection.</span>
            </div>
          )}
        </section>

        {/* Section 2: Privacy & Data Protection */}
        <section className="opt-card">
          <div className="opt-card-head">
            <div className="opt-card-head-text">
              <div className="opt-eyebrow">Privacy Architecture</div>
              <div className="opt-card-title">Zero Data Harvesting</div>
            </div>
          </div>

          <p className="opt-plain">
            Ssense is designed around data minimization. Only the public privacy policy URL of sites you visit is sent to the SLM server to parse statutory obligations. Your browsing history, page contents, inputs, and credentials never leave your browser.
          </p>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, paddingTop: 4 }}>
            <div>
              <div style={{ fontSize: '12px', fontWeight: 650, color: 'var(--opt-text-primary)' }}>Local Cache &amp; History</div>
              <div style={{ fontSize: '11px', color: 'var(--opt-text-muted)' }}>Purge stored site visits and cached DPDP compliance reports</div>
            </div>
            <button
              className="opt-btn opt-btn--danger"
              style={{ flexShrink: 0 }}
              disabled={resetState === 'resetting'}
              onClick={handleResetData}
            >
              {resetState === 'resetting' ? 'Clearing…' : resetState === 'done' ? '✓ Cleared' : 'Clear Data'}
            </button>
          </div>
        </section>

        {/* Section 3: Advanced (Self-Hosted Server Override) */}
        <div style={{ marginTop: 2 }}>
          <button className="opt-advanced-toggle" onClick={() => setShowAdvanced((v) => !v)}>
            <span>Advanced: Self-Hosted Server Configuration</span>
            <span>{showAdvanced ? '▾' : '▸'}</span>
          </button>

          {showAdvanced && (
            <section className="opt-card" style={{ marginTop: 8 }}>
              <p className="opt-plain opt-plain--muted">
                Only enable this if you are running your own local or remote Ssense SLM server instance. See <code>DEPLOYMENT.md</code> in the repository for instructions.
              </p>

              <label className="opt-checkbox-row">
                <input type="checkbox" checked={overrideEnabled} onChange={(e) => toggleOverride(e.target.checked)} />
                <span>Use custom server endpoint for this browser</span>
              </label>

              {overrideEnabled && (
                <>
                  <div className="opt-divider" />
                  <div className="opt-field">
                    <label className="opt-label">Server URL</label>
                    <input
                      className="opt-input opt-input--mono"
                      type="text"
                      value={serverUrl}
                      onChange={(e) => setServerUrl(e.target.value)}
                      placeholder="https://your-server.example.com"
                      spellCheck={false}
                    />
                  </div>
                  <div className="opt-field">
                    <label className="opt-label">API Key</label>
                    <input
                      className="opt-input opt-input--mono"
                      type={showSecrets ? 'text' : 'password'}
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="Your server's SSENSE_API_KEYS value"
                      autoComplete="off"
                      spellCheck={false}
                    />
                  </div>
                  <div className="opt-field opt-field--last">
                    <label className="opt-label">HMAC Secret</label>
                    <input
                      className="opt-input opt-input--mono"
                      type={showSecrets ? 'text' : 'password'}
                      value={hmacSecret}
                      onChange={(e) => setHmacSecret(e.target.value)}
                      placeholder="Your server's SSENSE_HMAC_SECRET value"
                      autoComplete="off"
                      spellCheck={false}
                    />
                  </div>
                  <label className="opt-checkbox-row">
                    <input type="checkbox" checked={showSecrets} onChange={(e) => setShowSecrets(e.target.checked)} />
                    <span>Show key values</span>
                  </label>
                </>
              )}

              <div className="opt-button-row" style={{ marginTop: 12 }}>
                <button className="opt-btn opt-btn--primary" disabled={!overrideValid || saveState === 'saving'} onClick={handleSaveOverride}>
                  {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? '✓ Configuration Saved' : 'Save Endpoint'}
                </button>
              </div>
              {!overrideValid && (
                <div className="opt-hint" style={{ color: 'var(--opt-red)' }}>
                  A valid HTTP/HTTPS URL, API key, and HMAC secret are all required to save a custom server.
                </div>
              )}
            </section>
          )}
        </div>

        {/* Section 4: About & System Info */}
        <section className="opt-card">
          <div className="opt-card-head">
            <div className="opt-card-head-text">
              <div className="opt-eyebrow">Release Details</div>
              <div className="opt-card-title">About Ssense</div>
            </div>
          </div>

          <p className="opt-plain" style={{ marginBottom: 12 }}>
            Ssense is an automated legal compliance auditor and privacy shield implementing the provisions of the Digital Personal Data Protection (DPDP) Act 2023.
          </p>

          <div className="opt-meta-grid">
            <div className="opt-meta-item">
              <div className="opt-meta-label">Extension Version</div>
              <div className="opt-meta-value">v{version}</div>
            </div>
            <div className="opt-meta-item">
              <div className="opt-meta-label">Manifest Specification</div>
              <div className="opt-meta-value">MV3 (Service Worker)</div>
            </div>
            <div className="opt-meta-item">
              <div className="opt-meta-label">Audit Engine</div>
              <div className="opt-meta-value">DPDP Act 2023 SLM</div>
            </div>
            <div className="opt-meta-item">
              <div className="opt-meta-label">Cryptographic Protocol</div>
              <div className="opt-meta-value">HMAC-SHA256 Signed</div>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="opt-footer">
          <div>Ssense Privacy Shield · Built for DPDP Act 2023 compliance</div>
          <div style={{ fontSize: '10px', color: 'var(--opt-text-muted)' }}>
            Only public privacy policy URLs are evaluated — your browsing activity never leaves your device.
          </div>
        </footer>
      </div>
    </div>
  );
}

const OPTIONS_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

  :root {
    --opt-bg-deep: #09090B;
    --opt-bg-surface: #131316;
    --opt-bg-elevated: rgba(255,255,255,0.035);
    --opt-border: rgba(255,255,255,0.08);
    --opt-border-strong: rgba(255,255,255,0.14);
    --opt-text-primary: #FAFAFA;
    --opt-text-secondary: #A1A1AA;
    --opt-text-muted: #71717A;
    --opt-cyan: #22D3EE;
    --opt-blue: #3B82F6;
    --opt-violet: #8B5CF6;
    --opt-green: #34D399;
    --opt-amber: #FBBF24;
    --opt-red: #FB7185;
    --opt-gradient: linear-gradient(135deg, var(--opt-cyan) 0%, var(--opt-violet) 100%);
    --opt-shadow: 0 20px 50px -20px rgba(0,0,0,0.55);
  }

  @media (prefers-color-scheme: light) {
    :root {
      --opt-bg-deep: #F8FAFC;
      --opt-bg-surface: #FFFFFF;
      --opt-bg-elevated: #F1F5F9;
      --opt-border: rgba(0,0,0,0.08);
      --opt-border-strong: rgba(0,0,0,0.15);
      --opt-text-primary: #0F172A;
      --opt-text-secondary: #475569;
      --opt-text-muted: #64748B;
      --opt-cyan: #0891B2;
      --opt-blue: #2563EB;
      --opt-violet: #7C3AED;
      --opt-green: #059669;
      --opt-amber: #D97706;
      --opt-red: #E11D48;
      --opt-gradient: linear-gradient(135deg, #0891B2 0%, #7C3AED 100%);
      --opt-shadow: 0 10px 30px -10px rgba(0,0,0,0.08);
    }
  }

  * { box-sizing: border-box; }

  .opt-page {
    min-height: 100vh;
    background:
      radial-gradient(1200px 600px at 15% -10%, rgba(139,92,246,0.08), transparent 60%),
      radial-gradient(1000px 500px at 100% 0%, rgba(34,211,238,0.06), transparent 55%),
      var(--opt-bg-deep);
    color: var(--opt-text-primary);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    -webkit-font-smoothing: antialiased;
    display: flex;
    justify-content: center;
    padding: 48px 20px;
    transition: background-color 0.2s ease, color 0.2s ease;
  }

  .opt-shell { width: 100%; max-width: 520px; display: flex; flex-direction: column; gap: 16px; }

  .opt-masthead { display: flex; align-items: center; gap: 14px; margin-bottom: 6px; }
  .opt-masthead-icon {
    width: 44px; height: 44px; border-radius: 12px; flex-shrink: 0;
    background: var(--opt-gradient);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 18px rgba(34,211,238,0.25);
  }
  .opt-title { font-size: 20px; font-weight: 800; letter-spacing: -0.01em; }
  .opt-subtitle { font-size: 13px; color: var(--opt-text-muted); margin-top: 2px; }

  .opt-card {
    background: var(--opt-bg-surface);
    border: 1px solid var(--opt-border);
    border-radius: 16px;
    padding: 22px;
    box-shadow: var(--opt-shadow);
    transition: background-color 0.2s ease, border-color 0.2s ease;
  }

  .opt-card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 14px; padding-bottom: 14px; border-bottom: 1px solid var(--opt-border); }
  .opt-eyebrow { font-size: 10px; font-weight: 700; letter-spacing: 0.08em; color: var(--opt-text-muted); text-transform: uppercase; margin-bottom: 4px; }
  .opt-card-title { font-size: 15px; font-weight: 700; color: var(--opt-text-primary); }

  .opt-plain { font-size: 13px; line-height: 1.6; color: var(--opt-text-secondary); margin: 0 0 16px; }
  .opt-plain--muted { font-size: 12px; margin-bottom: 14px; }
  .opt-plain code { background: var(--opt-bg-elevated); padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: var(--opt-text-secondary); }

  .opt-badge {
    flex-shrink: 0; display: inline-flex; align-items: center; gap: 6px;
    font-size: 11px; font-weight: 650; letter-spacing: 0.01em;
    padding: 4px 10px; border-radius: 20px; white-space: nowrap;
    border: 1px solid transparent;
  }
  .opt-badge-dot { width: 6px; height: 6px; border-radius: 50%; }
  .opt-badge--active { background: rgba(52,211,153,0.12); color: var(--opt-green); border-color: rgba(52,211,153,0.28); }
  .opt-badge--active .opt-badge-dot { background: var(--opt-green); box-shadow: 0 0 0 3px rgba(52,211,153,0.18); }
  .opt-badge--setup { background: rgba(245,158,11,0.12); color: var(--opt-amber); border-color: rgba(245,158,11,0.28); }
  .opt-badge--setup .opt-badge-dot { background: var(--opt-amber); box-shadow: 0 0 0 3px rgba(245,158,11,0.18); }

  .opt-field { margin-bottom: 16px; }
  .opt-field--last { margin-bottom: 4px; }
  .opt-label { display: block; font-size: 11.5px; font-weight: 650; color: var(--opt-text-secondary); margin-bottom: 6px; }

  .opt-input {
    width: 100%; background: var(--opt-bg-elevated);
    border: 1px solid var(--opt-border); border-radius: 9px;
    color: var(--opt-text-primary); font-size: 13px;
    padding: 10px 12px; outline: none;
    transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
  }
  .opt-input:hover { border-color: var(--opt-border-strong); }
  .opt-input:focus { border-color: var(--opt-cyan); box-shadow: 0 0 0 3px rgba(34,211,238,0.15); }
  .opt-input--mono { font-family: 'JetBrains Mono', ui-monospace, monospace; }

  .opt-divider { height: 1px; background: var(--opt-border); margin: 6px 0 16px; }

  .opt-checkbox-row {
    display: flex; align-items: center; gap: 8px; font-size: 12px;
    color: var(--opt-text-secondary); margin: 6px 0 14px; cursor: pointer; user-select: none;
  }
  .opt-checkbox-row input { width: 14px; height: 14px; accent-color: var(--opt-cyan); cursor: pointer; }

  .opt-advanced-toggle {
    display: flex; align-items: center; justify-content: space-between; width: 100%;
    background: transparent; border: none; color: var(--opt-text-muted);
    font-size: 12px; font-weight: 600; font-family: inherit; cursor: pointer;
    padding: 10px 4px 4px;
  }
  .opt-advanced-toggle:hover { color: var(--opt-text-primary); }

  .opt-button-row { display: flex; gap: 10px; }
  .opt-btn {
    border-radius: 9px; padding: 9px 14px; font-size: 12px; font-weight: 650;
    cursor: pointer; border: 1px solid transparent; font-family: inherit;
    transition: filter 0.15s ease, background 0.15s ease, opacity 0.15s ease, transform 0.1s ease, border-color 0.15s ease;
  }
  .opt-btn:active:not(:disabled) { transform: scale(0.98); }
  .opt-btn:disabled { opacity: 0.45; cursor: not-allowed; }
  .opt-btn--primary { flex: 1.2; background: var(--opt-gradient); color: #fff; box-shadow: 0 4px 14px rgba(34,211,238,0.3); }
  .opt-btn--primary:hover:not(:disabled) { filter: brightness(1.08); }
  .opt-btn--secondary { flex: 1; background: var(--opt-bg-elevated); color: var(--opt-text-primary); border-color: var(--opt-border-strong); }
  .opt-btn--secondary:hover:not(:disabled) { border-color: var(--opt-cyan); }
  .opt-btn--danger { background: rgba(244,63,94,0.1); color: var(--opt-red); border-color: rgba(244,63,94,0.25); }
  .opt-btn--danger:hover:not(:disabled) { background: rgba(244,63,94,0.18); }

  .opt-status {
    display: flex; align-items: flex-start; gap: 9px;
    margin-top: 14px; padding: 10px 12px; border-radius: 9px; font-size: 12px; line-height: 1.5;
  }
  .opt-status--ok { background: rgba(52,211,153,0.08); border: 1px solid rgba(52,211,153,0.22); color: var(--opt-green); }
  .opt-status--fail { background: rgba(251,113,133,0.08); border: 1px solid rgba(251,113,133,0.22); color: var(--opt-red); }
  .opt-status-icon {
    flex-shrink: 0; width: 16px; height: 16px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 800; background: var(--opt-bg-elevated);
  }

  .opt-hint { margin-top: 12px; font-size: 11px; color: var(--opt-text-muted); line-height: 1.5; }

  .opt-meta-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px;
  }
  .opt-meta-item {
    background: var(--opt-bg-elevated); border: 1px solid var(--opt-border);
    border-radius: 8px; padding: 8px 10px;
  }
  .opt-meta-label { font-size: 9.5px; color: var(--opt-text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
  .opt-meta-value { font-size: 11.5px; font-weight: 600; color: var(--opt-text-primary); margin-top: 2px; }

  .opt-footer {
    display: flex; flex-direction: column; align-items: center; gap: 6px;
    margin-top: 10px; font-size: 11px; color: var(--opt-text-muted);
    text-align: center; line-height: 1.5;
  }
`;
