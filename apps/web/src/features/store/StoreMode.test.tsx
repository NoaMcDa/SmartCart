import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { STORAGE_KEYS } from "@/features/profile/storage";
import { loadSavings } from "@/features/profile/savingsHistory";
import { lastResultFixture, shopperSeed, weeklyListState } from "@/mocks/lastResult";
import { clearLastResultCache } from "@/features/split/lastResult";
import { clearComparisonCache } from "@/state/comparison";
import { resetListStoreForTests } from "@/state/list";
import { PROFILE_KEY } from "@/state/shopper";
import { server } from "@/mocks/node";
import { trackEvent } from "@/features/seo/track";
import { StoreMode } from "./StoreMode";
import { buildSession, clearSession, loadSession, startSession } from "./session";

vi.mock("@/features/seo/track", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/seo/track")>()),
  trackEvent: vi.fn(),
}));

const push = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(search),
}));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const result = lastResultFixture();
const rami = result.compare!.stores.find((s) => s.store_id === 101)!;

beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
  clearComparisonCache();
  clearLastResultCache();
  clearSession();
  push.mockClear();
  search = "";
});

describe("store mode", () => {
  it("without a session or a store it shows an empty state", () => {
    render(<StoreMode />);
    expect(screen.getByRole("heading", { level: 1, name: "מצב חנות" })).toBeInTheDocument();
    expect(screen.getByTestId("store-empty")).toHaveTextContent("אין קנייה פעילה");
  });

  it("?store= starts a session for that store from the last result, sorted by department", async () => {
    window.localStorage.setItem("sc-list-v1", JSON.stringify(weeklyListState()));
    window.localStorage.setItem(PROFILE_KEY, JSON.stringify(shopperSeed()));
    search = "store=101";
    render(<StoreMode />);
    const items = await screen.findAllByTestId("shop-item");
    expect(items).toHaveLength(8);
    expect(loadSession()?.storeId).toBe(101);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(["פירות וירקות", "מוצרי חלב וביצים", "דגים", "מזון יבש ובישול"]);
  });

  describe("with a session", () => {
    beforeEach(() => {
      startSession(buildSession(rami, result, { overhead: 0 }));
    });

    it("reports store_mode_used once, with the plan and a coarse platform (#56)", async () => {
      vi.mocked(trackEvent).mockClear();
      const { rerender } = render(<StoreMode />);
      await screen.findAllByRole("checkbox");
      rerender(<StoreMode />);
      await userEvent.setup().click(screen.getAllByRole("checkbox")[0]!);
      const calls = vi.mocked(trackEvent).mock.calls.filter(([n]) => n === "store_mode_used");
      expect(calls).toEqual([
        ["store_mode_used", { plan: "single", platform: expect.stringMatching(/^[a-z]+$/) }],
      ]);
    });

    it("does not report store_mode_used for the empty state", () => {
      clearSession();
      vi.mocked(trackEvent).mockClear();
      render(<StoreMode />);
      expect(trackEvent).not.toHaveBeenCalled();
    });

    it("checking rows updates the progress and total, announces the state, and persists", async () => {
      const user = userEvent.setup();
      render(<StoreMode />);
      const checkboxes = await screen.findAllByRole("checkbox");
      expect(checkboxes).toHaveLength(8);
      expect(screen.getByTestId("progress-count")).toHaveTextContent("נאספו 0 מתוך 8");
      const milk = screen.getByRole("checkbox", { name: /חלב טרי 3% יטבתה/ });
      expect(milk).toHaveAttribute("aria-checked", "false");
      await user.click(milk);
      expect(screen.getByRole("checkbox", { name: /חלב טרי 3% יטבתה/ })).toHaveAttribute(
        "aria-checked",
        "true",
      );
      expect(screen.getByTestId("progress-count")).toHaveTextContent("נאספו 1 מתוך 8");
      expect(screen.getByTestId("progress-card")).toHaveTextContent("₪ 11.80");
      expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "1");
      // Persisted: a fresh mount (a reload) still has the mark.
      expect(loadSession()!.items.find((i) => i.canonicalId === 1001)!.checked).toBe(true);
    });

    it("undo restores an accidental tick", async () => {
      const user = userEvent.setup();
      render(<StoreMode />);
      await user.click(await screen.findByRole("checkbox", { name: /^עגבניות, 1/ }));
      expect(screen.getByTestId("progress-count")).toHaveTextContent("נאספו 1 מתוך 8");
      await user.click(
        within(screen.getByTestId("undo-bar")).getByRole("button", { name: "ביטול" }),
      );
      expect(screen.getByTestId("progress-count")).toHaveTextContent("נאספו 0 מתוך 8");
      // Tapping a checked row again also unchecks it.
      await user.click(screen.getByRole("checkbox", { name: /^עגבניות, 1/ }));
      await user.click(screen.getByRole("checkbox", { name: /^עגבניות, 1/ }));
      expect(screen.getByTestId("progress-count")).toHaveTextContent("נאספו 0 מתוך 8");
    });

    it("substitutes stay labeled and every row shows its price update time", async () => {
      render(<StoreMode />);
      const rows = await screen.findAllByTestId("shop-item");
      const milk = rows.find((r) => r.textContent?.includes("יטבתה"))!;
      expect(within(milk).getByText("תחליף")).toBeInTheDocument();
      for (const row of rows) expect(row).toHaveTextContent(/עודכן \d\d:\d\d/);
      const plain = rows.find((r) => r.textContent?.includes("ביצים L"))!;
      expect(within(plain).queryByText("תחליף")).not.toBeInTheDocument();
    });

    it("finish shows a summary, records the realized saving, and cleans the cache", async () => {
      const user = userEvent.setup();
      render(<StoreMode />);
      for (const row of await screen.findAllByRole("checkbox")) await user.click(row);
      await user.click(screen.getByTestId("finish"));
      expect(screen.getByTestId("summary")).toHaveTextContent("₪ 50.10");
      expect(screen.getByRole("dialog", { name: "סיכום הקנייה" })).toHaveTextContent(
        "חיסכון נטו שנרשם",
      );
      await user.click(screen.getByTestId("finish-confirm"));
      expect(push).toHaveBeenCalledWith("/");
      expect(window.localStorage.getItem(STORAGE_KEYS.shopping)).toBeNull();
      const saved = loadSavings();
      expect(saved).toHaveLength(1);
      expect(saved[0]).toMatchObject({ storeName: "רמי לוי · מודיעין" });
      expect(saved[0]!.net).toBeGreaterThan(0);
    });

    it("finishing with nothing checked records nothing and lists what was not collected", async () => {
      const user = userEvent.setup();
      render(<StoreMode />);
      await user.click(await screen.findByTestId("finish"));
      expect(screen.getByRole("dialog")).toHaveTextContent("לא נאספו (8)");
      await user.click(screen.getByTestId("finish-confirm"));
      expect(loadSavings()).toHaveLength(0);
    });

    it("works offline: the banner appears and the checklist keeps working", async () => {
      const user = userEvent.setup();
      Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
      render(<StoreMode />);
      window.dispatchEvent(new Event("offline"));
      expect(await screen.findByTestId("offline-banner")).toHaveTextContent("הסימונים נשמרים");
      await user.click(screen.getAllByRole("checkbox")[0]!);
      expect(screen.getByTestId("progress-count")).toHaveTextContent("נאספו 1 מתוך 8");
      Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
    });
  });
});
