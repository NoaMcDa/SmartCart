import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import type { PriceAlert } from "@/api/client";
import { API_BASE_URL } from "@/api/config";
import { server } from "@/mocks/node";
import { rememberAlertLabel } from "./alertNames";
import { AlertsScreen } from "./AlertsScreen";
import { disablePush } from "./push";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => window.localStorage.clear());

const alert = (over: Partial<PriceAlert> = {}): PriceAlert => ({
  id: 7,
  canonical_id: 1003,
  threshold_unit_price: "0.90",
  flex_level: "any_brand",
  radius_m: 5000,
  active: true,
  last_fired_at: null,
  created_at: "2026-10-01T08:00:00Z",
  ...over,
});

/** A server that keeps one alert and applies PUT bodies to it. */
function serve(initial: PriceAlert) {
  let current = initial;
  const puts: unknown[] = [];
  server.use(
    http.get(`${API_BASE_URL}/me/alerts`, () => HttpResponse.json([current])),
    http.put(`${API_BASE_URL}/me/alerts/:id`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      puts.push(body);
      current = {
        ...current,
        ...body,
        threshold_unit_price: String(body.threshold_unit_price),
      } as PriceAlert;
      return HttpResponse.json(current);
    }),
  );
  return puts;
}

describe("pause and edit alerts", () => {
  it("pauses with active=false, marks it paused, and resumes", async () => {
    rememberAlertLabel(1003, { name: "משקה סויה", unitLabel: 'ל-100 מ"ל' });
    const puts = serve(alert());
    const user = userEvent.setup();
    render(<AlertsScreen />);
    const item = await screen.findByTestId("alert-item");
    await user.click(within(item).getByRole("button", { name: "השהיית ההתראה על משקה סויה" }));
    await waitFor(() =>
      expect(within(screen.getByTestId("alert-item")).getByText("מושהית")).toBeInTheDocument(),
    );
    expect(puts[0]).toEqual({
      canonical_id: 1003,
      threshold_unit_price: "0.90",
      flex_level: "any_brand",
      radius_m: 5000,
      active: false,
    });
    expect(screen.getByRole("status")).toHaveTextContent("הושהתה");
    await user.click(screen.getByRole("button", { name: "הפעלה מחדש של ההתראה על משקה סויה" }));
    await waitFor(() => expect(screen.queryByText("מושהית")).toBeNull());
    expect(puts[1]).toMatchObject({ active: true });
  });

  it("edits the target and the level in a sheet and shows the new numbers", async () => {
    rememberAlertLabel(1003, { name: "משקה סויה", unitLabel: 'ל-100 מ"ל' });
    const puts = serve(alert());
    const user = userEvent.setup();
    render(<AlertsScreen />);
    await user.click(await screen.findByRole("button", { name: "עריכת ההתראה על משקה סויה" }));
    const sheet = await screen.findByRole("dialog", { name: "משקה סויה" });
    const price = within(sheet).getByRole("textbox", { name: /התריעי לי מתחת ל-₪/ });
    expect(price).toHaveValue("0.90");
    await user.clear(price);
    await user.type(price, "0,75");
    await user.click(within(sheet).getByRole("radio", { name: "תחליף קרוב" }));
    await user.click(within(sheet).getByRole("button", { name: "שמירה" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(puts[0]).toMatchObject({
      threshold_unit_price: "0.75",
      flex_level: "close",
      active: true,
    });
    const item = screen.getByTestId("alert-item");
    expect(item).toHaveTextContent(/מתחת ל-₪\s0\.75/);
    expect(item).toHaveTextContent("תחליף קרוב");
    expect(screen.getByRole("status")).toHaveTextContent("עודכנה");
  });

  it("rejects an empty price in the sheet without calling the API", async () => {
    const puts = serve(alert());
    const user = userEvent.setup();
    render(<AlertsScreen />);
    await user.click(await screen.findByRole("button", { name: /עריכת ההתראה/ }));
    const sheet = await screen.findByRole("dialog");
    await user.clear(within(sheet).getByRole("textbox"));
    await user.click(within(sheet).getByRole("button", { name: "שמירה" }));
    expect(await within(sheet).findByRole("alert")).toHaveTextContent("הקלידי מחיר חיובי");
    expect(puts).toHaveLength(0);
  });

  it("tells the shopper when the server refuses", async () => {
    server.use(
      http.get(`${API_BASE_URL}/me/alerts`, () => HttpResponse.json([alert()])),
      http.put(`${API_BASE_URL}/me/alerts/:id`, () => HttpResponse.json({}, { status: 500 })),
    );
    const user = userEvent.setup();
    render(<AlertsScreen />);
    await user.click(await screen.findByRole("button", { name: /השהיית ההתראה/ }));
    expect(await screen.findByRole("status")).toHaveTextContent("השרת החזיר שגיאה");
    expect(screen.queryByText("מושהית")).toBeNull();
  });
});

describe("turning push off", () => {
  it("unsubscribes this device and tells the server which endpoint", async () => {
    let endpoint: string | null = null;
    server.use(
      http.delete(`${API_BASE_URL}/me/push-subscriptions`, ({ request }) => {
        endpoint = new URL(request.url).searchParams.get("endpoint");
        return new HttpResponse(null, { status: 204 });
      }),
    );
    let unsubscribed = false;
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: {
        getRegistration: () =>
          Promise.resolve({
            pushManager: {
              getSubscription: () =>
                Promise.resolve({
                  endpoint: "https://push.example/abc",
                  unsubscribe: () => {
                    unsubscribed = true;
                    return Promise.resolve(true);
                  },
                }),
            },
          }),
      },
    });
    await disablePush();
    expect(unsubscribed).toBe(true);
    expect(endpoint).toBe("https://push.example/abc");
    delete (navigator as unknown as Record<string, unknown>).serviceWorker;
  });
});
