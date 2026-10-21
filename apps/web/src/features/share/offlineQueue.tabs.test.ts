import { beforeEach, describe, expect, it } from "vitest";
import { ALERT_NAMES_KEY } from "@/features/alerts/alertNames";
import { clearLocalData, LOCAL_DATA_KEYS } from "@/features/profile/storage";
import { SCAN_LOG_KEY } from "@/features/scan/scanLog";
import { SCAN_STORE_KEY } from "@/features/scan/stores";
import { SWAPS_KEY } from "@/features/swaps/swapState";
import {
  enqueueEdit,
  queuedCount,
  resetQueueForTests,
  SHARED_QUEUE_KEY,
  type QueuedEdit,
} from "./offlineQueue";
import { SHARED_LISTS_KEY } from "./sharedLists";

const edit: QueuedEdit = { kind: "quantity", itemId: 1, quantity: 2 };

beforeEach(() => {
  window.localStorage.clear();
  resetQueueForTests();
});

describe("the offline queue and other tabs", () => {
  it("reads the queue again when another tab replayed and emptied it", () => {
    enqueueEdit(7, edit);
    expect(queuedCount(7)).toBe(1);
    // The other tab sent the edit and emptied the queue.
    window.localStorage.removeItem(SHARED_QUEUE_KEY);
    window.dispatchEvent(new StorageEvent("storage", { key: SHARED_QUEUE_KEY }));
    expect(queuedCount(7)).toBe(0);
    // This tab's next edit builds on the empty queue, so the sent edit is not sent a second time.
    enqueueEdit(7, { kind: "checked", itemId: 1, checked: true });
    expect(JSON.parse(window.localStorage.getItem(SHARED_QUEUE_KEY)!).lists["7"]).toEqual([
      { kind: "checked", itemId: 1, checked: true },
    ]);
  });

  it("ignores storage events of other keys", () => {
    enqueueEdit(7, edit);
    window.localStorage.setItem("other", "x");
    window.dispatchEvent(new StorageEvent("storage", { key: "other" }));
    expect(queuedCount(7)).toBe(1);
  });
});

describe("delete my data", () => {
  it("removes every personal key the app writes, and drops the queue held in memory", () => {
    enqueueEdit(7, edit);
    for (const key of [
      SHARED_LISTS_KEY,
      ALERT_NAMES_KEY,
      SCAN_LOG_KEY,
      SCAN_STORE_KEY,
      SWAPS_KEY,
    ]) {
      expect(LOCAL_DATA_KEYS, key).toContain(key);
      window.localStorage.setItem(key, "{}");
    }
    expect(LOCAL_DATA_KEYS).toContain(SHARED_QUEUE_KEY);
    expect(LOCAL_DATA_KEYS).toContain("sc-session");
    clearLocalData();
    for (const key of LOCAL_DATA_KEYS) expect(window.localStorage.getItem(key), key).toBeNull();
    // A queued edit that stayed in this tab's memory would be written back by the next edit.
    expect(queuedCount(7)).toBe(0);
  });
});
