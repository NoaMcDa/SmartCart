/**
 * Price-history series maths (issue #28), kept apart from the SVG so it can be unit tested.
 *
 * The API returns a reconstructed series for one store (or the chain base price when `store_id` is
 * null): a point per day that has data. A day without a point is a gap, never a flat line: the
 * line is cut where consecutive points are more than MAX_JOIN_DAYS apart, and the chart says so.
 */
import type { PriceHistoryResponse, PromoWindow } from "@/api/client";

export const DAY_MS = 86_400_000;
/** Two points further apart than this are not joined by a line. The mock samples every 3 days. */
export const MAX_JOIN_DAYS = 3;

export type Metric = "unit" | "shelf";

export type SeriesPoint = { t: number; value: number; promo: string | null };
export type Window = { start: number; end: number };
export type Gap = { from: number; to: number; days: number };
export type PromoRange = {
  from: number;
  to: number;
  description: string;
  /** Only club members or card holders get it (the API's `club_only`). */
  clubOnly: boolean;
  clubName: string | null;
  /** Parsing confidence 0..1, or null when the API does not know it. */
  confidence: number | null;
};

/** Points with a usable value for `metric`, oldest first, one per instant. */
export function seriesOf(res: PriceHistoryResponse, metric: Metric): SeriesPoint[] {
  const byTime = new Map<number, SeriesPoint>();
  for (const p of res.points) {
    const t = Date.parse(p.date);
    const raw = metric === "unit" ? p.unit_price : p.shelf_price;
    const value = raw === null || raw === undefined ? NaN : Number.parseFloat(raw);
    if (!Number.isFinite(t) || !Number.isFinite(value)) continue;
    byTime.set(t, { t, value, promo: p.promo_description ?? null });
  }
  return [...byTime.values()].sort((a, b) => a.t - b.t);
}

/** The chart's time window: `days` back from when the series was generated. */
export function windowOf(res: PriceHistoryResponse, days: number): Window {
  const end = Date.parse(res.generated_at);
  const stop = Number.isFinite(end) ? end : Date.now();
  return { start: stop - days * DAY_MS, end: stop };
}

export function inWindow(points: SeriesPoint[], win: Window): SeriesPoint[] {
  return points.filter((p) => p.t >= win.start && p.t <= win.end);
}

/** Runs of points that are close enough to be joined by a line. */
export function splitSegments(points: SeriesPoint[], maxJoinDays = MAX_JOIN_DAYS): SeriesPoint[][] {
  const segments: SeriesPoint[][] = [];
  let current: SeriesPoint[] = [];
  for (const p of points) {
    const prev = current[current.length - 1];
    if (prev && p.t - prev.t > maxJoinDays * DAY_MS) {
      segments.push(current);
      current = [];
    }
    current.push(p);
  }
  if (current.length > 0) segments.push(current);
  return segments;
}

/** Stretches without data: inside the series, before its first point and after its last. */
export function findGaps(points: SeriesPoint[], win: Window, maxJoinDays = MAX_JOIN_DAYS): Gap[] {
  const limit = maxJoinDays * DAY_MS;
  const gaps: Gap[] = [];
  const add = (from: number, to: number) => {
    gaps.push({ from, to, days: Math.round((to - from) / DAY_MS) });
  };
  if (points.length === 0) {
    add(win.start, win.end);
    return gaps;
  }
  const first = points[0]!;
  const last = points[points.length - 1]!;
  if (first.t - win.start > limit) add(win.start, first.t);
  for (let i = 1; i < points.length; i += 1) {
    const a = points[i - 1]!;
    const b = points[i]!;
    if (b.t - a.t > limit) add(a.t, b.t);
  }
  if (win.end - last.t > limit) add(last.t, win.end);
  return gaps;
}

/** Promo windows that overlap the chart, clamped to it. */
export function promoRanges(promos: PromoWindow[] | undefined, win: Window): PromoRange[] {
  const out: PromoRange[] = [];
  for (const p of promos ?? []) {
    const from = p.starts_at ? Date.parse(p.starts_at) : win.start;
    const to = p.ends_at ? Date.parse(p.ends_at) : win.end;
    if (!Number.isFinite(from) || !Number.isFinite(to) || to < win.start || from > win.end)
      continue;
    out.push({
      from: Math.max(from, win.start),
      to: Math.min(to, win.end),
      description: p.description,
      clubOnly: p.club_only === true,
      clubName: p.club_name ?? null,
      confidence: typeof p.confidence === "number" ? p.confidence : null,
    });
  }
  return out.sort((a, b) => a.from - b.from);
}

/** Value range with a little air, never zero-height. */
export function valueDomain(points: SeriesPoint[]): { lo: number; hi: number } {
  if (points.length === 0) return { lo: 0, hi: 1 };
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = max === min ? Math.max(0.5, max * 0.1) : (max - min) * 0.15;
  return { lo: Math.max(0, min - pad), hi: max + pad };
}

export function linear(
  [d0, d1]: readonly [number, number],
  [r0, r1]: readonly [number, number],
): (x: number) => number {
  const span = d1 - d0;
  return (x) => (span === 0 ? (r0 + r1) / 2 : r0 + ((x - d0) / span) * (r1 - r0));
}

const TZ = "Asia/Jerusalem";

/** "07.10" in Israel time. */
export function formatDay(t: number): string {
  return new Date(t)
    .toLocaleDateString("he-IL", { day: "2-digit", month: "2-digit", timeZone: TZ })
    .replace(/\//g, ".");
}

export function money(value: number): string {
  return value.toFixed(2);
}

export type HistorySummary = {
  min: number;
  max: number;
  latest: number;
  promoDays: number;
  gapDays: number;
};

export function summarize(
  points: SeriesPoint[],
  promos: PromoRange[],
  gaps: Gap[],
): HistorySummary | null {
  const last = points[points.length - 1];
  if (!last) return null;
  const values = points.map((p) => p.value);
  return {
    min: Math.min(...values),
    max: Math.max(...values),
    latest: last.value,
    promoDays: promos.reduce(
      (sum, p) => sum + Math.max(1, Math.round((p.to - p.from) / DAY_MS)),
      0,
    ),
    gapDays: gaps.reduce((sum, g) => sum + g.days, 0),
  };
}

/** The promo window a point falls in, if any (for tooltips). */
export function promoAt(promos: PromoRange[], t: number): PromoRange | null {
  return promos.find((p) => t >= p.from - DAY_MS / 2 && t <= p.to + DAY_MS / 2) ?? null;
}

/** "מבצע מועדון · רמי לוי" or "מבצע לכולם". */
export function promoAudience(p: Pick<PromoRange, "clubOnly" | "clubName">): string {
  if (!p.clubOnly) return "מבצע לכולם";
  return p.clubName ? `מבצע מועדון · ${p.clubName}` : "מבצע מועדון";
}

/** Confidence on a promo (D10): a percentage, or "לא נבדק" when the API has none. */
export function promoConfidence(p: Pick<PromoRange, "confidence">): string {
  return p.confidence === null
    ? "ביטחון במבצע: לא נבדק"
    : `ביטחון במבצע: ${Math.round(p.confidence * 100)}%`;
}
