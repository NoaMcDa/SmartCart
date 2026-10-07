/**
 * Realistic Hebrew fixtures for the mock API, built from the artboards (docs/design/artboards):
 * "הקנייה השבועית", 9 items, Modi'in, prices updated today 06:40.
 *   רמי לוי · מודיעין   ₪389, 4.2 km, 3 substituted, 1 missing (cottage)  -> recommended single store
 *   רמי לוי + אושר עד   ₪371, 6 + 3 items, +12 min, ₪9 fuel              -> split
 *   שופרסל דיל · מודיעין ₪446, 1.1 km, the user's own store                 -> minimum effort / baseline
 * Store totals are the exact sum of their line totals. The split's net saving follows the API
 * arithmetic (basket_saving - travel_cost - extra_stop_cost), so it depends on the request's
 * travel.extra_stop_value (default ₪25): 75 - 9 - 25 = ₪41. The artboard's "₪75 net" is the
 * basket saving before travel.
 */
import type {
  AttributeTag,
  CanonicalRef,
  CompareResponse,
  OptimizeResponse,
  Plan,
  PricedItem,
  StoreResult,
} from "@/api/client";

export const PRICES_UPDATED_AT = "2026-10-07T03:40:00Z"; // 06:40 Israel time
export const HOME_STORE_ID = 103;

// ---------------------------------------------------------------------------------------------
// Catalog

type CatalogEntry = CanonicalRef & {
  /** Pack size in base units for unit pricing: ml, g, units, or 1 for per-kg goods. */
  size: number;
  uom: string;
  keywords: string[];
  weighed?: boolean;
};

export const CATALOG: Record<number, CatalogEntry> = {
  1001: {
    canonical_id: 1001,
    display_name_he: "חלב טרי 3%, 1 ליטר",
    taxonomy_id: "dairy.milk",
    category_path_he: ["מוצרי חלב", "חלב"],
    base_unit: "100ml",
    size: 1000,
    uom: '100 מ"ל',
    keywords: ["חלב"],
  },
  1002: {
    canonical_id: 1002,
    display_name_he: "קוטג' 5%, 250 ג'",
    taxonomy_id: "dairy.cottage",
    category_path_he: ["מוצרי חלב", "גבינות", "קוטג'"],
    base_unit: "100g",
    size: 250,
    uom: "100 ג'",
    keywords: ["קוטג", "קוטג'"],
  },
  1003: {
    canonical_id: 1003,
    display_name_he: "משקה סויה ללא סוכר, 1 ליטר",
    taxonomy_id: "dairy_alt.soy",
    category_path_he: ["מוצרי חלב", "תחליפי חלב", "משקה סויה"],
    base_unit: "100ml",
    size: 1000,
    uom: '100 מ"ל',
    keywords: ["סויה", "משקה סויה"],
  },
  1004: {
    canonical_id: 1004,
    display_name_he: "רסק עגבניות, 260 ג'",
    taxonomy_id: "pantry.tomato_paste",
    category_path_he: ["מזווה", "רסק עגבניות"],
    base_unit: "100g",
    size: 260,
    uom: "100 ג'",
    keywords: ["רסק", "רסק עגבניות"],
  },
  1005: {
    canonical_id: 1005,
    display_name_he: 'שמן זית כתית מעולה, 750 מ"ל',
    taxonomy_id: "pantry.olive_oil",
    category_path_he: ["מזווה", "שמן זית"],
    base_unit: "100ml",
    size: 750,
    uom: '100 מ"ל',
    keywords: ["שמן זית"],
  },
  1006: {
    canonical_id: 1006,
    display_name_he: "פסטה פנה, 500 ג'",
    taxonomy_id: "pantry.pasta",
    category_path_he: ["מזווה", "פסטה"],
    base_unit: "100g",
    size: 500,
    uom: "100 ג'",
    keywords: ["פסטה", "פנה"],
  },
  1007: {
    canonical_id: 1007,
    display_name_he: 'עגבניות, 1 ק"ג',
    taxonomy_id: "produce.tomato",
    category_path_he: ["ירקות ופירות", "עגבניות"],
    base_unit: "kg",
    size: 1,
    uom: 'ק"ג',
    keywords: ["עגבניות", "עגבניה"],
    weighed: true,
  },
  1008: {
    canonical_id: 1008,
    display_name_he: "פילה סלמון טרי",
    taxonomy_id: "fish.salmon",
    category_path_he: ["דגים ובשר", "סלמון"],
    base_unit: "kg",
    size: 1,
    uom: 'ק"ג',
    keywords: ["סלמון"],
    weighed: true,
  },
  1009: {
    canonical_id: 1009,
    display_name_he: "ביצים L, 12 יחידות",
    taxonomy_id: "eggs.chicken",
    category_path_he: ["מוצרי חלב", "ביצים"],
    base_unit: "unit",
    size: 12,
    uom: "ביצה",
    keywords: ["ביצים", "ביצה"],
  },
  // Alternatives offered when "שמן זית" is ambiguous.
  1010: {
    canonical_id: 1010,
    display_name_he: "שמן זית כתית, 1 ליטר",
    taxonomy_id: "pantry.olive_oil",
    category_path_he: ["מזווה", "שמן זית"],
    base_unit: "100ml",
    size: 1000,
    uom: '100 מ"ל',
    keywords: ["שמן זית"],
  },
  1011: {
    canonical_id: 1011,
    display_name_he: 'שמן זית כתית מעולה, 500 מ"ל',
    taxonomy_id: "pantry.olive_oil",
    category_path_he: ["מזווה", "שמן זית"],
    base_unit: "100ml",
    size: 500,
    uom: '100 מ"ל',
    keywords: ["שמן זית"],
  },
};

