/**
 * Comparison state: the /optimize request built from the list and the shopper context, a shared
 * cache of its result (results screen and substitution card read the same response), the basket
 * estimate from /compare, and helpers to find substitutes and their originals.
 */
import {
  compare,
  optimize,
  type BasketItemInput,
  type CompareInput,
  type CompareResponse,
  type OptimizeInput,
  type OptimizeResponse,
  type Plan,
  type PricedItem,
  type StoreResult,
} from "@/api/client";
import { createResourceCache } from "./resource";
import { shopperRequestFields, type ShopperContext } from "./shopper";

export type PlanKind = Plan["kind"];

export function buildOptimizeInput(
  items: BasketItemInput[],
  shopper: ShopperContext,
): OptimizeInput | null {
  if (items.length === 0) return null;
  return { items, ...shopperRequestFields(shopper) };
}

export function buildCompareInput(
  items: BasketItemInput[],
  shopper: ShopperContext,
): CompareInput | null {
  if (items.length === 0) return null;
  const { location, home_store_id, clubs } = shopperRequestFields(shopper);
  return { items, location, home_store_id, clubs };
}

const optimizeCache = createResourceCache<OptimizeInput, OptimizeResponse>(optimize);
const compareCache = createResourceCache<CompareInput, CompareResponse>(compare);

export function useOptimize(input: OptimizeInput | null) {
  return optimizeCache.useResource(input ? JSON.stringify(input) : null, input);
}

/**
 * The basket estimate only depends on which products and levels are asked for; quantities are
 * applied locally (see estimateRange), so changing a quantity does not refetch.
 */
export function useCompareEstimate(input: CompareInput | null) {
  const key = input
    ? JSON.stringify({
        ...input,
        items: input.items.map(({ quantity: _q, ...rest }) => rest),
      })
    : null;
  return compareCache.useResource(key, input);
}

export function clearComparisonCache() {
  optimizeCache.clear();
  compareCache.clear();
}

// ---------------------------------------------------------------------------------------------
// Basket estimate (list builder sticky bar)

export type Estimate = {
  min: number;
  max: number;
  /** Stores in the range: those that carry every product on the list. */
  storeCount: number;
  cheapest: StoreResult;
  home: { store: StoreResult; total: number } | null;
};

/** Price of one unit of a line: line totals scale with the quantity asked for. */
function perUnit(line: PricedItem): number {
  const q = Number.parseFloat(line.quantity);
  const total = Number.parseFloat(line.line_total);
  return q > 0 ? total / q : total;
}

/**
 * Range of basket totals over the stores that carry the whole list, with the list's current
 * quantities. Stores missing an item are left out so a gap never makes a store look cheap.
 */
export function estimateRange(
  res: CompareResponse,
  items: ReadonlyArray<Pick<BasketItemInput, "canonical_id" | "quantity">>,
): Estimate | null {
  if (items.length === 0) return null;
  const totals: Array<{ store: StoreResult; total: number }> = [];
  for (const store of res.stores) {
    let total = 0;
    let complete = true;
    for (const it of items) {
      const line = store.items.find((l) => l.canonical_id === it.canonical_id);
      if (!line) {
        complete = false;
        break;
      }
      total += perUnit(line) * Number(it.quantity);
    }
    if (complete) totals.push({ store, total: Math.round(total * 100) / 100 });
  }
  if (totals.length === 0) return null;
  totals.sort((a, b) => a.total - b.total);
  const home =
    res.home_store_id === null
      ? null
      : (totals.find((t) => t.store.store_id === res.home_store_id) ?? null);
  return {
    min: totals[0]!.total,
    max: totals[totals.length - 1]!.total,
    storeCount: totals.length,
    cheapest: totals[0]!.store,
    home,
  };
}

// ---------------------------------------------------------------------------------------------
// Plans, substitutes, originals

export function plansOf(res: OptimizeResponse): Plan[] {
  return [res.single, res.split ?? null, res.minimum_effort ?? null].filter(
    (p): p is Plan => p !== null,
  );
}

export function planByKind(res: OptimizeResponse, kind: PlanKind): Plan | null {
  if (kind === "single") return res.single;
  if (kind === "split") return res.split ?? null;
  return res.minimum_effort ?? null;
}

