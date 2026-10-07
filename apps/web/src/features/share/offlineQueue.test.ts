import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/api/client";
import type { SharedItem } from "./listSync";
import {
  applyEdit,
  applyEdits,
  clearEdits,
  coalesce,
  dropFirstEdits,
  enqueueEdit,
  isNetworkFailure,
  MAX_QUEUED_EDITS,
  placeholderId,
  queuedCount,
  queuedEdits,
  resetQueueForTests,
  SHARED_QUEUE_KEY,
  type QueuedEdit,
} from "./offlineQueue";

const item = (over: Partial<SharedItem> & { id: number }): SharedItem => ({
  canonicalId: 1001,
  name: "חלב",
  quantity: 1,
  flexLevel: "any_brand",
  confirmed: true,
  checked: false,
  sort: over.id,
  updatedAt: null,
  ...over,
});

beforeEach(() => {
  window.localStorage.clear();
  resetQueueForTests();
});
afterEach(() => vi.restoreAllMocks());

describe("coalescing", () => {
  it("keeps only the latest quantity and the latest checked value of an item", () => {
    let q: QueuedEdit[] = [];
    q = coalesce(q, { kind: "quantity", itemId: 1, quantity: 2 });
    q = coalesce(q, { kind: "checked", itemId: 1, checked: true });
    q = coalesce(q, { kind: "quantity", itemId: 1, quantity: 5 });
    q = coalesce(q, { kind: "checked", itemId: 1, checked: false });
    q = coalesce(q, { kind: "quantity", itemId: 2, quantity: 3 });
    expect(q).toEqual([
      { kind: "quantity", itemId: 1, quantity: 5 },
      { kind: "checked", itemId: 1, checked: false },
      { kind: "quantity", itemId: 2, quantity: 3 },
    ]);
  });

  it("a removal drops the earlier edits of that item and nothing else", () => {
    let q: QueuedEdit[] = [
      { kind: "quantity", itemId: 1, quantity: 2 },
      { kind: "checked", itemId: 1, checked: true },
      { kind: "quantity", itemId: 2, quantity: 4 },
    ];
    q = coalesce(q, { kind: "remove", itemId: 1 });
    expect(q).toEqual([
      { kind: "quantity", itemId: 2, quantity: 4 },
      { kind: "remove", itemId: 1 },
    ]);
  });

  it("an item added and then edited or removed while offline is one add, or nothing", () => {
    const add: QueuedEdit = {
      kind: "add",
      itemId: -5,
      canonicalId: 1004,
      name: "רסק עגבניות",
      quantity: 1,
    };
    const edited = coalesce([add], { kind: "quantity", itemId: -5, quantity: 3 });
    expect(edited).toEqual([{ ...add, quantity: 3 }]);
    // Never reached the server, so there is nothing to remove there.
    expect(coalesce(edited, { kind: "remove", itemId: -5 })).toEqual([]);
  });
});

describe("applying edits to the freshest list", () => {
  const server = [item({ id: 1 }), item({ id: 2, name: "ביצים", canonicalId: 1008 })];

  it("applies quantity, checked, remove and add in order", () => {
    const next = applyEdits(server, [
      { kind: "quantity", itemId: 1, quantity: 4 },
      { kind: "checked", itemId: 2, checked: true },
      { kind: "add", itemId: -9, canonicalId: 1004, name: "רסק עגבניות", quantity: 2 },
      { kind: "remove", itemId: 1 },
    ]);
    expect(next.map((i) => [i.id, i.quantity, i.checked, i.name])).toEqual([
      [2, 1, true, "ביצים"],
      [-9, 2, false, "רסק עגבניות"],
    ]);
  });

  it("does nothing for an item somebody else deleted meanwhile", () => {
    expect(applyEdit(server, { kind: "quantity", itemId: 99, quantity: 7 })).toEqual(server);
    expect(applyEdit(server, { kind: "checked", itemId: 99, checked: true })).toEqual(server);
    expect(applyEdit(server, { kind: "remove", itemId: 99 })).toEqual(server);
  });

  it("an add that is applied twice does not duplicate the item", () => {
    const add: QueuedEdit = { kind: "add", itemId: -9, canonicalId: 1004, name: "x", quantity: 1 };
    expect(applyEdits(server, [add, add])).toHaveLength(3);
  });

  it("does not change the list it was given", () => {
    const before = JSON.stringify(server);
    applyEdits(server, [{ kind: "remove", itemId: 1 }]);
    expect(JSON.stringify(server)).toBe(before);
  });
});

