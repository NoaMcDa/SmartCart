import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import type { PriceHistoryResponse } from "@/api/client";
import { API_BASE_URL } from "@/api/config";
import { server } from "@/mocks/node";
import { PriceHistory } from "./PriceHistory";
import { PriceHistoryChart } from "./PriceHistoryChart";
import { DAY_MS } from "./series";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const END = Date.parse("2026-10-07T03:40:00Z");
const day = (n: number) => new Date(END - n * DAY_MS).toISOString();

/** Two runs of data with six days missing between them, and one promo with two promo days. */
const WITH_GAP: PriceHistoryResponse = {
  canonical_id: 1001,
  store_id: 103,
  days: 90,
  generated_at: day(0),
  points: [
    ...[20, 19, 18].map((d) => ({ date: day(d), unit_price: "6.50", shelf_price: "65.00" })),
    ...[10, 9, 8, 7].map((d) => ({
      date: day(d),
      unit_price: d <= 9 ? "5.20" : "6.50",
      shelf_price: d <= 9 ? "52.00" : "65.00",
      promo_description: d <= 9 ? "1+1 על המוצר" : null,
    })),
    { date: day(0), unit_price: "6.40", shelf_price: "64.00" },
  ],
  promos: [{ description: "1+1 על המוצר", starts_at: day(9), ends_at: day(7) }],
};

describe("price history chart", () => {
  it("cuts the line at missing days, hatches the gap and says so", () => {
    const { container } = render(
      <PriceHistoryChart history={WITH_GAP} days={30} metric="unit" unitLabel='ל-100 מ"ל' />,
    );
    // 3 runs of data: days 20-18, days 10-7 and day 0. Single-point runs are dots, not lines.
    expect(container.querySelectorAll("polyline")).toHaveLength(2);
    expect(screen.getAllByTestId("history-gap").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByTestId("history-summary")).toHaveTextContent("מסומנים כרווח בלי קו");
    expect(screen.getByText(/ימים ללא נתונים מוצגים כרווח מקוקו ולא כקו ישר/)).toBeInTheDocument();
  });

  it("shades promo windows and marks promo days with a Hebrew tooltip", async () => {
    render(<PriceHistoryChart history={WITH_GAP} days={30} metric="unit" unitLabel='ל-100 מ"ל' />);
    expect(screen.getAllByTestId("history-promo")).toHaveLength(1);
    const markers = screen.getAllByTestId("history-marker");
    expect(markers).toHaveLength(3);
    expect(markers[0]!.querySelector("title")).toHaveTextContent(/מבצע: 1\+1 על המוצר/);
    expect(screen.getByTestId("history-tooltip")).toHaveTextContent("הצביעי על נקודת מבצע");
    fireEvent.pointerEnter(markers[0]!);
    expect(screen.getByTestId("history-tooltip")).toHaveTextContent(/₪ 5\.20 ל-100 מ"ל.*1\+1/);
    // A legend with text, so meaning is not by color alone.
    const legend = screen.getByRole("list", { name: "מקרא" });
    expect(within(legend).getByText("תקופת מבצע")).toBeInTheDocument();
    expect(within(legend).getByText("אין נתונים")).toBeInTheDocument();
  });

  it("gives screen readers a text summary and a table of every point, and hides the drawing", () => {
    const { container } = render(
      <PriceHistoryChart history={WITH_GAP} days={30} metric="unit" unitLabel='ל-100 מ"ל' />,
    );
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    const table = screen.getByTestId("history-table");
    expect(table.closest(".sr-only")).not.toBeNull();
    expect(within(table).getByRole("columnheader", { name: "מחיר ליחידה" })).toBeInTheDocument();
    expect(within(table).getAllByRole("row")).toHaveLength(1 + 8); // header + the 8 points
    // The summary's numbers are LTR islands inside the Hebrew sentence.
    const summary = screen.getByTestId("history-summary");
    for (const n of summary.querySelectorAll("span")) expect(n).toHaveAttribute("dir", "ltr");
    expect(summary).toHaveTextContent(/₪ 5\.20.*₪ 6\.50.*₪ 6\.40/);
    // Axis numbers are left-to-right even in the right-to-left page.
    expect(container.querySelector("text")?.getAttribute("class")).toMatch(/tick/);
  });

  it("switches to shelf price and says there is no data when the series is empty", () => {
    const { rerender } = render(
      <PriceHistoryChart history={WITH_GAP} days={30} metric="shelf" unitLabel="ליחידה" />,
    );
    expect(screen.getByTestId("history-summary")).toHaveTextContent(/₪ 52\.00.*₪ 65\.00/);
    rerender(
      <PriceHistoryChart
        history={{ ...WITH_GAP, points: [], promos: [] }}
        days={30}
        metric="unit"
        unitLabel="ליחידה"
      />,
    );
    expect(screen.getByTestId("history-empty")).toHaveTextContent("אין עדיין נתוני מחיר");
  });
});

describe("price history block", () => {
  it("loads 90 days of unit prices for my store, with the update time and the checkout disclaimer", async () => {
    const calls: string[] = [];
    server.use(
      http.get(`${API_BASE_URL}/history/:id`, ({ request }) => {
        calls.push(new URL(request.url).search);
        return HttpResponse.json(WITH_GAP);
      }),
    );
    render(
      <PriceHistory
        canonicalId={1001}
        unitLabel='ל-100 מ"ל'
        stores={[
          { storeId: 103, label: "הסניף שלי · שופרסל דיל" },
          { storeId: null, label: "מחיר בסיס של הרשת" },
        ]}
      />,
    );
    expect(await screen.findByTestId("history-chart")).toBeInTheDocument();
    expect(calls[0]).toContain("store_id=103");
    expect(calls[0]).toContain("days=90");
    expect(screen.getByText("המחיר הקובע הוא בקופה.")).toBeInTheDocument();
    expect(document.querySelector("time[datetime]")).not.toBeNull();
  });

  it("refetches for 30 days and for the chain base price", async () => {
    const calls: string[] = [];
    server.use(
      http.get(`${API_BASE_URL}/history/:id`, ({ request }) => {
        calls.push(new URL(request.url).search);
        return HttpResponse.json(WITH_GAP);
      }),
    );
    const user = userEvent.setup();
    render(
      <PriceHistory
        canonicalId={1001}
        unitLabel="ליחידה"
        stores={[
          { storeId: 103, label: "הסניף שלי" },
          { storeId: null, label: "מחיר בסיס של הרשת" },
        ]}
      />,
    );
    await screen.findByTestId("history-chart");
    await user.click(screen.getByRole("radio", { name: "30 יום" }));
    await waitFor(() => expect(calls.some((c) => c.includes("days=30"))).toBe(true));
    await user.selectOptions(screen.getByTestId("history-store"), "base");
    await waitFor(() =>
      expect(calls.some((c) => !c.includes("store_id") && c.includes("days=30"))).toBe(true),
    );
  });

  it("says so when the history cannot be loaded", async () => {
    server.use(
      http.get(`${API_BASE_URL}/history/:id`, () =>
        HttpResponse.json({ detail: "x" }, { status: 500 }),
      ),
    );
    render(
      <PriceHistory
        canonicalId={1001}
        unitLabel="ליחידה"
        stores={[{ storeId: null, label: "בסיס" }]}
      />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("לא הצלחנו לטעון");
  });
});
