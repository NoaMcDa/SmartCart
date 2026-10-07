import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import { resetPhase2Mock } from "@/mocks/handlers.phase2";
import { server } from "@/mocks/node";
import { rememberAlertLabel } from "./alertNames";
import { AlertsScreen } from "./AlertsScreen";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  resetPhase2Mock();
  window.localStorage.clear();
});

async function seedAlert(canonicalId: number, price: string, level = "any_brand") {
  await fetch(`${API_BASE_URL}/me/alerts`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      canonical_id: canonicalId,
      threshold_unit_price: price,
      flex_level: level,
    }),
  });
}

describe("alerts screen", () => {
  it("says there are none yet and where to make one", async () => {
    render(<AlertsScreen />);
    const empty = await screen.findByTestId("alerts-empty");
    expect(empty).toHaveTextContent("אין עדיין התראות");
    expect(within(empty).getByRole("link", { name: "לרשימה שלי" })).toHaveAttribute("href", "/");
  });

  it("lists each alert with the product, the unit price, the level and the radius, then deletes one", async () => {
    rememberAlertLabel(1003, { name: "משקה סויה ללא סוכר, 1 ליטר", unitLabel: 'ל-100 מ"ל' });
    await seedAlert(1003, "0.90", "close");
    await seedAlert(1001, "0.60");
    const user = userEvent.setup();
    render(<AlertsScreen />);

    const items = await screen.findAllByTestId("alert-item");
    expect(items).toHaveLength(2);
    const soy = items[0]!;
    expect(within(soy).getByRole("link", { name: "משקה סויה ללא סוכר, 1 ליטר" })).toHaveAttribute(
      "href",
      expect.stringMatching(/^\/product\/1003\?name=/),
    );
    expect(soy).toHaveTextContent(/מתחת ל-₪\s0\.90 ל-100 מ"ל/);
    expect(within(soy).getByText("תחליף קרוב")).toBeInTheDocument();
    expect(soy).toHaveTextContent('עד 5 ק"מ');
    expect(soy).toHaveTextContent("עוד לא הופעלה");
    // The second one was never named on this device.
    expect(items[1]).toHaveTextContent("מוצר מס' 1001");

    await user.click(
      within(soy).getByRole("button", { name: "מחיקת ההתראה על משקה סויה ללא סוכר, 1 ליטר" }),
    );
    await waitFor(() => expect(screen.getAllByTestId("alert-item")).toHaveLength(1));
    expect(screen.getByRole("status")).toHaveTextContent("נמחקה");
    expect(screen.getByTestId("alert-item")).toHaveTextContent("מוצר מס' 1001");
  });

  it("shows when an alert last fired, with its time", async () => {
    server.use(
      http.get(`${API_BASE_URL}/me/alerts`, () =>
        HttpResponse.json([
          {
            id: 7,
            canonical_id: 1001,
            threshold_unit_price: "0.60",
            flex_level: "any_brand",
            radius_m: 3000,
            active: true,
            last_fired_at: "2026-10-06T08:00:00Z",
            created_at: "2026-10-01T08:00:00Z",
          },
        ]),
      ),
    );
    render(<AlertsScreen />);
    const item = await screen.findByTestId("alert-item");
    expect(item).toHaveTextContent("הופעלה לאחרונה");
    expect(item.querySelector("time[datetime]")).toHaveAttribute(
      "datetime",
      "2026-10-06T08:00:00Z",
    );
    expect(item).toHaveTextContent('עד 3 ק"מ');
  });

  it("shows an error with a retry when the server is unreachable", async () => {
    server.use(http.get(`${API_BASE_URL}/me/alerts`, () => HttpResponse.json({}, { status: 500 })));
    const user = userEvent.setup();
    render(<AlertsScreen />);
    expect(await screen.findByRole("alert")).toHaveTextContent("השרת החזיר שגיאה");
    server.use(http.get(`${API_BASE_URL}/me/alerts`, () => HttpResponse.json([])));
    await user.click(screen.getByRole("button", { name: "נסי שוב" }));
    expect(await screen.findByTestId("alerts-empty")).toBeInTheDocument();
  });

  it("explains that push is unavailable without breaking the page", async () => {
    render(<AlertsScreen />);
    // jsdom has no Push API: the panel says so and the alerts still work.
    expect(await screen.findByTestId("push-unavailable")).toHaveTextContent(
      "לא תומך בהתראות דחיפה",
    );
    expect(await screen.findByTestId("alerts-empty")).toBeInTheDocument();
  });
});
