// First-run onboarding: sign in with Google → choose scanning behaviour → done.
import React, { useState } from 'react';
import { Avatar, BrandMark, Icon, Switch } from '../ui/components';
import { GoogleButton, SignInError, SignInPromise, useGoogleSignIn } from '../ui/SignIn';
import { useAuth, usePrefs, useTheme } from '../ui/hooks';

export const Welcome: React.FC = () => {
  const { auth, reload } = useAuth();
  const { prefs, update } = usePrefs();
  useTheme(prefs?.theme);
  const [step, setStep] = useState<0 | 1 | 2>(0);
  const { busy, error, signIn } = useGoogleSignIn(async () => { await reload(); setStep(1); });
  const current = auth?.signedIn && step === 0 ? 1 : step;

  return (
    <div className="wl">
      <aside className="wl-art">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <BrandMark size={40} /><div className="sx-display" style={{ fontSize: 22 }}>Ssense</div>
        </div>
        <div style={{ position: 'relative', zIndex: 1 }}>
          <div className="sx-eyebrow" style={{ marginBottom: 14 }}>DPDP Act 2023 · privacy shield</div>
          <h1 className="sx-display wl-h1">Every site’s privacy policy, <em>read for you.</em></h1>
          <p style={{ fontSize: 16, lineHeight: 1.6, color: 'var(--ssense-text-secondary)', maxWidth: 460, marginTop: 20 }}>
            Ssense audits sites as you open them, flags the clauses that fall short of Indian law, and keeps the results with you on every device.
          </p>
        </div>
        <div className="sx-muted" style={{ fontSize: 12, position: 'relative', zIndex: 1 }}>Your browsing never leaves your device.</div>
      </aside>

      <main className="wl-main">
        <div className="wl-card">
          <div className="wl-steps" aria-label={`Step ${current + 1} of 3`}>{[0, 1, 2].map((i) => <i key={i} data-on={i <= current} />)}</div>

          {current === 0 && (
            <>
              <div><div className="sx-eyebrow">Step 1 of 3</div><h2 className="sx-display" style={{ fontSize: 28, margin: '6px 0 0' }}>Connect your Google account</h2></div>
              <GoogleButton busy={busy} onClick={signIn} />
              <SignInError message={error} />
              <SignInPromise />
            </>
          )}

          {current === 1 && (
            <>
              <div><div className="sx-eyebrow">Step 2 of 3</div><h2 className="sx-display" style={{ fontSize: 28, margin: '6px 0 0' }}>How should Ssense work?</h2></div>
              {auth && (
                <div className="sx-card" style={{ display: 'flex', gap: 10, alignItems: 'center', padding: 10 }}>
                  <Avatar name={auth.name} email={auth.email} url={auth.avatarUrl} size={34} />
                  <div style={{ minWidth: 0 }}><div style={{ fontSize: 13, fontWeight: 650 }}>{auth.name}</div><div className="sx-muted sx-trunc" style={{ fontSize: 11.5 }}>{auth.email}</div></div>
                  <span className="sx-pill sx-tone-ok" style={{ marginLeft: 'auto' }}><i />Connected</span>
                </div>
              )}
              {prefs && (
                <div>
                  {([
                    ['autoScan', 'Scan sites automatically', 'Audit a site’s privacy policy as soon as you open it.'],
                    ['notifyOnLowScore', 'Alert me about risky sites', `Notify when a site scores below ${prefs.lowScoreThreshold}.`],
                    ['enforceProtections', 'Apply recommended protections', 'Block trackers and mask fingerprinting where an audit says to.'],
                    ['syncEnabled', 'Sync across my devices', 'Keep history and settings in step wherever you sign in.'],
                  ] as const).map(([k, t, d]) => (
                    <div key={k} className="wl-opt">
                      <div><div style={{ fontSize: 14, fontWeight: 650 }}>{t}</div><div className="sx-muted" style={{ fontSize: 12.5, marginTop: 2 }}>{d}</div></div>
                      <Switch label={t} checked={Boolean(prefs[k])} onChange={(v) => update({ [k]: v })} />
                    </div>
                  ))}
                </div>
              )}
              <button className="sx-btn sx-btn--primary sx-btn--block" onClick={() => setStep(2)}>Continue</button>
            </>
          )}

          {current === 2 && (
            <>
              <div><div className="sx-eyebrow">Step 3 of 3</div><h2 className="sx-display" style={{ fontSize: 28, margin: '6px 0 0' }}>You’re protected.</h2></div>
              <ol style={{ margin: 0, paddingLeft: 20, display: 'grid', gap: 10, fontSize: 14, lineHeight: 1.5, color: 'var(--ssense-text-secondary)' }}>
                <li><b style={{ color: 'var(--ssense-text-primary)' }}>Pin Ssense</b> — click the puzzle icon in the toolbar, then the pin beside Ssense.</li>
                <li><b style={{ color: 'var(--ssense-text-primary)' }}>Open any website.</b> The toolbar badge shows its trust score once the scan finishes.</li>
                <li><b style={{ color: 'var(--ssense-text-primary)' }}>Another browser or computer?</b> Install Ssense there and sign in with the same Google account.</li>
              </ol>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="sx-btn sx-btn--primary" style={{ flex: 1 }} onClick={() => window.close()}><Icon name="check" size={15} /> Start browsing</button>
                <button className="sx-btn" onClick={() => chrome.runtime.openOptionsPage()}><Icon name="settings" size={15} /> Settings</button>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
};
