import { describe, expect, it } from "vitest";
import {
  brandOffers,
  buyAgainItems,
  effectiveDefault,
  effectiveTrips,
  shoppingDays,
  usualGap,
  usualItems,
  usualQuantities,
  usualQuantity,
} from "./habits";
import {
  COTTAGE,
  EGGS,
  MILK,
  NOW,
  PASTA,
  TOMATOES,
  daysAgo,
  dismissal,
  doc,
  regularDoc,
  signal,
  trip,
} from "./fixtures";

describe("effectiveTrips and shoppingDays", () => {
  it("drops a cleared list that a finished trip of the same shop already covers", () => {
    const finished = trip(5, [[MILK], [COTTAGE], [PASTA]], "finished");
    const cleared = trip(4, [[MILK], [COTTAGE], [PASTA]], "list");
    expect(effectiveTrips([finished, cleared])).toEqual([finished]);
  });

  it("keeps a list that nothing finished, and a list far from a finished trip", () => {
    const finished = trip(20, [[MILK], [COTTAGE]], "finished");
    const near = trip(2, [[PASTA], [EGGS]], "list"); // other products
    const far = trip(5, [[MILK], [COTTAGE]], "list"); // same products, 15 days later
    expect(effectiveTrips([finished, near, far])).toEqual([finished, near, far]);
  });

  it("takes out only the products the finished trip holds and keeps the rest of the list", () => {
    const finished = trip(5, [[MILK]], "finished");
    const cleared = trip(5, [[MILK], [COTTAGE], [PASTA]], "list");
    const out = effectiveTrips([finished, cleared]);
    expect(out).toHaveLength(2);
    expect(out[1]!.lines.map((l) => l.canonical_id)).toEqual([
      COTTAGE.canonical_id,
      PASTA.canonical_id,
    ]);
    // A list nothing of which was finished is untouched, as the same object.
    const other = trip(5, [[EGGS]], "list");
    expect(effectiveTrips([finished, other])[1]).toBe(other);
  });

  it("a long list is not swallowed by a finished trip of one item", () => {
    const finished = trip(2, [[MILK]], "finished");
    const list = trip(1, [[MILK], [COTTAGE], [PASTA], [EGGS]], "list");
    const days = shoppingDays([finished, list]);
    expect([...days.at(-1)!.lines.keys()].sort()).toEqual(
      [COTTAGE, PASTA, EGGS].map((r) => r.canonical_id).sort(),
    );
  });

  it("folds trips of one Israel day into one shopping day with the larger quantity", () => {
    const days = shoppingDays([
      trip(3, [[MILK, 1]]),
      trip(3, [[MILK, 3], [COTTAGE]]),
      trip(1, [[MILK, 2]]),
    ]);
    expect(days).toHaveLength(2);
    expect(days[0]!.lines.get(MILK.canonical_id)).toBe(3);
    expect(days[0]!.lines.has(COTTAGE.canonical_id)).toBe(true);
  });
});

describe("usualQuantity", () => {
  it("is the median, whole for packs and in halves for a weight", () => {
    expect(usualQuantity([2, 2, 3], false)).toBe(2);
    expect(usualQuantity([1, 2], false)).toBe(2); // 1.5 rounds up to 2
    expect(usualQuantity([0.4], false)).toBe(1); // never below one pack
    expect(usualQuantity([1.2, 1.4, 1.6], true)).toBe(1.5);
    expect(usualQuantity([0.1], true)).toBe(0.5);
  });
});

describe("usualItems", () => {
  it("needs three shopping days, ranks by days then recency, and carries the usual quantity", () => {
    const d = regularDoc();
    const items = usualItems(d, NOW);
    expect(items.map((i) => i.ref.canonical_id)).toEqual([MILK.canonical_id, COTTAGE.canonical_id]);
    expect(items[0]).toMatchObject({ days: 5, quantity: 2, lastDaysAgo: 3 });
    expect(items[1]).toMatchObject({ days: 3, quantity: 1, lastDaysAgo: 10 });
  });

  it("leaves out a product bought on only two days", () => {
    const d = doc({ trips: [trip(9, [[EGGS]]), trip(2, [[EGGS]])] }, [EGGS]);
    expect(usualItems(d, NOW)).toEqual([]);
  });

  it("leaves out a product whose reference is unknown (nothing to draw)", () => {
    const d = doc({ trips: [trip(9, [[EGGS]]), trip(6, [[EGGS]]), trip(2, [[EGGS]])] }, []);
    expect(usualItems(d, NOW)).toEqual([]);
  });

  it("is at most twelve", () => {
    const refs = Array.from({ length: 20 }, (_, i) => ({ ...MILK, canonical_id: 5000 + i }));
    const trips = [9, 6, 2].map((ago) =>
      trip(
        ago,
        refs.map((r): [number, number] => [r.canonical_id, 1]),
      ),
    );
    expect(usualItems(doc({ trips }, refs), NOW)).toHaveLength(12);
  });

  it("gives the usual quantity per product for the list rows", () => {
    const map = usualQuantities(regularDoc(), NOW);
    expect(map.get(MILK.canonical_id)!.quantity).toBe(2);
    expect(map.has(PASTA.canonical_id)).toBe(false);
  });

  it("uses halves of a kilo for a weighed product", () => {
    const d = doc(
      {
        trips: [trip(9, [[TOMATOES, 1.5]]), trip(6, [[TOMATOES, 1.4]]), trip(2, [[TOMATOES, 1.6]])],
      },
      [TOMATOES],
    );
    expect(usualItems(d, NOW)[0]!.quantity).toBe(1.5);
  });
});

