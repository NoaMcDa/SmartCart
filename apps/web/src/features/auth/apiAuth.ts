/**
 * Attaches the Supabase access token to API calls without editing src/api/client.ts.
 *
 * `api` (openapi-fetch) supports middleware, so `ensureApiAuth()` registers one `onRequest` hook
 * (once) that sets `Authorization: Bearer <token>` whenever a token is set. AuthProvider calls
 * `setApiToken` on every session change. The mock handlers ignore the header, and the basket
 * routes ignore it too (anonymous callers are fine; /feedback/* record the user id when present).
 *
 * Any code that makes a call needing identity (/me/*, /feedback/*) calls `ensureApiAuth()` first;
 * it is idempotent and cheap. The root layout mounts AuthProvider, which does it for the whole
 * client session.
 */
import { api } from "@/api/client";

let token: string | null = null;
let installed = false;

export function setApiToken(next: string | null): void {
  token = next;
}

export function getApiToken(): string | null {
  return token;
}

export function ensureApiAuth(): void {
  if (installed) return;
  installed = true;
  api.use({
    onRequest({ request }) {
      if (token && !request.headers.has("Authorization")) {
        request.headers.set("Authorization", `Bearer ${token}`);
      }
      return request;
    },
  });
}