export function canonicalRef(id: number): CanonicalRef {
  const c = CATALOG[id];
  if (!c) throw new Error(`unknown canonical ${id}`);
  return {
    canonical_id: c.canonical_id,
    display_name_he: c.display_name_he,
    taxonomy_id: c.taxonomy_id,
    base_unit: c.base_unit,
    category_path_he: c.category_path_he ?? [],
  };
}

/** The weekly list from the artboards: canonical id -> quantity. */
export const WEEKLY_BASKET: ReadonlyArray<{
  canonical_id: number;
  quantity: number;
  flex_level: "exact" | "any_brand" | "close";
}> = [
  { canonical_id: 1001, quantity: 2, flex_level: "any_brand" },
  { canonical_id: 1002, quantity: 1, flex_level: "exact" },
  { canonical_id: 1003, quantity: 1, flex_level: "close" },
  { canonical_id: 1004, quantity: 2, flex_level: "any_brand" },
  { canonical_id: 1005, quantity: 1, flex_level: "exact" },
  { canonical_id: 1006, quantity: 3, flex_level: "any_brand" },
  { canonical_id: 1007, quantity: 1, flex_level: "any_brand" },
  { canonical_id: 1008, quantity: 2, flex_level: "any_brand" },
  { canonical_id: 1009, quantity: 2, flex_level: "any_brand" },
];

// ---------------------------------------------------------------------------------------------
// Money helpers (agorot integers, strings with two decimals on the wire)

const toAgorot = (shekels: number) => Math.round(shekels * 100);
export const money = (agorot: number) => (agorot / 100).toFixed(2);

// ---------------------------------------------------------------------------------------------
// Stores

type Line = {
  canonical_id: number;
  /** Shelf price per pack (or per kg for weighed goods), shekels. */
  price: number;
  /** Override the line total (multi-buy promos). */
  lineTotal?: number;
  name?: string;
  substitute?: { originalName: string; confidence: number; tags: AttributeTag[] };
  promo?: string;
  club?: string;
};

type StoreSpec = {
  store_id: number;
  chain_id: string;
  chain_name: string;
  store_name: string;
  distance_m: number;
  lines: Line[];
};

const SAME_TYPE: AttributeTag = { key: "אותו סוג מוצר", status: "matched", value: null };