/** The home store (the baseline every saving is measured against, D7). */
export function homeStore(res: OptimizeResponse): StoreResult | null {
  return res.minimum_effort?.stores[0]?.store ?? null;
}

export type Substitution = {
  item: PricedItem;
  store: StoreResult;
  plan: Plan;
};

/** Substitutes bought in a plan, in store order. */
export function planSubstitutions(plan: Plan): Substitution[] {
  const out: Substitution[] = [];
  for (const { store, item_ids } of plan.stores) {
    for (const item of store.items) {
      if (item.is_substitute && item_ids.includes(item.item_id)) out.push({ item, store, plan });
    }
  }
  return out;
}

/** Promotions included in a plan's lines; club promos counted separately. */
export function planPromos(plan: Plan): { total: number; club: number } {
  let total = 0;
  let club = 0;
  for (const { store, item_ids } of plan.stores) {
    for (const item of store.items) {
      if (!item_ids.includes(item.item_id) || !item.promo_description) continue;
      total += 1;
      if (item.club_required) club += 1;
    }
  }
  return { total, club };
}

/** The oldest price update among the plan's stores: the honest "updated at" for its total. */
export function planUpdatedAt(plan: Plan): string | null {
  const times = plan.stores.map((s) => s.store.prices_updated_at).filter(Boolean);
  if (times.length === 0) return null;
  return times.reduce((a, b) => (Date.parse(a) <= Date.parse(b) ? a : b));
}

export function responseUpdatedAt(res: OptimizeResponse): string | null {
  const times = plansOf(res)
    .map(planUpdatedAt)
    .filter((t): t is string => t !== null);
  if (times.length === 0) return null;
  return times.reduce((a, b) => (Date.parse(a) <= Date.parse(b) ? a : b));
}

export type SubstitutionContext = Substitution & {
  /** Position among the plan's substitutes, 0-based, and their count. */
  index: number;
  count: number;
  siblings: Substitution[];
  /**
   * What the user would have bought: the same product's line at the home store, when the home
   * store carries a non-substitute for it. The API does not return the original item's price at
   * the substitute's store, so the home store line is the comparison the saving is about (D7).
   */
  original: { item: PricedItem; store: StoreResult } | null;
};

export function findOriginal(
  res: OptimizeResponse,
  canonicalId: number,
): { item: PricedItem; store: StoreResult } | null {
  const home = homeStore(res);
  if (!home) return null;
  const item = home.items.find((i) => i.canonical_id === canonicalId && !i.is_substitute);
  return item ? { item, store: home } : null;
}

/**
 * Find a substitute by item id. `preferKind` picks the plan the user came from; otherwise the
 * recommended plan, then any plan that buys it.
 */
export function findSubstitution(
  res: OptimizeResponse,
  itemId: number,
  preferKind?: PlanKind,
): SubstitutionContext | null {
  const plans = plansOf(res);
  const ordered = [
    ...plans.filter((p) => p.kind === preferKind),
    ...plans.filter((p) => p.kind !== preferKind && p.recommended),
    ...plans.filter((p) => p.kind !== preferKind && !p.recommended),
  ];
  for (const plan of ordered) {
    const siblings = planSubstitutions(plan);
    const index = siblings.findIndex((s) => s.item.item_id === itemId);
    if (index >= 0) {
      const sub = siblings[index]!;
      return {
        ...sub,
        index,
        count: siblings.length,
        siblings,
        original: findOriginal(res, sub.item.canonical_id),
      };
    }
  }
  return null;
}

/** Shelf-price saving of the substitute against the original, times the quantity. */
export function substitutionSaving(ctx: Pick<SubstitutionContext, "item" | "original">): {
  perUnit: number;
  quantity: number;
  total: number;
} | null {
  if (!ctx.original) return null;
  const perUnitSaving =
    Number.parseFloat(ctx.original.item.shelf_price) - Number.parseFloat(ctx.item.shelf_price);
  const quantity = Number.parseFloat(ctx.item.quantity) || 1;
  return {
    perUnit: Math.round(perUnitSaving * 100) / 100,
    quantity,
    total: Math.round(perUnitSaving * quantity * 100) / 100,
  };
}
