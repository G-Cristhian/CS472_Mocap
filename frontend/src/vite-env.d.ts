/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend API base URL (src/lib/api.ts); defaults to http://localhost:8000 */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
