/**
 * "החיסכון שלי": realized savings, kept on the device in `sc-savings-history`. An entry is written
 * only when the user finishes an in-store session ("סיימתי"), from the lines they actually checked,
 * measured against their own store and after travel (D7). Never an estimate of what a basket might
 * save and never versus the most expensive chain.
 */
import { useSyncExternalStore } from "react";
import {
  STORAGE_KEYS,
  notifyStorageChange,
  readJson,
  readRaw,
  subscribeStorage,
  writeJson,
} from "./storage";

export type SavingsEntry = {
  id: string;
  /** ISO time the trip was finished. */
  at: string;
  storeName: string;
  listName: string | null;
  /** Net saving of the trip, ILS (can be negative: an honest trip is recorded as it was). */
  net: number;
};

/** A stored entry the screens can sum and list; anything else (edited or damaged data) is dropped. */
function isEntry(e: unknown): e is SavingsEntry {
  if (!e || typeof e !== "object") return false;
  const r = e as Partial<Record<keyof SavingsEntry, unknown>>;
  return (
    typeof r.id === "string" &&
    typeof r.at === "string" &&
    typeof r.storeName === "string" &&
    typeof r.net === "number" &&
    Number.isFinite(r.net)
  );
}

export function loadSavings(): SavingsEntry[] {
  if (typeof window === "undefined") return [];
  const raw = readJson<unknown>(STORAGE_KEYS.savings);
  return Array.isArray(raw) ? raw.filter(isEntry) : [];
}

const EMPTY: SavingsEntry[] = [];
let cachedRaw: string | null | undefined;
let cached: SavingsEntry[] = EMPTY;

function snapshot(): SavingsEntry[] {
  if (typeof window === "undefined") return cached;
  const raw = readRaw(STORAGE_KEYS.savings);
  if (raw === cachedRaw) return cached;
  cachedRaw = raw;
  cached = loadSavings();
  return cached;
}

export function recordSaving(
  entry: Omit<SavingsEntry, "id" | "at"> & { at?: string },
): SavingsEntry {
  const full: SavingsEntry = {
    id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`,
    at: entry.at ?? new Date().toISOString(),
    storeName: entry.storeName,
    listName: entry.listName,
    net: Math.round(entry.net * 100) / 100,
  };
  writeJson(STORAGE_KEYS.savings, [...loadSavings(), full]);
  notifyStorageChange();
  return full;
}

export function totalSaved(entries: ReadonlyArray<SavingsEntry>): number {
  return entries.reduce((acc, e) => acc + Math.round(e.net * 100), 0) / 100;
}

export function useSavings(): SavingsEntry[] {
  return useSyncExternalStore(subscribeStorage, snapshot, () => EMPTY);
}
