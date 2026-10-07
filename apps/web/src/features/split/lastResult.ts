/**
 * The comparison the split, map and store screens work from.
 *
 * It is assembled from the core screens' shared state (W4b, `src/state`): the list (`useList`),
 * where and how the user shops (`useShopper`), the /optimize response through the SAME cache the
 * results screen reads (`useOptimize`, so no second request), and a /compare response with the real
 * quantities, which the split view needs to price an item at the other store and the map needs for
 * every store's basket total. Nothing here is stored: after a reload the data is fetched again, and
 * the in-store checklist keeps its own copy (features/store/session.ts) so it works offline.
 */
import { useEffect } from "react";
import {
  compare,
  type CompareInput,
  type CompareResponse,
  type OptimizeResponse,
  type StoreResult,
} from "@/api/client";
import { adoptHomeStore, type TravelMode } from "@/features/profile/profileState";
import { buildCompareInput, buildOptimizeInput, useOptimize } from "@/state/comparison";
import { basketItems, useList, type ListState } from "@/state/list";
import { createResourceCache } from "@/state/resource";
import { useShopper, type ShopperContext } from "@/state/shopper";

export type LastResult = {
  version: 1;
  /** When the optimize response was generated; changes with every new comparison. */
  savedAt: string;
  /** Name of the list the result is for, e.g. "הקנייה השבועית". */
  listName: string | null;
  /** Where the comparison was centred, neighborhood-rounded. */
  location: { lat: number; lon: number; radius_m: number } | null;
  homeStoreId: number | null;
  travel: { mode: TravelMode; cost_per_km: number; extra_stop_value: number };
  compare: CompareResponse | null;
  optimize: OptimizeResponse | null;
  /** canonical id -> taxonomy id, from the list rows; used to sort the in-store checklist. */
  taxonomy: Record<number, string> | null;
};

export type ComparisonStatus = "loading" | "empty" | "error" | "ready";

export type Comparison = {
  status: ComparisonStatus;
  result: LastResult | null;
  reload: () => void;
};

const compareCache = createResourceCache<CompareInput, CompareResponse>(compare);

/** Test helper: forget the cached /compare responses. */
export function clearLastResultCache() {
  compareCache.clear();
  memo = null;
}

function taxonomyOf(list: ListState): Record<number, string> {
  const out: Record<number, string> = {};
  for (const item of list.items) {
    if (item.canonical) out[item.canonical.canonical_id] = item.canonical.taxonomy_id;
  }
  return out;
}

/** Assembles a LastResult from its parts. Pure, so tests and the hook share it. */
export function assembleResult(parts: {
  list: ListState;
  shopper: ShopperContext;
  optimize: OptimizeResponse | null;
  compare: CompareResponse | null;
}): LastResult {
  const { list, shopper } = parts;
  return {
    version: 1,
    savedAt: parts.optimize?.generated_at ?? parts.compare?.generated_at ?? "",
    listName: list.name,
    location: { lat: shopper.lat, lon: shopper.lon, radius_m: shopper.radiusM },
    homeStoreId: shopper.homeStoreId,
    travel: {
      mode: shopper.travelMode,
      cost_per_km: shopper.costPerKm,
      extra_stop_value: shopper.extraStopValue,
    },
    compare: parts.compare,
    optimize: parts.optimize,
    taxonomy: taxonomyOf(list),
  };
}

let memo: {
  optimize: OptimizeResponse;
  compare: CompareResponse | undefined;
  shopper: ShopperContext;
  list: ListState;
  result: LastResult;
} | null = null;

function stable(
  list: ListState,
  shopper: ShopperContext,
  optimize: OptimizeResponse,
  cmp: CompareResponse | undefined,
): LastResult {
  if (
    memo &&
    memo.optimize === optimize &&
    memo.compare === cmp &&
    memo.shopper === shopper &&
    memo.list === list
  ) {
    return memo.result;
  }
  const result = assembleResult({ list, shopper, optimize, compare: cmp ?? null });
  memo = { optimize, compare: cmp, shopper, list, result };
  return result;
}

/**
 * The current comparison: "empty" when the list has nothing to price, "loading" while the requests
 * run, "error" when /optimize fails (a failed /compare only means no per-store totals), "ready"
 * with a stable `result` otherwise.
 */
export function useComparison(): Comparison {
  const { state: list, hydrated } = useList();
  const shopper = useShopper();
  const items = basketItems(list);
  const optimizeInput = shopper ? buildOptimizeInput(items, shopper) : null;
  const compareInput = shopper ? buildCompareInput(items, shopper) : null;
  const optimizeRes = useOptimize(optimizeInput);
  const compareRes = compareCache.useResource(
    compareInput ? JSON.stringify(compareInput) : null,
    compareInput,
  );
  // A chosen home chain becomes a home store id as soon as any compare result shows its stores.
  const compareData = compareRes.status === "success" ? compareRes.data : undefined;
  useEffect(() => {
    if (compareData) adoptHomeStore(compareData.stores);
  }, [compareData]);
  const reload = () => {
    optimizeRes.reload();
    compareRes.reload();
  };

  if (!hydrated || !shopper) return { status: "loading", result: null, reload };
  if (items.length === 0) return { status: "empty", result: null, reload };
  if (optimizeRes.status === "error") return { status: "error", result: null, reload };
  const compareSettled = compareRes.status === "success" || compareRes.status === "error";
  if (optimizeRes.status !== "success" || !compareSettled) {
    return { status: "loading", result: null, reload };
  }
  return {
    status: "ready",
    result: stable(
      list,
      shopper,
      optimizeRes.data,
      compareRes.status === "success" ? compareRes.data : undefined,
    ),
    reload,
  };
}

/**
 * Stores with a complete or full-basket price: every compare store, else the single and
 * minimum-effort stores of the optimize result (a split's part-baskets are not whole baskets).
 */
export function wholeBasketStores(result: LastResult): StoreResult[] {
  if (result.compare) return result.compare.stores;
  const o = result.optimize;
  if (!o) return [];
  const out: StoreResult[] = [];
  for (const plan of [o.single, o.minimum_effort]) {
    const store = plan?.stores[0]?.store;
    if (store && !out.some((s) => s.store_id === store.store_id)) out.push(store);
  }
  return out;
}

/** The store the net saving is measured against, when the result carries it. */
export function homeStoreOf(result: LastResult): StoreResult | null {
  if (result.homeStoreId === null) return null;
  const fromCompare = result.compare?.stores.find((s) => s.store_id === result.homeStoreId);
  if (fromCompare) return fromCompare;
  const me = result.optimize?.minimum_effort?.stores[0]?.store;
  return me && me.store_id === result.homeStoreId ? me : null;
}
