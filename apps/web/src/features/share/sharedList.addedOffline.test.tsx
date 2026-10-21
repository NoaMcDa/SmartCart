/**
 * Realtime mode: an item added offline and ticked offline. The queue holds an "add" under a
 * placeholder id and a "checked" for that placeholder. If the replay is cut off after the add was
 * saved and before the tick was, the retry must send the tick for the real row; before the fix it
 * was sent for the placeholder, matched no row and was dropped, so the tick was lost.
 */
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { SupabaseClient } from "@supabase/supabase-js";
import { afterAll, afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import { API_BASE_URL } from "@/api/config";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { setSupabaseForTests } from "@/features/auth/supabaseClient";
import { resetMeMock } from "@/mocks/handlers";
import { resetPhase2Mock } from "@/mocks/handlers.phase2";
import { server } from "@/mocks/node";
import { queuedEdits, resetQueueForTests } from "./offlineQueue";
import { SharedListScreen } from "./SharedListScreen";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  setSupabaseForTests(undefined);
  vi.restoreAllMocks();
});
afterAll(() => server.close());
beforeEach(() => {
  resetMeMock();
  resetPhase2Mock();
  window.localStorage.clear();
  resetQueueForTests();
});

const REAL_ID = 5001;

function fakeSupabase() {
  const writes: Array<{ op: string; value?: unknown; id?: unknown }> = [];
  const state = { updatesDown: false };
  const channel = {
    on: () => channel,
    subscribe: (cb: (s: string) => void) => {
      cb("SUBSCRIBED");
      return channel;
    },
  };
  const client = {
    auth: {
      getSession: vi.fn(async () => ({
        data: { session: { access_token: "jwt", user: { email: "a@b.c" } } },
      })),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
      getUser: vi.fn(async () => ({ data: { user: { id: "user-1" } } })),
    },
    channel: vi.fn(() => channel),
    removeChannel: vi.fn(async () => "ok"),
    from: vi.fn(() => ({
      insert: (value: { input_text: string; quantity: number; sort: number }) => {
        writes.push({ op: "insert", value });
        return {
          select: () => ({
            single: async () => ({
              data: { id: REAL_ID, canonical_id: 1003, checked: false, ...value },
              error: null,
            }),
          }),
        };
      },
      update: (value: unknown) => ({
        eq: async (_c: string, id: unknown) => {
          if (state.updatesDown) return { error: { message: "TypeError: Failed to fetch" } };
          writes.push({ op: "update", value, id });
          return { error: null };
        },
      }),
      delete: () => ({
        eq: async (_c: string, id: unknown) => {
          writes.push({ op: "delete", id });
          return { error: null };
        },
      }),
    })),
  };
  return { client: client as unknown as SupabaseClient, writes, state };
}

it("retries the tick of an item added offline for the real row when the replay fails between the two writes", async () => {
  await fetch(`${API_BASE_URL}/me/lists`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      name: "x",
      is_recurring: false,
      items: [{ canonical_id: 1001, input_text: "חלב טרי", quantity: 1, flex_level: "any_brand" }],
    }),
  });
  const fake = fakeSupabase();
  setSupabaseForTests(fake.client);
  render(
    <AuthProvider>
      <SharedListScreen listId={1} />
    </AuthProvider>,
  );
  await screen.findAllByTestId("shared-item");
  await waitFor(() => expect(screen.getByTestId("sync-state")).toHaveTextContent("בזמן אמת"));

  // Offline: add an item (the search is a read of the mock API) and tick it.
  const online = vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("הוספת פריט לרשימה המשותפת"), "ביצים");
  await user.click(screen.getByRole("button", { name: "חיפוש" }));
  await user.click(await screen.findByRole("button", { name: /הוספי: / }));
  await waitFor(() => expect(screen.getAllByTestId("shared-item")).toHaveLength(2));
  const box = (n: number) =>
    within(screen.getAllByTestId("shared-item")[n]!).getByRole("checkbox") as HTMLInputElement;
  await user.click(box(1));
  expect(box(1)).toBeChecked();
  const queued = queuedEdits(1);
  expect(queued.map((e) => e.kind)).toEqual(["add", "checked"]);
  const placeholder = queued[0]!.itemId;
  expect(placeholder).toBeLessThan(0);
  expect(queued[1]!.itemId).toBe(placeholder);

  // The connection comes back, the add is saved, then the link drops before the tick is sent.
  online.mockReturnValue(true);
  fake.state.updatesDown = true;
  await act(async () => {
    window.dispatchEvent(new Event("online"));
  });
  await waitFor(() => expect(fake.writes.filter((w) => w.op === "insert")).toHaveLength(1));
  await waitFor(() =>
    expect(queuedEdits(1)).toEqual([{ kind: "checked", itemId: REAL_ID, checked: true }]),
  );
  expect(box(1)).toBeChecked(); // still what the person did, now on the saved row
  expect(screen.getAllByTestId("shared-item")).toHaveLength(2);
  expect(screen.getByTestId("pending-sync")).toBeInTheDocument();

  // The next replay sends the tick for the real id, and nothing for the placeholder.
  fake.state.updatesDown = false;
  await act(async () => {
    window.dispatchEvent(new Event("online"));
  });
  await waitFor(() => expect(screen.queryByTestId("pending-sync")).toBeNull());
  expect(fake.writes.filter((w) => w.op === "update")).toEqual([
    { op: "update", value: { checked: true }, id: REAL_ID },
  ]);
  expect(fake.writes.filter((w) => w.op === "insert")).toHaveLength(1);
  expect(queuedEdits(1)).toEqual([]);
  // (The mock API does not see Supabase writes, so the list read after the replay is not asserted.)
});
