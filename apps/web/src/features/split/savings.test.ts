import { describe, expect, it } from "vitest";
import { lastResultFixture } from "@/mocks/lastResult";
import {
  assignmentOf,
  buildSplitModel,
  computeSplit,
  estimateTravelCost,
  moveBlockedReason,
  netSavingForStore,
  toAgorot,
  type Assignment,
} from "./savings";
import { wholeBasketStores } from "./lastResult";

const result = lastResultFixture();
const model = buildSplitModel(result)!;
const initial = assignmentOf(model.plan);

const RAMI = 101;
const OSHER = 102;
const COTTAGE = 1002;
const MILK = 1001;

function sumOfSteps(w: NonNullable<ReturnType<typeof computeSplit>["waterfall"]>) {
  return (
    toAgorot(w.chainSwitch) +
    toAgorot(w.brandSwaps) +
    toAgorot(w.promos) -
    toAgorot(w.travel) -
    toAgorot(w.extraStop)
  );
}

describe("split model from the recommended plan", () => {
  it("assigns every item to the stores of the plan", () => {
    expect(initial.size).toBe(9);
    expect([...initial].filter(([, s]) => s === RAMI)).toHaveLength(6);
    expect([...initial].filter(([, s]) => s === OSHER)).toHaveLength(3);
  });

  it("reproduces the API's totals and net saving (basket 75, travel 9, extra stop 25, net 41)", () => {
    const view = computeSplit(model, initial);
    const [rami, osher] = view.columns;
    expect(rami!.store.store_id).toBe(RAMI);
    expect(view.total).toBe(371);
    expect(rami!.subtotal + osher!.subtotal).toBe(371);
    const w = view.waterfall!;
    expect(w.base).toBe(446);
    expect(w.basketSaving).toBe(75);
    expect(w.travel).toBe(9);
    expect(w.extraStop).toBe(25);
    expect(w.net).toBe(41);
    expect(view.extraMinutes).toBe(12);
    // Same numbers as the API's own breakdown.
    expect(w.net).toBe(Number(model.plan.breakdown!.net_saving));
  });

  it("the waterfall steps sum exactly to the net saving", () => {
    const w = computeSplit(model, initial).waterfall!;
    expect(sumOfSteps(w)).toBe(toAgorot(w.net));
    // Brand swaps and chain switch are both present in this basket.
    expect(w.chainSwitch).toBeGreaterThan(0);
    expect(w.brandSwaps).toBeGreaterThan(0);
    expect(w.chainSwitch + w.brandSwaps + w.promos).toBeCloseTo(w.basketSaving, 2);
  });

  it("recomputes subtotals, saving and the waterfall after a move, from line totals only", () => {
    // Milk costs 5.90 at Rami and 5.70 at Osher; moving 2 packs to Osher saves 0.40 on the basket.
    const next: Assignment = new Map(initial).set(MILK, OSHER);
    const view = computeSplit(model, next);
    const rami = view.columns.find((c) => c.store.store_id === RAMI)!;
    const osher = view.columns.find((c) => c.store.store_id === OSHER)!;
    expect(rami.items.some((i) => i.canonical_id === MILK)).toBe(false);
    expect(osher.items.some((i) => i.canonical_id === MILK)).toBe(true);
    expect(rami.subtotal).toBeCloseTo(computeSplit(model, initial).columns[0]!.subtotal - 11.8, 2);
    expect(osher.subtotal).toBeCloseTo(computeSplit(model, initial).columns[1]!.subtotal + 11.4, 2);
    expect(view.total).toBeCloseTo(370.6, 2);
    expect(view.waterfall!.net).toBeCloseTo(41.4, 2);
    expect(sumOfSteps(view.waterfall!)).toBe(toAgorot(view.waterfall!.net));
    // The milk at Osher is the brand itself, so the brand-swap saving of the Rami substitute is gone.
    expect(view.waterfall!.brandSwaps).toBeLessThan(
      computeSplit(model, initial).waterfall!.brandSwaps,
    );
  });

  it("steps still sum to the net saving for every single possible move", () => {
    for (const [canonical, from] of initial) {
      const to = from === RAMI ? OSHER : RAMI;
      if (moveBlockedReason(model, canonical, to)) continue;
      const view = computeSplit(model, new Map(initial).set(canonical, to));
      const w = view.waterfall!;
      expect(sumOfSteps(w), `moving ${canonical}`).toBe(toAgorot(w.net));
      expect(toAgorot(view.total)).toBe(view.columns.reduce((a, c) => a + toAgorot(c.subtotal), 0));
    }
  });

  it("a basket that ends up at one store drops the travel and extra stop of the other", () => {
    const onlyOsher: Assignment = new Map([
      [COTTAGE, OSHER],
      [1005, OSHER],
      [1006, OSHER],
    ]);
    const view = computeSplit(model, onlyOsher);
    expect(view.visited).toBe(1);
    expect(view.waterfall!.extraStop).toBe(0);
    expect(view.extraMinutes).toBe(0);
    // Travel falls to Osher's share of the plan travel (by distance), not the whole 9.
    expect(view.waterfall!.travel).toBeLessThan(9);
    expect(view.waterfall!.travel).toBeGreaterThan(0);
  });

  it("explains why an item cannot move: cottage cheese is not stocked at Rami Levy", () => {
    expect(moveBlockedReason(model, COTTAGE, RAMI)).toBe("לא נמצא ברמי לוי");
    expect(moveBlockedReason(model, COTTAGE, OSHER)).toBeNull();
    expect(moveBlockedReason(model, MILK, OSHER)).toBeNull();
  });

  it("has no waterfall without a home store (D7): no saving is invented", () => {
    const noHome = buildSplitModel(
      lastResultFixture({
        homeStoreId: null,
        optimize: { ...result.optimize!, split: { ...result.optimize!.split!, breakdown: null } },
      }),
    )!;
    expect(computeSplit(noHome, assignmentOf(noHome.plan)).waterfall).toBeNull();
  });

  it("is null when the optimizer found no split worth showing", () => {
    expect(
      buildSplitModel(lastResultFixture({ optimize: { ...result.optimize!, split: null } })),
    ).toBeNull();
  });
});

