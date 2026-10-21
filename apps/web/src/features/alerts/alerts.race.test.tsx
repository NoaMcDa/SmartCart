/**
 * Alerts: requests that outlive the screen state that started them. The first read of the list
 * answering after a create or a delete, a double tap on delete in the product form, and an edit
 * sheet whose save ends after another alert's sheet was opened.
 */
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import type { PriceAlert } from "@/api/client";
import { API_BASE_URL } from "@/api/config";
import { resetPhase2Mock } from "@/mocks/handlers.phase2";
import { server } from "@/mocks/node";
import { rememberAlertLabel } from "./alertNames";
import { AlertMe } from "./AlertMe";
import { AlertsScreen } from "./AlertsScreen";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  resetPhase2Mock();
  window.localStorage.clear();
});

const FORM = { canonicalId: 1001, name: "חלב טרי", unitLabel: 'ל-100 מ"ל' };

function hold() {
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { held, release };
}

async function listNow(): Promise<PriceAlert[]> {
  return (await fetch(`${API_BASE_URL}/me/alerts`)).json();
}

async function createWithForm(user: ReturnType<typeof userEvent.setup>, price: string) {
  const form = screen.getByTestId("alert-me");
  await user.type(within(form).getByRole("textbox", { name: /התריעי לי מתחת ל-₪/ }), price);
  await user.click(within(form).getByRole("button", { name: "יצירת התראה" }));
  return form;
}

describe("the alert form on product detail", () => {
  it("keeps the alert it just created when the first read of the list answers late with the older list", async () => {
    const { held, release } = hold();
    server.use(
      http.get(`${API_BASE_URL}/me/alerts`, async () => {
        await held;
        return HttpResponse.json([]); // asked before the create: it does not know the alert
      }),
    );
    const user = userEvent.setup();
    render(<AlertMe {...FORM} />);
    const form = await createWithForm(user, "5.90");
    await within(form).findByTestId("alert-created");
    expect(within(form).getAllByTestId("alert-existing")).toHaveLength(1);

    release();
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(within(form).getAllByTestId("alert-existing")).toHaveLength(1);
  });

  it("does not bring back an alert deleted while the first read of the list was still on its way", async () => {
    const { held, release } = hold();
    let answer: PriceAlert[] = [];
    server.use(
      http.get(
        `${API_BASE_URL}/me/alerts`,
        async () => {
          await held;
          return HttpResponse.json(answer);
        },
        { once: true }, // only the first read is held; the test's own read below is not
      ),
    );
    const user = userEvent.setup();
    render(<AlertMe {...FORM} />);
    const form = await createWithForm(user, "5.90");
    await within(form).findByTestId("alert-created");
    answer = await listNow(); // the server answered after the create, the answer is still travelling
    expect(answer).toHaveLength(1);
    await user.click(within(form).getByRole("button", { name: /מחיקת ההתראה/ }));
    await waitFor(() => expect(within(form).queryByTestId("alert-existing")).toBeNull());

    release();
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(within(form).queryByTestId("alert-existing")).toBeNull();
  });

  it("sends one delete for a double tap and shows no error", async () => {
    const user = userEvent.setup();
    render(<AlertMe {...FORM} />);
    const form = await createWithForm(user, "5.90");
    await within(form).findByTestId("alert-created");

    let deletes = 0;
    server.use(
      http.delete(`${API_BASE_URL}/me/alerts/:id`, async () => {
        deletes += 1;
        await new Promise((r) => setTimeout(r, 30));
        return new HttpResponse(null, { status: deletes === 1 ? 204 : 404 });
      }),
    );
    await user.dblClick(within(form).getByRole("button", { name: /מחיקת ההתראה/ }));
    await waitFor(() => expect(within(form).queryByTestId("alert-existing")).toBeNull());
    expect(deletes).toBe(1);
    expect(within(form).queryByTestId("alert-error")).toBeNull();
  });
});

describe("the edit sheet on /alerts", () => {
  const alert = (id: number, canonicalId: number, price: string): PriceAlert => ({
    id,
    canonical_id: canonicalId,
    threshold_unit_price: price,
    flex_level: "any_brand",
    radius_m: 5000,
    active: true,
    last_fired_at: null,
    created_at: "2026-10-01T08:00:00Z",
  });

  it("a save that ends after the person opened another alert's sheet does not close that sheet", async () => {
    rememberAlertLabel(1003, { name: "משקה סויה", unitLabel: 'ל-100 מ"ל' });
    rememberAlertLabel(1001, { name: "חלב טרי", unitLabel: 'ל-100 מ"ל' });
    const first = alert(7, 1003, "0.90");
    const second = alert(8, 1001, "0.60");
    const { held, release } = hold();
    server.use(
      http.get(`${API_BASE_URL}/me/alerts`, () => HttpResponse.json([first, second])),
      http.put(`${API_BASE_URL}/me/alerts/:id`, async ({ params, request }) => {
        await held;
        const body = (await request.json()) as Record<string, unknown>;
        const base = Number(params.id) === 7 ? first : second;
        return HttpResponse.json({
          ...base,
          ...body,
          threshold_unit_price: String(body.threshold_unit_price),
        });
      }),
    );
    const user = userEvent.setup();
    render(<AlertsScreen />);

    await user.click(await screen.findByRole("button", { name: "עריכת ההתראה על משקה סויה" }));
    let sheet = await screen.findByRole("dialog", { name: "משקה סויה" });
    const price = within(sheet).getByRole("textbox", { name: /התריעי לי מתחת ל-₪/ });
    await user.clear(price);
    await user.type(price, "0.75");
    await user.click(within(sheet).getByRole("button", { name: "שמירה" }));
    await user.keyboard("{Escape}"); // closes the sheet while the save is on its way
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    await user.click(screen.getByRole("button", { name: "עריכת ההתראה על חלב טרי" }));
    sheet = await screen.findByRole("dialog", { name: "חלב טרי" });

    release();
    await waitFor(() =>
      expect(screen.getAllByTestId("alert-item")[0]).toHaveTextContent(/₪\s0\.75/),
    );
    expect(screen.getByRole("dialog", { name: "חלב טרי" })).toBeInTheDocument();
  });
});
