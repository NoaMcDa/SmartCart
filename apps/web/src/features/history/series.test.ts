import { describe, expect, it } from "vitest";
import type { PriceHistoryResponse } from "@/api/client";
import {
  DAY_MS,
  findGaps,
  inWindow,
  linear,
  promoRanges,
  seriesOf,
  splitSegments,
  summarize,
  valueDomain,
  windowOf,
} from "./series";

const END = Date.parse("2026-10-07T03:40:00Z");
const day = (n: number) => new Date(END - n * DAY_MS).toISOString();

function history(
  points: Array<{ d: number; unit: string | null; promo?: string }>,
  promos: PriceHistoryResponse["promos"] = [],
): PriceHistoryResponse {
  return {
    canonical_id: 1001,
    store_id: 103,
    days: 90,
    generated_at: new Date(END).toISOString(),
    promos,
    points: points.map((p) => ({
      date: day(p.d),
      unit_price: p.unit as string,
      shelf_price: p.unit === null ? null : (Number(p.unit) * 10).toFixed(2),
      store_id: 103,
      promo_description: p.promo ?? null,
    })),
  };
}

describe("series", () => {
  it("keeps points with a value, oldest first, one per instant", () => {
    const res = history([
      { d: 1, unit: "6.50" },
      { d: 3, unit: "6.40" },
      { d: 2, unit: null },
      { d: 3, unit: "6.45" }, // same instant again: the later one wins
    ]);
    const s = seriesOf(res, "unit");
    expect(s.map((p) => p.value)).toEqual([6.45, 6.5]);
    expect(seriesOf(res, "shelf").map((p) => p.value)).toEqual([64.5, 65]);
  });

  it("windows the series from when it was generated", () => {
    const res = history([
      { d: 100, unit: "7.00" },
      { d: 20, unit: "6.50" },
      { d: 0, unit: "6.40" },
    ]);
    const win = windowOf(res, 30);
    expect(win.end).toBe(END);
    expect(win.start).toBe(END - 30 * DAY_MS);
    expect(inWindow(seriesOf(res, "unit"), win)).toHaveLength(2);
  });
});

describe("gaps are gaps, never interpolated", () => {
  const res = history([
    { d: 20, unit: "6.50" },
    { d: 19, unit: "6.50" },
    { d: 18, unit: "6.40" },
    // nothing for days 17 to 11
    { d: 10, unit: "6.30" },
    { d: 9, unit: "6.30" },
  ]);
  const win = { start: END - 30 * DAY_MS, end: END };
  const points = seriesOf(res, "unit");

  it("cuts the line where days are missing", () => {
    const segments = splitSegments(points);
    expect(segments.map((s) => s.length)).toEqual([3, 2]);
  });

  it("joins the mock's 3-day sampling", () => {
    const sampled = seriesOf(history([0, 3, 6, 9].map((d) => ({ d, unit: "6.50" }))), "unit");
    expect(splitSegments(sampled)).toHaveLength(1);
  });

  it("lists the gaps before, inside and after the data", () => {
    const gaps = findGaps(points, win);
    expect(gaps.map((g) => g.days)).toEqual([
      10, // 30 days ago to the first point, 20 days ago
      8, // the hole between day 18 and day 10
      9, // day 9 to now
    ]);
    expect(findGaps([], win)).toEqual([{ from: win.start, to: win.end, days: 30 }]);
  });

  it("reports a complete series as having no gaps", () => {
    const full = seriesOf(
      history(Array.from({ length: 31 }, (_, d) => ({ d, unit: "6.50" }))),
      "unit",
    );
    expect(findGaps(full, win)).toEqual([]);
  });
});

describe("promo windows and scales", () => {
  it("clamps promo windows to the chart and drops the ones outside it", () => {
    const win = { start: END - 30 * DAY_MS, end: END };
    const ranges = promoRanges(
      [
        { description: "ישן", starts_at: day(80), ends_at: day(70) },
        { description: "חוצה", starts_at: day(40), ends_at: day(25) },
        { description: "פעיל", starts_at: day(3), ends_at: null },
      ],
      win,
    );
    expect(ranges.map((r) => r.description)).toEqual(["חוצה", "פעיל"]);
    expect(ranges[0]!.from).toBe(win.start);
    expect(ranges[1]!.to).toBe(win.end);
  });

  it("gives a flat series some height and maps values linearly", () => {
    const flat = seriesOf(
      history([
        { d: 1, unit: "6.00" },
        { d: 0, unit: "6.00" },
      ]),
      "unit",
    );
    const { lo, hi } = valueDomain(flat);
    expect(hi).toBeGreaterThan(lo);
    const y = linear([0, 10], [100, 0]);
    expect(y(0)).toBe(100);
    expect(y(10)).toBe(0);
    expect(y(5)).toBe(50);
  });

  it("summarizes the range, the latest price and the days of promo and gap", () => {
    const res = history(
      [
        { d: 5, unit: "6.00" },
        { d: 4, unit: "5.00", promo: "מבצע" },
        { d: 0, unit: "6.20" },
      ],
      [{ description: "מבצע", starts_at: day(5), ends_at: day(3) }],
    );
    const win = windowOf(res, 90);
    const points = seriesOf(res, "unit");
    const s = summarize(points, promoRanges(res.promos, win), findGaps(points, win));
    expect(s).toMatchObject({ min: 5, max: 6.2, latest: 6.2, promoDays: 2 });
    expect(s!.gapDays).toBeGreaterThan(80);
    expect(summarize([], [], [])).toBeNull();
  });
});
