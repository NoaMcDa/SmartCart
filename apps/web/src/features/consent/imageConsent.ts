"use client";

import { useSyncExternalStore } from "react";

/**
 * Consent to read photos of receipts and handwritten lists on our server (issues #61 and #68,
 * decision D11: purchase data is sensitive, so there is an explicit yes before the first upload,
 * and the person can withdraw it).
 *
 * localStorage["sc-image-consent-v1"] = "1" means yes. Absent means not asked or withdrawn: the
 * upload code makes no request without it. The key is in `CORE_DATA_KEYS`
 * (features/profile/storage.ts), so "מחקי את הנתונים שלי" removes it and fires a `storage` event,
 * which `useImageConsent` hears. When storage is unavailable (private window) the answer is kept
 * in memory for the page session.
 */
export const IMAGE_CONSENT_KEY = "sc-image-consent-v1";

let memory: boolean | undefined;
const listeners = new Set<() => void>();

export function getImageConsent(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(IMAGE_CONSENT_KEY) === "1";
  } catch {
    return memory === true;
  }
}

export function setImageConsent(granted: boolean): void {
  try {
    if (granted) window.localStorage.setItem(IMAGE_CONSENT_KEY, "1");
    else window.localStorage.removeItem(IMAGE_CONSENT_KEY);
    memory = undefined;
  } catch {
    memory = granted;
  }
  for (const listener of listeners) listener();
}

export function subscribeImageConsent(listener: () => void): () => void {
  listeners.add(listener);
  // Another tab, or "delete my data", changed it.
  const onStorage = (e: StorageEvent) => {
    if (e.key === null || e.key === IMAGE_CONSENT_KEY) listener();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

/** Test helper: forget the in-memory fallback and the listeners. */
export function resetImageConsentForTests(): void {
  memory = undefined;
  listeners.clear();
}

/** The consent as React state; false on the server and in the first client render. */
export function useImageConsent(): boolean {
  return useSyncExternalStore(subscribeImageConsent, getImageConsent, () => false);
}
