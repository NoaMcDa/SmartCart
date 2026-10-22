/**
 * Local storage keys owned by the secondary screens, and safe accessors. Every access is wrapped
 * in try/catch: storage can be missing or throw (private window, blocked site data, SSR).
 * "Delete my data" removes every key listed in LOCAL_DATA_KEYS.
 */
import {
  readJson as stateReadJson,
  removeKey as stateRemoveKey,
  writeJson as stateWriteJson,
} from "@/state/storage";

export { readRaw, writeRaw } from "@/state/storage";

export const STORAGE_KEYS = {
  /** LocalProfile (features/profile/profileState.ts). */
  profile: "sc-profile",
  /** ShoppingSession: the in-store checklist, cached for offline use. */
  shopping: "sc-shopping",
  /** SavingsEntry[]: realized savings, written by "סיימתי" in store mode. */
  savings: "sc-savings-history",
  /** SpendStore: shops recorded by "סיימתי לקנות" (features/budget/spendState.ts, issue #70). */
  spend: "sc-spend-v1",
  /** StoredBudget: the monthly budget in ILS (features/budget/budgetState.ts, issue #70). */
  budget: "sc-budget-v1",
} as const;

/**
 * Keys owned by the core screens (W4b: `src/state/list.ts` LIST_KEY and `src/state/shopper.ts`
 * PROFILE_KEY) that also hold personal data, so "delete my data" removes them as well.
 */
export const CORE_DATA_KEYS: ReadonlyArray<string> = [
  "sc-list-v1",
  "sc-profile-v1",
  // Photo consent (features/consent/imageConsent.ts, issues #61 and #68).
  "sc-image-consent-v1",
  // Shared lists this device owns or joined (features/share/sharedLists.ts) and the edits still
  // waiting to be sent, which hold item names (features/share/offlineQueue.ts).
  "sc-shared-lists-v1",
  "sc-shared-queue-v1",
  // Names remembered for price alerts (features/alerts/alertNames.ts).
  "sc-alert-names-v1",
  // Scan counters and the store the shopper picked (features/scan/scanLog.ts, scan/stores.ts).
  "sc-scan-log-v1",
  "sc-scan-store-v1",
  // Dismissed swap suggestions (features/swaps/swapState.ts).
  "sc-swaps-v1",
  // What the app learned from the person's own lists and finished trips, and the two
  // personalization preferences (features/personal/personalState.ts).
  "sc-personal-v1",
  // The random id that ties usage events to one browser (features/seo/track.ts): deleting the data
  // starts a new one. The yes or no answer about events (`sc-events-consent`) is a setting and stays.
  "sc-session",
];

export const LOCAL_DATA_KEYS: ReadonlyArray<string> = [
  ...Object.values(STORAGE_KEYS),
  ...CORE_DATA_KEYS,
];

export function readJson<T>(key: string): T | null {
  return stateReadJson<T | null>(key, null);
}

export function writeJson(key: string, value: unknown): boolean {
  return stateWriteJson(key, value);
}

export function removeKey(key: string): void {
  stateRemoveKey(key);
}

/** Removes everything the secondary screens persisted. The theme choice is a device setting and stays. */
export function clearLocalData(): void {
  for (const key of LOCAL_DATA_KEYS) removeKey(key);
  // The core screens' stores re-read their key on a storage event.
  for (const key of CORE_DATA_KEYS) {
    try {
      window.dispatchEvent(new StorageEvent("storage", { key }));
    } catch {
      /* no StorageEvent constructor: they pick the change up on the next load */
    }
  }
  notifyStorageChange();
}

type Listener = () => void;
const listeners = new Set<Listener>();

/** Same-tab change notification (the `storage` event only fires in other tabs). */
export function subscribeStorage(listener: Listener): () => void {
  listeners.add(listener);
  const onStorage = () => listener();
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function notifyStorageChange(): void {
  for (const l of listeners) l();
}
