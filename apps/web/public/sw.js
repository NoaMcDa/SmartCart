/* SmartCart service worker (hand-written; see docs/web.md "PWA and offline" for why).
 *
 * - install: precache the app shell. Fetches "/" and "/offline", stores them, then parses their HTML
 *   (and the CSS they link) for /_next/static assets (JS chunks, CSS, the Heebo woff2 files) and
 *   precaches those too. This works with any bundler output, so Turbopack builds need no plugin.
 * - fetch:
 *     navigations           network first, cache the response; offline -> cached page -> /offline -> "/"
 *     /_next/static, fonts,  cache first (content-hashed, immutable)
 *     icons
 *     manifest              network first, cached copy offline
 *     anything else         network only (API calls are cross-origin and never cached here)
 * - activate: drop caches from older versions, take control of open pages.
 * - push: price-drop alerts (issue #23). The payload is JSON {title, body, url, tag, product, store,
 *   price, updated_at}; without `body` one is composed from the parts. The notification always says
 *   that the price at checkout governs. notificationclick opens (or focuses) the product page.
 */
const VERSION = "v1";
const SHELL_CACHE = `sc-shell-${VERSION}`;
const PAGES_CACHE = `sc-pages-${VERSION}`;
const ASSETS_CACHE = `sc-assets-${VERSION}`;
const KEEP = [SHELL_CACHE, PAGES_CACHE, ASSETS_CACHE];

const SHELL_PAGES = ["/", "/offline"];
const SHELL_FILES = [
  "/manifest.webmanifest",
  "/icons/icon.svg",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/apple-touch-icon.png",
];

function staticRefs(text) {
  const out = new Set();
  const re = /\/_next\/static\/[^"'()\s\\]+/g;
  let m;
  while ((m = re.exec(text))) out.add(m[0].replace(/&amp;/g, "&"));
  return out;
}

async function precacheShell() {
  const shell = await caches.open(SHELL_CACHE);
  await shell.addAll(SHELL_FILES);
  const assets = new Set();
  for (const page of SHELL_PAGES) {
    const res = await fetch(page, { cache: "no-store", credentials: "same-origin" });
    if (!res.ok) throw new Error(`precache ${page}: ${res.status}`);
    const html = await res.clone().text();
    await shell.put(page, res);
    staticRefs(html).forEach((u) => assets.add(u));
  }
  // CSS references the font files; follow one level.
  for (const url of Array.from(assets)) {
    if (!url.endsWith(".css")) continue;
    try {
      const css = await (await fetch(url)).text();
      staticRefs(css).forEach((u) => assets.add(u));
    } catch {
      /* best effort */
    }
  }
  const cache = await caches.open(ASSETS_CACHE);
  await Promise.all(
    Array.from(assets).map((u) => cache.add(u).catch(() => undefined)),
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(precacheShell().then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(names.filter((n) => n.startsWith("sc-") && !KEEP.includes(n)).map((n) => caches.delete(n)));
      await self.clients.claim();
    })(),
  );
});

function isImmutableAsset(url) {
  return (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/fonts/") ||
    url.pathname.startsWith("/icons/")
  );
}

async function cacheFirst(request) {
  const hit = await caches.match(request);
  if (hit) return hit;
  const res = await fetch(request);
  if (res.ok) {
    const cache = await caches.open(ASSETS_CACHE);
    cache.put(request, res.clone());
  }
  return res;
}

async function networkFirstPage(request) {
  try {
    const res = await fetch(request);
    if (res.ok && res.type === "basic") {
      const cache = await caches.open(PAGES_CACHE);
      cache.put(request, res.clone());
    }
    return res;
  } catch (err) {
    const cached =
      (await caches.match(request, { ignoreSearch: true })) ||
      (await caches.match("/offline")) ||
      (await caches.match("/"));
    if (cached) return cached;
    throw err;
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  // React Server Component payloads for client-side navigation: let them fail offline so the
  // router falls back to a full navigation, which the navigate branch below serves.
  if (request.headers.get("RSC") === "1" || url.searchParams.has("_rsc")) return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirstPage(request));
    return;
  }
  if (isImmutableAsset(url)) {
    event.respondWith(cacheFirst(request));
    return;
  }
  if (url.pathname === "/manifest.webmanifest") {
    event.respondWith(fetch(request).catch(() => caches.match(request)));
  }
});

// ---- Web push (price alerts) -------------------------------------------------------------------

const DEFAULT_ALERT_URL = "/alerts";
const CHECKOUT_NOTE = "המחיר הקובע הוא בקופה.";

/** Only same-origin paths are ever opened from a notification. */
function safeUrl(raw) {
  try {
    const url = new URL(raw || DEFAULT_ALERT_URL, self.location.origin);
    return url.origin === self.location.origin ? url.pathname + url.search : DEFAULT_ALERT_URL;
  } catch {
    return DEFAULT_ALERT_URL;
  }
}

function formatUpdated(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const opts = { timeZone: "Asia/Jerusalem" };
  const time = d.toLocaleTimeString("he-IL", { ...opts, hour: "2-digit", minute: "2-digit", hour12: false });
  const date = d.toLocaleDateString("he-IL", { ...opts, day: "2-digit", month: "2-digit" }).replace(/\//g, ".");
  return `${date} ${time}`;
}

function alertBody(data) {
  if (data.body) return String(data.body);
  const parts = [];
  if (data.product) parts.push(String(data.product));
  if (data.store) parts.push(String(data.store));
  if (data.price !== undefined && data.price !== null) parts.push(`₪\u00A0${data.price}`);
  const updated = data.updated_at ? formatUpdated(data.updated_at) : "";
  const head = parts.join(" · ") || "מוצר ברשימת ההתראות שלך הגיע למחיר שביקשת.";
  return [head, updated ? `מחיר מ-${updated}.` : "", CHECKOUT_NOTE].filter(Boolean).join(" ");
}

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : "" };
  }
  const title = data.title ? String(data.title) : "SmartCart · ירידת מחיר";
  event.waitUntil(
    self.registration.showNotification(title, {
      body: alertBody(data),
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      lang: "he",
      dir: "rtl",
      // One notification per alert and price: a second push for the same drop replaces it.
      tag: data.tag ? String(data.tag) : "price-alert",
      data: { url: safeUrl(data.url) },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = safeUrl(event.notification.data && event.notification.data.url);
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of windows) {
        if (new URL(client.url).origin !== self.location.origin) continue;
        await client.focus();
        if ("navigate" in client) await client.navigate(target).catch(() => undefined);
        return;
      }
      await self.clients.openWindow(target);
    })(),
  );
});
