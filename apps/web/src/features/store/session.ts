/**
 * In-store shopping session (issue #66). Everything the checklist needs is copied into
 * localStorage key `sc-shopping` when the user starts shopping, so it works with no network
 * and survives reloads: items, matched names, substitute labels, prices and their update times,
 * and the check marks. It is deleted when the user finishes ("סיימתי") and expires after 12 hours.
 */
import { useSyncExternalStore } from "react";
import type { PricedItem, StoreResult } from "@/api/client";
import { DEPARTMENTS } from "@/features/profile/dietOptions";
import {
  STORAGE_KEYS,
  notifyStorageChange,
  removeKey,
  subscribeStorage,
} from "@/features/profile/storage";
import { buildPool, toAgorot, type Pool } from "@/features/split/savings";
import type { LastResult } from "@/features/split/lastResult";

export const SESSION_TTL_MS = 12 * 60 * 60 * 1000;

export type ShopItem = {
  itemId: number;
  canonicalId: number;
  name: string;
  /** True when this is a substitute for the item on the list: it stays labeled (D10). */
  isSubstitute: boolean;
  confidence: number | null;
  quantity: string;
  uom: string;
  /** Line total, ILS decimal string. */
  lineTotal: string;
  shelfPrice: string;
  isEstimated: boolean;
  promo: string | null;
  priceUpdatedAt: string;
  /** Taxonomy department id ("dairy") or "other". */
  department: string;
  /** Saving of this line versus the home store, ILS; null when the home price is unknown. */
  saving: number | null;
  checked: boolean;
};

export type ShoppingSession = {
  version: 1;
  storeId: number;
  storeName: string;
  chainName: string;
  listName: string | null;
  startedAt: string;
  expiresAt: string;
  pricesUpdatedAt: string;
  /** Items the store could not supply, for the "לא נמצאו" count. */
  missingCount: number;
  /** Travel and extra-stop cost attributed to this store's trip, ILS (D7). Null without a home store. */
  overhead: number | null;
  /** Whether this checklist is a whole basket ("single") or one store's part of a split (issue #70). */
  plan?: "single" | "split";
  /** True once every item has a department (from the result, or looked up with /search). */
  departmentsResolved: boolean;
  items: ShopItem[];
};

/** Aisle order for the checklist: produce first, household last. */
export const DEPARTMENT_ORDER: ReadonlyArray<string> = [
  "produce",
  "bakery",
  "dairy",
  "deli",
  "meat",
  "fish",
  "frozen",
  "pantry",
  "canned",
  "snacks",
  "beverages",
  "alcohol",
  "holiday",
  "baby",
  "cleaning",
  "paper",
  "toiletries",
  "health",
  "pets",
  "other",
];

/** Roots seen in the mock catalog that belong to a real department. */
const ROOT_ALIASES: Record<string, string> = { dairy_alt: "dairy", eggs: "dairy" };

export function departmentOf(taxonomyId: string | null | undefined): string {
  if (!taxonomyId) return "other";
  const root = taxonomyId.split(".")[0] ?? "";
  const aliased = ROOT_ALIASES[root] ?? root;
  return DEPARTMENT_ORDER.includes(aliased) ? aliased : "other";
}

export function departmentLabel(id: string): string {
  return id === "other" ? "אחר" : (DEPARTMENTS.find((d) => d.id === id)?.label ?? "אחר");
}

export function departmentRank(id: string): number {
  const i = DEPARTMENT_ORDER.indexOf(id);
  return i < 0 ? DEPARTMENT_ORDER.length : i;
}

export type BuildOptions = {
  /** canonical id -> taxonomy id; anything missing goes to "other". */
  taxonomy?: Record<number, string>;
  /** Restrict to these canonicals (the split's current assignment). Default: every item of the store. */
  canonicalIds?: number[];
  overhead?: number | null;
  /** "split" when this store's part of a two-store plan; default "single". */
  plan?: "single" | "split";
  now?: Date;
};

