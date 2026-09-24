import { useEffect, useState } from 'react';
import { ChatInterface, DESIGN_SYSTEM_CSS } from './components/ChatInterface';
import { HistoryView } from './components/HistoryView';
import PrivacyView from './components/PrivacyView';
import { BrandMark, Spinner } from '../ui/components';
import { GoogleButton, SignInError, SignInPromise, useGoogleSignIn } from '../ui/SignIn';
import { useActiveTab, useAuth, usePrefs, useTheme } from '../ui/hooks';

type View = 'audit' | 'history' | 'privacy';

function SignInGate({ onDone }: { onDone: () => void }) {
  const { busy, error, signIn } = useGoogleSignIn(onDone);
  return (
    <div style={{ minHeight: '100dvh', display: 'grid', placeItems: 'center', padding: 22 }}>
      <div style={{ display: 'grid', gap: 16, maxWidth: 340 }}>
        <BrandMark size={40} />
        <h1 className="sx-display" style={{ fontSize: 28, lineHeight: 1.1, margin: 0 }}>Sign in to start auditing.</h1>
        <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.55, color: 'var(--ssense-text-secondary)' }}>
          Ssense checks each site’s privacy policy against the DPDP Act and keeps your history in sync across devices.
        </p>
        <GoogleButton busy={busy} onClick={signIn} />
        <SignInError message={error} />
        <SignInPromise />
      </div>
    </div>
  );
}

function App() {
  const [view, setView] = useState<View>('audit');
  const [domain, setDomain] = useState<string | null>(null);
  const { auth, reload } = useAuth();
  const { prefs } = usePrefs();
  const tab = useActiveTab();
  useTheme(prefs?.theme);

  useEffect(() => {
    const styleTag = document.createElement('style');
    styleTag.innerHTML = DESIGN_SYSTEM_CSS;
    document.head.appendChild(styleTag);
    return () => { document.head.removeChild(styleTag); };
  }, []);

  useEffect(() => { setDomain(tab.host); }, [tab.host]);

  // A view can be requested (by the popup) both before and after the panel is open.
  useEffect(() => {
    const apply = async () => {
      const requested = (await chrome.storage.local.get('ssense_sidepanel_view')).ssense_sidepanel_view;
      if (requested === 'history' || requested === 'privacy' || requested === 'audit') setView(requested);
      if (requested) chrome.storage.local.remove('ssense_sidepanel_view');
    };
    void apply();
    const l = (c: Record<string, chrome.storage.StorageChange>, area: string) => { if (area === 'local' && c.ssense_sidepanel_view?.newValue) void apply(); };
    chrome.storage.onChanged.addListener(l);
    return () => chrome.storage.onChanged.removeListener(l);
  }, []);

  if (!auth) return <div style={{ minHeight: '100dvh', display: 'grid', placeItems: 'center' }}><Spinner size={22} /></div>;
  if (!auth.signedIn) return <SignInGate onDone={reload} />;

  if (view === 'history') return <HistoryView onBack={() => setView('audit')} onOpenPrivacy={(d) => { setDomain(d); setView('privacy'); }} />;
  if (view === 'privacy' && domain) return <PrivacyView domain={domain} onBack={() => setView('history')} />;
  return <ChatInterface onOpenHistory={() => setView('history')} onOpenPrivacy={() => setView('privacy')} />;
}

export default App;
