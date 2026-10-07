import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
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
  MAX_DISMISSED,
  recordApplied,
  recordDismissed,
  resetSwapsForTests,
  swapKey,
  SWAPS_KEY,
  undoableSwaps,
  visibleSwaps,
  type SwapsState,
} from "./swapState";

const track = vi.hoisted(() => vi.fn());
vi.mock("@/features/seo/track", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/seo/track")>()),
  trackEvent: track,
}));
const events = (name: string) => track.mock.calls.filter(([n]) => n === name).map(([, p]) => p);

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
    track.mockClear();
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

  it("undo sends kept_original with source swap, reports swap_undone, and the swap is offered again", async () => {
    const bodies: Array<Record<string, unknown>> = [];
    server.use(
      http.post(`${API_BASE_URL}/feedback/substitution`, async ({ request }) => {
        bodies.push((await request.json()) as Record<string, unknown>);
        return HttpResponse.json({ ok: true, id: 1 });
      }),
    );
    listActions.add([row(1004, 1, "any_brand")]);
    const s = swap({ canonical_id: 1004, saving: "4.80", flex_level: "close", confidence: 0.96 });
    applySwap(s);
    expect(undoSwap(swapKey(s))).toBe(true);
    await new Promise((r) => setTimeout(r, 50));

    expect(bodies.map((b) => b.verdict)).toEqual(["accepted", "kept_original"]);
    expect(bodies[1]).toEqual({
      canonical_id: 1004,
      original_item_id: 100400,
      substitute_item_id: 100401,
      verdict: "kept_original",
      source: "swap",
      flex_level: "close",
      match_confidence: 0.96,
    });
    expect(events("swap_applied")).toEqual([{ flex_level: "close", saving_agorot: 480 }]);
    expect(events("swap_undone")).toEqual([{ flex_level: "close" }]);
    expect(events("swap_dismissed")).toEqual([]);
    expect(visibleSwaps([s], getSwapsState())).toHaveLength(1);
    // A second undo of the same swap does nothing and reports nothing more.
    expect(undoSwap(swapKey(s))).toBe(false);
    expect(events("swap_undone")).toHaveLength(1);
  });

  it("dismiss reports swap_dismissed with the level only, and no event carries an id, a name or a price text", () => {
    listActions.add([row(1002, 1, "any_brand")]);
    const s = swap({ canonical_id: 1002, saving: "5.00", flex_level: "close" });
    dismissSwap(s);
    applySwap(swap({ canonical_id: 1002, saving: "5.00", to_item_id: 7, from_item_id: 6 }));
    expect(events("swap_dismissed")).toEqual([{ flex_level: "close" }]);
    const sent = JSON.stringify(track.mock.calls);
    expect(sent).not.toMatch(/1002|100201|תחליף|5\.00/);
  });

  it("keeps an applied swap, with what undo needs, across a reload, and undoes it from storage", async () => {
    listActions.add([row(1004, 3, "any_brand")]);
    const id = getListState().items[0]!.id;
    const s = swap({ canonical_id: 1004, saving: "4.80", flex_level: "close" });
    applySwap(s);
    resetSwapsForTests(); // a reload: the module state is gone, localStorage is not
    const stored = getSwapsState();
    expect(stored.applied).toHaveLength(1);
    expect(stored.applied[0]).toMatchObject({
      key: swapKey(s),
      origin: { canonicalId: 1004, fromItemId: 100400, toItemId: 100401, flexLevel: "close" },
    });
    expect(undoableSwaps(stored, new Set([id]))).toHaveLength(1);
    expect(undoSwap(swapKey(s))).toBe(true);
    expect(getListState().items[0]).toMatchObject({ flexLevel: "any_brand", quantity: 3 });
    await new Promise((r) => setTimeout(r, 40));
  });

  it("undoes an entry stored before origins existed without sending feedback", async () => {
    listActions.add([row(1004, 1, "any_brand")]);
    const id = getListState().items[0]!.id;
    listActions.setFlex(id, { level: "close", allow: [], remember: false });
    window.localStorage.setItem(
      SWAPS_KEY,
      JSON.stringify({
        version: 1,
        dismissed: {},
        applied: [
          {
            key: "1004:100401",
            name: "x",
            saving: 4.8,
            at: "2026-10-07T00:00:00Z",
            rows: [{ rowId: id, flexLevel: "any_brand", allow: [], exactItemId: null }],
          },
        ],
      }),
    );
    resetSwapsForTests();
    const seen: unknown[] = [];
    server.use(
      http.post(`${API_BASE_URL}/feedback/substitution`, async ({ request }) => {
        seen.push(await request.json());
        return HttpResponse.json({ ok: true, id: 1 });
      }),
    );
    expect(undoSwap("1004:100401")).toBe(true);
    await new Promise((r) => setTimeout(r, 50));
    expect(getListState().items[0]!.flexLevel).toBe("any_brand");
    expect(seen).toEqual([]);
    expect(events("swap_undone")).toEqual([{}]);
  });

  it("an undo is not offered once every row it changed was removed from the list", () => {
    listActions.add([row(1004, 1, "any_brand")]);
    const id = getListState().items[0]!.id;
    applySwap(swap({ canonical_id: 1004, saving: "4.80" }));
    expect(undoableSwaps(getSwapsState(), new Set([id]))).toHaveLength(1);
    expect(undoableSwaps(getSwapsState(), new Set())).toHaveLength(0);
  });
});

describe("dismissals are bounded and re-dismissing moves the baseline", () => {
  beforeEach(() => {
    window.localStorage.clear();
    resetSwapsForTests();
  });

  it("a dismissed swap that comes back after a material change and is dismissed again compares against the new saving", () => {
    const first = swap({ canonical_id: 1002, saving: "5.00" });
    recordDismissed(first);
    const cheaper = swap({ canonical_id: 1002, saving: "9.00" });
    expect(visibleSwaps([cheaper], getSwapsState())).toHaveLength(1);
    recordDismissed(cheaper);
    expect(visibleSwaps([cheaper], getSwapsState())).toHaveLength(0);
    expect(visibleSwaps([swap({ canonical_id: 1002, saving: "9.40" })], getSwapsState())).toEqual(
      [],
    );
    // Back at the first saving it is a material change from 9.00 again.
    expect(visibleSwaps([first], getSwapsState())).toHaveLength(1);
  });

  it("applying a swap clears its dismissal", () => {
    const s = swap({ canonical_id: 1002, saving: "5.00" });
    recordDismissed(s);
    recordApplied({ key: swapKey(s), name: "x", saving: 5, rows: [], at: "2026-10-07T00:00:00Z" });
    expect(getSwapsState().dismissed).toEqual({});
  });

  it("keeps only the newest dismissals", () => {
    for (let i = 1; i <= MAX_DISMISSED + 5; i++) {
      recordDismissed(swap({ canonical_id: i, saving: "2.00" }));
    }
    const keys = Object.keys(getSwapsState().dismissed);
    expect(keys).toHaveLength(MAX_DISMISSED);
    expect(keys[0]).toBe(`6:601`);
    resetSwapsForTests();
    expect(Object.keys(getSwapsState().dismissed)).toHaveLength(MAX_DISMISSED);
  });

  it("drops a corrupt stored value instead of throwing", () => {
    window.localStorage.setItem(SWAPS_KEY, "{not json");
    resetSwapsForTests();
    expect(getSwapsState()).toEqual({ version: 1, dismissed: {}, applied: [] });
  });
});
