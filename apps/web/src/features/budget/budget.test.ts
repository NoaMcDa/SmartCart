/**
 * Monthly budget and spend state (issue #70): calendar helpers, the budget, the spend store, the
 * arithmetic, and the optional sync with the account.
 */
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, deleteSpend, postSpend, updateSpend, type SpendEntry } from "@/api/client";
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
  removeSpendRow,
  restoreSpendRow,
  spentInMonth,
  rowFromServer,
  validSpendTotal,
} from "./spendState";
import {
  commitSpendRemoval,
  correctSpend,
  pullSpendMonths,
  pushPendingSpend,
  syncSpend,
} from "./sync";

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
      client_id: expect.stringMatching(/^[0-9a-f-]{36}$/),
      date: "2026-10-08",
      store_id: 101,
      store_name: "רמי לוי · מודיעין",
      total: 371.4,
      item_count: 9,
      plan: "single",
    });
    expect(Object.keys(row).sort()).toEqual([
      "client_id",
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
      id: 77,
      date: "2026-10-03",
      store_id: 103,
      store_name: "שופרסל דיל · מודיעין",
      total: "120.50",
      item_count: 4,
      plan: "single",
    };
    expect(mergeServerEntries([theirs])).toBe(1);
    expect(mergeServerEntries([theirs])).toBe(0);
    expect(loadSpend().entries.map((e) => [e.id, e.server_id, e.total])).toEqual([
      [mine.id, undefined, 371.4],
      ["srv77", 77, 120.5],
    ]);
    // Merged entries come from the server, so they are never queued to be sent back.
    expect(loadSpend().pending).toEqual([]);
  });

  it("an entry this device already sent is recognised by its server id", () => {
    const mine = shop({ pending: true });
    markSynced([{ id: mine.id, serverId: 5 }]);
    expect(
      mergeServerEntries([
        {
          id: 5,
          date: mine.date,
          store_id: mine.store_id,
          store_name: mine.store_name,
          total: "371.40",
          item_count: mine.item_count,
          plan: mine.plan,
        },
      ]),
    ).toBe(0);
    expect(loadSpend().entries).toHaveLength(1);
  });

  it("ignores an entry that is not usable", () => {
    expect(rowFromServer({ id: 1, date: "bad" } as unknown as SpendEntry)).toBeNull();
    expect(mergeServerEntries([{ id: 1, date: "bad" } as unknown as SpendEntry])).toBe(0);
  });
});

describe("sync", () => {
  it("pushes pending entries with POST /me/spend and then stops queueing them", async () => {
    const queued = shop({ pending: true });
    const local = shop(); // recorded signed out: stays on the device
    expect(await pushPendingSpend()).toBe(1);
    // The account got the fields of the entry (no local id) and answered with its own number.
    expect(mockSpendEntries()).toEqual([
      {
        id: 1,
        client_id: queued.client_id,
        date: queued.date,
        store_id: queued.store_id,
        store_name: queued.store_name,
        total: "371.40",
        item_count: queued.item_count,
        plan: queued.plan,
      },
    ]);
    expect(loadSpend().pending).toEqual([]);
    expect(loadSpend().entries.find((e) => e.id === queued.id)?.server_id).toBe(1);
    expect(loadSpend().entries.find((e) => e.id === local.id)?.server_id).toBeUndefined();
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
    const fromPhone = await postSpend({
      date: "2026-10-05",
      store_id: 102,
      store_name: "אושר עד · מודיעין",
      total: "88.80",
      item_count: 3,
      plan: "single",
    });
    expect(await pullSpendMonths(["2026-09", "2026-10"])).toBe(1);
    expect(loadSpend().entries.map((e) => e.server_id)).toEqual([fromPhone.id]);
    expect(await pullSpendMonths(["2026-10"])).toBe(0);
  });

  it("pushing and then pulling the same month does not duplicate the device's own shop", async () => {
    shop({ pending: true, now: new Date("2026-10-08T09:00:00Z") });
    await syncSpend(["2026-10"]);
    expect(loadSpend().entries).toHaveLength(1);
  });

  it("a month that fails does not block the others, and nothing throws offline", async () => {
    server.use(http.get(`${API_BASE_URL}/me/spend`, () => HttpResponse.error()));
    await expect(syncSpend(["2026-09", "2026-10"])).resolves.toBeUndefined();
  });
});

