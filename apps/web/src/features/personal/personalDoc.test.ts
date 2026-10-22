import { describe, expect, it } from "vitest";
import {
  DEFAULT_PREFS,
  EMPTY_DOC,
  LIMITS,
  dayIndex,
  docBytes,
  docKey,
  isEmptyHistory,
  mergeDocs,
  normalizeDoc,
  sanitizeDoc,
} from "./personalDoc";
import {
  COTTAGE,
  EGGS,
  MILK,
  NOW,
  daysAgo,
  dismissal,
  doc,
  id,
  regularDoc,
  signal,
  trip,
} from "./fixtures";

describe("dayIndex", () => {
  it("counts Israel calendar days, not UTC ones", () => {
    // 22:30 UTC on the 21st is 01:30 on the 22nd in Israel (UTC+3 in October 2026, DST ends the 25th).
    const late = dayIndex("2026-10-21T22:30:00Z");
    const next = dayIndex("2026-10-22T08:00:00Z");
    expect(late).toBe(next);
    expect(dayIndex("2026-10-21T20:30:00Z")).toBe(next - 1);
  });

  it("is NaN for text that is not a time", () => {
    expect(Number.isNaN(dayIndex("yesterday"))).toBe(true);
  });
});

describe("sanitizeDoc", () => {
  it("reads nothing, junk and another version as an empty document", () => {
    expect(sanitizeDoc(null)).toEqual(EMPTY_DOC);
    expect(sanitizeDoc("x")).toEqual(EMPTY_DOC);
    expect(sanitizeDoc({ version: 2, trips: [{}] })).toEqual(EMPTY_DOC);
  });

  it("round-trips a good document", () => {
    const d = regularDoc();
    expect(sanitizeDoc(JSON.parse(JSON.stringify(d)), NOW)).toEqual(d);
  });

  it("drops what the screens or the API could not take, and keeps the rest", () => {
    const good = trip(2, [[MILK, 2]]);
    const raw = {
      version: 1,
      prefs: { learn: "yes", value_packs: 1, updated_at: "not a date" },
      refs: [MILK, { canonical_id: "x" }, { ...COTTAGE, base_unit: "litre" }, null],
      trips: [
        good,
        { ...good, id: "short" },
        { ...good, id: "trip-bad-kind", kind: "bought" },
        { ...good, id: "trip-no-lines", lines: [] },
        { ...good, id: "trip-bad-line", lines: [{ canonical_id: 1.5, quantity: 1 }] },
        { ...good, id: "trip-zero-qty", lines: [{ canonical_id: 1, quantity: 0 }] },
        { ...good, id: "trip-huge-qty", lines: [{ canonical_id: 1, quantity: 5000 }] },
        { ...good, id: "trip-bad-time", at: "later" },
        {
          ...good,
          id: "trip-dup-lines",
          lines: [
            { canonical_id: 7, quantity: 1 },
            { canonical_id: 7, quantity: 3 },
          ],
        },
      ],
      signals: [signal(1, "dairy.milk"), { id: "sig-000001", at: daysAgo(1), kind: "x" }],
      dismissals: [dismissal(1, "buy_again", "1001"), { kind: "other", key: "1", at: daysAgo(1) }],
    };
    const out = sanitizeDoc(raw, NOW);
    expect(out.prefs).toEqual(DEFAULT_PREFS); // wrong types fall back to the defaults
    expect(out.refs.map((r) => r.canonical_id)).toEqual([MILK.canonical_id]);
    expect(out.trips.map((t) => t.id).sort()).toEqual([good.id, "trip-dup-lines"].sort());
    expect(out.trips.find((t) => t.id === "trip-dup-lines")!.lines).toEqual([
      { canonical_id: 7, quantity: 1 },
    ]);
    expect(out.signals).toHaveLength(1);
    expect(out.dismissals).toHaveLength(1);
  });

  it("keeps the preferences it is given", () => {
    const out = sanitizeDoc(
      { version: 1, prefs: { learn: false, value_packs: true, updated_at: daysAgo(1) } },
      NOW,
    );
    expect(out.prefs).toEqual({ learn: false, value_packs: true, updated_at: daysAgo(1) });
  });
});

