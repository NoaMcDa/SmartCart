import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  basketItems,
  EMPTY_LIST,
  getListState,
  LIST_KEY,
  resetListStoreForTests,
  sanitizeState,
  useList,
} from "./list";
import { renderHook, act } from "@testing-library/react";
import { resetStorageMemoryForTests } from "./storage";

const canonical = {
  canonical_id: 1001,
  display_name_he: "חלב",
  taxonomy_id: "dairy.milk",
  category_path_he: ["מוצרי חלב"],
};

const item = (over: Record<string, unknown> = {}) => ({
  id: "r1",
  inputText: "חלב",
  canonical,
  candidates: [],
  quantity: 1,
  unit: null,
  isWeighed: false,
  flexLevel: "any_brand",
  allow: [],
  exactItemId: null,
  needsConfirmation: false,
  notFound: false,
  confidence: 1,
  ...over,
});

beforeEach(() => {
  window.localStorage.clear();
  resetStorageMemoryForTests();
  resetListStoreForTests();
});
afterEach(() => vi.restoreAllMocks());

describe("a stored list that was edited or damaged", () => {
  it("a canonical that is not a product becomes a not-found row, never a request with an undefined id", () => {
    const state = sanitizeState({
      version: 1,
      items: [
        item({ id: "a", canonical: 5 }),
        item({ id: "b", canonical: { display_name_he: "no id" } }),
        item({ id: "c", canonical: { canonical_id: "7", display_name_he: "id as text" } }),
        item({ id: "d", needsConfirmation: true, canonical: "milk" }),
        item({ id: "ok" }),
      ],
    });
    expect(state.items.map((i) => [i.id, i.notFound])).toEqual([
      ["a", true],
      ["b", true],
      ["c", true],
      ["d", true],
      ["ok", false],
    ]);
    expect(state.items.find((i) => i.id === "d")?.needsConfirmation).toBe(false);
    expect(basketItems(state).map((b) => b.canonical_id)).toEqual([1001]);
  });

  it("drops candidates that are not products", () => {
    const [row] = sanitizeState({
      version: 1,
      items: [item({ candidates: [canonical, null, 3, { canonical_id: 2 }] })],
    }).items;
    expect(row!.candidates).toEqual([canonical]);
  });

  it.each([null, 5, "x", [], { version: 2 }, { version: 1, items: "no", flexDefaults: 7 }])(
    "reads %j as an empty list",
    (raw) => {
      expect(sanitizeState(raw).items).toEqual([]);
    },
  );

  it("garbage in storage and a throwing storage both leave a working empty list", () => {
    window.localStorage.setItem(LIST_KEY, "{not json");
    expect(getListState()).toEqual(EMPTY_LIST);
    resetListStoreForTests();
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    expect(getListState()).toEqual(EMPTY_LIST);
  });
});

describe("the list in other tabs", () => {
  it("follows another tab that changed it, and an emptied localStorage (storage event without a key)", () => {
    const { result } = renderHook(() => useList());
    expect(result.current.state.items).toEqual([]);
    act(() => {
      window.localStorage.setItem(LIST_KEY, JSON.stringify({ ...EMPTY_LIST, items: [item()] }));
      window.dispatchEvent(new StorageEvent("storage", { key: LIST_KEY }));
    });
    expect(result.current.state.items).toHaveLength(1);
    // Another tab ran localStorage.clear(): the event carries no key.
    act(() => {
      window.localStorage.clear();
      window.dispatchEvent(new StorageEvent("storage", { key: null }));
    });
    expect(result.current.state.items).toEqual([]);
  });
});