const STORES: StoreSpec[] = [
  {
    store_id: 101,
    chain_id: "rami_levy",
    chain_name: "רמי לוי",
    store_name: "רמי לוי · מודיעין",
    distance_m: 4200,
    lines: [
      {
        canonical_id: 1001,
        price: 5.9,
        name: "חלב טרי 3% יטבתה, 1 ליטר",
        substitute: {
          originalName: "חלב טרי 3% תנובה, 1 ליטר",
          confidence: 0.98,
          tags: [
            SAME_TYPE,
            { key: "אותו גודל", status: "matched", value: "1 ליטר" },
            { key: "אחוז שומן", status: "matched", value: "3%" },
            { key: "מותג", status: "differs", value: "יטבתה במקום תנובה" },
          ],
        },
      },
      {
        canonical_id: 1003,
        price: 9.9,
        name: "משקה סויה ללא סוכר מותג פרטי, 1 ליטר",
        substitute: {
          originalName: "משקה סויה ללא סוכר אלפרו, 1 ליטר",
          confidence: 0.91,
          tags: [
            SAME_TYPE,
            { key: "ללא סוכר", status: "matched", value: null },
            { key: "חלבון", status: "unverified", value: "3.3 ג' ל-100 מ\"ל" },
            { key: "מותג", status: "differs", value: "מותג פרטי במקום אלפרו" },
          ],
        },
      },
      {
        canonical_id: 1004,
        price: 4.5,
        name: "רסק עגבניות מותג פרטי, 260 ג'",
        substitute: {
          originalName: "רסק עגבניות אסם, 260 ג'",
          confidence: 0.96,
          tags: [
            SAME_TYPE,
            { key: "אותו גודל", status: "matched", value: "260 ג'" },
            { key: "כשרות", status: "matched", value: "רבנות" },
            { key: "מוצקים", status: "unverified", value: "28%" },
            { key: "מותג", status: "differs", value: "מותג פרטי במקום אסם" },
          ],
        },
      },
      { canonical_id: 1005, price: 39.9, name: 'שמן זית כתית מעולה יד מרדכי, 750 מ"ל' },
      { canonical_id: 1006, price: 4.9, name: "פסטה פנה אסם, 500 ג'", promo: "מבצע: 3 ב-₪14.70" },
      { canonical_id: 1007, price: 4.9 },
      {
        canonical_id: 1008,
        price: 136.5,
        name: "פילה סלמון נורבגי טרי",
        promo: "מבצע מועדון",
        club: "רמי לוי",
      },
      { canonical_id: 1009, price: 12.9, name: "ביצים L, 12 יחידות" },
    ],
  },
  {
    store_id: 102,
    chain_id: "osher_ad",
    chain_name: "אושר עד",
    store_name: "אושר עד · מודיעין",
    distance_m: 5100,
    lines: [
      { canonical_id: 1001, price: 5.7, name: "חלב טרי 3% טרה, 1 ליטר" },
      { canonical_id: 1002, price: 4.8, name: "קוטג' 5% תנובה, 250 ג'" },
      { canonical_id: 1003, price: 10.9, name: "משקה סויה ללא סוכר אלפרו, 1 ליטר" },
      { canonical_id: 1004, price: 5.2, name: "רסק עגבניות אסם, 260 ג'" },
      {
        canonical_id: 1005,
        price: 24.9,
        name: 'שמן זית כתית מעולה יד מרדכי, 750 מ"ל',
        promo: "מבצע: ₪24.90 במקום ₪42.90",
      },
      {
        canonical_id: 1006,
        price: 2.3,
        lineTotal: 6.9,
        name: "פסטה פנה מותג פרטי, 500 ג'",
        promo: "מבצע: 3 ב-₪6.90",
        substitute: {
          originalName: "פסטה פנה אסם, 500 ג'",
          confidence: 0.97,
          tags: [
            SAME_TYPE,
            { key: "אותו גודל", status: "matched", value: "500 ג'" },
            { key: "סוג קמח", status: "unverified", value: "סמולינה" },
            { key: "מותג", status: "differs", value: "מותג פרטי במקום אסם" },
          ],
        },
      },
      { canonical_id: 1007, price: 5.9 },
      { canonical_id: 1009, price: 12.5 },
    ],
  },
  {
    store_id: 103,
    chain_id: "shufersal",
    chain_name: "שופרסל",
    store_name: "שופרסל דיל · מודיעין",
    distance_m: 1100,
    lines: [
      { canonical_id: 1001, price: 6.9, name: "חלב טרי 3% תנובה, 1 ליטר" },
      { canonical_id: 1002, price: 6.9, name: "קוטג' 5% תנובה, 250 ג'" },
      { canonical_id: 1003, price: 12.9, name: "משקה סויה ללא סוכר אלפרו, 1 ליטר" },
      { canonical_id: 1004, price: 6.9, name: "רסק עגבניות אסם, 260 ג'" },
      { canonical_id: 1005, price: 49.9, name: 'שמן זית כתית מעולה יד מרדכי, 750 מ"ל' },
      { canonical_id: 1006, price: 7.9, name: "פסטה פנה אסם, 500 ג'" },
      { canonical_id: 1007, price: 7.9 },
      { canonical_id: 1008, price: 142.65, name: "פילה סלמון נורבגי טרי" },
      { canonical_id: 1009, price: 15.9 },
    ],
  },
  {
    store_id: 104,
    chain_id: "yochananof",
    chain_name: "יוחננוף",
    store_name: "יוחננוף · מודיעין",
    distance_m: 3600,
    lines: [
      { canonical_id: 1001, price: 6.2 },
      { canonical_id: 1002, price: 5.5 },
      { canonical_id: 1003, price: 11.5 },
      { canonical_id: 1004, price: 5.9 },
      { canonical_id: 1005, price: 42.9 },
      { canonical_id: 1006, price: 5.5 },
      { canonical_id: 1007, price: 5.9 },
      { canonical_id: 1008, price: 133.85 },
      { canonical_id: 1009, price: 13.9 },
    ],
  },
  {
    store_id: 105,
    chain_id: "victory",
    chain_name: "ויקטורי",
    store_name: "ויקטורי · מודיעין",
    distance_m: 2400,
    lines: [
      { canonical_id: 1001, price: 6.5 },
      { canonical_id: 1002, price: 5.9 },
      { canonical_id: 1003, price: 12.5 },
      { canonical_id: 1004, price: 6.2 },
      { canonical_id: 1005, price: 44.9 },
      { canonical_id: 1006, price: 6.2 },
      { canonical_id: 1007, price: 6.9 },
      { canonical_id: 1008, price: 137.4 },
      { canonical_id: 1009, price: 14.5 },
    ],
  },
];

