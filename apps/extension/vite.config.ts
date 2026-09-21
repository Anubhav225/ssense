import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));

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
    const missing = ['VITE_SSENSE_SERVER_URL', 'VITE_SSENSE_API_KEY', 'VITE_SSENSE_HMAC_SECRET']
      .filter((k) => !env[k]);
    if (missing.length) {
      throw new Error(
        `Production build is missing: ${missing.join(', ')}. ` +
        `Copy .env.production.example to .env.production and fill in the values ` +
        `matching your deployed server's SSENSE_API_KEYS/SSENSE_HMAC_SECRET.`
      );
    }
  }

  return {
  plugins: [react()],
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