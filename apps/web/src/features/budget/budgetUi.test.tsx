/**
 * Monthly budget and spend on screen (issue #70): "נותר החודש" on the results and the split, the
 * Profile section with its six-month chart, and "סיימתי לקנות" in store mode.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ResultsView } from "@/features/compare/ResultsView";
import { STORAGE_KEYS } from "@/features/profile/storage";
import { clearLastResultCache } from "@/features/split/lastResult";
import { SplitView } from "@/features/split/SplitView";
import { StoreMode } from "@/features/store/StoreMode";
import { buildSession, clearSession, startSession } from "@/features/store/session";
import { formatPrice } from "@/lib/format";
import { mockSpendEntries, resetPhase3Mock } from "@/mocks/handlers.phase3";
import { lastResultFixture, shopperSeed, weeklyListState } from "@/mocks/lastResult";
import { server } from "@/mocks/node";
import { clearComparisonCache } from "@/state/comparison";
import { resetListStoreForTests } from "@/state/list";
import { PROFILE_KEY } from "@/state/shopper";
import { BudgetRemaining } from "./BudgetRemaining";
import { saveBudget } from "./budgetState";
import { MonthlyBudgetSection } from "./MonthlyBudgetSection";
import { currentMonth, monthsEndingAt } from "./month";
import { loadSpend, recordSpend } from "./spendState";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(),
}));

const auth = vi.hoisted(() => ({ status: "signed-out" as "signed-out" | "signed-in" }));
vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({
    status: auth.status,
    email: null,
    configured: false,
    openSignIn: () => {},
    signOut: async () => {},
  }),
}));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
  clearComparisonCache();
  clearLastResultCache();
  clearSession();
  resetPhase3Mock();
  push.mockClear();
  auth.status = "signed-out";
});

const spend = (total: number, over: Partial<Parameters<typeof recordSpend>[0]> = {}) =>
  recordSpend({
    storeId: 101,
    storeName: "רמי לוי · מודיעין",
    total,
    itemCount: 5,
    plan: "single",
    ...over,
  });

function seedComparison() {
  window.localStorage.setItem("sc-list-v1", JSON.stringify(weeklyListState()));
  window.localStorage.setItem(PROFILE_KEY, JSON.stringify(shopperSeed()));
}

const norm = (el: HTMLElement) => (el.textContent ?? "").replace(/ /g, " ");

describe("BudgetRemaining", () => {
  it("renders nothing without a budget: no prompt, no nagging", () => {
    spend(100);
    const { container } = render(<BudgetRemaining planTotal={389} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows what is left of the budget, labeled as the prices shown", () => {
    saveBudget(2500);
    spend(371.4);
    render(<BudgetRemaining />);
    const box = screen.getByTestId("budget-remaining");
    expect(box).toHaveTextContent("נותר החודש");
    expect(norm(screen.getByTestId("budget-left"))).toBe("₪ 2,128.60");
    expect(box).toHaveTextContent("מתוך ₪ 2,500");
    expect(box).toHaveTextContent("לפי המחירים שהוצגו, לא לפי קבלות");
    expect(within(box).getByRole("link", { name: "לתקציב" })).toHaveAttribute(
      "href",
      "/profile#budget",
    );
    expect(screen.queryByTestId("budget-after")).not.toBeInTheDocument();
  });

  it("subtracts the plan on screen, with the time of its prices", () => {
    saveBudget(2500);
    spend(371.4);
    render(<BudgetRemaining planTotal="389.00" updatedAt="2026-10-07T03:40:00Z" />);
    expect(screen.getByTestId("budget-after")).toHaveTextContent(
      "אחרי הקנייה הזו יישארו ₪ 1,739.60",
    );
    expect(screen.getByTestId("budget-remaining").querySelector("time[datetime]")).not.toBeNull();
  });

  it("over budget is a calm warning with the overage, not red and not a clamp", () => {
    saveBudget(400);
    spend(371.4);
    render(<BudgetRemaining planTotal={389} />);
    expect(screen.getByTestId("budget-after")).toHaveTextContent("הקנייה הזו חורגת מהתקציב ב");
    expect(norm(screen.getByTestId("budget-after"))).toContain("₪ 360.40");
    expect(screen.getByTestId("budget-left")).toBeInTheDocument();
  });

  it("an overspent month says so instead of showing a negative remainder", () => {
    saveBudget(300);
    spend(371.4);
    render(<BudgetRemaining />);
    expect(screen.getByTestId("budget-remaining")).toHaveTextContent("חריגה מהתקציב");
    expect(norm(screen.getByTestId("budget-left"))).toBe("₪ 71.40");
  });

  it("only this month's shops count", () => {
    saveBudget(1000);
    const [previous] = monthsEndingAt(currentMonth(), 2);
    spend(900, { now: new Date(`${previous}-15T09:00:00Z`) });
    render(<BudgetRemaining />);
    expect(norm(screen.getByTestId("budget-left"))).toBe("₪ 1,000");
  });
});

describe("on the results and the split", () => {
  it("results: remaining and what is left after the recommended plan", async () => {
    seedComparison();
    saveBudget(2500);
    spend(371.4);
    render(<ResultsView />);
    await screen.findByTestId("plan-single");
    const box = await screen.findByTestId("budget-remaining");
    expect(norm(screen.getByTestId("budget-left"))).toBe("₪ 2,128.60");
    expect(norm(screen.getByTestId("budget-after"))).toContain("₪ 1,739.60"); // 2128.60 - 389
    expect(box.querySelector("time[datetime]")).not.toBeNull();
  });

  it("results: nothing about a budget when none is set", async () => {
    seedComparison();
    render(<ResultsView />);
    await screen.findByTestId("plan-single");
    expect(screen.queryByTestId("budget-remaining")).not.toBeInTheDocument();
  });

  it("split: remaining after the split's total", async () => {
    seedComparison();
    saveBudget(2500);
    render(<SplitView />);
    await screen.findByTestId("split-summary");
    const total = Number(norm(screen.getByTestId("split-total")).replace(/[^\d.]/g, ""));
    expect(screen.getByTestId("budget-remaining")).toHaveTextContent("נותר החודש");
    expect(norm(screen.getByTestId("budget-after"))).toContain(
      formatPrice(2500 - total).replace(/\u00a0/g, " "),
    );
  });
});

describe("the Profile section", () => {
  it("starts empty, with the method stated", () => {
    render(<MonthlyBudgetSection />);
    expect(screen.getByRole("heading", { name: "תקציב חודשי" })).toBeInTheDocument();
    expect(screen.getByTestId("spend-empty")).toHaveTextContent("סיימתי לקנות");
    expect(screen.getByTestId("budget-facts")).toHaveTextContent("לא הוגדר תקציב");
    expect(screen.getByTestId("budget-method")).toHaveTextContent("לפי המחירים שהוצגו");
    expect(screen.getByTestId("budget-method")).toHaveTextContent("לא לפי קבלות");
    expect(screen.getByTestId("budget-method")).toHaveTextContent("מול הסופר שלך");
    expect(screen.queryByTestId("spend-chart")).not.toBeInTheDocument();
  });

  it("sets, changes and clears the budget", async () => {
    const user = userEvent.setup();
    render(<MonthlyBudgetSection />);
    const field = screen.getByLabelText(/כמה את רוצה להוציא/);
    await user.type(field, "2500");
    await user.click(screen.getByRole("button", { name: "שמירת תקציב" }));
    expect(screen.getByRole("status")).toHaveTextContent("התקציב נשמר");
    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEYS.budget)!)).toEqual({
      monthly: 2500,
    });
    expect(norm(screen.getByTestId("budget-remaining-value"))).toBe("₪ 2,500");

    await user.clear(field);
    await user.type(field, "3100");
    await user.click(screen.getByRole("button", { name: "שמירת תקציב" }));
    expect(norm(screen.getByTestId("budget-remaining-value"))).toBe("₪ 3,100");

    await user.click(screen.getByRole("button", { name: "ניקוי התקציב" }));
    expect(window.localStorage.getItem(STORAGE_KEYS.budget)).toBeNull();
    expect(screen.getByTestId("budget-facts")).toHaveTextContent("לא הוגדר תקציב");
    expect(field).toHaveValue(null);
  });

  it("refuses an amount that is not a positive number of shekels", async () => {
    const user = userEvent.setup();
    render(<MonthlyBudgetSection />);
    await user.type(screen.getByLabelText(/כמה את רוצה להוציא/), "-20");
    await user.click(screen.getByRole("button", { name: "שמירת תקציב" }));
    expect(screen.getByRole("alert")).toHaveTextContent("הזיני סכום חיובי");
    expect(window.localStorage.getItem(STORAGE_KEYS.budget)).toBeNull();
  });

  it("draws six months, oldest on the right, with the budget line and a table of every number", () => {
    const months = monthsEndingAt(currentMonth(), 6);
    const amounts = [120, 0, 300, 450.5, 80, 200];
    months.forEach((m, i) => {
      if (amounts[i]) spend(amounts[i]!, { now: new Date(`${m}-12T09:00:00Z`) });
    });
    saveBudget(500);
    render(<MonthlyBudgetSection />);

    const bars = screen.getAllByTestId("spend-bar");
    expect(bars.map((b) => b.getAttribute("data-month"))).toEqual(months);
    const x = (m: string) =>
      Number(bars.find((b) => b.getAttribute("data-month") === m)!.getAttribute("x"));
    // Reading direction: the older month is further to the right (larger x) in the drawing.
    expect(x(months[0]!)).toBeGreaterThan(x(months[5]!));
    const h = (m: string) =>
      Number(bars.find((b) => b.getAttribute("data-month") === m)!.getAttribute("height"));
    expect(h(months[3]!)).toBeGreaterThan(h(months[2]!));
    expect(h(months[2]!)).toBeGreaterThan(h(months[0]!));
    expect(h(months[1]!)).toBe(0); // a month without a shop is an empty slot, not a gap in the axis
    expect(screen.getByTestId("budget-line")).toBeInTheDocument();

    const table = screen.getByRole("table");
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(6);
    expect(norm(rows[0]!)).toContain("₪ 200"); // newest first
    expect(norm(rows[5]!)).toContain("₪ 120");
    expect(screen.getByTestId("spend-chart")).toHaveTextContent("לפי המחירים שהוצגו");
    expect(norm(screen.getByTestId("budget-spent"))).toBe("₪ 200");
    expect(norm(screen.getByTestId("budget-remaining-value"))).toBe("₪ 300");
  });

  it("lists this month's shops with the store, the plan and the item count but no item names", () => {
    spend(334.4, { storeName: "רמי לוי · מודיעין", itemCount: 6, plan: "split" });
    render(<MonthlyBudgetSection />);
    const li = within(screen.getByTestId("spend-entries")).getByRole("listitem");
    expect(li).toHaveTextContent("רמי לוי · מודיעין (פיצול)");
    expect(li).toHaveTextContent("6 פריטים");
    expect(norm(li)).toContain("₪ 334.40");
  });

  it("shows the month's net saving against the person's own store when trips were recorded", () => {
    window.localStorage.setItem(
      STORAGE_KEYS.savings,
      JSON.stringify([
        { id: "s1", at: new Date().toISOString(), storeName: "רמי לוי", listName: null, net: 41.4 },
      ]),
    );
    render(<MonthlyBudgetSection />);
    expect(norm(screen.getByTestId("budget-saved"))).toBe("₪ 41.40");
  });
});

describe("סיימתי לקנות in store mode", () => {
  const result = lastResultFixture();
  const rami = result.compare!.stores.find((s) => s.store_id === 101)!;

  function start(plan?: "split") {
    startSession(buildSession(rami, result, { overhead: 0, plan }));
  }

  it("records the total of what was collected, as shown, with store, count and plan", async () => {
    start();
    const user = userEvent.setup();
    render(<StoreMode />);
    for (const row of await screen.findAllByRole("checkbox")) await user.click(row);
    await user.click(screen.getByRole("button", { name: "סיימתי לקנות" }));
    const sheet = screen.getByRole("dialog", { name: "סיכום הקנייה" });
    const toggle = within(sheet).getByRole("switch", { name: "לרשום בתקציב החודשי" });
    expect(toggle).toBeChecked();
    expect(sheet).toHaveTextContent("לפי המחירים שהוצגו ולא לפי קבלה");
    await user.click(screen.getByTestId("finish-confirm"));

    const { entries, pending } = loadSpend();
    expect(entries).toHaveLength(1);
    expect(entries[0]).toMatchObject({
      store_id: 101,
      store_name: "רמי לוי · מודיעין",
      item_count: 8,
      plan: "single",
    });
    // The sum of the line totals of the store's basket.
    const expected =
      rami.items.reduce((acc, i) => acc + Math.round(Number(i.line_total) * 100), 0) / 100;
    expect(entries[0]!.total).toBe(expected);
    expect(pending).toEqual([]); // signed out: stays on the device
    expect(mockSpendEntries()).toEqual([]);
    expect(push).toHaveBeenCalledWith("/");
    // No item names anywhere in what was stored.
    expect(window.localStorage.getItem(STORAGE_KEYS.spend)).not.toMatch(/חלב|ביצים|סלמון|עגבניות/);
  });

  it("a split part is recorded as a split", async () => {
    start("split");
    const user = userEvent.setup();
    render(<StoreMode />);
    await user.click((await screen.findAllByRole("checkbox"))[0]!);
    await user.click(screen.getByRole("button", { name: "סיימתי לקנות" }));
    await user.click(screen.getByTestId("finish-confirm"));
    expect(loadSpend().entries[0]).toMatchObject({ plan: "split", item_count: 1 });
  });

  it("with nothing ticked it offers the whole plan for the store, and says so", async () => {
    start();
    const user = userEvent.setup();
    render(<StoreMode />);
    await user.click(await screen.findByTestId("finish"));
    expect(screen.getByRole("dialog")).toHaveTextContent("כל 8 הפריטים בחנות הזו, כי לא סומן דבר");
    await user.click(screen.getByTestId("finish-confirm"));
    expect(loadSpend().entries[0]).toMatchObject({ item_count: 8 });
  });

  it("the switch off records nothing", async () => {
    start();
    const user = userEvent.setup();
    render(<StoreMode />);
    await user.click((await screen.findAllByRole("checkbox"))[0]!);
    await user.click(screen.getByTestId("finish"));
    await user.click(screen.getByRole("switch", { name: "לרשום בתקציב החודשי" }));
    await user.click(screen.getByTestId("finish-confirm"));
    expect(window.localStorage.getItem(STORAGE_KEYS.spend)).toBeNull();
  });

  it("signed in, the entry is also sent to the account with POST /me/spend", async () => {
    auth.status = "signed-in";
    start();
    const user = userEvent.setup();
    render(<StoreMode />);
    await user.click((await screen.findAllByRole("checkbox"))[0]!);
    await user.click(screen.getByTestId("finish"));
    await user.click(screen.getByTestId("finish-confirm"));
    await waitFor(() => expect(mockSpendEntries()).toHaveLength(1));
    const [sent] = mockSpendEntries();
    expect(sent).toEqual(loadSpend().entries[0]);
    await waitFor(() => expect(loadSpend().pending).toEqual([]));
  });
});
