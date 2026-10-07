import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { optimizeFixture } from "@/mocks/fixtures";
import { orderedPlans, ResultsContent } from "./ResultsView";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const NAMES = new Map([[1002, "קוטג' 5%, 250 ג'"]]);

function renderResults(res = optimizeFixture()) {
  return render(<ResultsContent res={res} names={NAMES} onReportGap={() => {}} />);
}

/** Every rendered price (an LTR island with ₪) must sit in a scope that shows an update time. */
function assertEveryPriceHasATimestamp(container: HTMLElement) {
  const prices = [...container.querySelectorAll('span[dir="ltr"]')].filter((el) =>
    el.textContent?.includes("₪"),
  );
  expect(prices.length).toBeGreaterThan(10);
  for (const price of prices) {
    const scope = price.closest("[data-trust-scope]");
    expect(scope, `price ${price.textContent} has no trust scope`).not.toBeNull();
    expect(
      scope!.querySelector("time[datetime]"),
      `price ${price.textContent} has no update time`,
    ).not.toBeNull();
  }
}

describe("comparison results", () => {
  it("shows the three plans with the mock numbers, recommended first", () => {
    const res = optimizeFixture();
    expect(orderedPlans(res).map((p) => p.kind)).toEqual(["single", "split", "minimum_effort"]);
    renderResults(res);
    const single = screen.getByTestId("plan-single");
    expect(single).toHaveAttribute("data-recommended", "true");
    expect(within(single).getByTestId("plan-single-total")).toHaveTextContent("₪ 389");
    const saving = within(single).getByTestId("plan-single-saving");
    expect(saving).toHaveTextContent("חוסך ₪ 57");
    expect(saving).toHaveTextContent("לעומת שופרסל דיל · מודיעין, הסופר שלך");

    const split = screen.getByTestId("plan-split");
    expect(split).toHaveAttribute("data-recommended", "false");
    expect(within(split).getByTestId("plan-split-total")).toHaveTextContent("₪ 371");
    expect(within(split).getByText(/דק'/)).toHaveTextContent("+12 דק'");
    expect(within(split).getByTestId("plan-split-saving")).toHaveTextContent("נטו");

    const home = screen.getByTestId("plan-minimum_effort");
    expect(within(home).getByTestId("plan-minimum_effort-total")).toHaveTextContent("₪ 446");
    expect(home).toHaveTextContent("מינימום מאמץ · הסופר שלך");
  });

  it("marks the split recommended only when the API says so", () => {
    const res = optimizeFixture({ extraStopValue: 0 }); // net 66 > 57: the split wins
    renderResults(res);
    expect(screen.getByTestId("plan-split")).toHaveAttribute("data-recommended", "true");
    expect(screen.getByTestId("plan-single")).toHaveAttribute("data-recommended", "false");
  });

  it("omits the split when there is none", () => {
    renderResults(optimizeFixture({ minSplitSaving: 1000 }));
    expect(screen.queryByTestId("plan-split")).toBeNull();
  });

  it("lists missing items in red text with an icon, and links substitutes to their card", () => {
    renderResults();
    const single = screen.getByTestId("plan-single");
    const missing = within(single).getByRole("button", { name: /פריט חסר/ });
    expect(missing.querySelector("svg")).not.toBeNull();
    fireEvent.click(missing);
    expect(within(single).getByRole("list", { name: "פריטים חסרים" })).toHaveTextContent(
      "קוטג' 5%, 250 ג'",
    );
    expect(within(single).getByRole("link", { name: /3 פריטים הוחלפו/ })).toHaveAttribute(
      "href",
      "/compare/substitution/10101?plan=single",
    );
    for (const link of screen.getAllByRole("link", { name: /תחליף/ })) {
      expect(link.getAttribute("href")).toMatch(/^\/compare\/substitution\/\d+\?plan=/);
    }
  });

  it("shows the checkout disclaimer and a report-a-gap control", () => {
    renderResults();
    expect(screen.getByTestId("disclaimer")).toHaveTextContent("המחיר הקובע הוא בקופה.");
    expect(screen.getByRole("button", { name: "דיווח על פער במחיר" })).toBeInTheDocument();
  });

  it("links the methodology page next to the checkout disclaimer", () => {
    renderResults();
    const footer = screen.getByTestId("disclaimer");
    expect(footer).toHaveTextContent("המחיר הקובע הוא בקופה.");
    expect(within(footer).getByRole("link", { name: "איך אנחנו משווים מחירים" })).toHaveAttribute(
      "href",
      "/methodology",
    );
  });

  it("shows the promo confidence on promo lines: the score when the API gives one, otherwise not checked", () => {
    const res = optimizeFixture();
    // Give the first club-promo line a score; every other promo line has none.
    let scored = 0;
    for (const store of res.single.stores.flatMap((s) => [s.store])) {
      for (const item of store.items) {
        if (item.promo_description && scored === 0) {
          item.promo_confidence = 0.96;
          scored += 1;
        }
      }
    }
    expect(scored).toBe(1);
    renderResults(res);
    const details = screen.getByTestId("basket-details");
    expect(within(details).getByText("ביטחון 96%")).toBeInTheDocument();
    expect(within(details).getAllByText("לא נבדק").length).toBeGreaterThanOrEqual(1);
  });

  it("labels weighed lines estimated and club promos (trust signals, #12)", () => {
    renderResults();
    const details = screen.getByTestId("basket-details");
    expect(within(details).getAllByText("מחיר משוער · שקיל").length).toBeGreaterThanOrEqual(2);
    expect(within(details).getByText(/מבצע מועדון/)).toBeInTheDocument();
  });

  it("never renders a price without an update time", () => {
    const { container } = renderResults();
    assertEveryPriceHasATimestamp(container);
  });

  it("never compares with the most expensive store (D7)", () => {
    for (const res of [optimizeFixture(), optimizeFixture({ homeStoreId: null })]) {
      const { container, unmount } = renderResults(res);
      expect(container.textContent).not.toMatch(
        /היקר ביותר|הכי יקר|היקרה ביותר|הכי יקרה|יקרה ביותר|most expensive|max/i,
      );
      unmount();
    }
  });

  it("shows no saving at all without a home store", () => {
    renderResults(optimizeFixture({ homeStoreId: null }));
    expect(screen.queryByTestId("plan-single-saving")).toBeNull();
    expect(screen.queryByText(/חוסך/)).toBeNull();
    expect(screen.queryByTestId("plan-minimum_effort")).toBeNull();
  });
});
