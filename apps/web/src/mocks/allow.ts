/**
 * The mock's reading of `BasketItem.allow` (the real API offers sibling canonicals, see
 * docs/matching.md): prices stay as the fixtures have them, and every line of a product whose
 * request allowed an attribute to differ is labeled a substitute with a `differs` tag per allowed
 * attribute, so the UI's "every substitute is labeled" paths can be exercised against the mock.
 * Rows at the exact level ignore `allow`, as the API does.
 */
import type {
  BasketItemInput,
  CompareResponse,
  OptimizeResponse,
  Plan,
  PricedItem,
  StoreResult,
} from "@/api/client";

const MOCK_CONFIDENCE = 0.9;

function allowedByCanonical(items: BasketItemInput[]): Map<number, string[]> {
  const out = new Map<number, string[]>();
  for (const it of items) {
    const allow = it.flex_level === "exact" ? [] : (it.allow ?? []);
    if (allow.length > 0 && !out.has(it.canonical_id))
      out.set(it.canonical_id, [...new Set(allow)]);
  }
  return out;
}

function label(line: PricedItem, allow: string[] | undefined): PricedItem {
  if (!allow || line.is_substitute) return line;
  return {
    ...line,
    is_substitute: true,
    confidence: line.confidence ?? MOCK_CONFIDENCE,
    original_item_id: line.original_item_id ?? line.item_id,
    tags: allow.map((key) => ({ key, value: null, status: "differs" as const })),
  };
}

function labelStore(store: StoreResult, allowed: Map<number, string[]>): StoreResult {
  const items = store.items.map((l) => label(l, allowed.get(l.canonical_id)));
  return { ...store, items, substituted_count: items.filter((l) => l.is_substitute).length };
}

export function applyAllowToCompare(
  res: CompareResponse,
  items: BasketItemInput[],
): CompareResponse {
  const allowed = allowedByCanonical(items);
  if (allowed.size === 0) return res;
  return { ...res, stores: res.stores.map((s) => labelStore(s, allowed)) };
}

function labelPlan(plan: Plan | null | undefined, allowed: Map<number, string[]>) {
  if (!plan) return plan;
  const stores = plan.stores.map((a) => ({ ...a, store: labelStore(a.store, allowed) }));
  return {
    ...plan,
    stores,
    substituted_count: stores.reduce((n, a) => n + a.store.substituted_count, 0),
  };
}

export function applyAllowToOptimize(
  res: OptimizeResponse,
  items: BasketItemInput[],
): OptimizeResponse {
  const allowed = allowedByCanonical(items);
  if (allowed.size === 0) return res;
  return {
    ...res,
    single: labelPlan(res.single, allowed) as Plan,
    split: labelPlan(res.split, allowed),
    minimum_effort: labelPlan(res.minimum_effort, allowed),
  };
}