describe("usualGap", () => {
  it("is the median gap when the history is steady", () => {
    expect(usualGap([0, 10, 20])).toBe(10);
    expect(usualGap([0, 7, 14, 21, 28])).toBe(7);
    expect(usualGap([0, 9, 20])).toBe(10); // 9 and 11: median 10, deviation 1
  });

  it("is null for too few days, gaps under 3 or over 90 days, and erratic gaps", () => {
    expect(usualGap([0, 10])).toBeNull();
    expect(usualGap([0, 1, 2, 3])).toBeNull();
    expect(usualGap([0, 100, 200])).toBeNull();
    expect(usualGap([0, 3, 40, 44, 90])).toBeNull(); // 3, 37, 4, 46
  });

  it("uses the last six gaps only", () => {
    const old = [0, 30, 60, 90, 120]; // gaps of 30
    const recent = [127, 134, 141, 148, 155, 162, 169]; // gaps of 7
    expect(usualGap([...old, ...recent])).toBe(7);
  });
});

describe("buyAgainItems", () => {
  const d = regularDoc();

  it("suggests what is due: the usual gap has passed since the last purchase", () => {
    const items = buyAgainItems(d, NOW);
    expect(items).toEqual([
      { ref: COTTAGE, everyDays: 10, sinceDays: 10, quantity: 1 }, // exactly one gap
    ]);
  });

  it("does not suggest what was bought sooner than its gap", () => {
    expect(buyAgainItems(d, NOW).some((i) => i.ref.canonical_id === MILK.canonical_id)).toBe(false);
  });

  it("suggests milk once its 7 days have passed", () => {
    const later = new Date(NOW.getTime() + 5 * 86_400_000); // milk: 8 days since
    const ids = buyAgainItems(d, later).map((i) => i.ref.canonical_id);
    expect(ids).toContain(MILK.canonical_id);
  });

  it("gives up after three gaps beyond the last purchase", () => {
    const much = new Date(NOW.getTime() + 31 * 86_400_000); // cottage: 41 days since, gap 10
    expect(buyAgainItems(d, much).some((i) => i.ref.canonical_id === COTTAGE.canonical_id)).toBe(
      false,
    );
    const edge = new Date(NOW.getTime() + 30 * 86_400_000); // 40 days: still inside 10 x (1 + 3)
    expect(buyAgainItems(d, edge).some((i) => i.ref.canonical_id === COTTAGE.canonical_id)).toBe(
      true,
    );
  });

  it("leaves out what is on the list already", () => {
    expect(buyAgainItems(d, NOW, new Set([COTTAGE.canonical_id]))).toEqual([]);
  });

  it("leaves out a product with erratic history", () => {
    const erratic = doc(
      { trips: [trip(60, [[EGGS]]), trip(57, [[EGGS]]), trip(20, [[EGGS]]), trip(16, [[EGGS]])] },
      [EGGS],
    );
    expect(buyAgainItems(erratic, NOW)).toEqual([]);
  });

  describe("dismissals", () => {
    it("hides a dismissed product for one more gap from the dismissal", () => {
      const dismissed = {
        ...d,
        dismissals: [dismissal(0, "buy_again", String(COTTAGE.canonical_id))],
      };
      expect(buyAgainItems(dismissed, NOW)).toEqual([]);
      const sameWeek = new Date(NOW.getTime() + 9 * 86_400_000);
      expect(
        buyAgainItems(dismissed, sameWeek).some((i) => i.ref.canonical_id === COTTAGE.canonical_id),
      ).toBe(false);
      const nextGap = new Date(NOW.getTime() + 10 * 86_400_000);
      expect(
        buyAgainItems(dismissed, nextGap).some((i) => i.ref.canonical_id === COTTAGE.canonical_id),
      ).toBe(true);
    });

    it("a purchase after the dismissal brings the product back into the cycle", () => {
      // dismissed 12 days ago, bought 10 days ago: the dismissal is about an older cycle
      const dismissed = {
        ...d,
        dismissals: [dismissal(12, "buy_again", String(COTTAGE.canonical_id))],
      };
      expect(buyAgainItems(dismissed, NOW).map((i) => i.ref.canonical_id)).toEqual([
        COTTAGE.canonical_id,
      ]);
    });

    it("another product's dismissal does not hide it", () => {
      const dismissed = {
        ...d,
        dismissals: [dismissal(0, "buy_again", String(MILK.canonical_id))],
      };
      expect(buyAgainItems(dismissed, NOW)).toHaveLength(1);
    });
  });

  it("lists the most overdue first and at most five", () => {
    const refs = Array.from({ length: 8 }, (_, i) => ({ ...MILK, canonical_id: 7000 + i }));
    const trips = refs.flatMap((r, i) => [
      trip(40 + i, [[r]]),
      trip(30 + i, [[r]]),
      trip(20 + i, [[r]]),
    ]);
    const out = buyAgainItems(doc({ trips }, refs), NOW);
    expect(out).toHaveLength(5);
    const overdue = out.map((o) => o.sinceDays - o.everyDays);
    expect([...overdue].sort((a, b) => b - a)).toEqual(overdue);
  });
});

