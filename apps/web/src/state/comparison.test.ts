import { describe, expect, it } from "vitest";
import { compareFixture, optimizeFixture } from "@/mocks/fixtures";
import {
  buildOptimizeInput,
  estimateRange,
  findSubstitution,
  homeStore,
  planPromos,
  planSubstitutions,
  planUpdatedAt,
  substitutionSaving,
} from "./comparison";
import { shopperFromStored } from "./shopper";

describe("estimateRange", () => {
  it("ranges over the stores that carry every product, with the list's quantities", () => {
    const items = [
      { canonical_id: 1001, quantity: 1 },
      { canonical_id: 1004, quantity: 2 },
      { canonical_id: 1008, quantity: 1 },
    ];
    const e = estimateRange(compareFixture(), items)!;
    // אושר עד has no salmon: left out. רמי לוי: 5.90 + 2 x 4.50 + 136.50.
    expect(e.storeCount).toBe(4);
    expect(e.min).toBeCloseTo(151.4, 2);
    expect(e.cheapest.chain_name).toBe("רמי לוי");
    // שופרסל: 6.90 + 2 x 6.90 + 142.65.
    expect(e.max).toBeCloseTo(163.35, 2);
    expect(e.home?.store.store_id).toBe(103);
  });

  it("follows quantity changes without a new response", () => {
    const one = estimateRange(compareFixture(), [{ canonical_id: 1001, quantity: 1 }])!;
    const three = estimateRange(compareFixture(), [{ canonical_id: 1001, quantity: 3 }])!;
    expect(three.min).toBeCloseTo(one.min * 3, 2);
  });

  it("is null when no store carries the whole list", () => {
    expect(estimateRange(compareFixture(), [{ canonical_id: 9999, quantity: 1 }])).toBeNull();
    expect(estimateRange(compareFixture(), [])).toBeNull();
  });
});

describe("plans and substitutions", () => {
  const res = optimizeFixture();

  it("builds the optimize request from the list and the shopper context", () => {
    const input = buildOptimizeInput(
      [{ canonical_id: 1001, quantity: 2, flex_level: "any_brand" }],
      shopperFromStored({ home_store_id: 103, extra_stop_value: "30" }, false),
    )!;
    expect(input).toMatchObject({
      home_store_id: 103,
      location: { radius_m: 5000 },
      travel: { mode: "car", extra_stop_value: 30 },
    });
    expect(buildOptimizeInput([], shopperFromStored(null, false))).toBeNull();
  });

  it("finds the home store, substitutes, promos and the oldest update time", () => {
    expect(homeStore(res)?.store_name).toBe("שופרסל דיל · מודיעין");
    expect(planSubstitutions(res.single).map((s) => s.item.canonical_id)).toEqual([
      1001, 1003, 1004,
    ]);
    expect(planPromos(res.single)).toEqual({ total: 2, club: 1 });
    expect(planUpdatedAt(res.single)).toBe("2026-10-07T03:40:00Z");
  });

  it("finds a substitution with its position, original and saving times quantity", () => {
    const ctx = findSubstitution(res, 10104, "single")!;
    expect(ctx).toMatchObject({ index: 2, count: 3 });
    expect(ctx.original?.item.display_name_he).toBe("רסק עגבניות אסם, 260 ג'");
    // (6.90 - 4.50) x 2, the artboard's ₪4.80.
    expect(substitutionSaving(ctx)).toEqual({ perUnit: 2.4, quantity: 2, total: 4.8 });
    expect(findSubstitution(res, 42)).toBeNull();
  });

  it("without a home store there is no original to compare with", () => {
    const noHome = optimizeFixture({ homeStoreId: null });
    const ctx = findSubstitution(noHome, 10101)!;
    expect(ctx.original).toBeNull();
    expect(substitutionSaving(ctx)).toBeNull();
  });
});

describe("shopper context", () => {
  it("falls back to Modi'in and no home store outside the mock", () => {
    const ctx = shopperFromStored(null, false);
    expect(ctx).toMatchObject({ homeStoreId: null, cityLabel: "מודיעין", radiusM: 5000 });
    expect(shopperFromStored(null, true).homeStoreId).toBe(103);
    expect(shopperFromStored({ radius_m: 99999, max_stores: 7 }, false)).toMatchObject({
      radiusM: 15000,
      maxStores: 2,
    });
  });
});
