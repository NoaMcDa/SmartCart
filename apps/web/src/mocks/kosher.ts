/**
 * The mock's reading of the kosher filter (`CompareRequest.kosher`, `GET /search?kosher=`): the real
 * API reads certification from the item names (smartcart_catalog/kosher.py) and filters the basket
 * (docs/matching.md, "Kosher"). The fixtures' names state almost nothing, as the real files do, so
 * the mock keeps a small table of what some fixture items "state" and applies the same three
 * answers (meets, unknown, ruled out) to the fixture responses, so every kosher path of the UI can
 * be exercised against the mock:
 *   - unlisted items state nothing: unknown (labelled; left out with `only_stated`);
 *   - the Shufersal cottage cheese states בד"ץ, the Rami Levy milk states מהדרין, the Yohananof
 *     olive oil states בד"ץ העדה החרדית, the Osher Ad pasta states "כשר לפסח" and the Victory
 *     salmon says it is not kosher (ruled out at every level).
 * Totals, missing items, the savings against the home store and the plans' breakdowns are rebuilt
 * from the lines that remain, as the API computes them.
 */
import type {
  CompareResponse,
  OptimizeResponse,
  Plan,
  PricedItem,
  Schemas,
  StoreResult,
} from "@/api/client";

type KosherFilter = Schemas["KosherFilter"];
type KosherLabel = Schemas["KosherLabel"];
type Verdict = "meets" | "unknown" | "fails";

/** chain id -> canonical id -> the marks the item's name states (mock data). */
const STATED: Record<string, Record<number, string[]>> = {
  shufersal: { 1002: ["badatz"] },
  rami_levy: { 1001: ["mehadrin"] },
  yochananof: { 1005: ["badatz", "badatz_eida"] },
  osher_ad: { 1006: ["passover"] },
  victory: { 1008: ["not_kosher"] },
};

const SPECIFIC = new Set([
  "badatz_eida",
  "badatz_beit_yosef",
  "badatz_chatam_sofer",
  "badatz_agudat",
  "landau",
  "rabbanut_mehadrin",
]);
const BADATZ_FAMILY = new Set([
  "badatz",
  "badatz_eida",
  "badatz_beit_yosef",
  "badatz_chatam_sofer",
  "badatz_agudat",
]);
const SUPERVISED = new Set([
  ...BADATZ_FAMILY,
  "kosher",
  "mehadrin",
  "rabbanut",
  "rabbanut_mehadrin",
  "landau",
]);

const any = (marks: string[], set: Set<string>) => marks.some((m) => set.has(m));

/** The same answers as `smartcart_catalog.kosher.judge`. */
export function judgeLevel(marks: string[], level: string | null | undefined): Verdict {
  if (!level) return "meets";
  if (marks.includes("not_kosher")) return "fails";
  if (level === "regular") return any(marks, SUPERVISED) ? "meets" : "unknown";
  if (level === "mehadrin")
    return any(marks, new Set([...BADATZ_FAMILY, "mehadrin", "rabbanut_mehadrin"]))
      ? "meets"
      : "unknown";
  if (level === "badatz") return any(marks, BADATZ_FAMILY) ? "meets" : "unknown";
  if (marks.includes(level)) return "meets";
  return marks.some((m) => SPECIFIC.has(m) && m !== level) ? "fails" : "unknown";
}

function judgePassover(marks: string[]): Verdict {
  if (marks.includes("not_passover") || marks.includes("not_kosher")) return "fails";
  return marks.includes("passover") ? "meets" : "unknown";
}

function statedOf(chainId: string, canonicalId: number): string[] {
  return STATED[chainId]?.[canonicalId] ?? [];
}

/** The label of an item that may be offered, or null when the filter rules it out. */
function assess(
  marks: string[],
  f: KosherFilter,
): { label: KosherLabel; allowed: boolean; fails: boolean } {
  const level = judgeLevel(marks, f.level);
  const passover: Verdict = f.passover ? judgePassover(marks) : "meets";
  const fails = level === "fails" || passover === "fails";
  const allowed = !fails && !(f.only_stated && (level !== "meets" || passover !== "meets"));
  return {
    fails,
    allowed,
    label: {
      level: f.level ? (level === "meets" ? "meets" : "unknown") : null,
      passover: f.passover ? (passover === "meets" ? "meets" : "unknown") : null,
      stated: marks,
    },
  };
}

export function kosherActive(f: KosherFilter | null | undefined): f is KosherFilter {
  return Boolean(f && (f.level || f.passover));
}

const agorot = (v: string) => Math.round(Number(v) * 100);
const money = (a: number) => (a / 100).toFixed(2);

function filterStore(store: StoreResult, f: KosherFilter): StoreResult {
  const kept: PricedItem[] = [];
  const excluded: number[] = [];
  for (const line of store.items) {
    const a = assess(statedOf(store.chain_id, line.canonical_id), f);
    if (a.allowed) kept.push({ ...line, kosher: a.label });
    else excluded.push(line.canonical_id);
  }
  const missing = [...store.missing, ...excluded];
  return {
    ...store,
    items: kept,
    found_count: kept.length,
    missing,
    substituted_count: kept.filter((l) => l.is_substitute).length,
    total: money(kept.reduce((n, l) => n + agorot(l.line_total), 0)),
    kosher_excluded: excluded,
  };
}

