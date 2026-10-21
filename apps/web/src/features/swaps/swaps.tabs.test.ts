/**
 * The swaps store and other tabs: another tab's change and "delete my data" (in this tab or in
 * another) must be read again, never overwritten by the snapshot this tab kept in memory.
 */
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import type { SwapSuggestion } from "@/api/client";
import { clearLocalData } from "@/features/profile/storage";
import {
  getSwapsState,
  recordDismissed,
  resetSwapsForTests,
  swapKey,
  SWAPS_KEY,
  useSwapsState,
} from "./swapState";

const swap = (canonicalId: number, saving: string): SwapSuggestion => ({
  canonical_id: canonicalId,
  from_item_id: canonicalId * 100,
  to_item_id: canonicalId * 100 + 1,
  to_display_name_he: "תחליף",
  flex_level: "any_brand",
  confidence: 0.9,
  tags: [],
  saving,
});

const stored = () => JSON.parse(window.localStorage.getItem(SWAPS_KEY) ?? "null");
const storageEvent = (key: string | null) =>
  window.dispatchEvent(new StorageEvent("storage", { key }));

beforeEach(() => {
  window.localStorage.clear();
  resetSwapsForTests();
});

describe("the swaps store and delete my data", () => {
  it("does not write the dismissals back that 'delete my data' removed (this tab)", () => {
    recordDismissed(swap(1002, "5.00"));
    recordDismissed(swap(1004, "4.00"));
    expect(Object.keys(getSwapsState().dismissed)).toHaveLength(2);

    clearLocalData();
    expect(window.localStorage.getItem(SWAPS_KEY)).toBeNull();
    expect(getSwapsState().dismissed).toEqual({});

    recordDismissed(swap(1001, "2.00"));
    expect(Object.keys(stored().dismissed)).toEqual([swapKey(swap(1001, "2.00"))]);
  });

  it("does not write them back when another tab deleted the data", () => {
    recordDismissed(swap(1002, "5.00"));
    window.localStorage.removeItem(SWAPS_KEY);
    storageEvent(SWAPS_KEY);
    recordDismissed(swap(1001, "2.00"));
    expect(Object.keys(stored().dismissed)).toEqual(["1001:100101"]);
  });

  it("follows a keyless event (another tab ran localStorage.clear())", () => {
    recordDismissed(swap(1002, "5.00"));
    window.localStorage.clear();
    storageEvent(null);
    expect(getSwapsState().dismissed).toEqual({});
  });

  it("takes in a dismissal another tab made, and keeps it with this tab's next one", () => {
    recordDismissed(swap(1002, "5.00"));
    const other = {
      version: 1,
      dismissed: { "1002:100201": 5, "1009:100901": 3 },
      applied: [],
    };
    window.localStorage.setItem(SWAPS_KEY, JSON.stringify(other));
    storageEvent(SWAPS_KEY);
    recordDismissed(swap(1001, "2.00"));
    expect(Object.keys(stored().dismissed).sort()).toEqual([
      "1001:100101",
      "1002:100201",
      "1009:100901",
    ]);
  });

  it("ignores the storage events of other keys", () => {
    recordDismissed(swap(1002, "5.00"));
    const before = getSwapsState();
    window.localStorage.setItem("other", "x");
    storageEvent("other");
    expect(getSwapsState()).toBe(before);
  });

  it("re-renders a screen that shows the dismissals when the data is deleted", () => {
    recordDismissed(swap(1002, "5.00"));
    const { result } = renderHook(() => useSwapsState());
    expect(Object.keys(result.current.dismissed)).toHaveLength(1);
    act(() => clearLocalData());
    expect(result.current.dismissed).toEqual({});
  });
});
