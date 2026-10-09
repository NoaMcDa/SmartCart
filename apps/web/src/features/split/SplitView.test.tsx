import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { API_BASE_URL } from "@/api/config";
import { STORAGE_KEYS } from "@/features/profile/storage";
import { optimizeFixture } from "@/mocks/fixtures";
import { shopperSeed, weeklyListState } from "@/mocks/lastResult";
import { server } from "@/mocks/node";
import { clearComparisonCache } from "@/state/comparison";
import { resetListStoreForTests } from "@/state/list";
import { PROFILE_KEY } from "@/state/shopper";
import { clearLastResultCache } from "./lastResult";
import { SplitView } from "./SplitView";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(),
}));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

/** The list and the shopper context the comparison is built from (what onboarding and the list builder leave behind). */
function seed(shopper: Record<string, unknown> = {}) {
  window.localStorage.setItem("sc-list-v1", JSON.stringify(weeklyListState()));
  window.localStorage.setItem(PROFILE_KEY, JSON.stringify(shopperSeed(shopper)));
}

async function renderSplit() {
  render(<SplitView />);
  await screen.findByTestId("split-summary");
}

const text = (testId: string) => screen.getByTestId(testId).textContent ?? "";

beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
  clearComparisonCache();
  clearLastResultCache();
  push.mockClear();
});

