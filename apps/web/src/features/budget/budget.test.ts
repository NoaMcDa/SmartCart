/**
 * Monthly budget and spend state (issue #70): calendar helpers, the budget, the spend store, the
 * arithmetic, and the optional sync with the account.
 */
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { postSpend, type SpendEntry } from "@/api/client";
import { API_BASE_URL } from "@/api/config";
import { mockSpendEntries, resetPhase3Mock } from "@/mocks/handlers.phase3";
import { server } from "@/mocks/node";
import { STORAGE_KEYS } from "@/features/profile/storage";
import { clearBudget, loadBudget, saveBudget, validBudget } from "./budgetState";
import { currentMonth, dayLabel, israelDate, monthName, monthsEndingAt } from "./month";
import {
  budgetStatus,
  clearSpend,
  loadSpend,
  markSynced,
  mergeServerEntries,
  monthlyTotals,
  recordSpend,
  spentInMonth,
  toRow,
} from "./spendState";
import { pullSpendMonths, pushPendingSpend, syncSpend } from "./sync";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetPhase3Mock();
});

const shop = (over: Partial<Parameters<typeof recordSpend>[0]> = {}) =>
  recordSpend({
    storeId: 101,
    storeName: "רמי לוי · מודיעין",
    total: 371.4,
    itemCount: 9,
    plan: "single",
    now: new Date("2026-10-08T09:00:00Z"),
    ...over,
  });

describe("calendar", () => {
  it("dates and months are on the Israel calendar, not the browser's", () => {
    expect(israelDate(new Date("2026-10-08T09:00:00Z"))).toBe("2026-10-08");
    // 21:30 UTC on the 30th is 00:30 on the 1st in Israel.
    expect(israelDate(new Date("2026-09-30T21:30:00Z"))).toBe("2026-10-01");
    expect(currentMonth(new Date("2026-09-30T21:30:00Z"))).toBe("2026-10");
  });

  it("six months end at the given one, oldest first, across a year boundary", () => {
    expect(monthsEndingAt("2026-02", 6)).toEqual([
      "2025-09",
      "2025-10",
      "2025-11",
      "2025-12",
      "2026-01",
      "2026-02",
    ]);
    expect(monthsEndingAt("2026-10", 1)).toEqual(["2026-10"]);
  });

  it("names months in Hebrew and days as d.m", () => {
    expect(monthName("2026-10")).toBe("אוקטובר");
    expect(monthName("2026-01", "short")).toMatch(/^ינו/u);
    expect(dayLabel("2026-10-08")).toBe("8.10");
  });
});

describe("the budget", () => {
  it("accepts whole shekels from 1 to a million and nothing else", () => {
    expect(validBudget(2500)).toBe(2500);
    expect(validBudget("2500.4")).toBe(2500);
    expect(validBudget(1_000_000)).toBe(1_000_000);
    for (const bad of [0, -5, 0.2, 1_000_001, NaN, Infinity, "", "abc", null, undefined]) {
      expect(validBudget(bad), String(bad)).toBeNull();
    }
  });

  it("is set, changed and cleared, under sc-budget-v1", () => {
    expect(loadBudget()).toBeNull();
    expect(saveBudget(2500)).toBe(true);
    expect(JSON.parse(window.localStorage.getItem("sc-budget-v1")!)).toEqual({ monthly: 2500 });
    expect(saveBudget("3000")).toBe(true);
    expect(loadBudget()).toBe(3000);
    expect(saveBudget(-1)).toBe(false);
    expect(loadBudget()).toBe(3000); // an invalid amount changes nothing
    clearBudget();
    expect(loadBudget()).toBeNull();
    expect(window.localStorage.getItem("sc-budget-v1")).toBeNull();
  });

  it("a damaged value reads as no budget", () => {
    window.localStorage.setItem("sc-budget-v1", "{not json");
    expect(loadBudget()).toBeNull();
    window.localStorage.setItem("sc-budget-v1", JSON.stringify({ monthly: "lots" }));
    expect(loadBudget()).toBeNull();
  });

  it("is one of the keys that delete-my-data removes", async () => {
    const { LOCAL_DATA_KEYS } = await import("@/features/profile/storage");
    expect(LOCAL_DATA_KEYS).toContain("sc-budget-v1");
    expect(LOCAL_DATA_KEYS).toContain("sc-spend-v1");
  });
});

describe("recording a shop", () => {
  it("keeps the date, store, total, item count and plan, and nothing about the items", () => {
    const row = shop();
    expect(row).toEqual({
      id: expect.any(String),
      date: "2026-10-08",
      store_id: 101,
      store_name: "רמי לוי · מודיעין",
      total: 371.4,
      item_count: 9,
      plan: "single",
    });
    expect(Object.keys(row).sort()).toEqual([
      "date",
      "id",
      "item_count",
      "plan",
      "store_id",
      "store_name",
      "total",
    ]);
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEYS.spend)!);
    expect(stored).toEqual({ version: 1, entries: [row], pending: [] });
  });

  it("rounds to whole agorot and never records a negative total", () => {
    expect(shop({ total: 10.005 }).total).toBe(10.01);
    expect(shop({ total: -4 }).total).toBe(0);
  });

  it("queues the entry for the account only when asked", () => {
    const local = shop();
    const synced = shop({ pending: true });
    expect(loadSpend().pending).toEqual([synced.id]);
    expect(loadSpend().pending).not.toContain(local.id);
  });

  it("works with storage blocked: no throw, nothing persisted", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    expect(() => shop()).not.toThrow();
    expect(loadSpend().entries).toEqual([]);
  });

  it("drops damaged entries and pending ids that point nowhere", () => {
    const good = shop();
    window.localStorage.setItem(
      STORAGE_KEYS.spend,
      JSON.stringify({
        version: 1,
        entries: [good, { id: "", date: "x" }, { ...good, id: "neg", total: -1 }, good],
        pending: [good.id, "ghost"],
      }),
    );
    const store = loadSpend();
    expect(store.entries).toEqual([good]);
    expect(store.pending).toEqual([good.id]);
  });

  it("is removed entirely by clearSpend", () => {
    shop();
    clearSpend();
    expect(window.localStorage.getItem(STORAGE_KEYS.spend)).toBeNull();
  });
});

