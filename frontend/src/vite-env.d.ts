/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend API base URL (src/lib/api.ts); defaults to http://localhost:8000 */
  readonly VITE_API_URL?: string
  /** Supabase project URL and publishable key (src/lib/clips.ts); uploads are off without them */
  readonly VITE_SUPABASE_URL?: string
  readonly VITE_SUPABASE_PUBLISHABLE_KEY?: string
  readonly VITE_SUPABASE_SECRET_KEY?: string
  /** Django accounts API (src/lib/auth.ts); defaults to http://localhost:8000 */
  readonly VITE_DJANGO_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
