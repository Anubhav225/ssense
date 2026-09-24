// apps/extension/src/ui/SignIn.tsx — the one Google sign-in control used everywhere.

import React, { useState } from 'react';
import { GoogleG, Icon, Spinner } from './components';
import { send } from './hooks';

export function useGoogleSignIn(onDone?: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const signIn = async () => {
    setBusy(true); setError('');
    const r = await send<any>({ type: 'SIGN_IN_GOOGLE' });
    setBusy(false);
    if (r?.success) onDone?.();
    else setError(r?.error || 'Sign-in failed. Please try again.');
  };
  return { busy, error, signIn };
}

export const GoogleButton: React.FC<{ busy: boolean; onClick: () => void; label?: string }> = ({ busy, onClick, label = 'Continue with Google' }) => (
  <button type="button" className="sx-btn sx-btn--google sx-btn--block" onClick={onClick} disabled={busy} aria-busy={busy}>
    {busy ? <Spinner size={18} /> : <GoogleG />}
    {busy ? 'Waiting for Google…' : label}
  </button>
);

export const SignInError: React.FC<{ message: string }> = ({ message }) =>
  message ? (
    <div role="alert" style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 12, lineHeight: 1.45, padding: '9px 11px', borderRadius: 9, background: 'var(--ssense-bad-soft)', color: 'var(--ssense-accent-rose)' }}>
      <Icon name="alert" size={15} style={{ marginTop: 1, flexShrink: 0 }} /> <span>{message}</span>
    </div>
  ) : null;

/** What signing in shares — shown next to every sign-in button so consent is informed. */
export const SignInPromise: React.FC = () => (
  <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 7, fontSize: 12, color: 'var(--ssense-text-secondary)', lineHeight: 1.45 }}>
    {[
      ['lock', 'We read only your name, e-mail and photo — never your Google data.'],
      ['eyeOff', 'Your browsing stays on your device. Only a site’s public policy link is sent for auditing.'],
      ['sync', 'Same account on another browser = same history and settings.'],
    ].map(([i, t]) => (
      <li key={t} style={{ display: 'flex', gap: 9, alignItems: 'flex-start' }}>
        <Icon name={i} size={14} style={{ color: 'var(--ssense-accent)', marginTop: 2, flexShrink: 0 }} /> <span>{t}</span>
      </li>
    ))}
  </ul>
);