describe("brandOffers", () => {
  const three = [
    signal(30, "dairy.milk"),
    signal(20, "dairy.milk", "rejected_substitute"),
    signal(3, "dairy.milk"),
  ];

  it("offers a category after three signals in 90 days, with its count", () => {
    const offers = brandOffers(doc({ signals: three }, [MILK]), {}, NOW);
    expect(offers).toEqual([{ taxonomyId: "dairy.milk", count: 3, sample: MILK }]);
  });

  it("needs three: two signals are not enough", () => {
    expect(brandOffers(doc({ signals: three.slice(1) }), {}, NOW)).toEqual([]);
  });

  it("counts only the last 90 days", () => {
    const old = [signal(120, "dairy.milk"), signal(100, "dairy.milk"), signal(3, "dairy.milk")];
    expect(brandOffers(doc({ signals: old }), {}, NOW)).toEqual([]);
  });

  it("is not offered when the category is already exact, by the person or by default", () => {
    expect(brandOffers(doc({ signals: three }), { "dairy.milk": "exact" }, NOW)).toEqual([]);
    expect(brandOffers(doc({ signals: three }), { dairy: "exact" }, NOW)).toEqual([]);
    const baby = [signal(3, "baby.formula"), signal(2, "baby.formula"), signal(1, "baby.formula")];
    expect(brandOffers(doc({ signals: baby }), {}, NOW)).toEqual([]); // smart default
  });

  it("is still offered when the category has another level saved", () => {
    expect(brandOffers(doc({ signals: three }), { "dairy.milk": "close" }, NOW)).toHaveLength(1);
  });

  it("after a dismissal needs three new signals", () => {
    const dismissed = doc({
      signals: [...three, signal(1, "dairy.milk")],
      dismissals: [{ kind: "brand_default", key: "dairy.milk", at: daysAgo(2) }],
    });
    expect(brandOffers(dismissed, {}, NOW)).toEqual([]);
    const again = doc({
      signals: [
        ...three,
        signal(1, "dairy.milk"),
        signal(1, "dairy.milk"),
        signal(0, "dairy.milk"),
      ].map((s, i) => ({ ...s, at: i < 3 ? s.at : daysAgo(1) })),
      dismissals: [{ kind: "brand_default", key: "dairy.milk", at: daysAgo(2) }],
    });
    // three signals after the dismissal (those at "1 day ago" or later)
    expect(brandOffers(again, {}, NOW).map((o) => o.taxonomyId)).toEqual(["dairy.milk"]);
  });

  it("ranks categories by count and gives the category of a sample product", () => {
    const sig = [
      ...three,
      signal(2, "eggs.chicken"),
      signal(2, "eggs.chicken"),
      signal(1, "eggs.chicken"),
      signal(1, "eggs.chicken"),
    ];
    const offers = brandOffers(doc({ signals: sig }, [EGGS]), {}, NOW);
    expect(offers.map((o) => [o.taxonomyId, o.count])).toEqual([
      ["eggs.chicken", 4],
      ["dairy.milk", 3],
    ]);
    expect(offers[0]!.sample).toBe(EGGS);
    expect(offers[1]!.sample).toBeNull();
  });
});

describe("effectiveDefault", () => {
  it("reads the person's default, then the smart one", () => {
    expect(effectiveDefault("dairy.milk", { dairy: "close" })).toBe("close");
    expect(effectiveDefault("toiletries.soap", {})).toBe("exact");
    expect(effectiveDefault("dairy.milk", {})).toBeNull();
  });
});
