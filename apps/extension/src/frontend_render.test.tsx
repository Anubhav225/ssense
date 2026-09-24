// apps/extension/src/frontend_render.test.tsx
import { act } from 'react';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { createRoot } from 'react-dom/client';
import './ui/mock-chrome';
import { Popup } from './popup/Popup';
import Options from './options/Options';
import { Welcome } from './welcome/Welcome';
import App from './sidebar/App';

// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

describe('Frontend Surfaces Local Integration Tests', () => {
  let container: HTMLDivElement;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  afterEach(() => {
    document.body.removeChild(container);
  });

  it('renders Welcome onboarding screen successfully', async () => {
    const root = createRoot(container);
    await act(async () => {
      root.render(<Welcome />);
    });
    await new Promise((r) => setTimeout(r, 50));

    expect(container.textContent).toContain('Ssense');
    expect(container.textContent).toContain('DPDP Act 2023');
    expect(container.textContent).toContain('Scan sites automatically');
  });

  it('renders Popup interface with tabs and active site', async () => {
    const root = createRoot(container);
    await act(async () => {
      root.render(<Popup />);
    });
    await new Promise((r) => setTimeout(r, 50));

    expect(container.textContent).toContain('This site');
    expect(container.textContent).toContain('All sites');
    expect(container.textContent).toContain('zomato.com');
    expect(container.textContent).toContain('Compliant');
  });

  it('renders Options / Settings page with all sections', async () => {
    const root = createRoot(container);
    await act(async () => {
      root.render(<Options />);
    });
    await new Promise((r) => setTimeout(r, 50));

    expect(container.textContent).toContain('Settings');
    expect(container.textContent).toContain('Account');
    expect(container.textContent).toContain('Scanning');
    expect(container.textContent).toContain('Sync & devices');
    expect(container.textContent).toContain('Appearance');
    expect(container.textContent).toContain('Server');
    expect(container.textContent).toContain('anubhavdas11c05@gmail.com');
  });

  it('renders Sidebar App interface with DPDP navigation', async () => {
    const root = createRoot(container);
    await act(async () => {
      root.render(<App />);
    });
    await new Promise((r) => setTimeout(r, 50));

    expect(container.textContent).toBeTruthy();
  });
});
