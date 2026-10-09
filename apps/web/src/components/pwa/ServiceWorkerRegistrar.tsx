"use client";

import { useEffect } from "react";
import { startPwaEvents } from "./pwaEvents";

/**
 * Registers public/sw.js in production builds. Skipped in `next dev` (a caching worker fights
 * hot reload) and when NEXT_PUBLIC_DISABLE_SW=1. In dev, any previously installed worker is
 * removed so a stale production worker cannot serve old pages.
 */
export function ServiceWorkerRegistrar() {
  // Beta events for the native-app decision (#56): install and a tapped push notification.
  useEffect(() => startPwaEvents(), []);

  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const enabled =
      process.env.NODE_ENV === "production" && process.env.NEXT_PUBLIC_DISABLE_SW !== "1";
    if (!enabled) {
      navigator.serviceWorker
        .getRegistrations()
        .then((regs) =>
          regs.forEach((r) => r.active?.scriptURL.endsWith("/sw.js") && r.unregister()),
        )
        .catch(() => {});
      return;
    }
    const register = () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch((err: unknown) => {
        console.warn("SmartCart: service worker registration failed", err);
      });
    };
    if (document.readyState === "complete") register();
    else {
      window.addEventListener("load", register, { once: true });
      return () => window.removeEventListener("load", register);
    }
  }, []);
  return null;
}
