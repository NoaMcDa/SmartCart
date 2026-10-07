/**
 * Client-side saving arithmetic for the split view, the map sheet and in-store mode.
 *
 * It mirrors the API's rules (docs/api.md, "Saving semantics (D7)" and "POST /optimize") so a
 * move in the split view recomputes from the cached line totals instead of calling the server:
 *
 *   basket_saving = home store total - plan basket total, over the canonicals both supply
 *   travel_cost   = max(0, plan travel - home travel)
 *   extra_stop    = value per extra stop x (visited stores - 1)
 *   net_saving    = basket_saving - travel_cost - extra_stop        (the hero number, D7)
 *
 * All math is in integer agorot so the waterfall steps sum exactly to the net saving.
 *
 * The basket saving splits per line into three parts (home line H, plan line P, qty q):
 *   shelf difference  = H.shelf x q - P.shelf x q      -> "מעבר רשת", or "החלפת מותג" when P is a substitute
 *   promo difference  = (P.shelf x q - P.line_total) - (H.shelf x q - H.line_total)   -> "מבצעים"
 * and shelf + promo = H.line_total - P.line_total exactly.
 */
import type {
  CompareResponse,
  OptimizeResponse,
  Plan,
  PricedItem,
  StoreResult,
} from "@/api/client";
import type { TravelMode } from "@/features/profile/profileState";
import type { LastResult } from "./lastResult";

export const toAgorot = (value: string | number | null | undefined): number =>
  value === null || value === undefined ? 0 : Math.round(Number(value) * 100);

export const fromAgorot = (agorot: number): number => agorot / 100;

/** Flat estimate per store for walking or transit, ILS (same constant as the API default). */
export const WALK_TRANSIT_COST_PER_STORE = 11;

/** Round-trip travel to one store, ILS. Same formulas as the API; walking and transit is an estimate. */
export function estimateTravelCost(mode: TravelMode, distanceM: number, costPerKm: number): number {
  if (mode === "delivery") return 0;
  if (mode === "walk_transit") return WALK_TRANSIT_COST_PER_STORE;
  return Math.round(2 * (distanceM / 1000) * costPerKm * 100) / 100;
}

// ---------------------------------------------------------------------------------------------
// Line pool

export type Pool = {
  /** canonical id -> store id -> the item priced at that store. */
  priced: Map<number, Map<number, PricedItem>>;
  /** store id -> canonical ids the store is known not to supply (from /compare). */
  missingAt: Map<number, Set<number>>;
  stores: Map<number, StoreResult>;
};

function addPriced(pool: Pool, store: StoreResult) {
  pool.stores.set(store.store_id, store);
  for (const item of store.items) {
    let byStore = pool.priced.get(item.canonical_id);
    if (!byStore) pool.priced.set(item.canonical_id, (byStore = new Map()));
    byStore.set(store.store_id, item);
  }
  if (!pool.missingAt.has(store.store_id)) pool.missingAt.set(store.store_id, new Set());
}

/** Every price the cached result knows, per canonical and store. */
export function buildPool(
  compare: CompareResponse | null,
  optimize: OptimizeResponse | null,
): Pool {
  const pool: Pool = { priced: new Map(), missingAt: new Map(), stores: new Map() };
  for (const s of compare?.stores ?? []) {
    addPriced(pool, s);
    pool.missingAt.set(s.store_id, new Set(s.missing));
  }
  for (const plan of [optimize?.single, optimize?.split, optimize?.minimum_effort]) {
    for (const a of plan?.stores ?? []) {
      // Plan parts hold only the assigned items; do not let them overwrite a full compare store.
      if (!pool.stores.has(a.store.store_id)) addPriced(pool, a.store);
      else
        for (const item of a.store.items) {
          const byStore = pool.priced.get(item.canonical_id)?.get(a.store.store_id);
          if (!byStore) {
            let m = pool.priced.get(item.canonical_id);
            if (!m) pool.priced.set(item.canonical_id, (m = new Map()));
            m.set(a.store.store_id, item);
          }
        }
    }
  }
  return pool;
}

