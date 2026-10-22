/**
 * What the person's own history says (phase 3): the items they buy most often and how many they
 * usually take, the items whose usual interval has passed, and the categories where they keep
 * choosing the exact brand. Pure functions over `PersonalDoc`; nothing here reads a clock, a
 * store or the network, so every rule is unit tested with fixed dates.
 *
 * Rules, all deliberately conservative (precision over recall: a wrong "buy again" costs more
 * trust than a missed one):
 *
 * - A "shopping day" is one Israel calendar day with at least one trip. A cleared list loses the
 *   products a finished trip within three days already holds (the person finished that list, then
 *   cleared it: one shop, not two).
 * - "Usual" needs the product on at least 3 shopping days. Rank: days, then most recent.
 * - "Buy again" needs at least 3 shopping days (2 gaps), a median gap of 3 to 90 days that is
 *   steady (the median deviation of the gaps is at most 40% of the gap, at least 2 days, and no gap
 *   is over three times the usual one), the gap having passed since the last purchase, and no more
 *   than three gaps having passed (after that the person has probably stopped). A dismissal hides it until the person buys the product again
 *   or one more gap passes.
 * - A brand offer needs 3 signals in a category within 90 days, counted after the last dismissal.
 */
import type { CanonicalRef, FlexLevel } from "@/api/client";
import { lookupDefault, SMART_DEFAULTS, type FlexDefaults } from "@/state/flex";
import { dayIndex, type Dismissal, type PersonalDoc, type Trip } from "./personalDoc";

export const MIN_DAYS_FOR_USUAL = 3;
export const MIN_DAYS_FOR_BUY_AGAIN = 3;
export const MIN_GAP_DAYS = 3;
export const MAX_GAP_DAYS = 90;
export const GAPS_USED = 6;
export const OVERDUE_GIVE_UP = 3;
export const MIN_SIGNALS_FOR_OFFER = 3;
export const SIGNAL_WINDOW_DAYS = 90;
export const SUPERSEDE_DAYS = 3;
export const MAX_USUAL = 12;
export const MAX_BUY_AGAIN = 5;

const median = (xs: number[]): number => {
  const s = [...xs].sort((a, b) => a - b);
  const mid = s.length >> 1;
  return s.length % 2 ? s[mid]! : (s[mid - 1]! + s[mid]!) / 2;
};

const refsById = (doc: PersonalDoc): Map<number, CanonicalRef> =>
  new Map(doc.refs.map((r) => [r.canonical_id, r]));

// ---------------------------------------------------------------------------------------------
// Shopping days

export type ShoppingDay = { day: number; lines: Map<number, number> };

/**
 * The trips that count. A cleared list loses the products a finished trip within three days already
 * holds (the person finished that list, then cleared it: one shop, not two); what is left of it
 * (products that were not ticked) stays as the weaker evidence it is, and a list with nothing left
 * is dropped.
 */
export function effectiveTrips(trips: ReadonlyArray<Trip>): Trip[] {
  const finished = trips
    .filter((t) => t.kind === "finished")
    .map((t) => ({ day: dayIndex(t.at), ids: new Set(t.lines.map((l) => l.canonical_id)) }));
  const out: Trip[] = [];
  for (const t of trips) {
    if (t.kind !== "list") {
      out.push(t);
      continue;
    }
    const day = dayIndex(t.at);
    const near = finished.filter((f) => Math.abs(f.day - day) <= SUPERSEDE_DAYS);
    const lines = t.lines.filter((l) => !near.some((f) => f.ids.has(l.canonical_id)));
    if (lines.length === t.lines.length) out.push(t);
    else if (lines.length > 0) out.push({ ...t, lines });
  }
  return out;
}

