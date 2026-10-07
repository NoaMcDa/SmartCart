import { render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import { BasketDefinition, BasketMonthTable } from "./BasketTable";
import { PriceTable } from "./components";
import { getBasketIndex } from "./data";
import type { BasketMonth } from "./types";

const month: BasketMonth = {
  month: "2026-10",
  basket_version: 1,
  computed_at: "2026-10-07T06:00:00Z",
  price_date: "2026-10-07T05:00:00Z",
  cheapest_chain_id: "a",
  spread_pct: 4.4,
  status: "published",
  reviewed_by: "reviewer",
  chains: [
    {
      chain_id: "a",
      name: "רמי לוי",
      total: 34.2,
      delta_vs_cheapest: 0,
      delta_pct: 0,
      items_priced: 25,
      estimated_items: 0,
      stores: 12,
      complete: true,
      missing: [],
    },
    {
      chain_id: "b",
      name: "שופרסל",
      total: 35.7,
      delta_vs_cheapest: 1.5,
      delta_pct: 4.4,
      items_priced: 25,
      estimated_items: 3,
      stores: 30,
      complete: true,
      missing: [],
    },
    {
      chain_id: "c",
      name: "יוחננוף",
      total: null,
      delta_vs_cheapest: null,
      delta_pct: null,
      items_priced: 20,
      estimated_items: 0,
      stores: 4,
      complete: false,
      missing: ["eggs-l", "tomato"],
    },
  ],
};

/** Structural rules only: jsdom has no layout, so color contrast is checked in the browser suite. */
async function violations(container: Element) {
  const result = await axe.run(container, {
    rules: { "color-contrast": { enabled: false } },
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] },
  });
  return result.violations.map((v) => `${v.id}: ${v.nodes.length}`);
}

describe("BasketMonthTable", () => {
  it("lists chain, total, difference from the cheapest and the update date", () => {
    render(<BasketMonthTable month={month} />);
    const table = screen.getByRole("table");
    expect(within(table).getByText(/מחירים נכונים לתאריך/)).toBeInTheDocument();
    expect(screen.getByText("7 באוקטובר 2026")).toHaveAttribute("datetime", "2026-10-07");
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2); // the incomplete chain is not ranked
    expect(within(rows[0]!).getByText("רמי לוי")).toBeInTheDocument();
    expect(within(rows[0]!).getByText("הזולה ביותר")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("₪ 35.70")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("₪ 1.50")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("+4.4%")).toBeInTheDocument();
    // estimated prices carry an icon-and-text tag, not color alone
    expect(within(rows[1]!).getByText("כולל מחירי הערכה")).toBeInTheDocument();
  });

  it("names the chains that were not ranked and offers the press report", () => {
    render(<BasketMonthTable month={month} />);
    expect(screen.getByText(/יוחננוף \(2 פריטים\)/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /הדוח התמציתי לעיתונות, אוקטובר 2026/ });
    expect(link).toHaveAttribute("href", "/seo/reports/basket-index-2026-10.md");
  });

  it("prices are LTR islands inside the Hebrew table", () => {
    render(<BasketMonthTable month={month} />);
    expect(screen.getByText("₪ 34.20")).toHaveAttribute("dir", "ltr");
  });

  it("has no structural accessibility violations", async () => {
    const { container } = render(<BasketMonthTable month={month} />);
    expect(await violations(container)).toEqual([]);
  });
});

describe("BasketDefinition and PriceTable", () => {
  it("publishes the 25-item basket with versions and amounts", () => {
    const { basket } = getBasketIndex();
    render(<BasketDefinition basket={basket} />);
    expect(screen.getByText(/הסל הקבוע, גרסה 1: 25 מוצרים/)).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(26);
    expect(screen.getByText("חלב טרי 3%")).toBeInTheDocument();
  });

  it("price table: per-chain median and cheapest, estimated flagged with text", async () => {
    const { container } = render(
      <PriceTable
        unit="kg"
        prices={[
          {
            chain_id: "a",
            chain_name: "רמי לוי",
            min_unit_price: 5.9,
            median_unit_price: 6.9,
            stores: 3,
            is_estimated: true,
            price_valid_from: "2026-10-07T05:00:00Z",
          },
        ]}
      />,
    );
    expect(screen.getByRole("table", { name: "מחיר לק״ג בכל רשת" })).toBeInTheDocument();
    expect(screen.getByText("₪ 6.90")).toBeInTheDocument();
    expect(screen.getByText("הערכה, מוצר במשקל")).toBeInTheDocument();
    expect(await violations(container)).toEqual([]);
  });
});
