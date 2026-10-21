import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/api/client";
import type { SharedItem } from "./listSync";
import {
  applyEdit,
  applyEdits,
  clearEdits,
  coalesce,
  completeAdd,
  dropFirstEdits,
  enqueueEdit,
  isNetworkFailure,
  MAX_QUEUED_EDITS,
  placeholderId,
  queuedCount,
  queuedEdits,
  rebaseEdits,
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
  version: null,
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
    // A request the client gave up on (no answer within the timeout) is a dead link, not a refusal.
    expect(isNetworkFailure(new DOMException("timed out", "TimeoutError"))).toBe(true);
    vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    expect(isNetworkFailure(new Error("anything"))).toBe(true);
  });

  it("an unrelated error while online is not a lost connection", () => {
    expect(isNetworkFailure(new Error("duplicate key"))).toBe(false);
    expect(isNetworkFailure({ message: "row-level security" })).toBe(false);
  });
});

describe("an item added offline that reached the server", () => {
  beforeEach(() => {
    window.localStorage.clear();
    resetQueueForTests();
  });

  const add: QueuedEdit = { kind: "add", itemId: -5, canonicalId: 1001, name: "חלב", quantity: 1 };

  it("drops the add and gives the waiting edits of that item its real id, in one write", () => {
    enqueueEdit(3, add);
    enqueueEdit(3, { kind: "checked", itemId: -5, checked: true });
    enqueueEdit(3, { kind: "checked", itemId: 7, checked: true });
    completeAdd(3, -5, 900);
    const expected = [
      { kind: "checked", itemId: 900, checked: true },
      { kind: "checked", itemId: 7, checked: true },
    ];
    expect(queuedEdits(3)).toEqual(expected);
    // It is what a reload reads: a replay that failed right after the add keeps the real id.
    resetQueueForTests();
    expect(queuedEdits(3)).toEqual(expected);
  });

  it("empties the list's queue when the add was the only edit", () => {
    enqueueEdit(3, add);
    completeAdd(3, -5, 900);
    expect(queuedCount(3)).toBe(0);
    expect(JSON.parse(window.localStorage.getItem(SHARED_QUEUE_KEY)!).lists).toEqual({});
  });
});

describe("placeholder ids", () => {
  it("are negative and different every time", () => {
    const ids = new Set([placeholderId(), placeholderId(), placeholderId()]);
    expect(ids.size).toBe(3);
    for (const id of ids) expect(id).toBeLessThan(0);
  });
});

describe("what the person saw (version and value) travels with the edit", () => {
  it("a newer edit of the same field keeps what was seen before the first one", () => {
    let q: QueuedEdit[] = [];
    q = coalesce(q, { kind: "quantity", itemId: 1, quantity: 3, from: 2, base: "v1" });
    q = coalesce(q, { kind: "quantity", itemId: 1, quantity: 4, from: 3, base: "v1" });
    expect(q).toEqual([{ kind: "quantity", itemId: 1, quantity: 4, from: 2, base: "v1" }]);
    q = coalesce(q, { kind: "checked", itemId: 1, checked: true, from: false, base: "v1" });
    q = coalesce(q, { kind: "checked", itemId: 1, checked: false, from: true, base: "v1" });
    expect(q[1]).toEqual({ kind: "checked", itemId: 1, checked: false, from: false, base: "v1" });
  });

  it("an edit queued by an older version of the app (no version) still loads", () => {
    window.localStorage.setItem(
      SHARED_QUEUE_KEY,
      JSON.stringify({
        version: 1,
        lists: { "1": [{ kind: "checked", itemId: 2, checked: true }] },
      }),
    );
    resetQueueForTests();
    expect(queuedEdits(1)).toEqual([{ kind: "checked", itemId: 2, checked: true }]);
  });

  it("drops an edit whose version or value has the wrong type", () => {
    window.localStorage.setItem(
      SHARED_QUEUE_KEY,
      JSON.stringify({
        version: 1,
        lists: {
          "1": [
            { kind: "checked", itemId: 2, checked: true, base: 5 },
            { kind: "quantity", itemId: 2, quantity: 2, from: "x" },
            { kind: "remove", itemId: 2, base: "v1" },
          ],
        },
      }),
    );
    resetQueueForTests();
    expect(queuedEdits(1)).toEqual([{ kind: "remove", itemId: 2, base: "v1" }]);
  });

  it("rebaseEdits moves the waiting edits of one item to its new version, and only those", () => {
    enqueueEdit(4, { kind: "quantity", itemId: 1, quantity: 3, from: 2, base: "v1" });
    enqueueEdit(4, { kind: "checked", itemId: 1, checked: true, from: false, base: "v1" });
    enqueueEdit(4, { kind: "checked", itemId: 2, checked: true, from: false, base: "v1" });
    enqueueEdit(4, { kind: "quantity", itemId: 5, quantity: 3, from: 2, base: "other" });
    rebaseEdits(4, 1, "v1", "v2");
    expect(queuedEdits(4).map((e) => [e.itemId, "base" in e ? e.base : undefined])).toEqual([
      [1, "v2"],
      [1, "v2"],
      [2, "v1"],
      [5, "other"],
    ]);
    rebaseEdits(4, 1, null, "v9"); // no version to move from: nothing
    expect(queuedEdits(4)[0]).toMatchObject({ base: "v2" });
  });

  it("completeAdd gives the waiting edits the saved row's version as what they were made on", () => {
    enqueueEdit(3, { kind: "add", itemId: -5, canonicalId: 1, name: "x", quantity: 1 });
    enqueueEdit(3, { kind: "checked", itemId: -5, checked: true, from: false, base: null });
    completeAdd(3, -5, 900, "2026-10-21T10:00:00.123456Z");
    expect(queuedEdits(3)).toEqual([
      {
        kind: "checked",
        itemId: 900,
        checked: true,
        from: false,
        base: "2026-10-21T10:00:00.123456Z",
      },
    ]);
  });
});
