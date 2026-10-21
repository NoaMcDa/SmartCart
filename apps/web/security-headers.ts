/**
 * Security headers for every response of the web app (docs/security-review.md, section "Web").
 * `next.config.ts` serves them; `src/security/securityHeaders.test.ts` pins them down, and
 * `tests/e2e/security-headers.spec.ts` checks them on the production build.
 *
 * Content-Security-Policy, directive by directive, and why:
 *
 * - `default-src 'self'`: nothing loads from anywhere else unless a directive below says so.
 * - `script-src 'self' 'unsafe-inline'`: the app's own chunks, plus the inline scripts that Next
 *   itself emits into every page (the flight data `self.__next_f.push(...)` and the bootstrap) and
 *   the two first-paint scripts in `app/layout.tsx` (theme and locale, which must run before the
 *   first paint). A nonce or hash policy needs every page rendered per request, which would end
 *   the static SEO pages (docs/seo.md). The cost is that an injected inline script would run; what
 *   stays closed is a script from any other origin, `eval` (not allowed in production), `<object>`,
 *   `<base>` and a forged `<form action>`. The app renders no user-supplied HTML (React escapes
 *   text; the JSON-LD blocks escape `<`). Dev adds 'unsafe-eval' (React's debugging needs it).
 * - `style-src 'self' 'unsafe-inline'`: Next and React write `<style>` and `style=""` (the map
 *   fallback and the progress bars set CSS variables inline).
 * - `img-src 'self' data: blob: https://tile.openstreetmap.org`: icons, `blob:` for the photo and
 *   scan previews, OpenStreetMap raster tiles for the map.
 * - `font-src 'self'`: Heebo and Noto Sans Arabic are self-hosted (`next/font/local`); nothing
 *   reaches fonts.googleapis.com or fonts.gstatic.com.
 * - `connect-src`: the API origin (`NEXT_PUBLIC_API_BASE_URL`), Supabase over https and wss when
 *   configured (`NEXT_PUBLIC_SUPABASE_URL`: auth, PostgREST, Realtime), the tile origin (MapLibre
 *   fetches tiles with fetch), and in dev the HMR websocket.
 * - `worker-src 'self' blob:`: the service worker (`/sw.js`) and MapLibre's worker, which it makes
 *   from a blob.
 * - `manifest-src 'self'`, `media-src 'self' blob:`, `frame-src 'none'`, `object-src 'none'`.
 * - `base-uri 'self'`, `form-action 'self'`, `frame-ancestors 'none'` (and `X-Frame-Options: DENY`
 *   for browsers that predate it): the page cannot be framed, re-based or posted elsewhere.
 *
 * Permissions-Policy: the camera (barcode scan, photo of a receipt), the microphone (voice list)
 * and geolocation (neighborhood location) are for this origin only, everything else is off.
 *
 * Referrer-Policy `strict-origin-when-cross-origin`: other origins get our origin and no path (the
 * invite link and the beta code are in the path), and OpenStreetMap still gets the referrer its
 * tile usage policy requires (`no-referrer` would get the tiles blocked).
 *
 * HSTS: one year, subdomains, no `preload` (that is a commitment to make with the domain's owner).
 */

export type HeaderEnv = {
  /** NODE_ENV */
  nodeEnv?: string;
  /** NEXT_PUBLIC_API_BASE_URL, or the default local API when unset (src/api/config.ts) */
  apiBaseUrl?: string;
  /** NEXT_PUBLIC_SUPABASE_URL */
  supabaseUrl?: string;
};

export const TILE_ORIGIN = "https://tile.openstreetmap.org";
export const DEFAULT_API_BASE_URL = "http://localhost:8000";

function origin(url: string | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:" ? u.origin : null;
  } catch {
    return null;
  }
}

function websocketOrigin(httpOrigin: string): string {
  return httpOrigin.replace(/^http/, "ws");
}

export function contentSecurityPolicy(env: HeaderEnv = {}): string {
  const dev = env.nodeEnv === "development";
  const api = origin(env.apiBaseUrl ?? DEFAULT_API_BASE_URL);
  const supabase = origin(env.supabaseUrl);
  const connect = new Set<string>(["'self'", TILE_ORIGIN]);
  if (api) connect.add(api);
  if (supabase) {
    connect.add(supabase);
    connect.add(websocketOrigin(supabase)); // Realtime
  }
  if (dev) {
    connect.add("ws://localhost:*");
    connect.add("ws://127.0.0.1:*");
  }
  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    "script-src": ["'self'", "'unsafe-inline'", ...(dev ? ["'unsafe-eval'"] : [])],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:", "blob:", TILE_ORIGIN],
    "font-src": ["'self'"],
    "connect-src": [...connect],
    "worker-src": ["'self'", "blob:"],
    "manifest-src": ["'self'"],
    "media-src": ["'self'", "blob:"],
    "frame-src": ["'none'"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
  };
  return Object.entries(directives)
    .map(([name, values]) => `${name} ${values.join(" ")}`)
    .join("; ");
}

export const PERMISSIONS_POLICY = [
  "camera=(self)",
  "microphone=(self)",
  "geolocation=(self)",
  "payment=()",
  "usb=()",
  "serial=()",
  "bluetooth=()",
  "midi=()",
  "magnetometer=()",
  "gyroscope=()",
  "accelerometer=()",
  "display-capture=()",
  "interest-cohort=()",
  "browsing-topics=()",
].join(", ");

export type Header = { key: string; value: string };

export function securityHeaders(env: HeaderEnv = {}): Header[] {
  return [
    { key: "Content-Security-Policy", value: contentSecurityPolicy(env) },
    { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Permissions-Policy", value: PERMISSIONS_POLICY },
    { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
    { key: "X-Permitted-Cross-Domain-Policies", value: "none" },
  ];
}

/**
 * The mock API answers every request with invented prices (docs/web.md). It is a test and demo
 * switch: a production deployment that has it on would show made-up prices to real people, so the
 * build refuses. A production build is one that `deploy.yml` makes (`SEO_STRICT_SITE_URL=1`) or
 * that Vercel marks as production.
 */
export function assertNoMockInProduction(env: Readonly<Record<string, string | undefined>>): void {
  const production = env.SEO_STRICT_SITE_URL === "1" || env.VERCEL_ENV === "production";
  if (production && env.NEXT_PUBLIC_API_MOCK === "1") {
    throw new Error(
      "NEXT_PUBLIC_API_MOCK=1 in a production build: the app would show invented prices. " +
        "Unset it (docs/deploy.md).",
    );
  }
}