describe("normalizeDoc", () => {
  it("keeps the newest 40 trips and the lines of each up to 60", () => {
    const many = Array.from({ length: 50 }, (_, i) => trip(i, [[MILK]]));
    const out = normalizeDoc(doc({ trips: many }, [MILK]), NOW);
    expect(out.trips).toHaveLength(LIMITS.trips);
    expect(out.trips[0]!.at).toBe(daysAgo(39));
    expect(out.trips.at(-1)!.at).toBe(daysAgo(0));
  });

  it("drops what is older than the retention window", () => {
    const old = trip(LIMITS.retentionDays + 1, [[MILK]]);
    const fresh = trip(LIMITS.retentionDays - 1, [[MILK]]);
    const out = normalizeDoc(
      doc(
        {
          trips: [old, fresh],
          signals: [signal(LIMITS.retentionDays + 5, "dairy"), signal(3, "dairy")],
          dismissals: [dismissal(LIMITS.retentionDays + 5, "buy_again", "1")],
        },
        [MILK],
      ),
      NOW,
    );
    expect(out.trips.map((t) => t.id)).toEqual([fresh.id]);
    expect(out.signals).toHaveLength(1);
    expect(out.dismissals).toEqual([]);
  });

  it("keeps references only for products a kept trip names", () => {
    const out = normalizeDoc(doc({ trips: [trip(1, [[MILK]])] }, [MILK, COTTAGE, EGGS]), NOW);
    expect(out.refs.map((r) => r.canonical_id)).toEqual([MILK.canonical_id]);
  });

  it("keeps the latest dismissal of a (kind, key) only", () => {
    const out = normalizeDoc(
      doc({
        dismissals: [
          dismissal(10, "buy_again", "1"),
          dismissal(2, "buy_again", "1"),
          dismissal(5, "brand_default", "1"),
        ],
      }),
      NOW,
    );
    expect(out.dismissals).toHaveLength(2);
    expect(out.dismissals.find((d) => d.kind === "buy_again")!.at).toBe(daysAgo(2));
  });

  it("drops duplicate ids", () => {
    const t = trip(1, [[MILK]]);
    expect(normalizeDoc(doc({ trips: [t, t] }, [MILK]), NOW).trips).toHaveLength(1);
  });

  it("stays under the byte budget by dropping the oldest trips", () => {
    const longName = {
      ...MILK,
      display_name_he: "א".repeat(120),
      display_name_ar: "ب".repeat(120),
    };
    const refs = Array.from({ length: 200 }, (_, i) => ({ ...longName, canonical_id: 10_000 + i }));
    // Every trip names 60 of the 200 products, so every reference is kept.
    const trips = Array.from({ length: 40 }, (_, t) =>
      trip(
        t,
        refs
          .slice((t * 3) % 140, ((t * 3) % 140) + 60)
          .map((r): [number, number] => [r.canonical_id, 999.5]),
      ),
    );
    expect(docBytes(doc({ trips, refs }))).toBeGreaterThan(LIMITS.maxBytes);
    const out = normalizeDoc(doc({ trips }, refs), NOW);
    expect(docBytes(out)).toBeLessThanOrEqual(LIMITS.maxBytes);
    expect(out.trips.length).toBeGreaterThan(0);
    expect(out.trips.length).toBeLessThan(40);
    // the newest trip survives; the oldest go first
    expect(out.trips.at(-1)!.at).toBe(daysAgo(0));
  });

  it("is idempotent", () => {
    const once = normalizeDoc(regularDoc(), NOW);
    expect(normalizeDoc(once, NOW)).toEqual(once);
  });
});

describe("mergeDocs", () => {
  const a = doc({ trips: [trip(5, [[MILK]]), trip(3, [[MILK]])] }, [MILK]);
  const b = doc(
    { trips: [a.trips[0]!, trip(1, [[COTTAGE]])], signals: [signal(2, "dairy.milk")] },
    [COTTAGE],
  );

  it("is the union of both sides, by id", () => {
    const m = mergeDocs(a, b, NOW);
    expect(m.trips).toHaveLength(3);
    expect(m.signals).toHaveLength(1);
    expect(m.refs.map((r) => r.canonical_id).sort()).toEqual(
      [MILK.canonical_id, COTTAGE.canonical_id].sort(),
    );
  });

  it("changes nothing when merged twice or with itself", () => {
    const m = mergeDocs(a, b, NOW);
    expect(docKey(mergeDocs(m, b, NOW))).toBe(docKey(m));
    expect(docKey(mergeDocs(a, a, NOW))).toBe(docKey(normalizeDoc(a, NOW)));
    expect(docKey(mergeDocs(b, a, NOW))).toBe(docKey(m)); // either direction
  });

  it("takes the preferences of the side that changed them last; the device wins a tie", () => {
    const dev = doc({ prefs: { learn: true, value_packs: true, updated_at: daysAgo(1) } });
    const acc = doc({ prefs: { learn: false, value_packs: false, updated_at: daysAgo(5) } });
    expect(mergeDocs(dev, acc, NOW).prefs.value_packs).toBe(true);
    expect(mergeDocs(acc, dev, NOW).prefs.value_packs).toBe(true);
    const tie = doc({ prefs: { learn: false, value_packs: false, updated_at: daysAgo(1) } });
    expect(mergeDocs(dev, tie, NOW).prefs.value_packs).toBe(true);
    // never changed anywhere: the device keeps its defaults
    expect(mergeDocs(doc(), doc(), NOW).prefs).toEqual(DEFAULT_PREFS);
  });

  it("a dismissal is kept at its latest time", () => {
    const x = doc({ dismissals: [dismissal(9, "buy_again", "1001")] });
    const y = doc({ dismissals: [dismissal(2, "buy_again", "1001")] });
    expect(mergeDocs(x, y, NOW).dismissals).toEqual([dismissal(2, "buy_again", "1001")]);
  });
});

describe("docKey and isEmptyHistory", () => {
  it("ignores the order things were added in", () => {
    const t1 = trip(5, [[MILK]]);
    const t2 = trip(3, [[MILK]]);
    expect(docKey(doc({ trips: [t1, t2] }))).toBe(docKey(doc({ trips: [t2, t1] })));
  });

  it("sees a preference change", () => {
    const base = doc();
    expect(docKey({ ...base, prefs: { ...base.prefs, value_packs: true } })).not.toBe(docKey(base));
  });

  it("knows an empty history", () => {
    expect(isEmptyHistory(EMPTY_DOC)).toBe(true);
    expect(isEmptyHistory(doc({ signals: [signal(1, "dairy")] }))).toBe(false);
    expect(id("x")).toMatch(/^x-\d{6}$/);
  });
});