// ---------------------------------------------------------------------------------------------
// Split model

/** canonical id -> store id */
export type Assignment = Map<number, number>;

export function assignmentOf(plan: Plan): Assignment {
  const out: Assignment = new Map();
  for (const a of plan.stores) {
    const ids = new Set(a.item_ids);
    for (const item of a.store.items)
      if (ids.has(item.item_id)) out.set(item.canonical_id, a.store.store_id);
  }
  return out;
}

export type Waterfall = {
  /** Home store total over the lines both baskets supply (the reference, not a step). */
  base: number;
  chainSwitch: number;
  brandSwaps: number;
  promos: number;
  basketSaving: number;
  travel: number;
  extraStop: number;
  net: number;
};

export type StoreColumn = {
  store: StoreResult;
  items: PricedItem[];
  /** Sum of the line totals, ILS. */
  subtotal: number;
};

export type SplitComputation = {
  columns: StoreColumn[];
  total: number;
  /** Null when there is no home store (D7): no saving is shown then. */
  waterfall: Waterfall | null;
  extraMinutes: number;
  visited: number;
};

export type SplitModel = {
  plan: Plan;
  pool: Pool;
  /** The home store's items by canonical, when known. */
  home: Map<number, PricedItem> | null;
  /** Plan travel minus what the home store would cost (the API's `breakdown.travel_cost` base). */
  homeTravel: number;
  extraStopPerStop: number;
  hasBreakdown: boolean;
  columnStores: StoreResult[];
  /** Chain name of the home store (the baseline), when known. */
  homeName: string | null;
};

export function buildSplitModel(result: LastResult): SplitModel | null {
  const plan = result.optimize?.split;
  if (!plan || plan.stores.length < 2) return null;
  const pool = buildPool(result.compare, result.optimize);
  const homeStore =
    result.homeStoreId !== null ? (pool.stores.get(result.homeStoreId) ?? null) : null;
  const home = homeStore ? new Map(homeStore.items.map((i) => [i.canonical_id, i])) : null;
  const breakdown = plan.breakdown ?? null;
  const planTravel = toAgorot(plan.travel_cost);
  return {
    plan,
    pool,
    home,
    homeTravel: breakdown ? Math.max(0, planTravel - toAgorot(breakdown.travel_cost)) : 0,
    extraStopPerStop: breakdown
      ? toAgorot(breakdown.extra_stop_cost) / Math.max(1, plan.stores.length - 1)
      : 0,
    hasBreakdown: breakdown !== null,
    columnStores: plan.stores.map((a) => a.store),
    homeName: homeStore?.chain_name ?? null,
  };
}

const lineShelf = (item: PricedItem) =>
  Math.round(toAgorot(item.shelf_price) * Number(item.quantity));
const lineTotal = (item: PricedItem) => toAgorot(item.line_total);

