/**
 * Local storage keys owned by the secondary screens, and safe accessors. Every access is wrapped
 * in try/catch: storage can be missing or throw (private window, blocked site data, SSR).
 * "Delete my data" removes every key listed in LOCAL_DATA_KEYS.
 */
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
export const CORE_DATA_KEYS: ReadonlyArray<string> = ["sc-list-v1", "sc-profile-v1"];

export const LOCAL_DATA_KEYS: ReadonlyArray<string> = [
  ...Object.values(STORAGE_KEYS),
  ...CORE_DATA_KEYS,
];

export function readJson<T>(key: string): T | null {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? null : (JSON.parse(raw) as T);
  } catch {
    return null;
  }
}

export function writeJson(key: string, value: unknown): boolean {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function removeKey(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* nothing to remove */
  }
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
