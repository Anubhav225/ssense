import { useEffect, useState } from 'react';

// ═══════════════════════════════════════════════════════════════
// Ssense Options
//
// Ordinary users see NO server URL, API key, or HMAC secret here at all —
// this extension ships pre-configured to talk to Ssense's own free,
// centrally-hosted server, with shared credentials baked into the build
// (see background/api-client.ts's BAKED_* constants, sourced from
// apps/extension/.env.production at build time). There is nothing for a
// regular user to set up, and nothing technical to show them.
//
// The one thing this page DOES expose is an opt-in "Advanced" section for
// people who deliberately want to point the extension at their OWN
// self-hosted server (see docs/DEPLOYMENT.md) — hidden by default, and
// clearly separated from the default experience.
// ═══════════════════════════════════════════════════════════════

type TestState = 'idle' | 'testing' | 'ok' | 'fail';
type SavedState = 'idle' | 'saving' | 'saved' | 'error';

const OVERRIDE_KEYS = ['ssense_override_enabled', 'ssense_server_url', 'ssense_api_key', 'ssense_hmac_secret'] as const;

function isValidUrl(raw: string): boolean {
  try { const u = new URL(raw.trim()); return u.protocol === 'http:' || u.protocol === 'https:'; }
  catch { return false; }
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

  useEffect(() => {
    const styleTag = document.createElement('style');
    styleTag.innerHTML = OPTIONS_CSS;
    document.head.appendChild(styleTag);
    return () => { document.head.removeChild(styleTag); };
  }, []);

  useEffect(() => {
    chrome.storage.local.get(OVERRIDE_KEYS, (data) => {
      const enabled = Boolean(data.ssense_override_enabled);
      setOverrideEnabled(enabled);
      setShowAdvanced(enabled);
      if (data.ssense_server_url) setServerUrl(data.ssense_server_url);
      if (data.ssense_api_key) setApiKey(data.ssense_api_key);
      if (data.ssense_hmac_secret) setHmacSecret(data.ssense_hmac_secret);
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
        setTestDetail('Connected to Ssense.');
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
      setTimeout(() => setSaveState('idle'), 2000);
    } catch {
      setSaveState('error');
    }
  };

  const toggleOverride = (checked: boolean) => {
    setOverrideEnabled(checked);
    if (!checked) { setTestState('idle'); }
  };

  return (
    <div className="opt-page">
      <div className="opt-shell">
        <header className="opt-masthead">
          <div className="opt-masthead-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <div>
            <div className="opt-title">Ssense Settings</div>
            <div className="opt-subtitle">Privacy shield &amp; compliance auditor</div>
          </div>
        </header>

        <div className="opt-card">
          <div className="opt-card-head">
            <div className="opt-card-head-text">
              <div className="opt-eyebrow">Status</div>
              <div className="opt-card-title">You're all set</div>
            </div>
            <span className="opt-badge opt-badge--remote"><span className="opt-badge-dot" />Ready</span>
          </div>

          <p className="opt-plain">
            Ssense works out of the box — no account, no setup. Browse normally
            and the shield icon will light up with a compliance score whenever
            you're on a site with a privacy policy.
          </p>

          <div className="opt-button-row">
            <button className="opt-btn opt-btn--secondary" disabled={testState === 'testing'} onClick={handleTest}>
              {testState === 'testing' ? 'Checking…' : 'Check connection'}
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
              <span>{testDetail} Try again in a moment, or reinstall the extension if this keeps happening.</span>
            </div>
          )}
        </div>

        <button className="opt-advanced-toggle" onClick={() => setShowAdvanced((v) => !v)}>
          {showAdvanced ? '▾' : '▸'} Advanced: use my own server
        </button>

        {showAdvanced && (
          <div className="opt-card opt-card--advanced">
            <p className="opt-plain opt-plain--muted">
              Only change this if you're running your own Ssense server (see
              the project's <code>DEPLOYMENT.md</code>). Leave this off to
              keep using Ssense's free hosted service.
            </p>

            <label className="opt-checkbox-row">
              <input type="checkbox" checked={overrideEnabled} onChange={(e) => toggleOverride(e.target.checked)} />
              <span>Use a different server for this browser</span>
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
                  <span>Show values</span>
                </label>
              </>
            )}

            <div className="opt-button-row">
              <button className="opt-btn opt-btn--primary" disabled={!overrideValid || saveState === 'saving'} onClick={handleSaveOverride}>
                {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? '✓ Saved' : 'Save'}
              </button>
            </div>
            {!overrideValid && (
              <div className="opt-hint">Server URL, API key, and HMAC secret are all required to use your own server.</div>
            )}
          </div>
        )}

        <footer className="opt-footer">
          <span>SSENSE</span>
          <span className="opt-footer-dot">•</span>
          <span>Your browsing data never leaves your device except the policy page you're auditing</span>
        </footer>
      </div>
    </div>
  );
}

