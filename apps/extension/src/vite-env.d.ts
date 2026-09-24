/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SSENSE_SERVER_URL?: string;
  readonly VITE_SSENSE_API_KEY?: string;
  readonly VITE_SSENSE_HMAC_SECRET?: string;
  readonly VITE_GOOGLE_CLIENT_ID?: string;
  readonly VITE_GOOGLE_WEB_CLIENT_ID?: string;
  readonly VITE_EXTENSION_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
