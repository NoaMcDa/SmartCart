/**
 * localStorage access that never throws. Private windows, blocked site data and SSR all make
 * storage unavailable; callers then get the fallback and the app keeps working in memory.
 *
 * A write that fails (quota, a private window whose `setItem` throws) is kept in memory for this
 * page view and read back by `readRaw`, so "kept in memory" holds for every store built on these
 * helpers instead of the value vanishing on the next read. Another tab's change to the key (a
 * `storage` event) drops the in-memory copy: the stored value is newer.
 */
const memory = new Map<string, string | null>();
let watching = false;

function watchOtherTabs() {
  if (watching || typeof window === "undefined") return;
  watching = true;
  window.addEventListener("storage", (e) => {
    if (e.key === null) memory.clear();
    else memory.delete(e.key);
  });
}

/** The stored text, the in-memory copy of a write that failed, or null. Never throws. */
export function readRaw(key: string): string | null {
  if (memory.has(key)) return memory.get(key) ?? null;
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

/** Stores text; true when it reached localStorage, false when it only lives in memory. */
export function writeRaw(key: string, value: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    window.localStorage.setItem(key, value);
    memory.delete(key);
    return true;
  } catch {
    watchOtherTabs();
    memory.set(key, value);
    return false;
  }
}

export function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = readRaw(key);
    if (raw === null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeJson(key: string, value: unknown): boolean {
  try {
    return writeRaw(key, JSON.stringify(value));
  } catch {
    return false;
  }
}

export function removeKey(key: string): void {
  memory.delete(key);
  try {
    if (typeof window !== "undefined") window.localStorage.removeItem(key);
  } catch {
    // Storage blocked: nothing stored, and a stale in-memory copy must not come back.
    watchOtherTabs();
    memory.set(key, null);
  }
}

/** Test helper: forget what failed writes kept in memory. */
export function resetStorageMemoryForTests(): void {
  memory.clear();
}