const OPTIONS_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

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
  }

  * { box-sizing: border-box; }

  .opt-page {
    min-height: 100vh;
    background:
      radial-gradient(1200px 600px at 15% -10%, rgba(139,92,246,0.10), transparent 60%),
      radial-gradient(1000px 500px at 100% 0%, rgba(34,211,238,0.08), transparent 55%),
      var(--opt-bg-deep);
    color: var(--opt-text-primary);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    -webkit-font-smoothing: antialiased;
    display: flex;
    justify-content: center;
    padding: 56px 20px;
  }

  .opt-shell { width: 100%; max-width: 460px; }

  .opt-masthead { display: flex; align-items: center; gap: 13px; margin-bottom: 22px; }
  .opt-masthead-icon {
    width: 40px; height: 40px; border-radius: 10px; flex-shrink: 0;
    background: var(--opt-gradient);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 18px rgba(34,211,238,0.22);
  }
  .opt-title { font-size: 18px; font-weight: 800; letter-spacing: -0.01em; }
  .opt-subtitle { font-size: 12.5px; color: var(--opt-text-muted); margin-top: 2px; }

  .opt-card {
    background: var(--opt-bg-surface);
    border: 1px solid var(--opt-border);
    border-radius: 16px;
    padding: 22px;
    box-shadow: 0 20px 50px -20px rgba(0,0,0,0.55);
  }
  .opt-card--advanced { margin-top: 12px; }

  .opt-card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid var(--opt-border); }
  .opt-eyebrow { font-size: 10px; font-weight: 700; letter-spacing: 0.09em; color: var(--opt-text-muted); text-transform: uppercase; margin-bottom: 4px; }
  .opt-card-title { font-size: 15px; font-weight: 700; }

  .opt-plain { font-size: 13px; line-height: 1.6; color: var(--opt-text-secondary); margin: 0 0 18px; }
  .opt-plain--muted { font-size: 12px; margin-bottom: 14px; }
  .opt-plain code { background: rgba(255,255,255,0.06); padding: 1px 5px; border-radius: 4px; font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--opt-text-secondary); }

  .opt-badge {
    flex-shrink: 0; display: inline-flex; align-items: center; gap: 6px;
    font-size: 10.5px; font-weight: 650; letter-spacing: 0.01em;
    padding: 5px 10px; border-radius: 20px; white-space: nowrap;
    border: 1px solid transparent;
  }
  .opt-badge-dot { width: 6px; height: 6px; border-radius: 50%; }
  .opt-badge--remote { background: rgba(52,211,153,0.12); color: #6EE7B7; border-color: rgba(52,211,153,0.28); }
  .opt-badge--remote .opt-badge-dot { background: var(--opt-green); box-shadow: 0 0 0 3px rgba(52,211,153,0.18); }

  .opt-field { margin-bottom: 18px; }
  .opt-field--last { margin-bottom: 4px; }
  .opt-label { display: block; font-size: 11.5px; font-weight: 650; color: var(--opt-text-secondary); margin-bottom: 7px; letter-spacing: 0.01em; }

  .opt-input {
    width: 100%; background: rgba(255,255,255,0.04);
    border: 1px solid var(--opt-border); border-radius: 9px;
    color: var(--opt-text-primary); font-size: 13px;
    padding: 10px 12px; outline: none;
    transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
  }
  .opt-input:hover { border-color: var(--opt-border-strong); }
  .opt-input:focus { border-color: var(--opt-cyan); background: rgba(34,211,238,0.045); box-shadow: 0 0 0 3px rgba(34,211,238,0.12); }
  .opt-input--mono { font-family: 'JetBrains Mono', ui-monospace, monospace; }

  .opt-divider { height: 1px; background: var(--opt-border); margin: 4px 0 18px; }

  .opt-checkbox-row {
    display: flex; align-items: center; gap: 8px; font-size: 12px;
    color: var(--opt-text-secondary); margin: 4px 0 16px; cursor: pointer; user-select: none;
  }
  .opt-checkbox-row input { width: 14px; height: 14px; accent-color: var(--opt-cyan); cursor: pointer; }

  .opt-advanced-toggle {
    display: block; width: 100%; text-align: left; margin-top: 14px;
    background: transparent; border: none; color: var(--opt-text-muted);
    font-size: 12px; font-weight: 600; font-family: inherit; cursor: pointer;
    padding: 8px 4px;
  }
  .opt-advanced-toggle:hover { color: var(--opt-text-secondary); }

  .opt-button-row { display: flex; gap: 10px; }
  .opt-btn {
    border-radius: 9px; padding: 10px 14px; font-size: 12.5px; font-weight: 650;
    cursor: pointer; border: 1px solid transparent; font-family: inherit;
    transition: filter 0.15s ease, background 0.15s ease, opacity 0.15s ease, transform 0.1s ease, border-color 0.15s ease;
  }
  .opt-btn:active:not(:disabled) { transform: scale(0.98); }
  .opt-btn:disabled { opacity: 0.45; cursor: not-allowed; }
  .opt-btn--primary { flex: 1.3; background: var(--opt-gradient); color: #0A0A0C; box-shadow: 0 6px 18px -6px rgba(34,211,238,0.4); }
  .opt-btn--primary:hover:not(:disabled) { filter: brightness(1.08); }
  .opt-btn--secondary { flex: 1.3; background: rgba(255,255,255,0.06); color: var(--opt-text-primary); border-color: var(--opt-border-strong); }
  .opt-btn--secondary:hover:not(:disabled) { background: rgba(255,255,255,0.1); }

  .opt-status {
    display: flex; align-items: flex-start; gap: 9px;
    margin-top: 16px; padding: 11px 13px; border-radius: 10px; font-size: 12px; line-height: 1.5;
  }
  .opt-status--ok { background: rgba(52,211,153,0.08); border: 1px solid rgba(52,211,153,0.22); color: #6EE7B7; }
  .opt-status--fail { background: rgba(251,113,133,0.08); border: 1px solid rgba(251,113,133,0.22); color: #FDA4AF; }
  .opt-status-icon {
    flex-shrink: 0; width: 16px; height: 16px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 800; background: rgba(255,255,255,0.1);
  }

  .opt-hint { margin-top: 14px; font-size: 11px; color: var(--opt-text-muted); line-height: 1.6; }

  .opt-footer {
    display: flex; align-items: center; justify-content: center; gap: 8px;
    margin-top: 20px; font-size: 10.5px; color: var(--opt-text-muted); letter-spacing: 0.02em;
    text-align: center;
  }
  .opt-footer-dot { opacity: 0.5; flex-shrink: 0; }
`;
