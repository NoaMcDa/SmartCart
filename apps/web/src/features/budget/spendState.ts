/**
 * Spend tracking (issue #70): one entry per finished shop, kept on the device in `sc-spend-v1` as
 * `{ version: 1, entries: SpendRow[], pending: string[] }`.
 *
 * An entry holds the date, the store, the total of the prices the app showed, the number of items
 * and whether it was one store or a split. It never holds item names, a list name or a location.
 * `pending` lists the ids not yet confirmed by `POST /me/spend`; it is only ever non-empty for a
 * signed-in user whose request failed (see `sync.ts`). Totals are "לפי המחירים שהוצגו": the prices
 * the app showed at the time, not a receipt, so they are estimates (D10).
 */
import { useSyncExternalStore } from "react";
import type { SpendEntry } from "@/api/client";
import {
  STORAGE_KEYS,
  notifyStorageChange,
  readJson,
  removeKey,
  subscribeStorage,
  writeJson,
} from "@/features/profile/storage";
import { israelDate, monthOf } from "./month";

/** A stored entry: the API shape with `total` always a number of shekels. */
export type SpendRow = Omit<SpendEntry, "total"> & { total: number };

export type SpendStore = { version: 1; entries: SpendRow[]; pending: string[] };

const EMPTY: SpendStore = { version: 1, entries: [], pending: [] };

const cents = (n: number) => Math.round(n * 100);

/** Reads an API entry (the total may be a decimal string); null when it is not a usable entry. */
export function toRow(raw: SpendEntry): SpendRow | null {
  const total = Number(raw.total);
  if (
    typeof raw.id !== "string" ||
    !raw.id ||
    !/^\d{4}-\d{2}-\d{2}$/.test(raw.date) ||
    !Number.isFinite(total) ||
    total < 0 ||
    !Number.isFinite(raw.store_id)
  ) {
    return null;
  }
  return {
    id: raw.id,
    date: raw.date,
    store_id: raw.store_id,
    store_name: String(raw.store_name ?? ""),
    total: cents(total) / 100,
    item_count: Math.max(0, Math.round(Number(raw.item_count) || 0)),
    plan: raw.plan === "split" ? "split" : "single",
  };
}

function sanitize(raw: unknown): SpendStore {
  if (typeof raw !== "object" || raw === null) return EMPTY;
  const r = raw as Partial<SpendStore>;
  const seen = new Set<string>();
  const entries: SpendRow[] = [];
  for (const e of Array.isArray(r.entries) ? r.entries : []) {
    const row = toRow(e as SpendEntry);
    if (row && !seen.has(row.id)) {
      seen.add(row.id);
      entries.push(row);
    }
  }
  const pending = (Array.isArray(r.pending) ? r.pending : []).filter(
    (id): id is string => typeof id === "string" && seen.has(id),
  );
  return { version: 1, entries, pending };
}

export function loadSpend(): SpendStore {
  if (typeof window === "undefined") return EMPTY;
  return sanitize(readJson<unknown>(STORAGE_KEYS.spend));
}

let cachedRaw: string | null | undefined;
let cached: SpendStore = EMPTY;

function snapshot(): SpendStore {
  if (typeof window === "undefined") return EMPTY;
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEYS.spend);
  } catch {
    raw = null;
  }
  if (raw === cachedRaw) return cached;
  cachedRaw = raw;
  cached = loadSpend();
  return cached;
}

function save(store: SpendStore): void {
  writeJson(STORAGE_KEYS.spend, store);
  notifyStorageChange();
}

function newId(): string {
  const rand =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID().replace(/-/g, "").slice(0, 12)
      : Math.random().toString(36).slice(2, 14);
  return `sp${Date.now().toString(36)}${rand}`;
}

export type SpendInput = {
  storeId: number;
  storeName: string;
  /** ILS, the sum of the prices the app showed. */
  total: number;
  itemCount: number;
  plan: "single" | "split";
  now?: Date;
  /** Marks the entry as waiting for `POST /me/spend` (a signed-in user). */
  pending?: boolean;
};

/** Records one finished shop. Returns the stored entry. */
export function recordSpend(input: SpendInput): SpendRow {
  const row: SpendRow = {
    id: newId(),
    date: israelDate(input.now),
    store_id: input.storeId,
    store_name: input.storeName,
    total: cents(Math.max(0, input.total)) / 100,
    item_count: Math.max(0, Math.round(input.itemCount)),
    plan: input.plan,
  };
  const store = loadSpend();
  save({
    version: 1,
    entries: [...store.entries, row],
    pending: input.pending ? [...store.pending, row.id] : store.pending,
  });
  return row;
}

/** Marks entries as accepted by the server. */
export function markSynced(ids: string[]): void {
  const store = loadSpend();
  const next = store.pending.filter((id) => !ids.includes(id));
  if (next.length !== store.pending.length) save({ ...store, pending: next });
}

/** Adds entries the server has and this device does not (another device's shops). */
export function mergeServerEntries(incoming: SpendEntry[]): number {
  const store = loadSpend();
  const known = new Set(store.entries.map((e) => e.id));
  const added: SpendRow[] = [];
  for (const raw of incoming) {
    const row = toRow(raw);
    if (row && !known.has(row.id)) {
      known.add(row.id);
      added.push(row);
    }
  }
  if (added.length) save({ ...store, entries: [...store.entries, ...added] });
  return added.length;
}

export function clearSpend(): void {
  removeKey(STORAGE_KEYS.spend);
  notifyStorageChange();
}

export function useSpend(): SpendStore {
  return useSyncExternalStore(subscribeStorage, snapshot, () => EMPTY);
}

// ---------------------------------------------------------------------------------------------
// Arithmetic (integer agorot, so sums never drift)

/** Sum of the entries dated in `month` (`YYYY-MM`), ILS. */
export function spentInMonth(entries: ReadonlyArray<SpendRow>, month: string): number {
  return (
    entries.filter((e) => monthOf(e.date) === month).reduce((acc, e) => acc + cents(e.total), 0) /
    100
  );
}

export type MonthTotal = { month: string; total: number };

export function monthlyTotals(
  entries: ReadonlyArray<SpendRow>,
  months: ReadonlyArray<string>,
): MonthTotal[] {
  return months.map((month) => ({ month, total: spentInMonth(entries, month) }));
}

export type BudgetStatus = {
  budget: number;
  spent: number;
  /** budget - spent; negative when over. */
  remaining: number;
  /** remaining after buying a plan that costs `planTotal`; null when no plan is given. */
  afterPlan: number | null;
};

/** Null without a budget. */
export function budgetStatus(
  budget: number | null,
  entries: ReadonlyArray<SpendRow>,
  month: string,
  planTotal?: number | null,
): BudgetStatus | null {
  if (budget === null) return null;
  const spent = spentInMonth(entries, month);
  const remaining = (cents(budget) - cents(spent)) / 100;
  const afterPlan =
    planTotal !== null && planTotal !== undefined && Number.isFinite(planTotal)
      ? (cents(budget) - cents(spent) - cents(planTotal)) / 100
      : null;
  return { budget, spent, remaining, afterPlan };
}
