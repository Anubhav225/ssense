// apps/extension/src/options/Options.tsx — Settings (public v1)
//
// Sections: Account · Scanning · Alerts & protection · Sync & devices · Appearance ·
// Privacy & data · Server (advanced) · About. Every toggle saves immediately.

import React, { useEffect, useState } from 'react';
import { Avatar, BrandMark, ConfirmButton, Icon, Spinner, Switch, Toast, useToast } from '../ui/components';
import { GoogleButton, SignInError, SignInPromise, useGoogleSignIn } from '../ui/SignIn';
import { send, useAuth, usePrefs, useSyncState, useTheme } from '../ui/hooks';
import { formatRelative } from '../utils/status';
import { normaliseDomain } from '../utils/domain';

const NAV: [string, string, string][] = [
  ['account', 'Account', 'lock'], ['scanning', 'Scanning', 'scan'], ['alerts', 'Alerts & protection', 'bell'],
  ['sync', 'Sync & devices', 'sync'], ['appearance', 'Appearance', 'sparkle'], ['data', 'Privacy & data', 'shield'],
  ['server', 'Server', 'globe'], ['about', 'About', 'check'],
];
const OVERRIDE_KEYS = ['ssense_override_enabled', 'ssense_server_url', 'ssense_api_key', 'ssense_hmac_secret'];

const Item: React.FC<{ title: string; hint?: string; children: React.ReactNode }> = ({ title, hint, children }) => (
  <div className="op-item"><div style={{ minWidth: 0, flex: 1 }}><b>{title}</b>{hint && <small>{hint}</small>}</div>{children}</div>
);
const Section: React.FC<{ id: string; title: string; desc?: string; children: React.ReactNode }> = ({ id, title, desc, children }) => (
  <section className="op-sec" id={id}><h2 className="sx-display">{title}</h2>{desc && <p>{desc}</p>}<div className="sx-card op-list">{children}</div></section>
);

