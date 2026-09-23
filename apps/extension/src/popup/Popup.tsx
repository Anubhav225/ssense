// apps/extension/src/popup/Popup.tsx — One-time setup, Google identity handshake, and DPDP shield
import React, { useEffect, useState, useCallback } from 'react';
import { getServerConfig } from '../background/api-client';

type ServiceStatus = 'checking' | 'online' | 'offline' | 'unconfigured';

const css = `
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #09090B;
    color: #FAFAFA;
    min-width: 320px;
    max-width: 360px;
  }
  .popup {
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .logo {
    width: 30px;
    height: 30px;
    border-radius: 8px;
    background: linear-gradient(135deg, #06B6D4, #8B5CF6);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 0 12px rgba(6, 182, 212, 0.35);
  }
  .title { font-size: 14px; font-weight: 700; letter-spacing: -0.01em; }
  .subtitle { font-size: 10px; color: #71717A; margin-top: 1px; }

  /* Onboarding Card */
  .onboarding-card {
    background: linear-gradient(145deg, rgba(24, 24, 27, 0.95), rgba(9, 9, 11, 0.98));
    border: 1px solid rgba(6, 182, 212, 0.25);
    border-radius: 12px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  }
  .onboarding-tag {
    font-size: 9.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #38BDF8;
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.25);
    border-radius: 4px;
    padding: 2px 6px;
    align-self: flex-start;
  }
  .onboarding-desc {
    font-size: 11px;
    color: #A1A1AA;
    line-height: 1.45;
  }
  .form-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .form-label {
    font-size: 10.5px;
    font-weight: 600;
    color: #D4D4D8;
  }
  .form-input {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    color: #FAFAFA;
    font-size: 11.5px;
    padding: 8px 10px;
    outline: none;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .form-input:focus {
    border-color: #06B6D4;
    box-shadow: 0 0 0 2px rgba(6, 182, 212, 0.2);
  }
  .google-sync-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 11px;
    font-weight: 600;
    color: #E4E4E7;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }
  .google-sync-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.2);
  }
  .google-chip {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    color: #34D399;
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.25);
    border-radius: 6px;
    padding: 4px 8px;
  }

  /* User Profile Badge in Active Shield */
  .user-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .avatar {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: linear-gradient(135deg, #06B6D4, #8B5CF6);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    font-weight: 700;
    color: #fff;
    flex-shrink: 0;
    overflow: hidden;
  }
  .avatar img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .user-meta {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .user-name {
    font-size: 11px;
    font-weight: 600;
    color: #F4F4F5;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 170px;
  }
  .user-email {
    font-size: 9.5px;
    color: #71717A;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 170px;
  }

  /* Common Status & Controls */
  .status-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.06);
    font-size: 11px;
  }
  .dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .server-badge {
    font-size: 10px;
    color: #38BDF8;
    background: rgba(56, 189, 248, 0.1);
    border: 1px solid rgba(56, 189, 248, 0.2);
    border-radius: 6px;
    padding: 4px 8px;
    text-overflow: ellipsis;
    overflow: hidden;
    white-space: nowrap;
  }
  .btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 9px 14px;
    border-radius: 9px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    border: none;
    transition: opacity 0.15s, transform 0.05s;
    width: 100%;
  }
  .btn:active { transform: scale(0.99); }
  .btn:hover { opacity: 0.9; }
  .btn:disabled { opacity: 0.6; cursor: not-allowed; }
  .btn-primary { background: linear-gradient(135deg, #06B6D4, #8B5CF6); color: #fff; }
  .btn-accent { background: linear-gradient(135deg, #10B981, #06B6D4); color: #fff; font-weight: 700; box-shadow: 0 2px 10px rgba(16, 185, 129, 0.3); }
  .btn-ghost { background: rgba(255, 255, 255, 0.05); color: #A1A1AA; border: 1px solid rgba(255, 255, 255, 0.08); }
  .domain-chip {
    font-size: 10.5px;
    color: #A1A1AA;
    text-align: center;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 6px;
    padding: 4px 8px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .error-text {
    font-size: 10.5px;
    color: #F43F5E;
    text-align: center;
  }

  @keyframes shield-glow {
    0%, 100% { box-shadow: 0 0 10px rgba(6, 182, 212, 0.35); }
    50% { box-shadow: 0 0 18px rgba(6, 182, 212, 0.7); }
  }
  .logo.pulse {
    animation: shield-glow 2.5s infinite ease-in-out;
  }

  @media (prefers-color-scheme: light) {
    body {
      background: #FAFAFA;
      color: #18181B;
    }
    .subtitle {
      color: #71717A;
    }
    .onboarding-card {
      background: #FFFFFF;
      border-color: rgba(6, 182, 212, 0.3);
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    }
    .onboarding-desc {
      color: #52525B;
    }
    .form-label {
      color: #27272A;
    }
    .form-input {
      background: #F4F4F5;
      border-color: rgba(0, 0, 0, 0.12);
      color: #18181B;
    }
    .google-sync-btn {
      background: #F4F4F5;
      border-color: rgba(0, 0, 0, 0.12);
      color: #27272A;
    }
    .google-sync-btn:hover {
      background: #E4E4E7;
    }
    .user-pill {
      background: #FFFFFF;
      border-color: rgba(0, 0, 0, 0.1);
    }
    .user-name {
      color: #18181B;
    }
    .status-row {
      background: #FFFFFF;
      border-color: rgba(0, 0, 0, 0.08);
    }
    .domain-chip {
      background: #F4F4F5;
      border-color: rgba(0, 0, 0, 0.08);
      color: #52525B;
    }
    .btn-ghost {
      background: #F4F4F5;
      color: #52525B;
      border-color: rgba(0, 0, 0, 0.1);
    }
    .btn-ghost:hover {
      background: #E4E4E7;
      color: #18181B;
    }
  }
`;

