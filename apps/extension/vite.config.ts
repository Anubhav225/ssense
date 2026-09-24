import { defineConfig, loadEnv, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { fileURLToPath } from 'url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));

/** Fills the Google OAuth client id (and optional pinned extension key) into dist/manifest.json. */
function manifestPlugin(env: Record<string, string>): Plugin {
  return {
    name: 'ssense-manifest',
    apply: 'build',
    closeBundle() {
      const file = resolve(__dirname, 'dist/manifest.json');
      if (!existsSync(file)) return;
      const m = JSON.parse(readFileSync(file, 'utf8'));
      const id = env.VITE_GOOGLE_CLIENT_ID;
      if (id) m.oauth2.client_id = id;
      else { delete m.oauth2; console.warn('[ssense] VITE_GOOGLE_CLIENT_ID not set — Google sign-in will be unavailable in this dev build.'); }
      // A stable extension id is required for a Chrome-app OAuth client during development.
      if (env.VITE_EXTENSION_KEY) m.key = env.VITE_EXTENSION_KEY;
      writeFileSync(file, JSON.stringify(m, null, 2));
    },
  };
}

export default defineConfig(({ mode }) => {
  // Vite already auto-loads .env.production (or .env.development in dev)
  // based on `mode` - this explicit loadEnv call is just so we can validate
  // the values below at build time, not to change how they're read.
  const env = loadEnv(mode, __dirname, 'VITE_');

  // Fail the build loudly instead of silently shipping an extension that
  // can't reach any server. Dev builds get a working localhost default;
  // production builds must have the real values baked in via
  // .env.production (copy .env.production.example and fill it in).
  if (mode === 'production') {
    // Users get their own API key + HMAC secret when they sign in with Google, so no
    // shared credentials are baked in any more. What the build DOES need is the server
    // to talk to and the Google OAuth client the manifest declares.
    const missing = ['VITE_SSENSE_SERVER_URL', 'VITE_GOOGLE_CLIENT_ID'].filter((k) => !env[k]);
    if (missing.length) {
      throw new Error(
        `Production build is missing: ${missing.join(', ')}. ` +
        `Copy .env.production.example to .env.production and fill in the values.`
      );
    }
    if (/localhost|127\.0\.0\.1/.test(env.VITE_SSENSE_SERVER_URL)) {
      throw new Error('VITE_SSENSE_SERVER_URL points at localhost — a store build must use your public HTTPS server.');
    }
  }

  return {
  plugins: [react(), manifestPlugin(env)],
  base: '',
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
    // 🚀 SOTA FIX: Prevent Vite from injecting module preloads into content scripts
    modulePreload: { polyfill: false },
    // 🚀 SOTA FIX: Forces all CSS into a single style.css file for easy manifest.json injection
    cssCodeSplit: false,
    rollupOptions: {
      input: {
        sidepanel: resolve(__dirname, 'sidepanel.html'),
        options: resolve(__dirname, 'options.html'),
        popup: resolve(__dirname, 'popup.html'),
        welcome: resolve(__dirname, 'welcome.html'),
        'background/service-worker': resolve(__dirname, 'src/background/service-worker.ts'),
        'content/extractor': resolve(__dirname, 'src/content/extractor.ts'),
        'content/dark-pattern-blocker': resolve(__dirname, 'src/content/dark-pattern-blocker.ts'),
        'content/chat-widget': resolve(__dirname, 'src/content/chat-widget.ts'),
        'content/api-spoof': resolve(__dirname, 'src/content/api-spoof.ts'),
      },
      output: {
        // Manifest V3 requires exact filenames for background/content scripts. No hashing allowed here.
        entryFileNames: '[name].js',
        // React chunks and assets can be safely hashed since HTML loads them dynamically
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]'
      },
    },
  },
  };
});