describe("arithmetic", () => {
  it("sums a calendar month exactly, in agorot", () => {
    shop({ total: 0.1, now: new Date("2026-10-01T09:00:00Z") });
    shop({ total: 0.2, now: new Date("2026-10-31T09:00:00Z") });
    shop({ total: 50, now: new Date("2026-09-30T09:00:00Z") });
    const { entries } = loadSpend();
    expect(spentInMonth(entries, "2026-10")).toBe(0.3);
    expect(spentInMonth(entries, "2026-09")).toBe(50);
    expect(spentInMonth(entries, "2026-08")).toBe(0);
    expect(monthlyTotals(entries, ["2026-08", "2026-09", "2026-10"])).toEqual([
      { month: "2026-08", total: 0 },
      { month: "2026-09", total: 50 },
      { month: "2026-10", total: 0.3 },
    ]);
  });

  it("remaining is the budget minus what was spent, and the plan on screen comes off after that", () => {
    shop({ total: 371.4 });
    const { entries } = loadSpend();
    expect(budgetStatus(null, entries, "2026-10")).toBeNull();
    expect(budgetStatus(2500, entries, "2026-10")).toEqual({
      budget: 2500,
      spent: 371.4,
      remaining: 2128.6,
      afterPlan: null,
    });
    expect(budgetStatus(2500, entries, "2026-10", 389)?.afterPlan).toBe(1739.6);
    // Over budget is a negative number, not a clamp.
    expect(budgetStatus(400, entries, "2026-10")?.remaining).toBe(28.6);
    expect(budgetStatus(400, entries, "2026-10", 389)?.afterPlan).toBe(-360.4);
  });
});

describe("merging the account's entries", () => {
  it("adds entries this device lacks, once, and reads decimal-string totals", () => {
    const mine = shop();
    const theirs: SpendEntry = {
      id: "other-device",
      date: "2026-10-03",
      store_id: 103,
      store_name: "שופרסל דיל · מודיעין",
      total: "120.50",
      item_count: 4,
      plan: "single",
    };
    expect(mergeServerEntries([theirs, { ...mine }])).toBe(1);
    expect(mergeServerEntries([theirs])).toBe(0);
    expect(loadSpend().entries.map((e) => [e.id, e.total])).toEqual([
      [mine.id, 371.4],
      ["other-device", 120.5],
    ]);
    // Merged entries come from the server, so they are never queued to be sent back.
    expect(loadSpend().pending).toEqual([]);
  });

  it("ignores an entry that is not usable", () => {
    expect(toRow({ id: "x", date: "bad" } as unknown as SpendEntry)).toBeNull();
    expect(mergeServerEntries([{ id: "x", date: "bad" } as unknown as SpendEntry])).toBe(0);
  });
});

describe("sync", () => {
  it("pushes pending entries with POST /me/spend and then stops queueing them", async () => {
    const queued = shop({ pending: true });
    const local = shop(); // recorded signed out: stays on the device
    expect(await pushPendingSpend()).toBe(1);
    expect(mockSpendEntries().map((e) => e.id)).toEqual([queued.id]);
    expect(mockSpendEntries()[0]).toEqual(queued);
    expect(loadSpend().pending).toEqual([]);
    expect(loadSpend().entries.map((e) => e.id)).toContain(local.id);
    expect(await pushPendingSpend()).toBe(0);
  });

  it("keeps an entry pending when the request fails, and retries it later", async () => {
    const queued = shop({ pending: true });
    server.use(http.post(`${API_BASE_URL}/me/spend`, () => HttpResponse.error()));
    expect(await pushPendingSpend()).toBe(0);
    expect(loadSpend().pending).toEqual([queued.id]);
    server.resetHandlers();
    expect(await pushPendingSpend()).toBe(1);
    expect(loadSpend().pending).toEqual([]);
  });

  it("stops at the first failure so entries keep their order", async () => {
    const a = shop({ pending: true });
    const b = shop({ pending: true });
    let calls = 0;
    server.use(
      http.post(`${API_BASE_URL}/me/spend`, () => {
        calls += 1;
        return HttpResponse.json({ detail: "no" }, { status: 401 });
      }),
    );
    await pushPendingSpend();
    expect(calls).toBe(1);
    expect(loadSpend().pending).toEqual([a.id, b.id]);
  });

  it("pulls months from the account into the device copy", async () => {
    await postSpend({
      id: "from-phone",
      date: "2026-10-05",
      store_id: 102,
      store_name: "אושר עד · מודיעין",
      total: 88.8,
      item_count: 3,
      plan: "single",
    });
    expect(await pullSpendMonths(["2026-09", "2026-10"])).toBe(1);
    expect(loadSpend().entries.map((e) => e.id)).toEqual(["from-phone"]);
    expect(await pullSpendMonths(["2026-10"])).toBe(0);
  });

  it("a month that fails does not block the others, and nothing throws offline", async () => {
    server.use(http.get(`${API_BASE_URL}/me/spend`, () => HttpResponse.error()));
    await expect(syncSpend(["2026-09", "2026-10"])).resolves.toBeUndefined();
  });
});