function quantityOf(canonicalId: number): number {
  return WEEKLY_BASKET.find((b) => b.canonical_id === canonicalId)?.quantity ?? 1;
}

function pricedItem(store: StoreSpec, line: Line): PricedItem {
  const cat = CATALOG[line.canonical_id]!;
  const qty = quantityOf(line.canonical_id);
  const lineAgorot =
    line.lineTotal !== undefined ? toAgorot(line.lineTotal) : toAgorot(line.price) * qty;
  const unitDivisor =
    cat.base_unit === "100g" || cat.base_unit === "100ml" ? cat.size / 100 : cat.size;
  const itemId = store.store_id * 100 + (line.canonical_id - 1000);
  return {
    canonical_id: line.canonical_id,
    item_id: itemId,
    promo_applied: false,
    display_name_he: line.name ?? cat.display_name_he,
    quantity: String(qty),
    shelf_price: money(toAgorot(line.price)),
    effective_unit_price: money(Math.round(lineAgorot / qty / unitDivisor)),
    uom: cat.uom,
    line_total: money(lineAgorot),
    is_substitute: Boolean(line.substitute),
    original_item_id: line.substitute ? 900000 + line.canonical_id : null,
    confidence: line.substitute?.confidence ?? null,
    tags: line.substitute?.tags ?? [],
    price_valid_from: PRICES_UPDATED_AT,
    promo_description: line.promo ?? null,
    club_required: Boolean(line.club),
    club_name: line.club ?? null,
    is_estimated: Boolean(cat.weighed),
  };
}

function sumAgorot(items: PricedItem[]) {
  return items.reduce((acc, i) => acc + toAgorot(Number(i.line_total)), 0);
}

export function storeResult(
  storeId: number,
  homeTotalAgorot: number | null,
  onlyCanonical?: number[],
): StoreResult {
  const spec = STORES.find((s) => s.store_id === storeId);
  if (!spec) throw new Error(`unknown store ${storeId}`);
  const wanted = onlyCanonical ?? WEEKLY_BASKET.map((b) => b.canonical_id);
  const items = spec.lines
    .filter((l) => wanted.includes(l.canonical_id))
    .map((l) => pricedItem(spec, l));
  const missing = wanted.filter((id) => !items.some((i) => i.canonical_id === id));
  const total = sumAgorot(items);
  return {
    store_id: spec.store_id,
    chain_id: spec.chain_id,
    chain_name: spec.chain_name,
    store_name: spec.store_name,
    city: "מודיעין",
    distance_m: spec.distance_m,
    channel: "physical",
    total: money(total),
    found_count: items.length,
    missing,
    substituted_count: items.filter((i) => i.is_substitute).length,
    items,
    prices_updated_at: PRICES_UPDATED_AT,
    saving_vs_home: homeTotalAgorot === null ? null : money(homeTotalAgorot - total),
  };
}

export const STORE_IDS = STORES.map((s) => s.store_id);

// ---------------------------------------------------------------------------------------------
// Responses