export function computeSplit(model: SplitModel, assignment: Assignment): SplitComputation {
  const columns: StoreColumn[] = model.columnStores.map((store) => ({
    store,
    items: [],
    subtotal: 0,
  }));
  let chain = 0;
  let brand = 0;
  let promo = 0;
  let base = 0;
  let total = 0;
  for (const [canonicalId, storeId] of assignment) {
    const item = model.pool.priced.get(canonicalId)?.get(storeId);
    const col = columns.find((c) => c.store.store_id === storeId);
    if (!item || !col) continue;
    col.items.push(item);
    col.subtotal += lineTotal(item);
    total += lineTotal(item);
    const home = model.home?.get(canonicalId);
    if (home) {
      base += lineTotal(home);
      const shelfDelta = lineShelf(home) - lineShelf(item);
      const promoDelta = lineShelf(item) - lineTotal(item) - (lineShelf(home) - lineTotal(home));
      if (item.is_substitute) brand += shelfDelta;
      else chain += shelfDelta;
      promo += promoDelta;
    }
  }
  const visited = columns.filter((c) => c.items.length > 0).length;
  const originalStores = model.columnStores.length;

  // Travel: the plan's travel split across its stores by distance (exact for a car, where the cost
  // is linear in distance), counted only for stores that still receive items.
  const weights = model.columnStores.map((s) => Math.max(1, s.distance_m));
  const weightSum = weights.reduce((a, b) => a + b, 0);
  const visitedWeight = columns.reduce(
    (acc, c, i) => acc + (c.items.length > 0 ? (weights[i] ?? 0) : 0),
    0,
  );
  const planTravel = Math.round((toAgorot(model.plan.travel_cost) * visitedWeight) / weightSum);
  const travel = Math.max(0, planTravel - model.homeTravel);
  const extraStop = Math.round(model.extraStopPerStop * Math.max(0, visited - 1));
  const basketSaving = chain + brand + promo;
  const planExtraMinutes = model.plan.extra_minutes ?? 0;
  const extraMinutes =
    originalStores > 1
      ? Math.round((planExtraMinutes * Math.max(0, visited - 1)) / (originalStores - 1))
      : 0;

  return {
    columns: columns.map((c) => ({ ...c, subtotal: fromAgorot(c.subtotal) })),
    total: fromAgorot(total),
    waterfall:
      model.hasBreakdown && model.home
        ? {
            base: fromAgorot(base),
            chainSwitch: fromAgorot(chain),
            brandSwaps: fromAgorot(brand),
            promos: fromAgorot(promo),
            basketSaving: fromAgorot(basketSaving),
            travel: fromAgorot(travel),
            extraStop: fromAgorot(extraStop),
            net: fromAgorot(basketSaving - travel - extraStop),
          }
        : null,
    extraMinutes,
    visited,
  };
}

/** Why an item cannot be moved to a store, or null when it can. */
export function moveBlockedReason(
  model: SplitModel,
  canonicalId: number,
  targetStoreId: number,
): string | null {
  if (model.pool.priced.get(canonicalId)?.has(targetStoreId)) return null;
  const store = model.pool.stores.get(targetStoreId);
  const name = store?.chain_name ?? "החנות";
  if (model.pool.missingAt.get(targetStoreId)?.has(canonicalId)) return `לא נמצא ב${name}`;
  return `אין לנו מחיר לפריט הזה ב${name}`;
}

// ---------------------------------------------------------------------------------------------
// Net saving for any single store (map sheet)

export type StoreSaving = {
  /** Basket saving versus the home store, before travel. Null without a home store. */
  basket: number | null;
  travel: number;
  /** Net saving after travel (D7). Null without a home store. */
  net: number | null;
  /** True when the figure comes from the API's own /optimize breakdown, not an estimate. */
  fromApi: boolean;
};

export function netSavingForStore(result: LastResult, store: StoreResult): StoreSaving {
  const single = result.optimize?.single;
  if (
    single &&
    single.stores.length === 1 &&
    single.stores[0]?.store.store_id === store.store_id &&
    single.breakdown
  ) {
    return {
      basket: Number(single.breakdown.basket_saving),
      travel: Number(single.breakdown.travel_cost),
      net: Number(single.breakdown.net_saving),
      fromApi: true,
    };
  }
  const homeId = result.homeStoreId;
  if (homeId === null || store.saving_vs_home === null || store.saving_vs_home === undefined) {
    return { basket: null, travel: 0, net: null, fromApi: false };
  }
  const basket = Number(store.saving_vs_home);
  if (store.store_id === homeId) return { basket: 0, travel: 0, net: 0, fromApi: false };
  const { mode, cost_per_km } = result.travel;
  const home = result.compare?.stores.find((s) => s.store_id === homeId);
  const travel = Math.max(
    0,
    estimateTravelCost(mode, store.distance_m, cost_per_km) -
      (home ? estimateTravelCost(mode, home.distance_m, cost_per_km) : 0),
  );
  return { basket, travel, net: Math.round((basket - travel) * 100) / 100, fromApi: false };
}