function statusColor(s: ServiceStatus) {
  if (s === 'online') return '#10B981';
  if (s === 'checking') return '#F59E0B';
  return '#F43F5E';
}

function statusLabel(s: ServiceStatus) {
  if (s === 'online') return 'Ssense AI — Connected';
  if (s === 'checking') return 'Checking connection…';
  if (s === 'unconfigured') return 'Setup Required (One-Time)';
  return 'AI server offline / connecting…';
}

async function detectGoogleIdentity(): Promise<{ email: string; id: string } | null> {
  return new Promise((resolve) => {
    if (typeof chrome !== 'undefined' && chrome.identity && chrome.identity.getProfileUserInfo) {
      try {
        chrome.identity.getProfileUserInfo({ accountStatus: 'ANY' as any }, (userInfo) => {
          if (chrome.runtime.lastError || !userInfo || !userInfo.email) {
            chrome.identity.getProfileUserInfo((fallbackInfo) => {
              if (fallbackInfo && fallbackInfo.email) {
                resolve({ email: fallbackInfo.email, id: fallbackInfo.id || '' });
              } else {
                resolve(null);
              }
            });
          } else {
            resolve({ email: userInfo.email, id: userInfo.id || '' });
          }
        });
      } catch {
        resolve(null);
      }
    } else {
      resolve(null);
    }
  });
}