/** Home minus store over the canonicals both supply: missing items are never a saving. */
function savingVsHome(home: StoreResult | null, store: StoreResult, only?: Set<number>) {
  if (!home) return null;
  const mine = new Map(store.items.map((l) => [l.canonical_id, l]));
  let total = 0;
  for (const h of home.items) {
    const l = mine.get(h.canonical_id);
    if (l && (!only || only.has(h.canonical_id)))
      total += agorot(h.line_total) - agorot(l.line_total);
  }
  return money(total);
}

export function applyKosherToCompare(
  res: CompareResponse,
  f: KosherFilter | null | undefined,
): CompareResponse {
  if (!kosherActive(f)) return res;
  const filtered = res.stores.map((s) => filterStore(s, f));
  const home = filtered.find((s) => s.store_id === res.home_store_id) ?? null;
  const stores = filtered
    .filter((s) => s.items.length > 0)
    .map((s) => ({ ...s, saving_vs_home: savingVsHome(home, s) }))
    .sort(
      (a, b) =>
        a.missing.length - b.missing.length ||
        Number(a.total) - Number(b.total) ||
        a.distance_m - b.distance_m,
    );
  return {
    ...res,
    stores,
    home_store_total: home ? home.total : null,
    kosher_hidden_stores: filtered.filter((s) => s.items.length === 0 && s.kosher_excluded?.length)
      .length,
  };
}

function filterPlan(
  plan: Plan | null | undefined,
  f: KosherFilter,
  home: StoreResult | null,
): Plan | null | undefined {
  if (!plan) return plan;
  const dropped: number[] = [];
  const stores = plan.stores.map((a) => {
    const store = filterStore(a.store, f);
    // the plan's own missing list is not the store's: only what this part bought can be dropped
    dropped.push(...(store.kosher_excluded ?? []));
    const only = new Set(store.items.map((l) => l.canonical_id));
    return {
      item_ids: store.items.map((l) => l.item_id),
      store: { ...store, saving_vs_home: savingVsHome(home, store, only) },
    };
  });
  const total = stores.reduce((n, a) => n + agorot(a.store.total), 0);
  const kept = new Set(stores.flatMap((a) => a.store.items.map((l) => l.canonical_id)));
  let breakdown = plan.breakdown;
  if (breakdown && home) {
    const basketSaving = home.items
      .filter((h) => kept.has(h.canonical_id))
      .reduce((n, h) => {
        const mine = stores
          .flatMap((a) => a.store.items)
          .find((l) => l.canonical_id === h.canonical_id);
        return n + (mine ? agorot(h.line_total) - agorot(mine.line_total) : 0);
      }, 0);
    breakdown = {
      ...breakdown,
      basket_saving: money(basketSaving),
      net_saving: money(
        basketSaving - agorot(breakdown.travel_cost) - agorot(breakdown.extra_stop_cost),
      ),
    };
  }
  return {
    ...plan,
    stores,
    total: money(total),
    missing: [...new Set([...(plan.missing ?? []), ...dropped])],
    kosher_excluded: [...new Set(dropped)],
    substituted_count: stores.reduce((n, a) => n + a.store.substituted_count, 0),
    breakdown,
  };
}

export function applyKosherToOptimize(
  res: OptimizeResponse,
  f: KosherFilter | null | undefined,
): OptimizeResponse {
  if (!kosherActive(f)) return res;
  const homeStore = res.minimum_effort?.stores[0]?.store ?? null;
  const home = homeStore ? filterStore(homeStore, f) : null;
  return {
    ...res,
    single: filterPlan(res.single, f, home) as Plan,
    split: filterPlan(res.split, f, home),
    minimum_effort: filterPlan(res.minimum_effort, f, home),
  };
}

/** The label of one hit of `GET /search` under the filter, from the fixture items of the canonical. */
export function kosherHitLabel(
  canonicalId: number,
  chainIds: string[],
  f: KosherFilter,
): Schemas["KosherHitLabel"] {
  let meets = 0;
  let unknown = 0;
  let fails = 0;
  for (const chain of chainIds) {
    const a = assess(statedOf(chain, canonicalId), f);
    if (a.fails) fails += 1;
    else if (a.label.level !== "unknown" && a.label.passover !== "unknown") meets += 1;
    else unknown += 1;
  }
  const status = meets > 0 ? "meets" : unknown > 0 && !f.only_stated ? "unknown" : "none";
  return { status, meets, unknown, fails };
}

/** A mock swap's item (the item of the store's chain for the canonical): its label, and whether
 * the filter lets it be suggested. Without a filter it is allowed and has no label. */
export function kosherSwap(
  chainId: string,
  canonicalId: number,
  f: KosherFilter | null | undefined,
): { label: KosherLabel | null; allowed: boolean } {
  if (!kosherActive(f)) return { label: null, allowed: true };
  const a = assess(statedOf(chainId, canonicalId), f);
  return { label: a.label, allowed: a.allowed };
}
