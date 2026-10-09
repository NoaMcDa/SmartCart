/**
 * Spend tracking (issue #70): one entry per finished shop, kept on the device in `sc-spend-v1` as
 * `{ version: 1, entries: SpendRow[], pending: string[] }`.
 *
 * An entry holds the date, the store, the total of the prices the app showed, the number of items
 * and whether it was one store or a split. It never holds item names, a list name or a location.
 * Ids are local strings. `server_id` is the numeric id `POST /me/spend` returned (set once the
 * entry reached the account); `pending` lists the local ids still to be sent, only ever non-empty
 * for a signed-in user (see `sync.ts`). `client_id` is a random UUID made with the entry and sent
 * on every `POST /me/spend`, so a retry after a lost response returns the stored entry instead of
 * a duplicate. A person can correct an entry's total ("תיקון הסכום", `corrected`) or delete it. Totals are "לפי המחירים שהוצגו": the prices the app showed
 * at the time, not a receipt, so they are estimates (D10).
 */
import { useSyncExternalStore } from "react";
import type { SpendEntry, SpendEntryInput } from "@/api/client";
import {
  STORAGE_KEYS,
  notifyStorageChange,
  readJson,
  removeKey,
  subscribeStorage,
  writeJson,
} from "@/features/profile/storage";
import { israelDate, monthOf } from "./month";

/** A stored entry: the API's fields with a local id, and `total` as a number of shekels. */
export type SpendRow = {
  id: string;
  /** The account's id for this entry, once it has one. */
  server_id?: number;
  /** Random UUID sent with every POST of this entry, so retries never duplicate it. */
  client_id?: string;
  date: string;
  store_id: number;
  store_name: string;
  total: number;
  item_count: number;
  plan: "single" | "split";
  /** The person replaced the app's estimate with their actual total. Stays on this device. */
  corrected?: true;
};

export type SpendStore = { version: 1; entries: SpendRow[]; pending: string[] };

const EMPTY: SpendStore = { version: 1, entries: [], pending: [] };

const cents = (n: number) => Math.round(n * 100);

type Loose = Partial<Record<keyof SpendRow, unknown>>;

/** A usable row from stored or server data; null when a field is missing or out of range. */
function rowFrom(raw: Loose, id: string, serverId: number | undefined): SpendRow | null {
  const total = Number(raw.total);
  const storeId = Number(raw.store_id);
  if (
    typeof raw.date !== "string" ||
    !/^\d{4}-\d{2}-\d{2}$/.test(raw.date) ||
    !Number.isFinite(total) ||
    total < 0 ||
    !Number.isFinite(storeId)
  ) {
    return null;
  }
  const clientId =
    typeof raw.client_id === "string" && /^[A-Za-z0-9_-]{8,64}$/.test(raw.client_id)
      ? raw.client_id
      : undefined;
  return {
    id,
    ...(serverId !== undefined ? { server_id: serverId } : {}),
    ...(clientId ? { client_id: clientId } : {}),
    date: raw.date,
    store_id: storeId,
    store_name: String(raw.store_name ?? ""),
    total: cents(total) / 100,
    item_count: Math.max(0, Math.round(Number(raw.item_count) || 0)),
    plan: raw.plan === "split" ? "split" : "single",
    ...(raw.corrected === true ? { corrected: true as const } : {}),
  };
}

/** An entry the account returned (the total is a decimal string). */
export function rowFromServer(entry: SpendEntry): SpendRow | null {
  return rowFrom(entry, `srv${entry.id}`, entry.id);
}