export const Popup: React.FC = () => {
  const [status, setStatus] = useState<ServiceStatus>('checking');
  const [isOnboarded, setIsOnboarded] = useState<boolean>(false);
  const [domain, setDomain] = useState<string | null>(null);
  const [serverUrl, setServerUrl] = useState<string>('');
  const [isOverride, setIsOverride] = useState<boolean>(false);

  // User form / profile state
  const [name, setName] = useState<string>('');
  const [email, setEmail] = useState<string>('');
  const [googleId, setGoogleId] = useState<string>('');
  const [avatarUrl, setAvatarUrl] = useState<string>('');
  const [isGoogleDetected, setIsGoogleDetected] = useState<boolean>(false);

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string>('');

  const checkConnection = useCallback(async () => {
    setStatus('checking');
    const cfg = await getServerConfig();
    setServerUrl(cfg.url);

    const storage = await chrome.storage.local.get([
      'ssense_override_enabled',
      'ssense_onboarded',
      'ssense_user_name',
      'ssense_user_email',
      'ssense_google_id',
      'ssense_avatar_url',
    ]);

    setIsOverride(Boolean(storage.ssense_override_enabled));
    const onboarded = Boolean(storage.ssense_onboarded && cfg.configured);
    setIsOnboarded(onboarded);

    if (storage.ssense_user_name) setName(storage.ssense_user_name);
    if (storage.ssense_user_email) setEmail(storage.ssense_user_email);
    if (storage.ssense_google_id) setGoogleId(storage.ssense_google_id);
    if (storage.ssense_avatar_url) setAvatarUrl(storage.ssense_avatar_url);

    if (!onboarded) {
      setStatus('unconfigured');
      // Attempt 1-click detection of active Chrome Google profile
      const detected = await detectGoogleIdentity();
      if (detected && detected.email) {
        setEmail(detected.email);
        setGoogleId(detected.id);
        setIsGoogleDetected(true);
        if (!storage.ssense_user_name) {
          const guessedName = detected.email.split('@')[0].replace(/[._-]/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
          setName(guessedName);
        }
      }
      return;
    }

    try {
      const res = await chrome.runtime.sendMessage({ type: 'HEALTH_CHECK', requestId: crypto.randomUUID() });
      setStatus(res?.success ? 'online' : 'offline');
    } catch {
      setStatus('offline');
    }
  }, []);

  useEffect(() => {
    checkConnection();
    chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
      try {
        if (tabs[0]?.url?.startsWith('http')) {
          setDomain(new URL(tabs[0].url).hostname);
        }
      } catch {}
    });
  }, [checkConnection]);

  const handleGoogleDetectClick = async () => {
    const detected = await detectGoogleIdentity();
    if (detected && detected.email) {
      setEmail(detected.email);
      setGoogleId(detected.id);
      setIsGoogleDetected(true);
      if (!name) {
        const guessedName = detected.email.split('@')[0].replace(/[._-]/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        setName(guessedName);
      }
    } else {
      // Guide user to enter Gmail address
      if (!email.includes('@gmail.com') && !email.includes('@')) {
        setEmail('user@gmail.com');
      }
    }
  };

  const handleCompleteSetup = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setErrorMessage('');
    setIsSubmitting(true);

    try {
      const res = await chrome.runtime.sendMessage({
        type: 'REGISTER_DEVICE',
        name: name.trim() || undefined,
        email: email.trim() || undefined,
        googleId: googleId.trim() || undefined,
        avatarUrl: avatarUrl.trim() || undefined,
      });

      if (res?.success) {
        setIsOnboarded(true);
        setStatus('online');
        if (res.userName) setName(res.userName);
        if (res.userEmail) setEmail(res.userEmail);
        if (res.avatarUrl) setAvatarUrl(res.avatarUrl);
      } else {
        setErrorMessage(res?.error || 'Registration failed. Check server connection.');
      }
    } catch (err: any) {
      setErrorMessage(err?.message || 'Could not communicate with Ssense server.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const openPanel = useCallback(async () => {
    try {
      const currentWin = await chrome.windows.getCurrent();
      if (currentWin?.id !== undefined) {
        await chrome.sidePanel.open({ windowId: currentWin.id });
        window.close();
        return;
      }
    } catch {}
    const [win] = await chrome.windows.getAll({ populate: false });
    if (win?.id !== undefined) {
      await chrome.sidePanel.open({ windowId: win.id });
      window.close();
    }
  }, []);

  const userInitial = (name || email || 'S').trim().charAt(0).toUpperCase();

  return (
    <>
      <style>{css}</style>
      <div className="popup">
        {/* Header */}
        <div className="header">
          <div className="brand">
            <div className={`logo${status === 'online' ? ' pulse' : ''}`}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
            </div>
            <div>
              <div className="title">Ssense Privacy Shield</div>
              <div className="subtitle">DPDP Act 2023 Compliance</div>
            </div>
          </div>

          {isOnboarded && (
            <div className="user-pill" title={`${name} (${email})`}>
              <div className="avatar">
                {avatarUrl ? <img src={avatarUrl} alt={name} /> : userInitial}
              </div>
            </div>
          )}
        </div>

        {/* View A: One-time setup view */}
        {!isOnboarded ? (
          <form className="onboarding-card" onSubmit={handleCompleteSetup}>
            <div className="onboarding-tag">⚡ Initial Setup (Once)</div>
            <p className="onboarding-desc">
              Connect your Google identity to register this device and activate real-time DPDP compliance auditing.
            </p>

            <div className="form-group">
              <label className="form-label">Your Name</label>
              <input
                className="form-input"
                type="text"
                placeholder="e.g. Anubhav Singh"
                value={name}
                onChange={e => setName(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Google / Gmail Account</label>
              <input
                className="form-input"
                type="email"
                placeholder="e.g. anubhav@gmail.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
              />
            </div>

            <button
              type="button"
              className="google-sync-btn"
              onClick={handleGoogleDetectClick}
            >
              <svg width="14" height="14" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.8-2.4 3.65v3.03h3.88c2.27-2.09 3.66-5.17 3.66-9.12z"/>
                <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.03c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.13C3.26 21.41 7.33 24 12 24z"/>
                <path fill="#FBBC05" d="M5.28 14.29c-.25-.72-.38-1.49-.38-2.29s.13-1.57.38-2.29V6.58H1.25C.45 8.16 0 9.98 0 12s.45 3.84 1.25 5.42l4.03-3.13z"/>
                <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.59 1.25 6.58l4.03 3.13c.95-2.83 3.6-4.96 6.72-4.96z"/>
              </svg>
              {isGoogleDetected ? '✓ Google Profile Detected' : 'Detect Chrome Google Profile'}
            </button>

            {serverUrl && (
              <div className="server-badge" title={serverUrl}>
                🌐 {isOverride ? 'Custom Server' : 'Ssense Cloud'}: {serverUrl}
              </div>
            )}
            {errorMessage && <div className="error-text">⚠️ {errorMessage}</div>}

            <button
              type="submit"
              className="btn btn-accent"
              disabled={isSubmitting || !name.trim() || !email.trim()}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
              </svg>
              {isSubmitting ? 'Registering Device & IP…' : 'Connect & Activate Shield'}
            </button>
          </form>
        ) : (
          /* View B: Active Shield View (Post-Onboarding) */
          <>
            <div className="status-row">
              <div
                className="dot"
                style={{
                  background: statusColor(status),
                  boxShadow: status === 'online' ? '0 0 6px #10B981' : undefined,
                }}
              />
              <span style={{ color: status === 'online' ? '#10B981' : status === 'checking' ? '#F59E0B' : '#F43F5E' }}>
                {statusLabel(status)}
              </span>
            </div>

            {serverUrl && (
              <div className="server-badge" title={serverUrl}>
                🌐 {isOverride ? 'Custom Server' : 'Ssense Cloud'}: {serverUrl}
              </div>
            )}

            <div className="user-pill">
              <div className="avatar">
                {avatarUrl ? <img src={avatarUrl} alt={name} /> : userInitial}
              </div>
              <div className="user-meta">
                <div className="user-name">{name || 'Registered Reviewer'}</div>
                <div className="user-email">{email}</div>
              </div>
            </div>

            {domain && <div className="domain-chip">Active site: <strong>{domain}</strong></div>}

            <button className="btn btn-primary" onClick={openPanel}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
              Open Privacy Panel
            </button>

            <button className="btn btn-ghost" onClick={() => chrome.runtime.openOptionsPage()}>
              ⚙️ Settings
            </button>
          </>
        )}
      </div>
    </>
  );
};
