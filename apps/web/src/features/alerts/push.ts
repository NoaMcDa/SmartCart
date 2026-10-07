/**
 * Web push for price alerts (issue #23). The browser asks for permission only after a tap, the
 * subscription (endpoint and keys, never an identity) is stored through `POST /me/push-subscriptions`,
 * and `public/sw.js` shows the notification. Everything is feature-detected: without the VAPID
 * public key (`NEXT_PUBLIC_VAPID_PUBLIC_KEY`, inlined at build time), a service worker or the Push
 * API the app still works and alerts are listed on /alerts.
 */
import { addPushSubscription } from "@/api/client";
import { ensureApiAuth } from "@/features/auth/apiAuth";

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
    const permission = await Notification.requestPermission();
    if (permission !== "granted") return { ok: false, reason: "denied" };
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

/** Stops this device's push subscription. The server drops it on the next failed delivery. */
export async function disablePush(): Promise<void> {
  const sub = await currentSubscription();
  await sub?.unsubscribe().catch(() => false);
}

export const PUSH_MESSAGES: Record<Exclude<PushSupport, "supported"> | "denied" | "error", string> =
  {
    "no-key": "שליחת התראות לדפדפן עוד לא מוגדרת בגרסה הזו. ההתראות נשמרות ויופיעו במסך ההתראות.",
    unsupported: "הדפדפן הזה לא תומך בהתראות דחיפה. ההתראות יופיעו במסך ההתראות.",
    "ios-install":
      "ב-iPhone ובאייפד התראות דחיפה עובדות רק אחרי הוספת האפליקציה למסך הבית (iOS 16.4 ומעלה): בכפתור השיתוף של ספארי בחרי ״הוספה למסך הבית״ ופתחי משם.",
    denied:
      "ההתראות חסומות בדפדפן, ולכן לא נשלח אליך כלום. אפשר לאשר אותן בהגדרות האתר. עד אז ההתראות יופיעו רק במסך ההתראות.",
    error: "לא הצלחנו להפעיל התראות בדפדפן. ההתראות עצמן נשמרו, ואפשר לנסות שוב.",
  };