/** Trips folded to one entry per Israel calendar day, oldest first. A product keeps its largest quantity that day. */
export function shoppingDays(trips: ReadonlyArray<Trip>): ShoppingDay[] {
  const byDay = new Map<number, Map<number, number>>();
  for (const t of effectiveTrips(trips)) {
    const day = dayIndex(t.at);
    if (!Number.isFinite(day)) continue;
    const lines = byDay.get(day) ?? new Map<number, number>();
    for (const l of t.lines)
      lines.set(l.canonical_id, Math.max(lines.get(l.canonical_id) ?? 0, l.quantity));
    byDay.set(day, lines);
  }
  return [...byDay.entries()].sort((a, b) => a[0] - b[0]).map(([day, lines]) => ({ day, lines }));
}

type Stats = { id: number; days: number[]; quantities: number[] };

function statsOf(days: ReadonlyArray<ShoppingDay>): Map<number, Stats> {
  const out = new Map<number, Stats>();
  for (const d of days) {
    for (const [id, q] of d.lines) {
      const s = out.get(id) ?? { id, days: [], quantities: [] };
      s.days.push(d.day);
      s.quantities.push(q);
      out.set(id, s);
    }
  }
  return out;
}

/** The usual quantity: the median of what was taken, whole numbers (halves for a weight). */
export function usualQuantity(quantities: number[], weighed: boolean): number {
  const m = median(quantities);
  if (weighed) return Math.max(0.5, Math.round(m * 2) / 2);
  return Math.max(1, Math.round(m));
}

// ---------------------------------------------------------------------------------------------
// My usual

export type UsualItem = {
  ref: CanonicalRef;
  /** Shopping days the product was on. */
  days: number;
  quantity: number;
  /** Days since the last purchase (0 = today). */
  lastDaysAgo: number;
};

function allUsual(doc: PersonalDoc, now: Date): UsualItem[] {
  const refs = refsById(doc);
  const today = dayIndex(now.toISOString());
  const out: UsualItem[] = [];
  for (const s of statsOf(shoppingDays(doc.trips)).values()) {
    const ref = refs.get(s.id);
    if (!ref || s.days.length < MIN_DAYS_FOR_USUAL) continue;
    out.push({
      ref,
      days: s.days.length,
      quantity: usualQuantity(s.quantities, ref.base_unit === "kg"),
      lastDaysAgo: Math.max(0, today - Math.max(...s.days)),
    });
  }
  return out;
}

/** The products bought most often, at most 12: more days first, then the more recent. */
export function usualItems(doc: PersonalDoc, now: Date): UsualItem[] {
  return allUsual(doc, now)
    .sort(
      (a, b) =>
        b.days - a.days || a.lastDaysAgo - b.lastDaysAgo || a.ref.canonical_id - b.ref.canonical_id,
    )
    .slice(0, MAX_USUAL);
}

/** Every product with a usual quantity, by canonical id, for the "you usually take N" line of a row. */
export function usualQuantities(doc: PersonalDoc, now: Date): Map<number, UsualItem> {
  return new Map(allUsual(doc, now).map((u) => [u.ref.canonical_id, u]));
}

// ---------------------------------------------------------------------------------------------
// Buy again

export type BuyAgainItem = {
  ref: CanonicalRef;
  /** The usual gap between purchases, in days (median, rounded). */
  everyDays: number;
  /** Days since the last purchase. */
  sinceDays: number;
  quantity: number;
};

function gapsOf(days: number[]): number[] {
  const sorted = [...days].sort((a, b) => a - b);
  const gaps: number[] = [];
  for (let i = 1; i < sorted.length; i += 1) gaps.push(sorted[i]! - sorted[i - 1]!);
  return gaps.slice(-GAPS_USED);
}

/** The gap the person usually leaves, or null when the history is too thin or too erratic. */
export function usualGap(days: number[]): number | null {
  if (days.length < MIN_DAYS_FOR_BUY_AGAIN) return null;
  const gaps = gapsOf(days);
  const m = median(gaps);
  const mad = median(gaps.map((g) => Math.abs(g - m)));
  const every = Math.round(m);
  if (every < MIN_GAP_DAYS || every > MAX_GAP_DAYS) return null;
  if (mad > Math.max(2, 0.4 * m)) return null;
  // One long pause (a holiday, a change of store) means the pattern is not steady enough to predict.
  if (Math.max(...gaps) > 3 * m) return null;
  return every;
}

