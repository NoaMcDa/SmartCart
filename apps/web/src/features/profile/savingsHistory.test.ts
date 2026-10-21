import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetStorageMemoryForTests } from "@/state/storage";
import { loadSavings, recordSaving, totalSaved } from "./savingsHistory";
import { STORAGE_KEYS } from "./storage";

beforeEach(() => {
  window.localStorage.clear();
  resetStorageMemoryForTests();
});
afterEach(() => vi.restoreAllMocks());

describe("realized savings read back from storage", () => {
  it("keeps good entries and drops anything that would break the total or the list", () => {
    const good = {
      id: "a",
      at: "2026-10-08T05:00:00Z",
      storeName: "רמי לוי",
      listName: null,
      net: 12.5,
    };
    window.localStorage.setItem(
      STORAGE_KEYS.savings,
      JSON.stringify([
        good,
        null,
        7,
        "x",
        { ...good, id: "b", net: "12" },
        { ...good, id: "c", net: null },
      ]),
    );
    expect(loadSavings()).toEqual([good]);
    expect(totalSaved(loadSavings())).toBe(12.5);
  });

  it("is an empty list for a stored value that is not a list", () => {
    for (const raw of ["{}", "5", '"x"', "null", "{broken"]) {
      window.localStorage.setItem(STORAGE_KEYS.savings, raw);
      expect(loadSavings()).toEqual([]);
    }
  });

  it("a trip recorded while storage refuses writes is still in the history for this page view", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("quota", "QuotaExceededError");
    });
    recordSaving({ storeName: "רמי לוי", listName: null, net: -3.5 });
    expect(loadSavings().map((e) => e.net)).toEqual([-3.5]);
  });
});
