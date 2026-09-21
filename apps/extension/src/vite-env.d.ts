/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SSENSE_SERVER_URL?: string;
  readonly VITE_SSENSE_API_KEY?: string;
  readonly VITE_SSENSE_HMAC_SECRET?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
