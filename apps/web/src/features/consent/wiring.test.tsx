/**
 * Where the beta events are fired (docs/beta-plan.md section 5): the list builder, the results,
 * the substitution actions, the flexibility sheet, the split view and the gap report. `trackEvent`
 * is replaced by a spy so each test sees exactly what a screen would send; the consent gate
 * itself is covered in betaEvents.test.ts and consent.test.tsx.
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ReportGapSheet } from "@/features/compare/ReportGapSheet";
import { ResultsView } from "@/features/compare/ResultsView";
import { GapReportSheet } from "@/features/feedback/GapReportSheet";
import { FlexibilitySheet } from "@/features/list/FlexibilitySheet";
import { ListBuilder } from "@/features/list/ListBuilder";
import { clearLastResultCache } from "@/features/split/lastResult";
import { SplitView } from "@/features/split/SplitView";
import { acceptSubstitute, keepOriginal, rejectSubstitute } from "@/features/substitution/actions";
import { compareFixture, optimizeFixture } from "@/mocks/fixtures";
import { parseRow } from "@/mocks/handlers";
import { shopperSeed, weeklyListState } from "@/mocks/lastResult";
import { server } from "@/mocks/node";
import { clearComparisonCache, findSubstitution } from "@/state/comparison";
import { dispatch, getListState, resetListStoreForTests } from "@/state/list";
import { PROFILE_KEY } from "@/state/shopper";
import { reportListPasted, resetBetaEventsForTests } from "./betaEvents";

const track = vi.hoisted(() => vi.fn());
vi.mock("@/features/seo/track", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/seo/track")>()),
  trackEvent: track,
}));

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(),
}));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function seed() {
  window.localStorage.setItem("sc-list-v1", JSON.stringify(weeklyListState()));
  window.localStorage.setItem(PROFILE_KEY, JSON.stringify(shopperSeed()));
}

const calls = (name: string) => track.mock.calls.filter(([n]) => n === name).map(([, p]) => p);

beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
  resetBetaEventsForTests();
  clearComparisonCache();
  clearLastResultCache();
  track.mockClear();
  push.mockClear();
});

describe("list builder", () => {
  it("reports list_pasted with the number of rows for a pasted list, not for typing", async () => {
    const user = userEvent.setup();
    render(<ListBuilder />);
    const box = screen.getByLabelText("הוסיפי פריטים לרשימה");

    await user.type(box, "חלב{Enter}");
    await screen.findAllByTestId("list-row");
    expect(calls("list_pasted")).toEqual([]);

    await user.click(box);
    await user.paste("קוטג', 2 רסק עגבניות, סלמון");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(calls("list_pasted")).toEqual([{ item_count: 3 }]));
    // Only a count: no text of the list is in any event.
    expect(JSON.stringify(track.mock.calls)).not.toMatch(/קוטג|סלמון|חלב/);
  });
});

describe("results", () => {
  it("reports results_shown once with the paste-to-results time, and substitutions_shown per level", async () => {
    seed();
    reportListPasted(9, Date.now() - 2_500);
    track.mockClear();
    render(<ResultsView />);
    await screen.findByTestId("plan-single");

    await waitFor(() => expect(calls("results_shown")).toHaveLength(1));
    const [shown] = calls("results_shown") as Array<Record<string, number>>;
    expect(Object.keys(shown!).sort()).toEqual(["duration_ms", "item_count", "store_count"]);
    expect(shown!.duration_ms).toBeGreaterThanOrEqual(2_500);
    expect(shown!.duration_ms).toBeLessThan(60_000);
    expect(shown!.item_count).toBe(9);
    expect(shown!.store_count).toBe(3); // the stores in the three plans

    const subs = calls("substitutions_shown") as Array<{ flex_level: string; count: number }>;
    expect(subs.length).toBeGreaterThan(0);
    for (const s of subs) {
      expect(Object.keys(s).sort()).toEqual(["count", "flex_level"]);
      expect(["exact", "any_brand", "close"]).toContain(s.flex_level);
      expect(s.count).toBeGreaterThanOrEqual(1);
    }
    // The three substitutes of the recommended plan, split by the level of their list rows.
    expect(subs.reduce((n, s) => n + s.count, 0)).toBe(3);
    expect(new Set(subs.map((s) => s.flex_level)).size).toBe(subs.length);
  });

  it("has no paste to measure after a reload, so it reports no duration", async () => {
    seed();
    render(<ResultsView />);
    await screen.findByTestId("plan-single");
    await waitFor(() => expect(calls("substitutions_shown").length).toBeGreaterThan(0));
    expect(calls("results_shown")).toEqual([]);
  });
});

describe("substitution actions", () => {
  function substitute() {
    window.localStorage.clear();
    resetListStoreForTests();
    seed();
    resetListStoreForTests(); // re-read sc-list-v1
    return findSubstitution(optimizeFixture(), 10104, "single")!.item;
  }

  it("reports the verdict with the level the user set for the product", async () => {
    const item = substitute();
    const level = getListState().items.find(
      (i) => i.canonical?.canonical_id === item.canonical_id,
    )!.flexLevel;
    // Reading state lazily: make sure the list is loaded.
    expect(getListState().items.length).toBeGreaterThan(0);

    acceptSubstitute(item);
    expect(calls("substitution_verdict")).toEqual([{ flex_level: level, verdict: "accepted" }]);
    track.mockClear();

    await rejectSubstitute(item, "x");
    // The row went exact afterwards, but the event carries the level it had when the person decided.
    expect(calls("substitution_verdict")).toEqual([{ flex_level: level, verdict: "not_good" }]);
    expect(
      getListState().items.find((i) => i.canonical?.canonical_id === item.canonical_id),
    ).toMatchObject({
      flexLevel: "exact",
    });
  });

  it("reports kept_original, and nothing when the product is not in the list", () => {
    const item = substitute();
    keepOriginal(item, "x");
    expect(calls("substitution_verdict")).toEqual([
      expect.objectContaining({ verdict: "kept_original" }),
    ]);
    track.mockClear();
    keepOriginal({ ...item, canonical_id: 999_999 }, "y");
    expect(calls("substitution_verdict")).toEqual([]);
  });
});

describe("flexibility sheet", () => {
  function setup() {
    window.localStorage.clear();
    resetListStoreForTests();
    dispatch({ type: "add", rows: [parseRow("חלב")] });
    const state = getListState();
    return { item: state.items[0]!, state };
  }

  it("reports flex_changed with the level people move to, only when it changed", () => {
    const { item, state } = setup();
    render(<FlexibilitySheet item={item} flexDefaults={state.flexDefaults} onClose={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "שמרי" })); // unchanged: any brand
    expect(calls("flex_changed")).toEqual([]);

    fireEvent.click(screen.getByRole("radio", { name: /תחליף קרוב/ }));
    fireEvent.click(screen.getByRole("button", { name: "שמרי" }));
    expect(calls("flex_changed")).toEqual([{ flex_level: "close" }]);
  });

  it("does not report a cancelled change", () => {
    const { item, state } = setup();
    render(<FlexibilitySheet item={item} flexDefaults={state.flexDefaults} onClose={() => {}} />);
    fireEvent.click(screen.getByRole("radio", { name: /מוצר מדויק/ }));
    fireEvent.click(screen.getByRole("button", { name: "ביטול" }));
    expect(calls("flex_changed")).toEqual([]);
  });
});

describe("split view", () => {
  it("reports split_viewed when a split is on screen", async () => {
    seed();
    render(<SplitView />);
    await screen.findByTestId("split-summary");
    expect(calls("split_viewed")).toEqual([undefined]);
  });
});

describe("report a gap", () => {
  it("reports gap_reported only after the report was accepted", async () => {
    const user = userEvent.setup();
    const stores = compareFixture().stores;
    render(<ReportGapSheet open onClose={() => {}} stores={stores} items={[]} />);
    expect(calls("gap_reported")).toEqual([]);
    await user.click(screen.getByRole("button", { name: "שליחת הדיווח" }));
    await screen.findByText(/הדיווח נשלח/);
    expect(calls("gap_reported")).toHaveLength(1);
  });

  it("the shared gap sheet reports it too", async () => {
    const user = userEvent.setup();
    render(
      <GapReportSheet
        open
        onClose={() => {}}
        context={{ storeId: 101, storeName: "רמי לוי · מודיעין" }}
      />,
    );
    await user.click(screen.getByRole("button", { name: "שליחה" }));
    await screen.findByTestId("gap-sent");
    expect(calls("gap_reported")).toHaveLength(1);
    expect(within(screen.getByTestId("gap-sent")).getByRole("status")).toBeInTheDocument();
  });
});