function mockBody(row: ReturnType<typeof shop>) {
  return {
    date: row.date,
    store_id: row.store_id,
    store_name: row.store_name,
    total: row.total.toFixed(2),
    item_count: row.item_count,
    plan: row.plan,
  };
}

describe("client_id: a lost response never duplicates a shop", () => {
  it("every entry gets a UUID, kept with it and reused by every POST", async () => {
    const queued = shop({ pending: true });
    expect(queued.client_id).toMatch(/^[0-9a-f-]{36}$/);
    const ids: unknown[] = [];
    server.use(
      http.post(`${API_BASE_URL}/me/spend`, async ({ request }) => {
        ids.push(((await request.json()) as { client_id?: string }).client_id);
        return HttpResponse.error(); // the request reached the server, the response did not
      }),
    );
    await pushPendingSpend();
    await pushPendingSpend();
    expect(ids).toEqual([queued.client_id, queued.client_id]);
    expect(loadSpend().pending).toEqual([queued.id]);
  });

  it("the account returns the stored entry for a repeated client_id, so the retry adds nothing", async () => {
    const queued = shop({ pending: true });
    // First try: stored by the account, response lost.
    const body = { ...mockBody(queued), client_id: queued.client_id };
    const first = await postSpend(body);
    const again = await postSpend(body);
    expect(again.id).toBe(first.id);
    expect(mockSpendEntries()).toHaveLength(1);
    // The device's own retry also lands on the same entry and links to it.
    expect(await pushPendingSpend()).toBe(1);
    expect(mockSpendEntries()).toHaveLength(1);
    expect(loadSpend().entries[0]?.server_id).toBe(first.id);
    expect(loadSpend().pending).toEqual([]);
  });

  it("a pull adopts an entry whose response was lost instead of adding it a second time", async () => {
    const queued = shop({ pending: true });
    await postSpend({ ...mockBody(queued), client_id: queued.client_id });
    expect(await pullSpendMonths(["2026-10"])).toBe(0);
    const { entries, pending } = loadSpend();
    expect(entries).toHaveLength(1);
    expect(entries[0]?.server_id).toBe(1);
    expect(pending).toEqual([]);
  });

  it("an entry saved before client_id existed gets one on its first POST and keeps it", async () => {
    window.localStorage.setItem(
      STORAGE_KEYS.spend,
      JSON.stringify({
        version: 1,
        entries: [
          {
            id: "sp1",
            date: "2026-10-08",
            store_id: 101,
            store_name: "x",
            total: 10,
            item_count: 1,
            plan: "single",
          },
        ],
        pending: ["sp1"],
      }),
    );
    await pushPendingSpend();
    const stored = loadSpend().entries[0]!;
    expect(stored.client_id).toBeTruthy();
    expect(mockSpendEntries()[0]?.client_id).toBe(stored.client_id);
  });
});

describe("client helpers: PUT and DELETE /me/spend/{id}", () => {
  it("updateSpend replaces the entry and keeps its id and client_id", async () => {
    const queued = shop({ pending: true });
    await pushPendingSpend();
    const saved = await updateSpend(1, { ...mockBody(queued), total: "350.00" });
    expect(saved).toMatchObject({ id: 1, total: "350.00", client_id: queued.client_id });
    expect(mockSpendEntries()).toHaveLength(1);
  });

  it("deleteSpend removes it; an unknown id is a 404 ApiError", async () => {
    shop({ pending: true });
    await pushPendingSpend();
    await expect(deleteSpend(1)).resolves.toBeUndefined();
    expect(mockSpendEntries()).toEqual([]);
    await expect(deleteSpend(1)).rejects.toMatchObject({ status: 404 });
    await expect(deleteSpend(1)).rejects.toBeInstanceOf(ApiError);
    await expect(updateSpend(9, mockBody(shop()))).rejects.toMatchObject({ status: 404 });
  });
});

