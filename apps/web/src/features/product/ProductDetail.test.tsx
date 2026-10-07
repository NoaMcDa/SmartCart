import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { getListState, resetListStoreForTests } from "@/state/list";
import { PROFILE_KEY } from "@/state/shopper";
import { server } from "@/mocks/node";
import { ProductDetail } from "./ProductDetail";
import { formatUpdated, storeRows, unitLabel, variantsOf } from "./productData";
import { compareFixture } from "@/mocks/fixtures";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
});

describe("product data", () => {
  it("ranks variants ascending by unit price and labels the unit", () => {
    const rows = storeRows(compareFixture(103), 1001);
    const variants = variantsOf(rows);
    expect(variants.length).toBeGreaterThanOrEqual(3);
    const prices = variants.map((v) => v.unitPrice);
    expect(prices).toEqual([...prices].sort((a, b) => a - b));
    expect(variants[0]!.unitLabel).toBe('ל-100 מ"ל');
    expect(unitLabel('ק"ג')).toBe('לק"ג');
    expect(unitLabel("ביצה")).toBe("לביצה");
  });

  it("flags weighed goods as estimated", () => {
    const variants = variantsOf(storeRows(compareFixture(103), 1008));
    expect(variants.every((v) => v.isEstimated)).toBe(true);
  });

  it("formats the update time as today or a date, in Israel time", () => {
    const now = new Date("2026-10-07T10:00:00Z");
    expect(formatUpdated("2026-10-07T03:40:00Z", now)).toBe("היום 06:40");
    expect(formatUpdated("2026-10-05T03:40:00Z", now)).toMatch(/^05\.10 06:40$/);
  });
});

describe("product detail", () => {
  it("shows variants by unit price, a price per store with update times, and the phase-2 alert placeholder", async () => {
    window.localStorage.setItem(
      PROFILE_KEY,
      JSON.stringify({ clubs: ["רמי לוי"], home_store_id: 103 }),
    );
    render(<ProductDetail canonicalId={1001} nameHint="חלב טרי 3%, 1 ליטר" />);

    const variants = await screen.findByTestId("variants");
    const names = within(variants).getAllByRole("listitem");
    expect(names.length).toBeGreaterThanOrEqual(3);

    const table = within(screen.getByTestId("store-prices"));
    const rows = table.getAllByRole("row").slice(1); // header row first
    expect(rows).toHaveLength(5);
    for (const row of rows) {
      expect(row).toHaveTextContent(/עודכן היום|עודכן \d\d\.\d\d/);
      for (const price of within(row).getAllByText(/₪/)) {
        expect(price.closest('[dir="ltr"]')).not.toBeNull();
      }
    }
    // Cheapest first, with distance.
    expect(rows[0]).toHaveTextContent("אושר עד");
    expect(rows[0]).toHaveTextContent('5.1 ק"מ');

    // The alert is a visible, disabled placeholder labeled as phase 2, and it creates nothing.
    const alert = screen.getByRole("region", { name: "התראה כשהמחיר יורד" });
    expect(within(alert).getByText("בקרוב · שלב 2")).toBeInTheDocument();
    expect(within(alert).getByRole("textbox")).toBeDisabled();
    expect(within(alert).getByRole("button", { name: "יצירת התראה" })).toBeDisabled();
    // No price history chart.
    expect(document.querySelector("canvas, svg[role='img'], [data-chart]")).toBeNull();
    // Every row has a report-a-gap control.
    expect(screen.getAllByRole("button", { name: /דיווח:/ })).toHaveLength(5);
  });

  it("add to list puts the product on the shared list with the chosen flexibility", async () => {
    const user = userEvent.setup();
    render(<ProductDetail canonicalId={1001} nameHint="חלב טרי 3%, 1 ליטר" />);
    await screen.findByTestId("variants");
    await user.click(screen.getByRole("button", { name: "רמת גמישות: כל מותג" }));
    await user.click(screen.getByRole("button", { name: "הוספה לרשימה" }));
    expect(screen.getByText("נוסף לרשימה")).toBeInTheDocument();
    const rows = getListState().items;
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ flexLevel: "exact", quantity: 1 });
    expect(rows[0]!.canonical).toMatchObject({ canonical_id: 1001 });
  });
});