describe("split view", () => {
  it("shows an empty state, read-only, when the list is empty", async () => {
    render(<SplitView />);
    await screen.findByTestId("split-empty");
    expect(screen.getByRole("heading", { level: 1, name: "פיצול סל" })).toBeInTheDocument();
    expect(screen.getByTestId("split-empty")).toHaveTextContent("אין עדיין השוואה לפצל");
    expect(screen.getByRole("link", { name: "חזרה להשוואה" })).toHaveAttribute("href", "/compare");
  });

  it("shows each store's distance, approximate only for the one at its town centre", async () => {
    seed();
    const res = optimizeFixture();
    const second = res.split!.stores[1]!.store;
    second.distance_approximate = true;
    second.geo_precision = "locality";
    second.distance_m = 5100;
    server.use(http.post(`${API_BASE_URL}/optimize`, () => HttpResponse.json(res)));
    await renderSplit();
    const first = res.split!.stores[0]!.store;
    expect(screen.getByTestId(`split-distance-${first.store_id}`).textContent).toMatch(
      /^\d(\.\d)? ק"מ$/,
    );
    expect(screen.getByTestId(`split-distance-${second.store_id}`)).toHaveTextContent(
      'כ־5.1 ק"מ · מיקום משוער',
    );
  });

  it("shows another empty state when no split is worth it", async () => {
    seed();
    server.use(
      http.post(`${API_BASE_URL}/optimize`, () =>
        HttpResponse.json({ ...optimizeFixture(), split: null }),
      ),
    );
    render(<SplitView />);
    expect(await screen.findByTestId("split-empty")).toHaveTextContent("אין פיצול משתלם");
  });

  it("both stores with correct subtotals, the net saving versus the home store, and the waterfall", async () => {
    seed();
    await renderSplit();
    expect(text("subtotal-101")).toContain("334.40");
    expect(text("subtotal-102")).toContain("36.60");
    expect(text("split-total")).toContain("371");
    expect(text("net-saving")).toContain("41");
    expect(screen.getByTestId("split-summary")).toHaveTextContent("חיסכון נטו מול שופרסל");
    const waterfall = within(screen.getByTestId("waterfall"));
    for (const label of [
      "מעבר רשת",
      "החלפת מותג",
      "מבצעים",
      "עלות נסיעה",
      "שווי עצירה נוספת",
      "חיסכון נטו",
    ]) {
      expect(waterfall.getByText(label)).toBeInTheDocument();
    }
    expect(waterfall.getByText(/מחיר בסיס בשופרסל/)).toBeInTheDocument();
    // Each step is text plus a number, in an LTR price span.
    for (const el of waterfall.getAllByText(/₪/)) {
      expect(el.closest('[dir="ltr"]')).not.toBeNull();
    }
  });

  it("moving an item with the button updates subtotals, net saving, waterfall and announces it", async () => {
    seed();
    const user = userEvent.setup();
    await renderSplit();
    const column = within(screen.getByTestId("split-column-101"));
    await user.click(
      column.getByRole("button", { name: "העברת חלב טרי 3% יטבתה, 1 ליטר לאושר עד" }),
    );
    expect(text("subtotal-101")).toContain("322.60");
    expect(text("subtotal-102")).toContain("48");
    expect(text("split-total")).toContain("370.60");
    expect(text("net-saving")).toContain("41.40");
    expect(
      within(screen.getByTestId("waterfall")).getByText("חיסכון נטו").closest("li"),
    ).toHaveTextContent("41.40");
    expect(text("split-announcer")).toContain("הועבר לאושר עד");
    // The item is now in the other column.
    expect(
      within(screen.getByTestId("split-column-102")).getByText(/חלב טרי 3% טרה/),
    ).toBeInTheDocument();
  });

  it("an item missing at the other store cannot move and says why", async () => {
    seed();
    const user = userEvent.setup();
    await renderSplit();
    const osher = within(screen.getByTestId("split-column-102"));
    const row = osher.getAllByTestId("split-item").find((li) => li.dataset.canonical === "1002")!;
    const button = within(row).getByRole("button", { name: /העברת קוטג/ });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(within(row).getByTestId("move-reason")).toHaveTextContent("לא נמצא ברמי לוי");
    await user.click(button);
    expect(
      within(screen.getByTestId("split-column-102")).getAllByTestId("split-item"),
    ).toHaveLength(3);
    expect(text("split-announcer")).toContain("לא ניתן להעביר");
    expect(text("subtotal-102")).toContain("36.60");
  });

  it("reset restores the recommended split", async () => {
    seed();
    const user = userEvent.setup();
    await renderSplit();
    const reset = screen.getByRole("button", { name: "איפוס לפיצול המומלץ" });
    expect(reset).toBeDisabled();
    await user.click(
      within(screen.getByTestId("split-column-101")).getByRole("button", { name: /העברת חלב/ }),
    );
    expect(reset).toBeEnabled();
    await user.click(reset);
    expect(text("subtotal-101")).toContain("334.40");
    expect(text("net-saving")).toContain("41");
    expect(reset).toBeDisabled();
  });

  it("two tabs, one per store, one panel visible at a time", async () => {
    seed();
    const user = userEvent.setup();
    await renderSplit();
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(2);
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
    await user.click(tabs[1]!);
    expect(tabs[1]).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("split-column-102")).toHaveAttribute("data-active", "true");
    expect(screen.getByTestId("split-column-101")).toHaveAttribute("data-active", "false");
  });

  it("no baseline store: no saving is shown, with a pointer to the profile", async () => {
    seed({ home_store_id: null });
    await renderSplit();
    expect(screen.getByTestId("baseline-missing")).toHaveTextContent("בלי חנות בסיס");
    expect(screen.queryByTestId("net-saving")).not.toBeInTheDocument();
    expect(screen.queryByTestId("waterfall")).not.toBeInTheDocument();
    expect(text("subtotal-101")).toContain("334.40");
  });

  it("start shopping creates the session for that store from the current assignment", async () => {
    seed();
    const user = userEvent.setup();
    await renderSplit();
    await user.click(
      within(screen.getByTestId("split-column-101")).getByRole("button", { name: /העברת חלב/ }),
    );
    await user.click(screen.getByRole("button", { name: "התחילי קנייה באושר עד" }));
    expect(push).toHaveBeenCalledWith("/store-mode?store=102");
    const session = JSON.parse(window.localStorage.getItem(STORAGE_KEYS.shopping)!);
    expect(session.storeId).toBe(102);
    expect(session.items.map((i: { canonicalId: number }) => i.canonicalId).sort()).toEqual([
      1001, 1002, 1005, 1006,
    ]);
  });
});
