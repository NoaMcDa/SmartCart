/**
 * Where the brand signals come from (phase 3): keeping the original over a substitute, "not a good
 * substitute", an undone or dismissed swap, and choosing the exact product in the flexibility
 * sheet. Each is one signal in the category of the product, recorded on the device only, and none
 * while learning is off.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import type { PricedItem, SwapSuggestion } from "@/api/client";
import { FlexibilitySheet } from "@/features/list/FlexibilitySheet";
import { applySwap, dismissSwap, undoSwap } from "@/features/swaps/actions";
import { resetSwapsForTests, swapKey } from "@/features/swaps/swapState";
import { keepOriginal, rejectSubstitute } from "@/features/substitution/actions";
import { server } from "@/mocks/node";
import { parseRow } from "@/mocks/parseRow";
import { getListState, listActions, resetListStoreForTests } from "@/state/list";
import { getPersonal, personalActions, resetPersonalStoreForTests } from "./personalState";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
  resetPersonalStoreForTests();
  resetSwapsForTests();
  listActions.add([parseRow("חלב"), parseRow("קוטג'")]);
});

const substitute = (canonicalId: number): PricedItem =>
  ({
    canonical_id: canonicalId,
    item_id: canonicalId * 100 + 1,
    original_item_id: canonicalId * 100,
    is_substitute: true,
    display_name_he: "תחליף",
    quantity: "1",
    shelf_price: "5.00",
    effective_unit_price: "0.50",
    line_total: "5.00",
    uom: '100 מ"ל',
    price_valid_from: "2026-10-22T05:00:00Z",
    promo_applied: false,
    club_required: false,
    is_estimated: false,
    tags: [],
  }) as PricedItem;

const swap = (canonicalId: number): SwapSuggestion => ({
  canonical_id: canonicalId,
  from_item_id: canonicalId * 100,
  to_item_id: canonicalId * 100 + 1,
  to_display_name_he: "תחליף",
  flex_level: "any_brand",
  confidence: 0.9,
  saving: "3.00",
  tags: [],
});

const kinds = () => getPersonal().signals.map((s) => [s.taxonomy_id, s.kind]);

describe("brand signals", () => {
  it("keeping the original is a kept-brand signal in the product's category", () => {
    keepOriginal(substitute(1001), "חלב טרי");
    expect(kinds()).toEqual([["dairy.milk", "kept_brand"]]);
  });

  it('"not a good substitute" is a rejected-substitute signal, even when the feedback fails', async () => {
    await rejectSubstitute(substitute(1002), "קוטג'");
    expect(kinds()).toEqual([["dairy.cottage", "rejected_substitute"]]);
  });

  it("a dismissed swap is a rejection; an undone swap is a kept brand", () => {
    dismissSwap(swap(1001));
    expect(kinds()).toEqual([["dairy.milk", "rejected_substitute"]]);
    const entry = applySwap(swap(1002))!;
    expect(kinds()).toHaveLength(1); // applying a swap is not a signal
    undoSwap(entry.key);
    expect(kinds()).toEqual([
      ["dairy.milk", "rejected_substitute"],
      ["dairy.cottage", "kept_brand"],
    ]);
    expect(swapKey(swap(1002))).toBe(entry.key);
  });

  it("choosing the exact product in the flexibility sheet is a kept-brand signal, once", () => {
    const item = getListState().items[0]!;
    const { rerender } = render(
      <FlexibilitySheet item={item} flexDefaults={{}} onClose={() => {}} />,
    );
    fireEvent.click(screen.getByRole("radio", { name: /מוצר מדויק/ }));
    fireEvent.click(screen.getByRole("button", { name: "שמרי" }));
    expect(kinds()).toEqual([["dairy.milk", "kept_brand"]]);
    // Saving again with the level unchanged records nothing more.
    const again = getListState().items[0]!;
    rerender(<FlexibilitySheet item={again} flexDefaults={{}} onClose={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "שמרי" }));
    expect(kinds()).toHaveLength(1);
  });

  it("choosing another level is not a signal", () => {
    const item = getListState().items[0]!;
    render(<FlexibilitySheet item={item} flexDefaults={{}} onClose={() => {}} />);
    fireEvent.click(screen.getByRole("radio", { name: /תחליף קרוב/ }));
    fireEvent.click(screen.getByRole("button", { name: "שמרי" }));
    expect(kinds()).toEqual([]);
  });

  it("nothing is recorded while learning is off", async () => {
    personalActions.setPrefs({ learn: false });
    keepOriginal(substitute(1001));
    await rejectSubstitute(substitute(1002));
    dismissSwap(swap(1001));
    expect(getPersonal().signals).toEqual([]);
  });

  it("a product that is not on the list has no category to file a signal under", () => {
    keepOriginal(substitute(4242));
    expect(getPersonal().signals).toEqual([]);
  });
});