export default function Options() {
  const { auth, reload } = useAuth();
  const { prefs, update } = usePrefs();
  const { state: sync, syncNow } = useSyncState();
  const { msg, show } = useToast();
  useTheme(prefs?.theme);
  const [section, setSection] = useState('account');
  const [devices, setDevices] = useState<any[]>([]);
  const [ignoreInput, setIgnoreInput] = useState('');
  const [serverUrl, setServerUrl] = useState('');
  const [activeUrl, setActiveUrl] = useState('');
  const [override, setOverride] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [hmac, setHmac] = useState('');
  const [test, setTest] = useState<'idle' | 'busy' | 'ok' | 'fail'>('idle');
  const { busy, error, signIn } = useGoogleSignIn(() => { void reload(); show('Signed in'); });
  const version = chrome.runtime.getManifest?.().version ?? '1.0.0';

  const set = (patch: Parameters<typeof update>[0]) => { void update(patch); show('Saved'); };

  useEffect(() => {
    chrome.storage.local.get(OVERRIDE_KEYS).then((d) => {
      setOverride(Boolean(d.ssense_override_enabled)); setServerUrl(d.ssense_server_url || ''); setApiKey(d.ssense_api_key && d.ssense_override_enabled ? d.ssense_api_key : ''); setHmac(d.ssense_hmac_secret && d.ssense_override_enabled ? d.ssense_hmac_secret : '');
    });
    void send<any>({ type: 'GET_ENGINE_CONFIG' }).then((r) => r?.url && setActiveUrl(r.url));
  }, []);
  useEffect(() => { if (auth?.signedIn) void send<any>({ type: 'GET_USER_PROFILE' }).then((r) => setDevices(r?.profile?.devices || [])); }, [auth?.signedIn, sync?.lastSyncAt]);

  useEffect(() => {
    const ids = NAV.map(([id]) => id);
    const io = new IntersectionObserver((es) => { const v = es.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]; if (v) setSection(v.target.id); }, { rootMargin: '-10% 0px -70% 0px' });
    ids.forEach((id) => { const el = document.getElementById(id); if (el) io.observe(el); });
    return () => io.disconnect();
  }, [prefs === null]);

  const addIgnore = () => {
    const d = normaliseDomain(ignoreInput);
    if (!d || !d.includes('.')) { show('Enter a domain like example.com'); return; }
    if (prefs && !prefs.ignoredDomains.includes(d)) set({ ignoredDomains: [...prefs.ignoredDomains, d] });
    setIgnoreInput('');
  };

  const saveServer = async () => {
    try {
      const u = new URL(serverUrl.trim());
      if (!/^https?:$/.test(u.protocol)) throw new Error();
    } catch { show('Enter a valid http(s) URL'); return; }
    if (override && (!apiKey.trim() || !hmac.trim())) { show('API key and HMAC secret are required'); return; }
    if (override) await chrome.storage.local.set({ ssense_override_enabled: true, ssense_server_url: serverUrl.trim().replace(/\/$/, ''), ssense_api_key: apiKey.trim(), ssense_hmac_secret: hmac.trim(), ssense_auth_provider: 'custom' });
    else await chrome.storage.local.remove(['ssense_override_enabled', 'ssense_server_url']);
    show('Server saved'); void reload();
    void send<any>({ type: 'GET_ENGINE_CONFIG' }).then((r) => r?.url && setActiveUrl(r.url));
  };
  const testConn = async () => { setTest('busy'); const r = await send<any>({ type: 'HEALTH_CHECK' }); setTest(r?.success ? 'ok' : 'fail'); };

  const handleBackToBrowsing = async () => {
    try {
      const tabs = await chrome.tabs.query({ currentWindow: true });
      const browsingTab = tabs.find((t) => t.url && t.url.startsWith('http') && !t.url.includes('chrome-extension://'));
      if (browsingTab?.id) {
        await chrome.tabs.update(browsingTab.id, { active: true });
        const curr = await chrome.tabs.getCurrent();
        if (curr?.id) await chrome.tabs.remove(curr.id);
        return;
      }
    } catch {}
    if (window.history.length > 1) {
      window.history.back();
    } else {
      window.close();
    }
  };

  if (!prefs || !auth) return <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}><Spinner size={24} /></div>;

  return (
    <div className="op">
      <nav className="op-nav" aria-label="Settings sections">
        <button
          className="sx-btn sx-btn--ghost"
          onClick={handleBackToBrowsing}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            marginBottom: 16,
            padding: '8px 12px',
            fontSize: 12.5,
            fontWeight: 650,
            color: 'var(--ssense-accent-cyan)',
            background: 'var(--ssense-bg-elevated)',
            border: '1px solid var(--ssense-border)',
            borderRadius: 8,
            cursor: 'pointer',
            width: '100%',
            justifyContent: 'flex-start',
            transition: 'all 0.15s ease'
          }}
          title="Return to your active webpage / browsing tab"
        >
          <Icon name="arrowLeft" size={14} />
          <span>← Back to Browsing</span>
        </button>

        <div className="op-brand" style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}><BrandMark size={32} /><div className="sx-display" style={{ fontSize: 18 }}>Settings</div></div>
        {NAV.map(([id, label, icon]) => (
          <a key={id} href={`#${id}`} aria-current={section === id} onClick={(e) => { e.preventDefault(); document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' }); setSection(id); }}>
            <Icon name={icon} size={15} />{label}
          </a>
        ))}
      </nav>

      <main className="op-main">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 14, marginBottom: 16, borderBottom: '1px solid var(--ssense-border)' }}>
          <button
            className="sx-btn sx-btn--ghost sx-btn--sm"
            onClick={handleBackToBrowsing}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 650, color: 'var(--ssense-accent-cyan)' }}
            title="Return to your active webpage"
          >
            <Icon name="arrowLeft" size={14} />
            <span>← Back to Browsing</span>
          </button>
          <button
            className="sx-btn sx-btn--ghost sx-btn--sm"
            onClick={() => chrome.tabs.create({ url: chrome.runtime.getURL('sidepanel.html') })}
            title="Open Widescreen Dashboard in a new tab"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <Icon name="maximize" size={13} />
            <span>Open Dashboard</span>
          </button>
        </div>

        <Section id="account" title="Account" desc="Signing in with Google keeps your history and settings on every device you use.">
          {auth.signedIn ? (
            <>
              <div className="op-item">
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', minWidth: 0 }}>
                  <Avatar name={auth.name} email={auth.email} url={auth.avatarUrl} size={44} />
                  <div style={{ minWidth: 0 }}><b>{auth.name || 'Signed in'}</b><small className="sx-trunc">{auth.email}</small></div>
                </div>
                <span className="sx-pill sx-tone-ok"><i />{auth.provider === 'google' ? 'Google account' : 'Custom server'}</span>
              </div>
              <Item title="Sign out" hint="Removes this device’s credentials. You can keep or erase the audit history stored here.">
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button className="sx-btn sx-btn--sm" onClick={async () => { await send({ type: 'SIGN_OUT', keepLocalData: true }); await reload(); }}><Icon name="logout" size={14} /> Sign out, keep data</button>
                  <ConfirmButton size="sm" label="Sign out & erase" confirmLabel="Erase" onConfirm={async () => { await send({ type: 'SIGN_OUT', keepLocalData: false }); await reload(); }} />
                </div>
              </Item>
            </>
          ) : (
            <div style={{ padding: '16px 0', display: 'grid', gap: 12, maxWidth: 420 }}>
              <GoogleButton busy={busy} onClick={signIn} /><SignInError message={error} /><SignInPromise />
            </div>
          )}
        </Section>

        <Section id="scanning" title="Scanning & Layout" desc="Ssense reads a site’s public privacy policy — never the pages you browse.">
          <Item title="Extension icon click" hint="Choose what opens when you click the Ssense icon in your browser toolbar.">
            <select
              className="sx-input sx-select"
              style={{ width: 'auto' }}
              value={prefs.toolbarAction || 'sidepanel'}
              onChange={(e) => set({ toolbarAction: e.target.value as any })}
              aria-label="Extension icon click behavior"
            >
              <option value="sidepanel">Side Panel (Docked, Stretchable &amp; Commands) [Default]</option>
              <option value="tab">Full Widescreen Dashboard (New Tab)</option>
              <option value="popup">Fixed Popup Window (480px)</option>
            </select>
          </Item>
          <Item title="Scan sites automatically" hint="Audit a site when you open it."><Switch label="Scan automatically" checked={prefs.autoScan} onChange={(v) => set({ autoScan: v })} /></Item>
          <Item title="Re-scan after" hint="Sites audited more recently than this are served instantly from your saved results.">
            <select className="sx-input sx-select" style={{ width: 'auto' }} value={prefs.rescanAfterDays} onChange={(e) => set({ rescanAfterDays: Number(e.target.value) })} aria-label="Re-scan interval">
              {[7, 14, 30, 60, 90].map((d) => <option key={d} value={d}>{d} days</option>)}
            </select>
          </Item>
          <div style={{ padding: '14px 0', display: 'grid', gap: 10 }}>
            <div><b style={{ fontSize: 14 }}>Never scan these sites</b><small style={{ display: 'block', fontSize: 12.5, color: 'var(--ssense-text-muted)', marginTop: 2 }}>Banks, work tools, anything you’d rather skip. Subdomains are included.</small></div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input className="sx-input" value={ignoreInput} onChange={(e) => setIgnoreInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addIgnore()} placeholder="example.com" aria-label="Domain to ignore" />
              <button className="sx-btn" onClick={addIgnore}>Add</button>
            </div>
            <div className="op-chips">
              {prefs.ignoredDomains.length === 0 && <span className="sx-muted" style={{ fontSize: 12.5 }}>No ignored sites.</span>}
              {prefs.ignoredDomains.map((d) => (
                <span key={d} className="sx-tag" style={{ display: 'inline-flex', gap: 6, alignItems: 'center', padding: '4px 6px 4px 10px' }}>{d}
                  <button className="sx-icon-btn" style={{ width: 18, height: 18 }} aria-label={`Stop ignoring ${d}`} onClick={() => set({ ignoredDomains: prefs.ignoredDomains.filter((x) => x !== d) })}><Icon name="x" size={11} /></button>
                </span>
              ))}
            </div>
          </div>
        </Section>

        <Section id="alerts" title="Alerts & protection">
          <Item title="Low-score notifications" hint="A desktop notification when a site drops below your threshold."><Switch label="Low-score notifications" checked={prefs.notifyOnLowScore} onChange={(v) => set({ notifyOnLowScore: v })} /></Item>
          <Item title={`Alert below ${prefs.lowScoreThreshold}`} hint="Trust score that counts as risky.">
            <input type="range" min={10} max={90} step={5} value={prefs.lowScoreThreshold} disabled={!prefs.notifyOnLowScore} onChange={(e) => set({ lowScoreThreshold: Number(e.target.value) })} aria-label="Alert threshold" style={{ accentColor: 'var(--ssense-accent)', width: 160 }} />
          </Item>
          <Item title="Apply recommended protections" hint="Block third-party trackers, send GPC and mask fingerprinting on sites whose audit calls for it."><Switch label="Apply protections" checked={prefs.enforceProtections} onChange={(v) => set({ enforceProtections: v })} /></Item>
          <Item title="Score on toolbar icon" hint="Show the trust score as a badge."><Switch label="Toolbar badge" checked={prefs.showBadge} onChange={(v) => set({ showBadge: v })} /></Item>
        </Section>

        <Section id="sync" title="Sync & devices" desc="History and settings follow your Google account across every browser where Ssense is installed.">
          <Item title="Sync my data" hint="Audit results, scan status, visit counts and these settings. Page content is never synced."><Switch label="Sync" checked={prefs.syncEnabled} onChange={(v) => { set({ syncEnabled: v }); if (v) void syncNow(); }} /></Item>
          <Item title={sync?.status === 'syncing' ? 'Syncing…' : sync?.status === 'error' ? 'Last sync failed' : sync?.lastSyncAt ? `Synced ${formatRelative(sync.lastSyncAt)}` : 'Not synced yet'}
            hint={sync?.lastError || (sync?.lastSyncAt ? `↑ ${sync.pushed} sent · ↓ ${sync.pulled} received in the last sync` : 'Sync runs automatically every 15 minutes and after each scan.')}>
            <button className="sx-btn sx-btn--sm" onClick={async () => { await syncNow(); show('Sync finished'); }} disabled={!auth.signedIn || !prefs.syncEnabled || sync?.status === 'syncing'}>
              {sync?.status === 'syncing' ? <Spinner size={13} /> : <Icon name="sync" size={13} />} Sync now
            </button>
          </Item>
          <div style={{ padding: '14px 0', display: 'grid', gap: 8 }}>
            <b style={{ fontSize: 14 }}>Your devices</b>
            {devices.length === 0 ? <span className="sx-muted" style={{ fontSize: 12.5 }}>{auth.signedIn ? 'Devices appear after their first sign-in.' : 'Sign in to see your devices.'}</span> : devices.map((d) => (
              <div key={d.device_id} className="sx-kv" style={{ gridTemplateColumns: 'auto 1fr auto', alignItems: 'center', gap: 10 }}>
                <Icon name="device" size={16} /><b className="sx-trunc">{d.device_name || 'Device'}</b>
                <span className="sx-muted" style={{ fontSize: 11.5 }}>{d.last_active_at ? formatRelative(d.last_active_at * 1000) : ''}</span>
              </div>
            ))}
            <small className="sx-muted" style={{ fontSize: 12, lineHeight: 1.5 }}>Phones and tablets: sync works on any Chromium browser that supports extensions and Google sign-in (for example Kiwi Browser on Android). Chrome for Android doesn’t run extensions.</small>
          </div>
        </Section>

        <Section id="appearance" title="Appearance">
          <Item title="Theme" hint="Follow your system or choose one.">
            <div style={{ display: 'flex', gap: 4, padding: 3, borderRadius: 10, background: 'var(--ssense-bg-elevated)' }} role="radiogroup" aria-label="Theme">
              {(['system', 'light', 'dark'] as const).map((t) => (
                <button key={t} role="radio" aria-checked={prefs.theme === t} className="sx-btn sx-btn--sm" style={{ border: 0, background: prefs.theme === t ? 'var(--ssense-bg-surface)' : 'transparent' }} onClick={() => set({ theme: t })}>{t[0].toUpperCase() + t.slice(1)}</button>
              ))}
            </div>
          </Item>
        </Section>

        <Section id="data" title="Privacy & data" desc="Only a site’s public privacy-policy address is sent for auditing. Browsing history, page content and form input never leave your browser.">
          <Item title="Clear history on this device" hint="Removes visited sites and saved audits here. Synced copies stay in your account."><ConfirmButton size="sm" icon="trash" label="Clear local data" confirmLabel="Clear" onConfirm={async () => { await send({ type: 'CLEAR_HISTORY' }); show('Local data cleared'); }} /></Item>
          <Item title="Delete my synced data" hint="Permanently removes your history and settings from the Ssense server. Other devices keep their local copy."><ConfirmButton size="sm" icon="trash" label="Delete cloud data" confirmLabel="Delete" disabled={!auth.signedIn} onConfirm={async () => { const r = await send<any>({ type: 'DELETE_CLOUD_DATA' }); show(r?.success ? 'Cloud data deleted' : r?.error || 'Failed'); }} /></Item>
        </Section>

        <Section id="server" title="Server" desc="Advanced. Only change this if you run your own Ssense server.">
          <Item title="Active server" hint={activeUrl || '…'}><span className="sx-pill sx-tone-muted">{override ? 'Self-hosted' : 'Ssense Cloud'}</span></Item>
          <Item title="Use my own server"><Switch label="Custom server" checked={override} onChange={setOverride} /></Item>
          {override && (
            <div style={{ display: 'grid', gap: 9, padding: '4px 0 14px' }}>
              <input className="sx-input sx-mono" value={serverUrl} onChange={(e) => setServerUrl(e.target.value)} placeholder="https://your-server.example.com" aria-label="Server URL" spellCheck={false} />
              <input className="sx-input sx-mono" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="API key" aria-label="API key" autoComplete="off" />
              <input className="sx-input sx-mono" type="password" value={hmac} onChange={(e) => setHmac(e.target.value)} placeholder="HMAC secret" aria-label="HMAC secret" autoComplete="off" />
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, padding: '12px 0', alignItems: 'center' }}>
            <button className="sx-btn sx-btn--primary sx-btn--sm" onClick={saveServer}>Save</button>
            <button className="sx-btn sx-btn--sm" onClick={testConn} disabled={test === 'busy'}>{test === 'busy' ? <Spinner size={13} /> : null} Test connection</button>
            {test === 'ok' && <span className="sx-pill sx-tone-ok"><i />Connected</span>}
            {test === 'fail' && <span className="sx-pill sx-tone-bad"><i />Unreachable</span>}
          </div>
        </Section>

        <Section id="about" title="About">
          <Item title="Ssense — DPDP Privacy Shield" hint="Automated compliance auditing against the Digital Personal Data Protection Act, 2023."><span className="sx-stamp">v{version}</span></Item>
          <Item title="Severity labels" hint="High / medium / low impact groupings are a display aid derived from the violation type; they don’t change the trust score."><span /></Item>
        </Section>
      </main>
      <Toast message={msg} />
    </div>
  );
}
