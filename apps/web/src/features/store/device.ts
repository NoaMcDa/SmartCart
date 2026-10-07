import { useEffect, useSyncExternalStore } from "react";

function subscribeOnline(listener: () => void) {
  window.addEventListener("online", listener);
  window.addEventListener("offline", listener);
  return () => {
    window.removeEventListener("online", listener);
    window.removeEventListener("offline", listener);
  };
}

/** Browser connectivity (a hint, not a guarantee). Server and first paint assume online. */
export function useOnline(): boolean {
  return useSyncExternalStore(
    subscribeOnline,
    () => navigator.onLine,
    () => true,
  );
}

type WakeLockSentinelLike = { release: () => Promise<void> };

/**
 * Keeps the screen awake while `active`, where the Wake Lock API exists (not in every browser).
 * The lock is released when the tab is hidden by the browser, so it is requested again when the
 * tab becomes visible. Failures are ignored: the checklist works with the screen off too.
 */
export function useWakeLock(active: boolean): void {
  useEffect(() => {
    if (!active) return;
    const nav = navigator as Navigator & {
      wakeLock?: { request: (type: "screen") => Promise<WakeLockSentinelLike> };
    };
    if (!nav.wakeLock) return;
    let sentinel: WakeLockSentinelLike | null = null;
    let cancelled = false;
    const acquire = () => {
      nav.wakeLock
        ?.request("screen")
        .then((s) => {
          if (cancelled) void s.release().catch(() => undefined);
          else sentinel = s;
        })
        .catch(() => undefined);
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") acquire();
    };
    acquire();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisible);
      void sentinel?.release().catch(() => undefined);
    };
  }, [active]);
}

/** Name of the service worker's page cache (public/sw.js, PAGES_CACHE). */
const PAGES_CACHE = "sc-pages-v1";

/**
 * Makes sure the store-mode page itself is in the service worker's page cache, so a reload with no
 * network still opens it even if the user got here through client-side navigation (the worker only
 * caches full navigations). Best effort: no worker, no Cache API, or a different cache version
 * simply means no extra copy.
 */
export async function warmStoreModePage(): Promise<void> {
  try {
    if (!("caches" in window)) return;
    const cache = await caches.open(PAGES_CACHE);
    await cache.add(new Request("/store-mode", { credentials: "same-origin" }));
  } catch {
    /* best effort */
  }
}
