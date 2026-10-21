/**
 * Polling mode: an item added while the answer of the API is lost. The server saved the item, the
 * browser saw a network error and kept the add in the offline queue; the replay sent the add again
 * and, before the idempotency key (`client_id`), the list got the item twice. The queue now makes
 * one id per add and sends it with every attempt; the API answers the repeat with the stored row.
 */
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import { resetMeMock } from "@/mocks/handlers";
import { resetPhase2Mock } from "@/mocks/handlers.phase2";
import { server } from "@/mocks/node";
import { queuedEdits, resetQueueForTests } from "./offlineQueue";
import { SharedListScreen } from "./SharedListScreen";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});
afterAll(() => server.close());
beforeEach(() => {
  resetMeMock();
  resetPhase2Mock();
  window.localStorage.clear();
  resetQueueForTests();
});

type Row = { id: number; input_text: string; client_id: string | null };

async function savedItems(): Promise<Row[]> {
  const res = await fetch(`${API_BASE_URL}/me/lists/1`);
  return ((await res.json()) as { items: Row[] }).items;
}

it("adds the item once when the answer to the first attempt is lost and the queue sends it again", async () => {
  await fetch(`${API_BASE_URL}/me/lists`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      name: "x",
      is_recurring: false,
      items: [{ canonical_id: 1001, input_text: "חלב טרי", quantity: 1 }],
    }),
  });

  // The first POST of an item reaches the server (the nested fetch falls through to the mock's own
  // handler) but its answer never gets back.
  const bodies: Array<{ client_id?: string }> = [];
  let lost = false;
  server.use(
    http.post(`${API_BASE_URL}/me/lists/:id/items`, async ({ request }) => {
      const body = (await request.clone().json()) as { client_id?: string };
      bodies.push(body);
      if (lost) return undefined; // the retry, and the nested call below: the mock answers
      lost = true;
      await fetch(request.clone());
      return HttpResponse.error();
    }),
  );

  render(<SharedListScreen listId={1} />);
  await screen.findAllByTestId("shared-item");

  const user = userEvent.setup();
  await user.type(screen.getByLabelText("הוספת פריט לרשימה המשותפת"), "ביצים");
  await user.click(screen.getByRole("button", { name: "חיפוש" }));
  await user.click(await screen.findByRole("button", { name: /הוספי: / }));

  // The add is still waiting: the server has the item, the screen has not heard.
  await waitFor(() => expect(bodies).toHaveLength(2));
  expect(queuedEdits(1)).toMatchObject([{ kind: "add", clientId: expect.any(String) }]);
  const afterLoss = await savedItems();
  expect(afterLoss).toHaveLength(2);

  // The connection is back; the queue sends the same add again.
  await act(async () => {
    window.dispatchEvent(new Event("online"));
  });
  await waitFor(() => expect(queuedEdits(1)).toEqual([]));
  expect(bodies).toHaveLength(3);
  expect(bodies[1]!.client_id).toBeTruthy();
  expect(new Set(bodies.map((b) => b.client_id)).size).toBe(1);

  const items = await savedItems();
  expect(items).toHaveLength(2);
  expect(items[1]!.id).toBe(afterLoss[1]!.id);
  expect(items[1]!.client_id).toBe(bodies[0]!.client_id);
  await waitFor(() => expect(screen.getAllByTestId("shared-item")).toHaveLength(2));
});
