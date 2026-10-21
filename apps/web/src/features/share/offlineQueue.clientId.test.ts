/** The client id of a queued add (the idempotency key sent with every attempt to save it). */
import { beforeEach, describe, expect, it } from "vitest";
import {
  enqueueEdit,
  queuedEdits,
  resetQueueForTests,
  SHARED_QUEUE_KEY,
  type QueuedEdit,
} from "./offlineQueue";

beforeEach(() => {
  window.localStorage.clear();
  resetQueueForTests();
});

const add: QueuedEdit = {
  kind: "add",
  itemId: -5,
  canonicalId: 1001,
  name: "חלב",
  quantity: 1,
  clientId: "0f6a6f0e-7c0b-4a39-a1a5-5d52e3a1b001",
};

describe("the client id of a queued add", () => {
  it("survives a quantity edit made while offline and a reload", () => {
    enqueueEdit(3, add);
    enqueueEdit(3, { kind: "quantity", itemId: -5, quantity: 4 });
    const expected = [{ ...add, quantity: 4 }];
    expect(queuedEdits(3)).toEqual(expected);
    resetQueueForTests();
    expect(queuedEdits(3)).toEqual(expected);
  });

  it("goes with the add when the item is removed before it was ever sent", () => {
    enqueueEdit(3, add);
    enqueueEdit(3, { kind: "remove", itemId: -5 });
    expect(queuedEdits(3)).toEqual([]);
  });

  it("an add stored without one (queued by an older version) is read, one with a bad one is not", () => {
    const bare = { kind: "add", itemId: -1, canonicalId: null, name: "x", quantity: 1 };
    const bad = { ...bare, itemId: -2, clientId: 7 };
    window.localStorage.setItem(
      SHARED_QUEUE_KEY,
      JSON.stringify({ version: 1, lists: { "3": [bare, bad] } }),
    );
    resetQueueForTests();
    expect(queuedEdits(3)).toEqual([bare]);
  });
});