describe("net saving for a single store", () => {
  it("uses the API breakdown for the recommended single store", () => {
    const rami = wholeBasketStores(result).find((s) => s.store_id === RAMI)!;
    expect(netSavingForStore(result, rami)).toMatchObject({ net: 57, basket: 57, fromApi: true });
  });

  it("estimates from the basket saving and travel for the other stores, never versus the max", () => {
    const yocha = wholeBasketStores(result).find((s) => s.store_id === 104)!;
    const s = netSavingForStore(result, yocha);
    expect(s.fromApi).toBe(false);
    expect(s.basket).toBe(Number(yocha.saving_vs_home));
    // Car at 1.2 per km, round trip 3.6 km each way, home store 1.1 km away.
    expect(s.travel).toBeCloseTo(
      estimateTravelCost("car", 3600, 1.2) - estimateTravelCost("car", 1100, 1.2),
      2,
    );
    expect(s.net).toBeCloseTo(s.basket! - s.travel, 2);
  });

  it("is null without a home store, and zero for the home store itself", () => {
    const home = wholeBasketStores(result).find((s) => s.store_id === 103)!;
    expect(netSavingForStore(result, home).net).toBe(0);
    const stores = wholeBasketStores(lastResultFixture({ homeStoreId: null }));
    expect(netSavingForStore(lastResultFixture({ homeStoreId: null }), stores[0]!).net).toBeNull();
  });

  it("travel estimates follow the API formulas", () => {
    expect(estimateTravelCost("car", 4200, 1.2)).toBe(10.08);
    expect(estimateTravelCost("walk_transit", 4200, 1.2)).toBe(11);
    expect(estimateTravelCost("delivery", 4200, 1.2)).toBe(0);
  });
});