export function compareFixture(homeStoreId: number | null = HOME_STORE_ID): CompareResponse {
  const home = homeStoreId === null ? null : storeResult(homeStoreId, null);
  const homeTotal = home ? toAgorot(Number(home.total)) : null;
  const stores = STORE_IDS.map((id) => storeResult(id, homeTotal)).sort((a, b) => {
    const completeA = a.missing.length === 0 ? 0 : 1;
    const completeB = b.missing.length === 0 ? 0 : 1;
    return completeA - completeB || Number(a.total) - Number(b.total);
  });
  return {
    stores,
    home_store_id: homeStoreId,
    home_store_total: home ? home.total : null,
    generated_at: new Date().toISOString(),
    disclaimer_he: "המחיר הקובע הוא בקופה.",
  };
}

const SPLIT_RAMI = [1001, 1003, 1004, 1007, 1008, 1009];
const SPLIT_OSHER = [1002, 1005, 1006];
/** Fuel for the extra stop, from the artboard. */
const SPLIT_TRAVEL_AGOROT = 900;
const SPLIT_EXTRA_MINUTES = 12;

export function optimizeFixture(
  opts: { homeStoreId?: number | null; extraStopValue?: number; minSplitSaving?: number } = {},
): OptimizeResponse {
  const homeStoreId = opts.homeStoreId === undefined ? HOME_STORE_ID : opts.homeStoreId;
  const extraStopAgorot = toAgorot(opts.extraStopValue ?? 25);
  const minSplitAgorot = toAgorot(opts.minSplitSaving ?? 25);
  const home = homeStoreId === null ? null : storeResult(homeStoreId, null);
  const homeTotal = home ? toAgorot(Number(home.total)) : null;

  const breakdown = (totalAgorot: number, travel: number, extra: number) =>
    homeTotal === null
      ? null
      : {
          basket_saving: money(homeTotal - totalAgorot),
          travel_cost: money(travel),
          extra_stop_cost: money(extra),
          net_saving: money(homeTotal - totalAgorot - travel - extra),
        };

  const rami = storeResult(101, homeTotal);
  const single: Plan = {
    kind: "single",
    travel_cost: money(0),
    stores: [{ store: rami, item_ids: rami.items.map((i) => i.item_id) }],
    total: rami.total,
    missing: rami.missing,
    substituted_count: rami.substituted_count,
    extra_minutes: 0,
    recommended: true,
    breakdown: breakdown(toAgorot(Number(rami.total)), 0, 0),
  };

  const ramiPart = storeResult(101, null, SPLIT_RAMI);
  const osherPart = storeResult(102, null, SPLIT_OSHER);
  const splitTotal = toAgorot(Number(ramiPart.total)) + toAgorot(Number(osherPart.total));
  const splitNet =
    homeTotal === null ? null : homeTotal - splitTotal - SPLIT_TRAVEL_AGOROT - extraStopAgorot;
  const split: Plan | null =
    splitNet !== null && splitNet < minSplitAgorot
      ? null
      : {
          kind: "split",
          travel_cost: money(SPLIT_TRAVEL_AGOROT),
          stores: [
            { store: ramiPart, item_ids: ramiPart.items.map((i) => i.item_id) },
            { store: osherPart, item_ids: osherPart.items.map((i) => i.item_id) },
          ],
          total: money(splitTotal),
          missing: [],
          substituted_count: ramiPart.substituted_count + osherPart.substituted_count,
          extra_minutes: SPLIT_EXTRA_MINUTES,
          recommended: false,
          breakdown: breakdown(splitTotal, SPLIT_TRAVEL_AGOROT, extraStopAgorot),
        };

  // The recommended plan is the one with the higher net saving.
  if (
    split &&
    single.breakdown &&
    split.breakdown &&
    Number(split.breakdown.net_saving) > Number(single.breakdown.net_saving)
  ) {
    single.recommended = false;
    split.recommended = true;
  }

  const minimum_effort: Plan | null = home
    ? {
        kind: "minimum_effort",
        travel_cost: money(0),
        stores: [
          {
            store: { ...home, saving_vs_home: "0.00" },
            item_ids: home.items.map((i) => i.item_id),
          },
        ],
        total: home.total,
        missing: home.missing,
        substituted_count: 0,
        extra_minutes: 0,
        recommended: false,
        breakdown: breakdown(toAgorot(Number(home.total)), 0, 0),
      }
    : null;

  const n = STORE_IDS.length;
  return {
    single,
    split,
    minimum_effort,
    solver: "heuristic",
    subsets_evaluated: n + (n * (n - 1)) / 2,
    generated_at: new Date().toISOString(),
    disclaimer_he: "המחיר הקובע הוא בקופה.",
  };
}
