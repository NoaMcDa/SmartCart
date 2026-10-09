/**
 * Web push for price alerts (issue #23). The browser asks for permission only after a tap, the
 * subscription (endpoint and keys, never an identity) is stored through `POST /me/push-subscriptions`,
 * and `public/sw.js` shows the notification. Everything is feature-detected: without the VAPID
 * public key (`NEXT_PUBLIC_VAPID_PUBLIC_KEY`, inlined at build time), a service worker or the Push
 * API the app still works and alerts are listed on /alerts.
 */
import { addPushSubscription, deletePushSubscription } from "@/api/client";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { trackEvent } from "@/features/seo/track";
import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { alertMessages, type AlertMessageKey } from "@/i18n/messages/alerts";
import { detectPlatform } from "@/lib/platform";

export const VAPID_PUBLIC_KEY = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY ?? "";

export type PushSupport = "supported" | "no-key" | "unsupported" | "ios-install";

export type PushPermission = "granted" | "denied" | "default" | "unsupported";

export type EnableResult =
  | { ok: true }
  | { ok: false; reason: "denied" | "unsupported" | "no-key" | "ios-install" | "error" };

function isIos(): boolean {
  if (typeof navigator === "undefined") return false;
  return /iPad|iPhone|iPod/.test(navigator.userAgent);
}

/** What this browser, build and installation can do. */
export function pushSupport(key: string = VAPID_PUBLIC_KEY): PushSupport {
  if (typeof window === "undefined") return "unsupported";
  const apis = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  if (!apis) return isIos() ? "ios-install" : "unsupported";
  if (!key) return "no-key";
  return "supported";
}

export function pushPermission(): PushPermission {
  if (typeof window === "undefined" || !("Notification" in window)) return "unsupported";
  return Notification.permission;
}

/** VAPID public keys travel as URL-safe base64; `subscribe` wants the raw bytes. */
export function urlBase64ToUint8Array(value: string): Uint8Array<ArrayBuffer> {
  const padded = value + "=".repeat((4 - (value.length % 4)) % 4);
  const raw = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return out;
}

async function registration(): Promise<ServiceWorkerRegistration | null> {
  if (!("serviceWorker" in navigator)) return null;
  const existing = await navigator.serviceWorker.getRegistration();
  if (existing) return existing;
  // The worker registers in production builds only; do not wait forever in development.
  return Promise.race([
    navigator.serviceWorker.ready,
    new Promise<null>((resolve) => setTimeout(() => resolve(null), 4000)),
  ]);
}

export async function currentSubscription(): Promise<PushSubscription | null> {
  try {
    const reg = await registration();
    return reg ? await reg.pushManager.getSubscription() : null;
  } catch {
    return null;
  }
}

/** Ask for permission (call from a tap), subscribe and store the subscription for this device. */
export async function enablePush(key: string = VAPID_PUBLIC_KEY): Promise<EnableResult> {
  const support = pushSupport(key);
  if (support !== "supported") return { ok: false, reason: support };
  try {
    const before = Notification.permission;
    // The denominator of the opt-in rate (#56): only when the browser will really show its prompt.
    if (before === "default") trackEvent("push_prompt_shown", { platform: detectPlatform() });
    const permission = await Notification.requestPermission();
    if (permission !== "granted") return { ok: false, reason: "denied" };
    // Counted when the permission becomes granted through our button (#56), not when it already was.
    if (before !== "granted") trackEvent("push_opt_in", { platform: detectPlatform() });
    const reg = await registration();
    if (!reg) return { ok: false, reason: "unsupported" };
    const sub =
      (await reg.pushManager.getSubscription()) ??
      (await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(key),
      }));
    const json = sub.toJSON();
    const p256dh = json.keys?.p256dh;
    const auth = json.keys?.auth;
    if (!json.endpoint || !p256dh || !auth) return { ok: false, reason: "error" };
    ensureApiAuth();
    await addPushSubscription({
      endpoint: json.endpoint,
      p256dh,
      auth,
      user_agent: navigator.userAgent.slice(0, 200),
    });
    return { ok: true };
  } catch {
    return { ok: false, reason: "error" };
  }
}

/** Stops this device's push subscription, here and on the server. */
export async function disablePush(): Promise<void> {
  const sub = await currentSubscription();
  if (!sub) return;
  const endpoint = sub.endpoint;
  await sub.unsubscribe().catch(() => false);
  try {
    ensureApiAuth();
    await deletePushSubscription(endpoint);
  } catch {
    // The server drops a dead endpoint on its next failed delivery anyway.
  }
}

export type PushMessageReason = Exclude<PushSupport, "supported"> | "denied" | "error";

const PUSH_MESSAGE_KEYS: Record<PushMessageReason, AlertMessageKey> = {
  "no-key": "pm_no_key",
  unsupported: "pm_unsupported",
  "ios-install": "pm_ios_install",
  denied: "pm_denied",
  error: "pm_error",
};

/** Why push is off or failed, in the UI language (Hebrew by default). */
export function pushMessage(reason: PushMessageReason, locale: Locale = DEFAULT_LOCALE): string {
  return translate(alertMessages, locale, PUSH_MESSAGE_KEYS[reason]);
}

/** The Hebrew texts; `pushMessage(reason, locale)` is the one to show to the user. */
export const PUSH_MESSAGES: Record<PushMessageReason, string> = {
  "no-key": pushMessage("no-key"),
  unsupported: pushMessage("unsupported"),
  "ios-install": pushMessage("ios-install"),
  denied: pushMessage("denied"),
  error: pushMessage("error"),
};
