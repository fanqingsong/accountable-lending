/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_LENDING_API_BASE: string;
  readonly VITE_LENDING_EXPLORER_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
