import { beforeEach, describe, expect, it } from "vitest";
import { lastResultFixture } from "@/mocks/lastResult";
import {
  SESSION_TTL_MS,
  buildSession,
  clearSession,
  departmentOf,
  groupByDepartment,
  loadSession,
  progressOf,
  realizedSaving,
  setChecked,
  startSession,
} from "./session";
import { STORAGE_KEYS } from "@/features/profile/storage";

const result = lastResultFixture();
const rami = result.compare!.stores.find((s) => s.store_id === 101)!;

beforeEach(() => {
  window.localStorage.clear();
  clearSession();
});

describe("shopping session", () => {
  it("copies the store's items with labels, prices, update times and departments", () => {
    const session = buildSession(rami, result, { overhead: 0 });
    expect(session.items).toHaveLength(8);
    expect(session.missingCount).toBe(1);
    const milk = session.items.find((i) => i.canonicalId === 1001)!;
    expect(milk).toMatchObject({
      isSubstitute: true,
      lineTotal: "11.80",
      department: "dairy",
      priceUpdatedAt: "2026-10-07T03:40:00Z",
    });
    expect(session.items.every((i) => i.priceUpdatedAt)).toBe(true);
    expect(session.departmentsResolved).toBe(true);
  });

  it("sorts by department in aisle order and sinks checked items", () => {
    const session = buildSession(rami, result, { overhead: 0 });
    session.items[0]!.checked = true;
    const groups = groupByDepartment(session.items);
    const order = groups.map((g) => g.department);
    expect(order).toEqual([...order].sort((a, b) => order.indexOf(a) - order.indexOf(b)));
    expect(order.indexOf("produce")).toBeLessThan(order.indexOf("dairy"));
    expect(order.indexOf("dairy")).toBeLessThan(order.indexOf("pantry"));
    for (const g of groups) {
      const checkedAt = g.items.map((i) => i.checked);
      expect(checkedAt).toEqual([...checkedAt].sort((a, b) => Number(a) - Number(b)));
    }
  });

  it("restricts to the canonicals of the split's assignment, using prices known for the store", () => {
    const osher = result.compare!.stores.find((s) => s.store_id === 102)!;
    const session = buildSession(osher, result, { canonicalIds: [1002, 1005, 1001] });
    expect(session.items.map((i) => i.canonicalId).sort()).toEqual([1001, 1002, 1005]);
  });

  it("persists check marks, keeps them across a restart of the same store, and cleans up", () => {
    startSession(buildSession(rami, result, { overhead: 0 }));
    const first = loadSession()!.items[0]!;
    setChecked(first.itemId, true);
    expect(loadSession()!.items.find((i) => i.itemId === first.itemId)!.checked).toBe(true);

    // Starting the same store with the same items keeps the marks.
    startSession(buildSession(rami, result, { overhead: 0 }));
    expect(loadSession()!.items.find((i) => i.itemId === first.itemId)!.checked).toBe(true);

    // A different store replaces the session.
    const osher = result.compare!.stores.find((s) => s.store_id === 102)!;
    startSession(buildSession(osher, result, { overhead: 0 }));
    expect(loadSession()!.storeId).toBe(102);

    clearSession();
    expect(window.localStorage.getItem(STORAGE_KEYS.shopping)).toBeNull();
  });

  it("expires after 12 hours and cleans the cache", () => {
    const start = new Date("2026-10-07T08:00:00Z");
    startSession(buildSession(rami, result, { overhead: 0, now: start }));
    expect(loadSession(new Date(start.getTime() + SESSION_TTL_MS - 1000))).not.toBeNull();
    expect(loadSession(new Date(start.getTime() + SESSION_TTL_MS + 1000))).toBeNull();
    expect(window.localStorage.getItem(STORAGE_KEYS.shopping)).toBeNull();
  });

  it("counts progress and the checked total", () => {
    const session = buildSession(rami, result, { overhead: 0 });
    session.items[0]!.checked = true;
    session.items[1]!.checked = true;
    const p = progressOf(session);
    expect(p.total).toBe(8);
    expect(p.checked).toBe(2);
    expect(p.allTotal).toBe(Number(rami.total));
    expect(p.checkedTotal).toBeCloseTo(
      Number(session.items[0]!.lineTotal) + Number(session.items[1]!.lineTotal),
      2,
    );
  });

  it("realized saving is the checked lines' saving versus the home store, minus the trip's cost", () => {
    const session = buildSession(rami, result, { overhead: 10 });
    expect(realizedSaving(session)).toBe(0); // nothing checked: no trip made
    for (const i of session.items) i.checked = true;
    const lines = session.items.reduce((a, i) => a + Math.round((i.saving ?? 0) * 100), 0) / 100;
    expect(realizedSaving(session)).toBeCloseTo(lines - 10, 2);
    // Without a baseline there is nothing to report.
    expect(realizedSaving({ ...session, overhead: null })).toBeNull();
  });

  it("maps taxonomy ids to departments, with the mock catalog's legacy roots aliased", () => {
    expect(departmentOf("dairy.milk.fresh")).toBe("dairy");
    expect(departmentOf("dairy_alt.soy")).toBe("dairy");
    expect(departmentOf("eggs.chicken")).toBe("dairy");
    expect(departmentOf("unknown.thing")).toBe("other");
    expect(departmentOf(null)).toBe("other");
  });
});