function sanitize(raw: unknown): SpendStore {
  if (typeof raw !== "object" || raw === null) return EMPTY;
  const r = raw as Partial<SpendStore>;
  const seen = new Set<string>();
  const entries: SpendRow[] = [];
  for (const e of Array.isArray(r.entries) ? r.entries : []) {
    const loose = e as Loose;
    const id = typeof loose.id === "string" ? loose.id : "";
    const serverId =
      typeof loose.server_id === "number" && Number.isInteger(loose.server_id)
        ? loose.server_id
        : undefined;
    const row = id ? rowFrom(loose, id, serverId) : null;
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

/** A fresh UUID for `client_id`. */
export function newClientId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
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
    client_id: newClientId(),
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

/** The account accepted these entries: remember their server ids and stop queueing them. */
export function markSynced(accepted: ReadonlyArray<{ id: string; serverId: number }>): void {
  if (accepted.length === 0) return;
  const store = loadSpend();
  const serverIds = new Map(accepted.map((a) => [a.id, a.serverId]));
  save({
    ...store,
    entries: store.entries.map((e) =>
      serverIds.has(e.id) ? { ...e, server_id: serverIds.get(e.id) } : e,
    ),
    pending: store.pending.filter((id) => !serverIds.has(id)),
  });
}

/**
 * Adds entries the account has and this device does not (another device's shops). An entry that
 * carries the `client_id` of one of ours is that same entry whose response was lost: it is adopted
 * (gets its `server_id`, stops being pending) instead of being added a second time.
 */
export function mergeServerEntries(incoming: ReadonlyArray<SpendEntry>): number {
  const store = loadSpend();
  const known = new Set(
    store.entries.flatMap((e) => (e.server_id !== undefined ? [e.server_id] : [])),
  );
  const byClient = new Map(
    store.entries.flatMap((e) =>
      e.client_id && e.server_id === undefined ? [[e.client_id, e.id] as const] : [],
    ),
  );
  const adopted = new Map<string, number>();
  const added: SpendRow[] = [];
  for (const raw of incoming) {
    if (known.has(raw.id) || removedServerIds.has(raw.id)) continue;
    const mine = raw.client_id ? byClient.get(raw.client_id) : undefined;
    if (mine !== undefined) {
      adopted.set(mine, raw.id);
      known.add(raw.id);
      continue;
    }
    const row = rowFromServer(raw);
    if (row) {
      known.add(raw.id);
      added.push(row);
    }
  }
  if (added.length || adopted.size) {
    save({
      ...store,
      entries: [
        ...store.entries.map((e) =>
          adopted.has(e.id) ? { ...e, server_id: adopted.get(e.id) } : e,
        ),
        ...added,
      ],
      pending: store.pending.filter((id) => !adopted.has(id)),
    });
  }
  return added.length;
}

/** The request body for an entry (`POST` and `PUT /me/spend`). */
export function spendInput(row: SpendRow): SpendEntryInput {
  return {
    date: row.date,
    store_id: row.store_id,
    store_name: row.store_name,
    total: row.total.toFixed(2),
    item_count: row.item_count,
    plan: row.plan,
    ...(row.client_id ? { client_id: row.client_id } : {}),
  };
}

/** Gives an entry made before `client_id` existed its id, once, and keeps it for every retry. */
export function ensureClientId(id: string): SpendRow | null {
  const store = loadSpend();
  const row = store.entries.find((e) => e.id === id);
  if (!row) return null;
  if (row.client_id) return row;
  const next = { ...row, client_id: newClientId() };
  save({ ...store, entries: store.entries.map((e) => (e.id === id ? next : e)) });
  return next;
}

// ---------------------------------------------------------------------------------------------
// Correct and delete (issue #70). Local first: these change the device copy at once; `sync.ts`
// tells the account and puts the old entry back if the account refuses.

export const MAX_SPEND_TOTAL = 100_000;

/**
 * A usable corrected total: a positive amount of shekels, at most two decimals, up to 100,000.
 * Accepts "371.4", "371,40" and "₪ 371"; anything else is null.
 */
export function validSpendTotal(value: unknown): number | null {
  const text =
    typeof value === "number"
      ? String(value)
      : typeof value === "string"
        ? value.replace(/₪/g, "").trim().replace(",", ".")
        : "";
  if (!/^\d+(\.\d{1,2})?$/.test(text)) return null;
  const n = Number(text);
  return n > 0 && n <= MAX_SPEND_TOTAL ? cents(n) / 100 : null;
}

/** Replaces one entry's total with the person's own. Returns the entry before and after. */
export function correctSpendTotal(
  id: string,
  total: number,
): { before: SpendRow; after: SpendRow } | null {
  const store = loadSpend();
  const before = store.entries.find((e) => e.id === id);
  if (!before) return null;
  const after: SpendRow = { ...before, total: cents(total) / 100, corrected: true };
  save({ ...store, entries: store.entries.map((e) => (e.id === id ? after : e)) });
  return { before, after };
}

/** Puts `row` back in place of the entry with its id (rollback of a correction). */
export function replaceSpendRow(row: SpendRow): void {
  const store = loadSpend();
  if (!store.entries.some((e) => e.id === row.id)) return;
  save({ ...store, entries: store.entries.map((e) => (e.id === row.id ? row : e)) });
}

/**
 * Server ids of entries deleted on this device whose delete may not have reached the account yet
 * (inside the undo window, or on its way). A pull must not bring them back meanwhile.
 */
const removedServerIds = new Set<number>();

export type RemovedSpend = { row: SpendRow; index: number; wasPending: boolean };

/** Removes one entry from the device copy. Returns what is needed to bring it back. */
export function removeSpendRow(id: string): RemovedSpend | null {
  const store = loadSpend();
  const index = store.entries.findIndex((e) => e.id === id);
  const row = store.entries[index];
  if (!row) return null;
  save({
    ...store,
    entries: store.entries.filter((e) => e.id !== id),
    pending: store.pending.filter((p) => p !== id),
  });
  if (row.server_id !== undefined) removedServerIds.add(row.server_id);
  return { row, index, wasPending: store.pending.includes(id) };
}

/** Undo of `removeSpendRow`: the entry returns to where it was, and to the queue if it was in it. */
export function restoreSpendRow(removed: RemovedSpend): void {
  const store = loadSpend();
  if (removed.row.server_id !== undefined) removedServerIds.delete(removed.row.server_id);
  if (store.entries.some((e) => e.id === removed.row.id)) return;
  const entries = [...store.entries];
  entries.splice(Math.min(removed.index, entries.length), 0, removed.row);
  save({
    ...store,
    entries,
    pending:
      removed.wasPending && !store.pending.includes(removed.row.id)
        ? [...store.pending, removed.row.id]
        : store.pending,
  });
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
