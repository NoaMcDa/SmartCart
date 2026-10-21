/**
 * The shared list's items and how changes merge into them (issue #34).
 *
 * Conflict rule, per item and never per list: a change to an item replaces what we know of it
 * unless it is older. "Older" is decided by the row's `updated_at` (the API sends it for every
 * item). Two people editing different items never touch each other's rows, so nothing is lost; a
 * delete removes only that item; an insert whose id is already known is an update, so a reconnect
 * that replays events cannot duplicate an item. Edits to the same item are written with the version
 * they were made on (`SharedItem.version`); see `itemWrites.ts` for what happens when it is stale.
 */
import type { FlexLevel, ShoppingList } from "@/api/client";
import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { shareMessages } from "@/i18n/messages/share";

export type SharedItem = {
  id: number;
  canonicalId: number | null;
  /**
   * The Hebrew product name written when the item was added; empty for a row that has none (it is
   * never filled with a placeholder: it travels back to the server as written). The screens show
   * `sharedItemName`.
   */
  name: string;
  quantity: number;
  flexLevel: FlexLevel;
  confirmed: boolean;
  /** Ticked off in the store; every member sees it. */
  checked: boolean;
  sort: number;
  /** Epoch ms of the row's `updated_at`, when the server sent one. */
  updatedAt: number | null;
  /**
   * The row's `updated_at` exactly as the server wrote it (microseconds): sent back as
   * `expected_updated_at` so the server can tell whether the item changed since this was read.
   * Null for a row that has not been saved yet.
   */
  version: string | null;
};

export type RawRow = {
  id?: number | string;
  canonical_id?: number | string | null;
  input_text?: string | null;
  quantity?: number | string | null;
  flex_level?: string | null;
  confirmed?: boolean | null;
  checked?: boolean | null;
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
    name: row.input_text?.trim() ?? "",
    quantity: Number.isFinite(quantity) && quantity > 0 ? quantity : 1,
    flexLevel: LEVELS.has(row.flex_level ?? "") ? (row.flex_level as FlexLevel) : "any_brand",
    confirmed: row.confirmed !== false,
    checked: row.checked === true,
    sort: typeof row.sort === "number" ? row.sort : 0,
    updatedAt: Number.isFinite(updated) ? updated : null,
    version: row.updated_at || null,
  };
}

/** The name to show for an item: its own, else a numbered or generic one in the UI language. */
export function sharedItemName(
  item: Pick<SharedItem, "name" | "canonicalId">,
  locale: Locale = DEFAULT_LOCALE,
): string {
  if (item.name) return item.name;
  return item.canonicalId !== null
    ? translate(shareMessages, locale, "itemNumbered", { id: item.canonicalId })
    : translate(shareMessages, locale, "itemUnnamed");
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
