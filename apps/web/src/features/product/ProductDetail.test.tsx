import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { resetPhase2Mock } from "@/mocks/handlers.phase2";
import { getListState, resetListStoreForTests } from "@/state/list";
import { PROFILE_KEY } from "@/state/shopper";
import { server } from "@/mocks/node";
import { ProductDetail } from "./ProductDetail";
import { formatUpdated, storeRows, unitLabel, variantsOf } from "./productData";
import { compareFixture } from "@/mocks/fixtures";
import { LocaleProvider } from "@/i18n/LocaleProvider";
import { LOCALE_KEY } from "@/i18n/locales";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  resetPhase2Mock();
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
  it("shows variants by unit price, a price per store with update times, the history and the alert form", async () => {
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

    // The alert form is live (issue #23): a price field and a create button.
    const alert = screen.getByRole("region", { name: "התראה כשהמחיר יורד" });
    expect(within(alert).getByRole("textbox", { name: /התריעי לי מתחת ל-₪/ })).toBeEnabled();
    expect(within(alert).getByRole("button", { name: "יצירת התראה" })).toBeEnabled();
    expect(within(alert).queryByText("בקרוב · שלב 2")).toBeNull();
    // The 90-day history is there (issue #28), with the accessible table fallback.
    expect(await screen.findByTestId("history-chart")).toBeInTheDocument();
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

  it("creates a price alert at the chosen level and remembers the product name for /alerts", async () => {
    const user = userEvent.setup();
    render(<ProductDetail canonicalId={1001} nameHint="חלב טרי 3%, 1 ליטר" />);
    await screen.findByTestId("variants");
    const alert = screen.getByRole("region", { name: "התראה כשהמחיר יורד" });
    await user.click(within(alert).getByRole("radio", { name: "תחליף קרוב" }));
    await user.type(within(alert).getByRole("textbox", { name: /התריעי לי מתחת ל-₪/ }), "5,90");
    await user.click(within(alert).getByRole("button", { name: "יצירת התראה" }));
    const done = await within(alert).findByTestId("alert-created");
    expect(done).toHaveTextContent(/₪\s5\.90/);
    expect(within(alert).getAllByTestId("alert-existing")).toHaveLength(1);
    expect(JSON.parse(window.localStorage.getItem("sc-alert-names-v1") ?? "{}")).toMatchObject({
      byCanonical: { "1001": { name: "חלב טרי 3%, 1 ליטר" } },
    });
  });

  it("rejects an empty or non-positive alert price without calling the API", async () => {
    const user = userEvent.setup();
    render(<ProductDetail canonicalId={1001} nameHint="חלב טרי 3%, 1 ליטר" />);
    await screen.findByTestId("variants");
    const alert = screen.getByRole("region", { name: "התראה כשהמחיר יורד" });
    await user.click(within(alert).getByRole("button", { name: "יצירת התראה" }));
    expect(await within(alert).findByTestId("alert-error")).toHaveTextContent("הקלידי מחיר חיובי");
    expect(within(alert).queryByTestId("alert-existing")).toBeNull();
  });
});

describe("product detail: approximate distances and Arabic store names", () => {
  afterEach(() => {
    document.cookie = `${LOCALE_KEY}=; path=/; max-age=0`;
    document.documentElement.lang = "he";
  });

  it("marks the distance of a town-centre store as approximate and leaves the others exact", async () => {
    render(<ProductDetail canonicalId={1001} nameHint="חלב טרי 3%, 1 ליטר" />);
    const distances = await screen.findAllByTestId("product-distance");
    const approximate = distances.filter((d) => d.getAttribute("data-approximate") === "true");
    expect(approximate).toHaveLength(1);
    expect(approximate[0]).toHaveTextContent('כ־3.6 ק"מ · מיקום משוער');
    expect(approximate[0]?.closest("tr")).toHaveTextContent("יוחננוף");
    for (const d of distances.filter((d) => !approximate.includes(d))) {
      expect(d.textContent).toMatch(/^\d(\.\d)? ק"מ$/);
    }
  });

  it("writes chains in Latin letters, cities in Arabic, and the units and the note in Arabic", async () => {
    document.cookie = `${LOCALE_KEY}=ar; path=/`;
    render(
      <LocaleProvider>
        <ProductDetail canonicalId={1001} nameHint="حليب" />
      </LocaleProvider>,
    );
    const table = await screen.findByTestId("store-prices");
    const names = table.querySelectorAll("th[scope='row'] > span:first-child");
    expect(names.length).toBe(5);
    for (const name of names) expect(name.textContent).not.toMatch(/[֐-׿]/);
    expect(table.textContent).toContain("Yochananof");
    expect(table.textContent).toContain("نحو 3.6 كم · الموقع تقريبي");
  });
});
