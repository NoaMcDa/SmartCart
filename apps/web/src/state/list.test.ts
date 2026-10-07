import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { parseRow } from "@/mocks/handlers";
import {
  basketItems,
  dispatch,
  EMPTY_LIST,
  getListState,
  groupByDepartment,
  LIST_KEY,
  listReducer,
  resetListStoreForTests,
  sanitizeState,
  type ListState,
} from "./list";

const rows = (text: string, defaults: Record<string, string> = {}) =>
  text.split(",").map((s) => parseRow(s.trim(), defaults));

function add(state: ListState, text: string) {
  return listReducer(state, { type: "add", rows: rows(text) });
}

describe("listReducer", () => {
  it('turns "חלב, 2 רסק עגבניות, סלמון" into three rows with quantities 1, 2, 1', () => {
    const s = add(EMPTY_LIST, "חלב, 2 רסק עגבניות, סלמון");
    expect(s.items.map((i) => i.quantity)).toEqual([1, 2, 1]);
    expect(s.items.map((i) => i.canonical?.canonical_id)).toEqual([1001, 1004, 1008]);
    expect(s.items[2]?.isWeighed).toBe(true);
    expect(groupByDepartment(s.items).map((g) => g.name)).toEqual([
      "מוצרי חלב",
      "מזווה",
      "דגים ובשר",
    ]);
  });

  it("adds up the same product instead of duplicating the row", () => {
    const s = add(add(EMPTY_LIST, "חלב"), "2 חלב");
    expect(s.items).toHaveLength(1);
    expect(s.items[0]?.quantity).toBe(3);
  });

  it("keeps not-found rows explicit and out of the basket", () => {
    const s = add(EMPTY_LIST, "חלב, קקטוס");
    expect(s.items[1]).toMatchObject({ notFound: true, canonical: null });
    expect(basketItems(s).map((b) => b.canonical_id)).toEqual([1001]);
    expect(groupByDepartment(s.items).flatMap((g) => g.items)).toHaveLength(1);
  });

  it("flags low-confidence rows and resolves them on accept or pick", () => {
    let s = add(EMPTY_LIST, "שמן זית");
    const row = s.items[0]!;
    expect(row.needsConfirmation).toBe(true);
    expect(row.candidates.length).toBeGreaterThan(1);
    // Still priceable while unconfirmed: Compare stays usable.
    expect(basketItems(s)).toHaveLength(1);
    const other = row.candidates.find((c) => c.canonical_id === 1010)!;
    s = listReducer(s, { type: "confirm", id: row.id, canonical: other });
    expect(s.items[0]).toMatchObject({ needsConfirmation: false, candidates: [] });
    expect(s.items[0]?.canonical?.canonical_id).toBe(1010);
  });

  it("setFlex with remember stores the category default and applies it to that category", () => {
    let s = add(EMPTY_LIST, "חלב, רסק עגבניות");
    const milk = s.items[0]!;
    s = listReducer(s, {
      type: "setFlex",
      id: milk.id,
      choice: { level: "close", allow: ["fat_pct"], remember: true },
    });
    expect(s.flexDefaults).toEqual({ "dairy.milk": "close" });
    expect(s.items[0]).toMatchObject({ flexLevel: "close", allow: ["fat_pct"] });
    expect(s.items[1]?.flexLevel).toBe("any_brand");
    // A new milk row picks up the remembered default.
    s = listReducer(s, { type: "remove", id: milk.id });
    s = add(s, "חלב");
    expect(s.items.find((i) => i.canonical?.canonical_id === 1001)?.flexLevel).toBe("close");
  });

  it("setFlex without remember changes only the row", () => {
    let s = add(EMPTY_LIST, "חלב");
    s = listReducer(s, {
      type: "setFlex",
      id: s.items[0]!.id,
      choice: { level: "exact", allow: ["pack_size"], remember: false },
    });
    expect(s.flexDefaults).toEqual({});
    expect(s.items[0]).toMatchObject({ flexLevel: "exact", allow: [] });
  });

  it("keepOriginal switches the product to exact with the original barcode", () => {
    let s = add(EMPTY_LIST, "חלב, רסק עגבניות");
    s = listReducer(s, { type: "keepOriginal", canonicalId: 1004, originalItemId: 901004 });
    expect(basketItems(s)).toEqual([
      { canonical_id: 1001, quantity: 1, flex_level: "any_brand" },
      { canonical_id: 1004, quantity: 1, flex_level: "exact", exact_item_id: 901004 },
    ]);
  });

  it("ignores non-positive quantities", () => {
    let s = add(EMPTY_LIST, "חלב");
    s = listReducer(s, { type: "setQuantity", id: s.items[0]!.id, quantity: 0 });
    expect(s.items[0]?.quantity).toBe(1);
    s = listReducer(s, { type: "setQuantity", id: s.items[0]!.id, quantity: 4 });
    expect(s.items[0]?.quantity).toBe(4);
  });

  it("applies smart defaults for cosmetics when the server says any_brand", () => {
    const s = listReducer(EMPTY_LIST, {
      type: "add",
      rows: [
        {
          input_text: "שמפו",
          canonical: {
            canonical_id: 5000,
            display_name_he: "שמפו",
            taxonomy_id: "toiletries.hair.shampoo",
            base_unit: "100ml",
          },
          confidence: 0.9,
          needs_confirmation: false,
          not_found: false,
          quantity: "1",
          flex_level: "any_brand",
          is_weighed: false,
        },
      ],
    });
    expect(s.items[0]?.flexLevel).toBe("exact");
  });
});

describe("sanitizeState", () => {
  it("rejects other versions and junk", () => {
    expect(sanitizeState(null)).toBe(EMPTY_LIST);
    expect(sanitizeState({ version: 2, items: [] })).toBe(EMPTY_LIST);
    const s = sanitizeState({
      version: 1,
      items: [{ id: "a", inputText: "חלב", flexLevel: "weird", quantity: "x" }, { nope: 1 }],
      flexDefaults: { "dairy.milk": "close", bad: "xx" },
    });
    expect(s.items).toHaveLength(1);
    expect(s.items[0]).toMatchObject({ flexLevel: "any_brand", quantity: 1, notFound: true });
    expect(s.flexDefaults).toEqual({ "dairy.milk": "close" });
  });
});

describe("persistence", () => {
  beforeEach(() => {
    window.localStorage.clear();
    resetListStoreForTests();
  });
  afterEach(() => {
    vi.restoreAllMocks();
    resetListStoreForTests();
  });

  it("writes to localStorage and restores after a reload", () => {
    dispatch({ type: "add", rows: rows("חלב, 2 רסק עגבניות") });
    expect(JSON.parse(window.localStorage.getItem(LIST_KEY)!).items).toHaveLength(2);
    resetListStoreForTests(); // simulates a reload
    expect(getListState().items.map((i) => i.quantity)).toEqual([1, 2]);
  });

  it("keeps working in memory when storage throws (private mode)", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(getListState()).toEqual(EMPTY_LIST);
    const next = dispatch({ type: "add", rows: rows("חלב") });
    expect(next.items).toHaveLength(1);
    expect(getListState().items).toHaveLength(1);
  });
});
