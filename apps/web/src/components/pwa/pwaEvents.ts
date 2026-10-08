/**
 * Beta events for the native-app decision (#56) that come from the installed app and the service
 * worker: `pwa_installed` and `push_opened`. Platform only, never an identity (D10, D11). Every
 * send goes through `trackEvent`, so nothing is queued before the person accepted the consent
 * screen, and nothing at all outside a beta build.
 *
 * `pwa_installed` is counted once per browser: on the `appinstalled` event, or on the first launch
 * in standalone mode (iOS never fires `appinstalled`, and a PWA installed before the person gave
 * consent would otherwise never be counted). `sc-pwa-installed` in localStorage remembers that it
 * was sent. It is only written when the event was really queued, so a launch before consent is
 * counted on a later launch.
 */
import { isTrackingEnabled, subscribeTrackingConsent, trackEvent } from "@/features/seo/track";
import { detectPlatform } from "@/lib/platform";

export const INSTALLED_KEY = "sc-pwa-installed";
/** The message `public/sw.js` posts to every open page when a push notification is tapped. */
export const PUSH_OPENED_MESSAGE = "sc-push-opened";

/** Fallback when storage is blocked: at most one report per page load. */
let sentThisLoad = false;

function readFlag(): boolean {
  try {
    return window.localStorage.getItem(INSTALLED_KEY) === "1";
  } catch {
    return false;
  }
}

function writeFlag(): void {
  try {
    window.localStorage.setItem(INSTALLED_KEY, "1");
  } catch {
    // Blocked storage: `sentThisLoad` still stops a second report on this page.
  }
}

/** Test helper: forget that this page load already reported an install. */
export function resetPwaEventsForTests(): void {
  sentThisLoad = false;
}

/** Sends `pwa_installed` once per browser. Returns true when it was sent now. */
export function reportInstalled(): boolean {
  if (typeof window === "undefined" || sentThisLoad || readFlag()) return false;
  if (!isTrackingEnabled()) return false; // not consented yet: try again on a later launch
  trackEvent("pwa_installed", { platform: detectPlatform() });
  writeFlag();
  sentThisLoad = true;
  return true;
}

/** True when the page runs as an installed app (display-mode standalone, or iOS home screen). */
export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  const ios = (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return ios || Boolean(window.matchMedia?.("(display-mode: standalone)").matches);
}

/** Sends `push_opened` for a tapped notification. */
export function reportPushOpened(): void {
  trackEvent("push_opened", { platform: detectPlatform() });
}

/** Starts listening; returns the cleanup. Safe to call where `navigator.serviceWorker` is absent. */
export function startPwaEvents(): () => void {
  if (typeof window === "undefined") return () => undefined;

  const onInstalled = () => {
    reportInstalled();
  };
  window.addEventListener("appinstalled", onInstalled);

  // First standalone launch, now or as soon as the person has accepted the consent screen.
  const launch = () => {
    if (isStandalone()) reportInstalled();
  };
  launch();
  const unsubscribe = subscribeTrackingConsent(launch);

  const onMessage = (event: MessageEvent) => {
    const data: unknown = event.data;
    if (typeof data === "object" && data !== null && "type" in data) {
      if ((data as { type: unknown }).type === PUSH_OPENED_MESSAGE) reportPushOpened();
    }
  };
  const sw = "serviceWorker" in navigator ? navigator.serviceWorker : undefined;
  sw?.addEventListener("message", onMessage);

  return () => {
    window.removeEventListener("appinstalled", onInstalled);
    unsubscribe();
    sw?.removeEventListener("message", onMessage);
  };
}
