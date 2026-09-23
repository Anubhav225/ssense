// apps/extension/src/config.ts
//
// Dynamic Domain & Connection Configuration
// The default server URL is injected from the VITE_SSENSE_SERVER_URL environment variable
// (e.g. Cloudflare Tunnel URL, lab server domain, or local development server).

/** Default server URL baked in from build environment variable (VITE_SSENSE_SERVER_URL). */
export const DEFAULT_SERVER_URL: string = import.meta.env.VITE_SSENSE_SERVER_URL || 'http://localhost:8000';

/** Local loopback fallback for direct container dev. */
export const LOCAL_SERVER_URL: string = 'http://localhost:8000';

export type ServerMode = 'auto' | 'local' | 'online';

export const DEFAULT_SERVER_MODE: ServerMode = 'auto';

export function urlForMode(mode: Exclude<ServerMode, 'auto'>): string {
  return mode === 'local' ? LOCAL_SERVER_URL : DEFAULT_SERVER_URL;
}

