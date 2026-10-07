import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import type { ParsedRow, SwapSuggestion } from "@/api/client";
import { API_BASE_URL } from "@/api/config";
import { canonicalRef } from "@/mocks/fixtures";
import { server } from "@/mocks/node";
import { getListState, listActions, resetListStoreForTests } from "@/state/list";
import { applySwap, dismissSwap, undoSwap } from "./actions";
import {
  aggregate,
  getSwapsState,
  isMaterialChange,
  resetSwapsForTests,
  swapKey,
  visibleSwaps,
  type SwapsState,
} from "./swapState";

const swap = (
  over: Partial<SwapSuggestion> & { canonical_id: number; saving: string },
): SwapSuggestion => ({
  from_item_id: over.canonical_id * 100,
  to_item_id: over.canonical_id * 100 + 1,
  to_display_name_he: "תחליף",
  flex_level: "any_brand",
  confidence: 0.9,
  tags: [],
  ...over,
});

const EMPTY: SwapsState = { version: 1, dismissed: {}, applied: [] };

describe("what is still worth offering", () => {
  const swaps = [
    swap({ canonical_id: 1002, saving: "5.00" }),
    swap({ canonical_id: 1004, saving: "4.80" }),
    swap({ canonical_id: 1001, saving: "1.20" }),
  ];

  it("shows everything the API returned when nothing was dismissed or applied", () => {
    expect(visibleSwaps(swaps, EMPTY)).toHaveLength(3);
  });

  it("hides a dismissed swap, and keeps it hidden while its saving barely moves", () => {
    const state: SwapsState = { ...EMPTY, dismissed: { [swapKey(swaps[0]!)]: 5.0 } };
    expect(visibleSwaps(swaps, state).map((s) => s.canonical_id)).toEqual([1004, 1001]);
    const nudged = [swap({ canonical_id: 1002, saving: "5.30" }), ...swaps.slice(1)];
    expect(visibleSwaps(nudged, state)).toHaveLength(2);
  });

  it("offers a dismissed swap again once its saving changed materially", () => {
    const state: SwapsState = { ...EMPTY, dismissed: { [swapKey(swaps[0]!)]: 5.0 } };
    const cheaper = [swap({ canonical_id: 1002, saving: "7.00" }), ...swaps.slice(1)];
    expect(visibleSwaps(cheaper, state)).toHaveLength(3);
    expect(isMaterialChange(5, 6.2)).toBe(false); // a ₪1.20 move on ₪5 is 24%
    expect(isMaterialChange(5, 6.3)).toBe(true);
    expect(isMaterialChange(2, 2.5)).toBe(false); // 25% but under ₪1
  });

  it("does not offer a swap that is already applied", () => {
    const state: SwapsState = {
      ...EMPTY,
      applied: [
        { key: swapKey(swaps[1]!), name: "x", saving: 4.8, rows: [], at: "2026-10-07T00:00:00Z" },
      ],
    };
    expect(visibleSwaps(swaps, state).map((s) => s.canonical_id)).toEqual([1002, 1001]);
  });
});

describe("N swaps save X", () => {
  it("is the exact sum of the swaps shown, in whole agorot, counting each product once", () => {
    const swaps = [
      swap({ canonical_id: 1002, saving: "5.00" }),
      swap({ canonical_id: 1004, saving: "4.80" }),
      swap({ canonical_id: 1001, saving: "1.20" }),
    ];
    expect(aggregate(swaps)).toEqual({ count: 3, total: 11 }); // 5.00 + 4.80 + 1.20
    // Floating-point trap: 0.1 + 0.2 must be 0.30, not 0.30000000000000004.
    expect(
      aggregate([
        swap({ canonical_id: 1, saving: "0.10" }),
        swap({ canonical_id: 2, saving: "0.20" }),
      ]).total,
    ).toBe(0.3);
    expect(aggregate([])).toEqual({ count: 0, total: 0 });
  });
});

describe("apply, undo and dismiss", () => {
  beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
  // Feedback is fire-and-forget: let it land before the next test installs its own handler.
  afterEach(async () => {
    await new Promise((r) => setTimeout(r, 40));
    server.resetHandlers();
  });
  afterAll(() => server.close());
  beforeEach(() => {
    window.localStorage.clear();
    resetListStoreForTests();
    resetSwapsForTests();
  });

  const row = (id: number, quantity: number, flex: ParsedRow["flex_level"]): ParsedRow => ({
    input_text: "x",
    canonical: canonicalRef(id),
    confidence: 1,
    needs_confirmation: false,
    not_found: false,
    candidates: [],
    quantity: String(quantity),
    flex_level: flex,
    is_weighed: false,
  });

  it("switches the list row to the swap's level only on a tap, and undo restores it", () => {
    listActions.add([row(1004, 2, "any_brand")]);
    const id = getListState().items[0]!.id;
    listActions.setFlex(id, { level: "exact", allow: [], remember: false });
    listActions.keepOriginal(1004, 10104);
    expect(getListState().items[0]).toMatchObject({ flexLevel: "exact", exactItemId: 10104 });

    const s = swap({
      canonical_id: 1004,
      saving: "4.80",
      flex_level: "close",
      to_display_name_he: "רסק עגבניות שופרסל",
    });
    expect(getListState().items[0]!.flexLevel).toBe("exact"); // nothing changed by itself

    const entry = applySwap(s);
    expect(entry).toMatchObject({ key: swapKey(s), name: "רסק עגבניות שופרסל", saving: 4.8 });
    expect(getListState().items[0]).toMatchObject({
      flexLevel: "close",
      exactItemId: null,
      quantity: 2,
    });
    expect(visibleSwaps([s], getSwapsState())).toEqual([]);

    expect(undoSwap(swapKey(s))).toBe(true);
    expect(getListState().items[0]).toMatchObject({
      flexLevel: "exact",
      exactItemId: 10104,
      quantity: 2,
    });
    expect(getSwapsState().applied).toEqual([]);
    expect(visibleSwaps([s], getSwapsState())).toHaveLength(1);
  });

  it("does nothing for a product that is not on the list", () => {
    expect(applySwap(swap({ canonical_id: 1004, saving: "1.00" }))).toBeNull();
    expect(getSwapsState().applied).toEqual([]);
  });

  it("sends an accepted signal on apply and not_good on dismiss, and remembers the dismissal", async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post(`${API_BASE_URL}/feedback/substitution`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ ok: true, id: 1 });
      }),
    );
    listActions.add([row(1004, 1, "any_brand"), row(1002, 1, "any_brand")]);
    applySwap(swap({ canonical_id: 1004, saving: "4.80" }));
    dismissSwap(swap({ canonical_id: 1002, saving: "5.00" }));
    await new Promise((r) => setTimeout(r, 50));
    expect(bodies).toHaveLength(2);
    expect(bodies).toEqual(
      expect.arrayContaining([
        {
          canonical_id: 1004,
          original_item_id: 100400,
          substitute_item_id: 100401,
          verdict: "accepted",
          source: "swap",
          flex_level: expect.any(String),
          match_confidence: expect.anything(),
        },
        {
          canonical_id: 1002,
          original_item_id: 100200,
          substitute_item_id: 100201,
          verdict: "not_good",
          source: "swap",
          flex_level: expect.any(String),
          match_confidence: expect.anything(),
        },
      ]),
    );
    expect(getSwapsState().dismissed).toEqual({ "1002:100201": 5 });
    // And it survives a reload.
    resetSwapsForTests();
    expect(getSwapsState().dismissed).toEqual({ "1002:100201": 5 });
  });
});
