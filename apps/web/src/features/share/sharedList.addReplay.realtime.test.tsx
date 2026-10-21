/**
 * Realtime mode (Supabase client): the add is an insert into `list_items` with the add's client id.
 * When the insert was saved before and its answer was lost, the repeat violates the unique index
 * `(list_id, client_id)` (Postgres 23505); the replay reads the row that is there instead of
 * treating it as a refusal (which would undo the add on screen while the item is on the server).
 */
import { render, screen, waitFor } from "@testing-library/react";
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

const STORED_ID = 5001;

function fakeSupabase(insertError: { code: string; message: string } | null) {
  const inserts: Array<{ client_id?: string; input_text: string }> = [];
  const lookups: Array<[string, unknown]> = [];
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
      insert: (value: { client_id?: string; input_text: string; quantity: number }) => {
        inserts.push(value);
        return {
          select: () => ({
            single: async () =>
              insertError
                ? { data: null, error: insertError }
                : {
                    data: { id: STORED_ID, canonical_id: 1003, checked: false, ...value },
                    error: null,
                  },
          }),
        };
      },
      select: () => {
        const chain = {
          eq: (column: string, value: unknown) => {
            lookups.push([column, value]);
            return chain;
          },
          single: async () => ({
            data: {
              id: STORED_ID,
              canonical_id: 1003,
              input_text: "ביצים L",
              quantity: 1,
              checked: false,
              sort: 1,
              client_id: inserts[0]?.client_id,
            },
            error: null,
          }),
        };
        return chain;
      },
    })),
  };
  return { client: client as unknown as SupabaseClient, inserts, lookups };
}

async function openAndAdd(fake: ReturnType<typeof fakeSupabase>) {
  await fetch(`${API_BASE_URL}/me/lists`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      name: "x",
      is_recurring: false,
      items: [{ canonical_id: 1001, input_text: "חלב טרי", quantity: 1 }],
    }),
  });
  setSupabaseForTests(fake.client);
  render(
    <AuthProvider>
      <SharedListScreen listId={1} />
    </AuthProvider>,
  );
  await screen.findAllByTestId("shared-item");
  await waitFor(() => expect(screen.getByTestId("sync-state")).toHaveTextContent("בזמן אמת"));
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("הוספת פריט לרשימה המשותפת"), "ביצים");
  await user.click(screen.getByRole("button", { name: "חיפוש" }));
  await user.click(await screen.findByRole("button", { name: /הוספי: / }));
}

it("sends the client id with the insert", async () => {
  const fake = fakeSupabase(null);
  await openAndAdd(fake);
  await waitFor(() => expect(fake.inserts).toHaveLength(1));
  expect(fake.inserts[0]!.client_id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-/);
  await waitFor(() => expect(queuedEdits(1)).toEqual([]));
});

it("reads the stored row when the insert hits the unique index of a repeated add", async () => {
  const fake = fakeSupabase({ code: "23505", message: "duplicate key value" });
  await openAndAdd(fake);
  await waitFor(() => expect(fake.lookups).toHaveLength(2));
  expect(fake.lookups).toEqual([
    ["list_id", 1],
    ["client_id", fake.inserts[0]!.client_id],
  ]);
  await waitFor(() => expect(queuedEdits(1)).toEqual([]));
  expect(screen.getAllByTestId("shared-item")).toHaveLength(2);
  expect(screen.queryByTestId("pending-sync")).not.toBeInTheDocument();
});
