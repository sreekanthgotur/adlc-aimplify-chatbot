interface ImportMetaEnv {
  readonly MODE: string;
  readonly VITE_API_ORIGIN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}