describe("the stored queue", () => {
  it("survives a reload, per list", () => {
    enqueueEdit(7, { kind: "checked", itemId: 1, checked: true });
    enqueueEdit(8, { kind: "quantity", itemId: 4, quantity: 2 });
    expect(queuedCount(7)).toBe(1);
    resetQueueForTests(); // a reload: memory gone, localStorage not
    expect(queuedEdits(7)).toEqual([{ kind: "checked", itemId: 1, checked: true }]);
    expect(queuedEdits(8)).toEqual([{ kind: "quantity", itemId: 4, quantity: 2 }]);
    expect(queuedEdits(9)).toEqual([]);
  });

  it("dropFirstEdits keeps what was queued while sending, clearEdits empties the list", () => {
    enqueueEdit(7, { kind: "checked", itemId: 1, checked: true });
    enqueueEdit(7, { kind: "quantity", itemId: 2, quantity: 2 });
    enqueueEdit(7, { kind: "quantity", itemId: 3, quantity: 3 });
    dropFirstEdits(7, 2);
    expect(queuedEdits(7)).toEqual([{ kind: "quantity", itemId: 3, quantity: 3 }]);
    clearEdits(7);
    expect(queuedCount(7)).toBe(0);
    expect(window.localStorage.getItem(SHARED_QUEUE_KEY)).not.toContain('"7"');
  });

  it("appends without coalescing while the queue is being sent", () => {
    enqueueEdit(7, { kind: "quantity", itemId: 1, quantity: 2 });
    enqueueEdit(7, { kind: "quantity", itemId: 1, quantity: 3 }, { append: true });
    expect(queuedEdits(7)).toHaveLength(2);
  });

  it("caps a long outage at the newest edits", () => {
    for (let i = 1; i <= MAX_QUEUED_EDITS + 10; i++) {
      enqueueEdit(7, { kind: "quantity", itemId: i, quantity: 2 });
    }
    const q = queuedEdits(7);
    expect(q).toHaveLength(MAX_QUEUED_EDITS);
    expect(q[0]).toMatchObject({ itemId: 11 });
  });

  it("holds ids, quantities and names the person typed, nothing about them", () => {
    enqueueEdit(7, { kind: "add", itemId: -1, canonicalId: 1004, name: "רסק", quantity: 1 });
    const raw = window.localStorage.getItem(SHARED_QUEUE_KEY) ?? "";
    expect(raw).not.toMatch(/lat|lon|radius|email|token|price/i);
  });

  it("ignores a corrupt or foreign value, and bad entries inside a good one", () => {
    window.localStorage.setItem(SHARED_QUEUE_KEY, "{oops");
    resetQueueForTests();
    expect(queuedEdits(7)).toEqual([]);
    window.localStorage.setItem(
      SHARED_QUEUE_KEY,
      JSON.stringify({
        version: 1,
        lists: {
          "7": [
            { kind: "quantity", itemId: 1, quantity: 2 },
            { kind: "quantity", itemId: "1", quantity: 2 },
            { kind: "quantity", itemId: 1, quantity: -3 },
            { kind: "nonsense", itemId: 1 },
            null,
          ],
        },
      }),
    );
    resetQueueForTests();
    expect(queuedEdits(7)).toEqual([{ kind: "quantity", itemId: 1, quantity: 2 }]);
  });

  it("works in memory when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    enqueueEdit(7, { kind: "checked", itemId: 1, checked: true });
    expect(queuedEdits(7)).toHaveLength(1);
  });
});

describe("telling no connection from a refusal", () => {
  it("a server answer, whatever its status, is a refusal", () => {
    expect(isNetworkFailure(new ApiError(500, null))).toBe(false);
    expect(isNetworkFailure(new ApiError(403, null))).toBe(false);
  });

  it("fetch rejecting, or the browser saying it is offline, is a lost connection", () => {
    expect(isNetworkFailure(new TypeError("Failed to fetch"))).toBe(true);
    expect(isNetworkFailure({ message: "TypeError: Failed to fetch" })).toBe(true);
    expect(isNetworkFailure({ message: "Load failed" })).toBe(true);
    vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    expect(isNetworkFailure(new Error("anything"))).toBe(true);
  });

  it("an unrelated error while online is not a lost connection", () => {
    expect(isNetworkFailure(new Error("duplicate key"))).toBe(false);
    expect(isNetworkFailure({ message: "row-level security" })).toBe(false);
  });
});

describe("placeholder ids", () => {
  it("are negative and different every time", () => {
    const ids = new Set([placeholderId(), placeholderId(), placeholderId()]);
    expect(ids.size).toBe(3);
    for (const id of ids) expect(id).toBeLessThan(0);
  });
});