export function buildSession(
  store: StoreResult,
  result: LastResult | null,
  options: BuildOptions = {},
): ShoppingSession {
  const now = options.now ?? new Date();
  const pool: Pool | null = result ? buildPool(result.compare, result.optimize) : null;
  const homeItems =
    result && result.homeStoreId !== null
      ? (pool?.stores.get(result.homeStoreId)?.items ?? [])
      : [];
  const home = new Map(homeItems.map((i) => [i.canonical_id, i]));
  const wanted = options.canonicalIds ? new Set(options.canonicalIds) : null;
  // With a restriction (the split's current assignment) look up every price the cache knows for
  // the store, so an item moved here is included; otherwise the caller's store is authoritative.
  const known = new Map<number, PricedItem>();
  for (const [canonicalId, byStore] of pool?.priced ?? []) {
    const item = byStore.get(store.store_id);
    if (item) known.set(canonicalId, item);
  }
  const source: PricedItem[] = wanted
    ? [...wanted].flatMap(
        (id) => known.get(id) ?? store.items.find((i) => i.canonical_id === id) ?? [],
      )
    : store.items;
  const items: ShopItem[] = source.map((item) => {
    const homeItem = home.get(item.canonical_id);
    return {
      itemId: item.item_id,
      canonicalId: item.canonical_id,
      name: item.display_name_he,
      isSubstitute: item.is_substitute,
      confidence: item.confidence ?? null,
      quantity: item.quantity,
      uom: item.uom,
      lineTotal: item.line_total,
      shelfPrice: item.shelf_price,
      isEstimated: Boolean(item.is_estimated),
      promo: item.promo_description ?? null,
      priceUpdatedAt: item.price_valid_from,
      department: departmentOf(
        options.taxonomy?.[item.canonical_id] ?? result?.taxonomy?.[item.canonical_id],
      ),
      saving: homeItem ? (toAgorot(homeItem.line_total) - toAgorot(item.line_total)) / 100 : null,
      checked: false,
    };
  });
  return {
    version: 1,
    storeId: store.store_id,
    storeName: store.store_name,
    chainName: store.chain_name,
    listName: result?.listName ?? null,
    startedAt: now.toISOString(),
    expiresAt: new Date(now.getTime() + SESSION_TTL_MS).toISOString(),
    pricesUpdatedAt: store.prices_updated_at,
    missingCount: store.missing.length,
    overhead: options.overhead ?? null,
    plan: options.plan ?? "single",
    departmentsResolved: items.every((i) => i.department !== "other"),
    items,
  };
}

/** Items grouped by department in aisle order; checked items sink to the bottom of each group. */
export function groupByDepartment(items: ReadonlyArray<ShopItem>) {
  const groups = new Map<string, ShopItem[]>();
  for (const item of items) {
    const g = groups.get(item.department) ?? [];
    g.push(item);
    groups.set(item.department, g);
  }
  return [...groups.entries()]
    .sort((a, b) => departmentRank(a[0]) - departmentRank(b[0]))
    .map(([department, list]) => ({
      department,
      label: departmentLabel(department),
      items: [...list].sort((a, b) => Number(a.checked) - Number(b.checked)),
    }));
}

export function progressOf(session: ShoppingSession) {
  const checked = session.items.filter((i) => i.checked);
  return {
    total: session.items.length,
    checked: checked.length,
    checkedTotal: checked.reduce((acc, i) => acc + toAgorot(i.lineTotal), 0) / 100,
    allTotal: session.items.reduce((acc, i) => acc + toAgorot(i.lineTotal), 0) / 100,
  };
}

/**
 * The saving actually realized: the savings of the lines the user checked, minus the trip's
 * travel and extra-stop cost when anything was bought (D7). Null when the home store is unknown.
 */
export function realizedSaving(session: ShoppingSession): number | null {
  if (session.overhead === null) return null;
  const checked = session.items.filter((i) => i.checked);
  if (checked.some((i) => i.saving === null)) return null;
  if (checked.length === 0) return 0;
  const lines = checked.reduce((acc, i) => acc + Math.round((i.saving ?? 0) * 100), 0);
  return Math.round(lines - session.overhead * 100) / 100;
}

// ---------------------------------------------------------------------------------------------
// Storage

let cachedRaw: string | null | undefined;
let cached: ShoppingSession | null = null;

export function loadSession(now: Date = new Date()): ShoppingSession | null {
  if (typeof window === "undefined") return null;
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEYS.shopping);
  } catch {
    raw = null;
  }
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    try {
      const parsed = raw === null ? null : (JSON.parse(raw) as ShoppingSession);
      cached = parsed && parsed.version === 1 && Array.isArray(parsed.items) ? parsed : null;
    } catch {
      cached = null;
    }
  }
  if (cached && new Date(cached.expiresAt).getTime() < now.getTime()) {
    // Expired: clean the cache (issue #66).
    removeKey(STORAGE_KEYS.shopping);
    cachedRaw = undefined;
    cached = null;
  }
  return cached;
}

export function saveSession(session: ShoppingSession): void {
  try {
    window.localStorage.setItem(STORAGE_KEYS.shopping, JSON.stringify(session));
  } catch {
    /* storage unavailable: the session lives only in memory for this page view */
  }
  notifyStorageChange();
}

export function clearSession(): void {
  removeKey(STORAGE_KEYS.shopping);
  cachedRaw = undefined;
  cached = null;
  notifyStorageChange();
}

/**
 * Starts (or keeps) the session for a store. If one already exists for the same store and the same
 * items, it is kept with its check marks; otherwise it replaces the old one.
 */
export function startSession(next: ShoppingSession): ShoppingSession {
  const current = loadSession();
  if (current && current.storeId === next.storeId) {
    const same =
      current.items.length === next.items.length &&
      next.items.every((i) => current.items.some((c) => c.itemId === i.itemId));
    if (same) return current;
  }
  saveSession(next);
  return next;
}

export function setChecked(itemId: number, checked: boolean): ShoppingSession | null {
  const current = loadSession();
  if (!current) return null;
  const next: ShoppingSession = {
    ...current,
    items: current.items.map((i) => (i.itemId === itemId ? { ...i, checked } : i)),
  };
  saveSession(next);
  return next;
}

export function useSession(): ShoppingSession | null {
  return useSyncExternalStore(
    subscribeStorage,
    () => loadSession(),
    () => null,
  );
}