const dismissalOf = (doc: PersonalDoc, kind: Dismissal["kind"], key: string) =>
  doc.dismissals.find((d) => d.kind === kind && d.key === key);

/**
 * Items whose usual gap has passed, most overdue first. `onList` holds canonical ids already on
 * the list (they are not suggested).
 */
export function buyAgainItems(
  doc: PersonalDoc,
  now: Date,
  onList: ReadonlySet<number> = new Set(),
): BuyAgainItem[] {
  const refs = refsById(doc);
  const today = dayIndex(now.toISOString());
  const out: Array<BuyAgainItem & { over: number }> = [];
  for (const s of statsOf(shoppingDays(doc.trips)).values()) {
    const ref = refs.get(s.id);
    if (!ref || onList.has(s.id)) continue;
    const every = usualGap(s.days);
    if (every === null) continue;
    const last = Math.max(...s.days);
    const since = today - last;
    if (since < every || since > every * (1 + OVERDUE_GIVE_UP)) continue;
    const dismissed = dismissalOf(doc, "buy_again", String(s.id));
    if (dismissed) {
      const at = dayIndex(dismissed.at);
      // Bought again since: the dismissal is about an older cycle. Otherwise one more gap from the
      // dismissal.
      if (!(last > at) && today < at + every) continue;
    }
    out.push({
      ref,
      everyDays: every,
      sinceDays: since,
      quantity: usualQuantity(s.quantities, ref.base_unit === "kg"),
      over: since - every,
    });
  }
  return out
    .sort((a, b) => b.over - a.over || a.ref.canonical_id - b.ref.canonical_id)
    .slice(0, MAX_BUY_AGAIN)
    .map(({ over: _over, ...item }) => item);
}

// ---------------------------------------------------------------------------------------------
// Brand preferences

export type BrandOffer = {
  taxonomyId: string;
  /** Signals counted (3 or more). */
  count: number;
  /** A product of the category the person's history names, for the category's own name. */
  sample: CanonicalRef | null;
};

/** The level a category has now, with the person's defaults over the smart ones. */
export function effectiveDefault(taxonomyId: string, defaults: FlexDefaults): FlexLevel | null {
  return lookupDefault(taxonomyId, defaults) ?? lookupDefault(taxonomyId, SMART_DEFAULTS) ?? null;
}

/**
 * Categories where the person has kept the exact brand or turned a substitute down at least three
 * times in 90 days, and whose default is not already "exact". An offer: nothing is applied.
 */
export function brandOffers(doc: PersonalDoc, defaults: FlexDefaults, now: Date): BrandOffer[] {
  const today = dayIndex(now.toISOString());
  const categories = new Set(doc.signals.map((s) => s.taxonomy_id));
  const out: BrandOffer[] = [];
  for (const taxonomyId of categories) {
    if (effectiveDefault(taxonomyId, defaults) === "exact") continue;
    const dismissed = dismissalOf(doc, "brand_default", taxonomyId);
    const windowStart = today - SIGNAL_WINDOW_DAYS;
    const count = doc.signals.filter((s) => {
      if (s.taxonomy_id !== taxonomyId) return false;
      const t = Date.parse(s.at);
      if (dayIndex(s.at) < windowStart) return false;
      return dismissed ? t > Date.parse(dismissed.at) : true;
    }).length;
    if (count < MIN_SIGNALS_FOR_OFFER) continue;
    out.push({
      taxonomyId,
      count,
      sample: doc.refs.find((r) => r.taxonomy_id === taxonomyId) ?? null,
    });
  }
  return out.sort((a, b) => b.count - a.count || a.taxonomyId.localeCompare(b.taxonomyId));
}
