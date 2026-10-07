/**
 * Supabase client for sign-in. Configured from NEXT_PUBLIC_SUPABASE_URL and
 * NEXT_PUBLIC_SUPABASE_ANON_KEY (inlined at build time; the anon key is public by design, row
 * level security protects the data). Without both variables `getSupabase()` returns null and the
 * app runs signed out: mock mode and local development need no Supabase project.
 *
 * supabase-js stores the session itself (localStorage, key `sb-<project>-auth-token`) and refreshes
 * the token; this module never touches it.
 */
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const URL_ = process.env.NEXT_PUBLIC_SUPABASE_URL;
const ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

let client: SupabaseClient | null | undefined;

export function isSupabaseConfigured(): boolean {
  if (client !== undefined) return client !== null;
  return Boolean(URL_ && ANON_KEY);
}

export function getSupabase(): SupabaseClient | null {
  if (client !== undefined) return client;
  if (typeof window === "undefined" || !URL_ || !ANON_KEY) {
    // Do not cache on the server: the browser will build its own.
    if (typeof window !== "undefined") client = null;
    return null;
  }
  client = createClient(URL_, ANON_KEY, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
  });
  return client;
}

/** Test hook: inject a fake client (or null to simulate no configuration). */
export function setSupabaseForTests(next: SupabaseClient | null | undefined): void {
  client = next;
}
