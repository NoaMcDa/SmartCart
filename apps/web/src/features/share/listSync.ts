/**
 * The shared list's items and how changes merge into them (issue #34).
 *
 * Conflict rule, per item and never per list: a change to an item replaces what we know of it
 * unless it is older. "Older" is decided by the row's `updated_at` when the server sends one;
 * without it (the API's `ShoppingList` has none yet) the latest change we receive wins, which is
 * last-write-wins by arrival order. Two people editing different items never touch each other's
 * rows, so nothing is lost; a delete removes only that item; an insert whose id is already known is
 * an update, so a reconnect that replays events cannot duplicate an item.
 */
import type { FlexLevel, Schemas, ShoppingList, ShoppingListInput } from "@/api/client";

type ListItemIn = Schemas["ListItemIn"];

export type SharedItem = {
  id: number;
  canonicalId: number | null;
  /** What members see: the Hebrew product name written when the item was added. */
  name: string;
  quantity: number;
  flexLevel: FlexLevel;
  confirmed: boolean;
  sort: number;
  /** Epoch ms of the row's `updated_at`, when the server sent one. */
  updatedAt: number | null;
};

export type RawRow = {
  id?: number | string;
  canonical_id?: number | string | null;
  input_text?: string | null;
  quantity?: number | string | null;
  flex_level?: string | null;
  confirmed?: boolean | null;
  sort?: number | null;
  updated_at?: string | null;
};

const LEVELS = new Set(["exact", "any_brand", "close"]);

export function itemFromRow(row: RawRow): SharedItem | null {
  const id = Number(row.id);
  if (!Number.isFinite(id)) return null;
  const canonicalId =
    row.canonical_id === null || row.canonical_id === undefined ? null : Number(row.canonical_id);
  const quantity = Number(row.quantity ?? 1);
  const updated = row.updated_at ? Date.parse(row.updated_at) : NaN;
  return {
    id,
    canonicalId: canonicalId !== null && Number.isFinite(canonicalId) ? canonicalId : null,
    name: row.input_text?.trim() || (canonicalId !== null ? `מוצר מס' ${canonicalId}` : "פריט"),
    quantity: Number.isFinite(quantity) && quantity > 0 ? quantity : 1,
    flexLevel: LEVELS.has(row.flex_level ?? "") ? (row.flex_level as FlexLevel) : "any_brand",
    confirmed: row.confirmed !== false,
    sort: typeof row.sort === "number" ? row.sort : 0,
    updatedAt: Number.isFinite(updated) ? updated : null,
  };
}

export function itemsOf(list: Pick<ShoppingList, "items">): SharedItem[] {
  return list.items
    .map((i) => itemFromRow(i))
    .filter((i): i is SharedItem => i !== null)
    .sort((a, b) => a.sort - b.sort || a.id - b.id);
}

export type Change =
  | { type: "upsert"; item: SharedItem }
  | { type: "remove"; id: number }
  | { type: "replace"; items: SharedItem[] };

export function applyChange(items: ReadonlyArray<SharedItem>, change: Change): SharedItem[] {
  switch (change.type) {
    case "replace":
      return [...change.items];
    case "remove":
      return items.filter((i) => i.id !== change.id);
    case "upsert": {
      const known = items.find((i) => i.id === change.item.id);
      if (
        known &&
        known.updatedAt !== null &&
        change.item.updatedAt !== null &&
        change.item.updatedAt < known.updatedAt
      ) {
        return [...items]; // an older change arrived late: keep the newer row
      }
      const next = known
        ? items.map((i) => (i.id === change.item.id ? change.item : i))
        : [...items, change.item];
      return next.sort((a, b) => a.sort - b.sort || a.id - b.id);
    }
  }
}

/** Supabase Realtime payload to a change (INSERT and UPDATE upsert, DELETE removes by id). */
export function changeFromPayload(payload: {
  eventType: string;
  new?: RawRow | null;
  old?: RawRow | null;
}): Change | null {
  if (payload.eventType === "DELETE") {
    const id = Number(payload.old?.id);
    return Number.isFinite(id) ? { type: "remove", id } : null;
  }
  const item = payload.new ? itemFromRow(payload.new) : null;
  return item ? { type: "upsert", item } : null;
}

/** The full list as a PUT body, for the polling fallback (the API replaces the item set). */
export function serverBody(name: string, items: ReadonlyArray<SharedItem>): ShoppingListInput {
  const rows: ListItemIn[] = items.map((i) => ({
    canonical_id: i.canonicalId,
    input_text: i.name,
    quantity: i.quantity,
    flex_level: i.flexLevel,
    confirmed: i.confirmed,
  }));
  return { name, is_recurring: false, items: rows };
}
