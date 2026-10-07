/**
 * Supabase client for sign-in. Configured from NEXT_PUBLIC_SUPABASE_URL and
 * NEXT_PUBLIC_SUPABASE_ANON_KEY (inlined at build time; the anon key is public by design, row
 * level security protects the data). Without both variables `loadSupabase()` resolves to null and
 * the app runs signed out: mock mode and local development need no Supabase project.
 *
 * supabase-js stores the session itself (localStorage, key `sb-<project>-auth-token`) and refreshes
 * the token; this module never touches it.
 */
import type { SupabaseClient } from "@supabase/supabase-js";

const URL_ = process.env.NEXT_PUBLIC_SUPABASE_URL;
const ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

let client: SupabaseClient | null | undefined;

export function isSupabaseConfigured(): boolean {
  if (client !== undefined) return client !== null;
  return Boolean(URL_ && ANON_KEY);
}

/** The client if it is already loaded, else null. Use `loadSupabase()` to wait for it. */
export function getSupabase(): SupabaseClient | null {
  return client ?? null;
}

let loading: Promise<SupabaseClient | null> | undefined;

/**
 * Loads supabase-js on demand and creates the client. The library (about 250 KB before gzip) is a
 * separate chunk, fetched only in a build that has the Supabase variables, so the SEO pages and
 * every mock or local build never download it even though AuthProvider sits in the root layout.
 * Resolves to null without configuration or on the server.
 */
export function loadSupabase(): Promise<SupabaseClient | null> {
  if (client !== undefined) return Promise.resolve(client);
  if (typeof window === "undefined") return Promise.resolve(null); // the browser builds its own
  if (!URL_ || !ANON_KEY) {
    client = null;
    return Promise.resolve(null);
  }
  loading ??= import("@supabase/supabase-js").then(({ createClient }) => {
    client ??= createClient(URL_, ANON_KEY, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
    });
    return client;
  });
  return loading;
}

/** Test hook: inject a fake client (or null to simulate no configuration). */
export function setSupabaseForTests(next: SupabaseClient | null | undefined): void {
  client = next;
  loading = undefined;
}