describe("correcting a total", () => {
  it("validates: positive, at most two decimals, a comma is fine, up to 100,000", () => {
    expect(validSpendTotal("371.4")).toBe(371.4);
    expect(validSpendTotal("371,40")).toBe(371.4);
    expect(validSpendTotal(" ₪ 88 ")).toBe(88);
    expect(validSpendTotal(100000)).toBe(100000);
    for (const bad of ["", "0", "-5", "abc", "1.234", "1e3", "100000.01", "12 34", null, NaN]) {
      expect(validSpendTotal(bad)).toBeNull();
    }
  });

  it("signed out: changes the device copy only and marks the amount as the person's", async () => {
    const row = shop();
    expect(await correctSpend(row.id, "350", false)).toBe("ok");
    expect(loadSpend().entries[0]).toMatchObject({ total: 350, corrected: true });
    expect(mockSpendEntries()).toEqual([]);
  });

  it("an invalid amount changes nothing", async () => {
    const row = shop();
    expect(await correctSpend(row.id, "0", true)).toBe("invalid");
    expect(await correctSpend("nope", "10", true)).toBe("missing");
    expect(loadSpend().entries[0]?.total).toBe(371.4);
  });

  it("signed in, an entry already on the account is sent with PUT", async () => {
    const row = shop({ pending: true });
    await pushPendingSpend();
    expect(await correctSpend(row.id, "350.50", true)).toBe("ok");
    expect(mockSpendEntries()[0]).toMatchObject({ total: "350.50", client_id: row.client_id });
  });

  it("signed in, a pending entry goes out later with the corrected total", async () => {
    const row = shop({ pending: true });
    expect(await correctSpend(row.id, "300", true)).toBe("ok");
    expect(mockSpendEntries()).toEqual([]);
    await pushPendingSpend();
    expect(mockSpendEntries()[0]?.total).toBe("300.00");
  });

  it("rolls the device copy back when the account refuses", async () => {
    const row = shop({ pending: true });
    await pushPendingSpend();
    server.use(
      http.put(`${API_BASE_URL}/me/spend/:id`, () => HttpResponse.json({}, { status: 500 })),
    );
    expect(await correctSpend(row.id, "10", true)).toBe("failed");
    expect(loadSpend().entries[0]).toMatchObject({ total: 371.4 });
    expect(loadSpend().entries[0]?.corrected).toBeUndefined();
  });
});

describe("deleting an entry", () => {
  it("removes it from the device and from the pending queue, and undo puts it back in place", () => {
    const a = shop();
    const b = shop({ pending: true });
    const c = shop();
    const removed = removeSpendRow(b.id)!;
    expect(loadSpend().entries.map((e) => e.id)).toEqual([a.id, c.id]);
    expect(loadSpend().pending).toEqual([]);
    restoreSpendRow(removed);
    expect(loadSpend().entries.map((e) => e.id)).toEqual([a.id, b.id, c.id]);
    expect(loadSpend().pending).toEqual([b.id]);
    expect(removeSpendRow("nope")).toBeNull();
  });

  it("signed in, the account's copy is deleted; signed out or never synced, nothing is sent", async () => {
    const synced = shop({ pending: true });
    await pushPendingSpend();
    const local = shop();
    const sentLocal = removeSpendRow(local.id)!;
    expect(await commitSpendRemoval(sentLocal, true)).toBe(true);
    expect(mockSpendEntries()).toHaveLength(1);
    const removed = removeSpendRow(synced.id)!;
    expect(await commitSpendRemoval(removed, false)).toBe(true);
    expect(mockSpendEntries()).toHaveLength(1);
    expect(await commitSpendRemoval(removed, true)).toBe(true);
    expect(mockSpendEntries()).toEqual([]);
  });

  it("brings the entry back when the account refuses, and counts an already-gone entry as done", async () => {
    const row = shop({ pending: true });
    await pushPendingSpend();
    const removed = removeSpendRow(row.id)!;
    server.use(
      http.delete(`${API_BASE_URL}/me/spend/:id`, () => new HttpResponse(null, { status: 500 })),
    );
    expect(await commitSpendRemoval(removed, true)).toBe(false);
    expect(loadSpend().entries.map((e) => e.id)).toEqual([row.id]);
    server.resetHandlers();
    const again = removeSpendRow(row.id)!;
    server.use(
      http.delete(`${API_BASE_URL}/me/spend/:id`, () => HttpResponse.json({}, { status: 404 })),
    );
    expect(await commitSpendRemoval(again, true)).toBe(true);
    expect(loadSpend().entries).toEqual([]);
  });

  it("a pull inside the undo window does not bring the deleted entry back", async () => {
    const row = shop({ pending: true });
    await pushPendingSpend();
    const removed = removeSpendRow(row.id)!;
    expect(await pullSpendMonths(["2026-10"])).toBe(0);
    expect(loadSpend().entries).toEqual([]);
    restoreSpendRow(removed);
    expect(loadSpend().entries).toHaveLength(1);
  });
});
