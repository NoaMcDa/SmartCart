import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { API_BASE_URL } from "@/api/config";
import { server } from "@/mocks/node";
import { buildGapRequest } from "./gapReport";
import { GapReportSheet } from "./GapReportSheet";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const context = {
  storeId: 101,
  storeName: "רמי לוי · מודיעין",
  canonicalId: 1001,
  itemId: 10101,
  itemName: "חלב טרי 3% יטבתה, 1 ליטר",
  shownPrice: "11.80",
  priceUpdatedAt: "2026-10-07T03:40:00Z",
};

describe("buildGapRequest", () => {
  it("fills store, item and shown price from the context, with no typing", () => {
    expect(buildGapRequest(context, { reason: null, actualPrice: "", note: "" })).toEqual({
      store_id: 101,
      canonical_id: 1001,
      item_id: 10101,
      shown_price: 11.8,
      actual_price: null,
      note: "#shown_at=2026-10-07T03:40:00Z",
    });
  });

  it("adds the reason and parses the shelf price and the note", () => {
    const body = buildGapRequest(context, {
      reason: "promo_wrong",
      actualPrice: "₪ 12,50",
      note: " המבצע לא תקף ",
    });
    expect(body.actual_price).toBe(12.5);
    expect(body.note).toBe("המבצע לא תקף #reason=promo_wrong #shown_at=2026-10-07T03:40:00Z");
  });

  it("keeps the whole note within the API limit of 500 characters", () => {
    const body = buildGapRequest(context, {
      reason: "price_differs",
      actualPrice: "x",
      note: "א".repeat(900),
    });
    expect(body.note!.length).toBeLessThanOrEqual(500);
    expect(body.note).toContain("#reason=price_differs");
    expect(body.actual_price).toBeNull();
  });
});

describe("GapReportSheet", () => {
  it("one tap on send reports the captured price and shows the confirmation", async () => {
    let sent: unknown = null;
    server.use(
      http.post(`${API_BASE_URL}/feedback/gap`, async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ ok: true, id: 7 });
      }),
    );
    const user = userEvent.setup();
    render(<GapReportSheet open onClose={() => undefined} context={context} />);
    expect(screen.getByRole("dialog", { name: context.itemName })).toBeInTheDocument();
    expect(screen.getByText(/עודכן/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "המחיר שונה" }));
    await user.click(screen.getByRole("button", { name: "שליחה" }));
    await waitFor(() => expect(screen.getByTestId("gap-sent")).toBeInTheDocument());
    expect(sent).toMatchObject({
      store_id: 101,
      canonical_id: 1001,
      item_id: 10101,
      shown_price: 11.8,
    });
    expect((sent as { note: string }).note).toContain("#reason=price_differs");
    expect(screen.getByRole("status")).toHaveTextContent("הדיווח התקבל");
  });

  it("says so when sending fails and lets the user retry", async () => {
    server.use(
      http.post(`${API_BASE_URL}/feedback/gap`, () => HttpResponse.json({}, { status: 500 })),
    );
    const user = userEvent.setup();
    render(<GapReportSheet open onClose={() => undefined} context={context} />);
    await user.click(screen.getByRole("button", { name: "שליחה" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("לא הצלחנו לשלוח");
    expect(screen.getByRole("button", { name: "שליחה" })).toBeEnabled();
  });
});
