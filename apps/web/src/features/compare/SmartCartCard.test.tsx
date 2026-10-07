import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import type { ParsedRow } from "@/api/client";
import { canonicalRef, optimizeFixture } from "@/mocks/fixtures";
import { server } from "@/mocks/node";
import { clearSwapsCache } from "@/features/swaps/useSwaps";
import { resetSwapsForTests } from "@/features/swaps/swapState";
import { getListState, listActions, resetListStoreForTests } from "@/state/list";
import { PROFILE_KEY } from "@/state/shopper";
import { SmartCartCard } from "./SmartCartCard";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const row = (id: number, quantity: number): ParsedRow => ({
  input_text: "x",
  canonical: canonicalRef(id),
  confidence: 1,
  needs_confirmation: false,
  not_found: false,
  candidates: [],
  quantity: String(quantity),
  flex_level: "any_brand",
  is_weighed: false,
});

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem(PROFILE_KEY, JSON.stringify({ home_store_id: 103 }));
  resetListStoreForTests();
  resetSwapsForTests();
  clearSwapsCache();
  listActions.add([row(1001, 2), row(1002, 1), row(1004, 2)]);
});

const plan = () => optimizeFixture().single;

describe("smart cart card", () => {
  it("headlines the mock's three swaps with their exact total (₪11, not 10.90) and shows the biggest one", async () => {
    render(<SmartCartCard plan={plan()} />);
    const title = await screen.findByTestId("smart-cart-title");
    expect(title).toHaveTextContent("3 החלפות יחסכו לך");
    expect(title).toHaveTextContent(/₪\s11$/); // 5.00 + 4.80 + 1.20: the mock's total_saving is 11.00
    const top = screen.getByTestId("smart-cart-top");
    expect(top).toHaveTextContent("משקה סויה ללא סוכר, מותג פרטי, 1 ל'"); // ₪5.00, the largest
    expect(top).toHaveTextContent(/חיסכון\s*₪\s5(\.00)?/);
    expect(top).toHaveTextContent("ביטחון בהתאמה 88%");
    expect(screen.getByTestId("smart-cart-why")).toHaveTextContent("תחליף קרוב");
    // Tags are real Tag components with an icon and the three statuses' meaning in text.
    const tags = within(top).getAllByText(/סוג מוצר|בסיס|מותג/);
    expect(tags.length).toBeGreaterThan(1);
    expect(top.querySelector('[data-variant="matched"] svg')).not.toBeNull();
    expect(top.querySelector('[data-variant="differs"]')).toHaveTextContent("מותג: מותג פרטי");
    // Trust signals: an update time and the checkout disclaimer.
    const card = screen.getByTestId("smart-cart");
    expect(card.querySelector("time[datetime]")).not.toBeNull();
    expect(card).toHaveTextContent("המחיר הקובע הוא בקופה");
    expect(card).toHaveTextContent("רמי לוי");
  });

  it("is built from the list at the recommended store, and sends nothing until the shopper taps", async () => {
    const calls: Array<{ store: string | null; body: { items: Array<{ canonical_id: number }> } }> =
      [];
    server.use(
      http.post(`${API_BASE_URL}/optimize/swaps`, async ({ request }) => {
        calls.push({
          store: new URL(request.url).searchParams.get("store_id"),
          body: (await request.json()) as never,
        });
        return HttpResponse.json({
          store_id: 101,
          swaps: [],
          top_swap: null,
          total_saving: "0.00",
          generated_at: "2026-10-07T03:40:00Z",
        });
      }),
    );
    render(<SmartCartCard plan={plan()} />);
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0]!.store).toBe("101"); // רמי לוי, the recommended single store
    expect(calls[0]!.body.items.map((i) => i.canonical_id).sort()).toEqual([1001, 1002, 1004]);
    expect(screen.queryByTestId("smart-cart")).toBeNull(); // nothing to suggest: nothing shown
  });

  it("dismissing the top swap leaves the other two and a smaller total, and it stays dismissed", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<SmartCartCard plan={plan()} />);
    await screen.findByTestId("smart-cart-title");
    await user.click(screen.getByRole("button", { name: "לא עכשיו" }));
    await waitFor(() =>
      expect(screen.getByTestId("smart-cart-title")).toHaveTextContent("2 החלפות יחסכו לך"),
    );
    expect(screen.getByTestId("smart-cart-title")).toHaveTextContent(/₪\s6(\.00)?/);
    expect(screen.getByTestId("smart-cart-top")).toHaveTextContent("רסק עגבניות שופרסל 260 ג'");
    unmount();
    // After a reload the dismissal is still there.
    resetSwapsForTests();
    clearSwapsCache();
    render(<SmartCartCard plan={plan()} />);
    await waitFor(() =>
      expect(screen.getByTestId("smart-cart-title")).toHaveTextContent("2 החלפות"),
    );
  });

  it("applies after a tap, shows what changed with an undo, and undo brings the list back", async () => {
    const user = userEvent.setup();
    // The biggest swap (₪5.00) loosens product 1002 to "close"; the shopper has it at exact now.
    const before = getListState().items.find((i) => i.canonical?.canonical_id === 1002)!;
    listActions.setFlex(before.id, { level: "exact", allow: [], remember: false });
    render(<SmartCartCard plan={plan()} />);
    await screen.findByTestId("smart-cart-title");
    expect(getListState().items.find((i) => i.id === before.id)?.flexLevel).toBe("exact");

    await user.click(screen.getByRole("button", { name: /החליפי למשקה סויה/ }));
    expect(getListState().items.find((i) => i.id === before.id)?.flexLevel).toBe("close");
    const applied = await screen.findByTestId("smart-cart-applied");
    expect(applied).toHaveTextContent("הוחלף: משקה סויה ללא סוכר, מותג פרטי, 1 ל'");
    expect(screen.getByTestId("smart-cart-title")).toHaveTextContent("2 החלפות");

    await user.click(within(applied).getByRole("button", { name: "ביטול ההחלפה" }));
    expect(getListState().items.find((i) => i.id === before.id)?.flexLevel).toBe("exact");
    expect(await screen.findByTestId("smart-cart-undone")).toBeInTheDocument();
    expect(screen.getByTestId("smart-cart-title")).toHaveTextContent("3 החלפות");
  });

  it("renders nothing when the request fails", async () => {
    server.use(
      http.post(`${API_BASE_URL}/optimize/swaps`, () => HttpResponse.json({}, { status: 500 })),
    );
    render(<SmartCartCard plan={plan()} />);
    await new Promise((r) => setTimeout(r, 100));
    expect(screen.queryByTestId("smart-cart")).toBeNull();
  });
});
