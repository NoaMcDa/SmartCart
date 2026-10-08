/**
 * The monthly grocery budget (issue #70), kept on the device in `sc-budget-v1` as
 * `{ "monthly": 2500 }` (whole ILS). The API `Profile` schema has no budget field yet, so this is
 * not part of `sc-profile` / `PUT /me/profile`; `GET /me/spend` returns a `budget` that the app
 * does not read until a profile field exists to write it. Removed by "delete my data".
 */
import { useSyncExternalStore } from "react";
import {
  STORAGE_KEYS,
  notifyStorageChange,
  readJson,
  removeKey,
  subscribeStorage,
  writeJson,
} from "@/features/profile/storage";

export const MAX_BUDGET = 1_000_000;

type StoredBudget = { monthly?: unknown };

/** A usable budget: a positive whole number of shekels up to a million; anything else is null. */
export function validBudget(value: unknown): number | null {
  const n = typeof value === "number" ? value : typeof value === "string" ? Number(value) : NaN;
  if (!Number.isFinite(n)) return null;
  const whole = Math.round(n);
  return whole >= 1 && whole <= MAX_BUDGET ? whole : null;
}

export function loadBudget(): number | null {
  if (typeof window === "undefined") return null;
  return validBudget(readJson<StoredBudget>(STORAGE_KEYS.budget)?.monthly);
}

/** Saves the budget; returns false (and saves nothing) for an invalid amount. */
export function saveBudget(value: unknown): boolean {
  const monthly = validBudget(value);
  if (monthly === null) return false;
  writeJson(STORAGE_KEYS.budget, { monthly });
  notifyStorageChange();
  return true;
}

export function clearBudget(): void {
  removeKey(STORAGE_KEYS.budget);
  notifyStorageChange();
}

/** The budget, or null when none is set (also on the server and before hydration). */
export function useBudget(): number | null {
  return useSyncExternalStore(subscribeStorage, loadBudget, () => null);
}
