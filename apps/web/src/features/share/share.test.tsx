import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { SupabaseClient } from "@supabase/supabase-js";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { setSupabaseForTests } from "@/features/auth/supabaseClient";
import { resetMeMock } from "@/mocks/handlers";
import { resetPhase2Mock } from "@/mocks/handlers.phase2";
import { server } from "@/mocks/node";
import { AcceptInvite } from "./AcceptInvite";
import { inviteLink, ShareSheet } from "./ShareSheet";
import { SharedListScreen } from "./SharedListScreen";
import { readRegistry } from "./sharedLists";

const router = { push: vi.fn(), replace: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  setSupabaseForTests(undefined);
});
afterAll(() => server.close());
beforeEach(() => {
  resetMeMock();
  resetPhase2Mock();
  window.localStorage.clear();
  router.push.mockClear();
  router.replace.mockClear();
});

async function api(path: string, method: string, body?: unknown) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return res.json();
}

const WEEK = {
  name: "הקנייה השבועית",
  is_recurring: false,
  items: [
    {
      canonical_id: 1001,
      input_text: "חלב טרי 3%, 1 ליטר",
      quantity: 2,
      flex_level: "any_brand",
      confirmed: true,
    },
    {
      canonical_id: 1004,
      input_text: "רסק עגבניות",
      quantity: 1,
      flex_level: "close",
      confirmed: true,
    },
  ],
};

describe("invite link", () => {
  it("accepts a path or a full address from the API", () => {
    expect(inviteLink({ url: "/lists/accept/abc" }, "https://x.example")).toBe(
      "https://x.example/lists/accept/abc",
    );
    expect(inviteLink({ url: "https://y.example/lists/accept/abc" }, "https://x.example")).toBe(
      "https://y.example/lists/accept/abc",
    );
  });
});

describe("share sheet", () => {
  it("creates an invite for the chosen role, shows the link and copies it", async () => {
    await api("/me/lists", "POST", WEEK);
    let role: unknown;
    server.use(
      http.post(`${API_BASE_URL}/me/lists/:id/share`, async ({ request }) => {
        role = ((await request.json()) as { role: string }).role;
        return HttpResponse.json(
          { list_id: 1, token: "inv-1-xyz", url: "/lists/accept/inv-1-xyz", role },
          { status: 201 },
        );
      }),
    );
    const invited = vi.fn();
    const user = userEvent.setup();
    // user-event installs its own clipboard on setup; replace it after.
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(<ShareSheet open onClose={() => {}} listId={1} onInvited={invited} />);

    await user.click(screen.getByRole("radio", { name: "צפייה בלבד" }));
    await user.click(screen.getByRole("button", { name: "יצירת קישור הזמנה" }));
    const link = (await screen.findByLabelText(/קישור הזמנה/)) as HTMLInputElement;
    expect(role).toBe("viewer");
    expect(link.value).toBe(`${window.location.origin}/lists/accept/inv-1-xyz`);
    expect(link).toHaveAttribute("dir", "ltr");
    expect(invited).toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "העתקת הקישור" }));
    expect(writeText).toHaveBeenCalledWith(link.value);
    expect(await screen.findByTestId("invite-copied")).toBeInTheDocument();
  });

  it("explains a refusal (not a subscriber, not the owner) instead of failing silently", async () => {
    server.use(
      http.post(`${API_BASE_URL}/me/lists/:id/share`, () => HttpResponse.json({}, { status: 403 })),
    );
    const user = userEvent.setup();
    render(<ShareSheet open onClose={() => {}} listId={1} />);
    await user.click(screen.getByRole("button", { name: "יצירת קישור הזמנה" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("חלק מהמנוי");
  });
});

describe("accepting an invite", () => {
  it("joins only after a tap, remembers the list and opens it", async () => {
    await api("/me/lists", "POST", WEEK);
    const user = userEvent.setup();
    render(<AcceptInvite token="inv-1-abc" />);
    expect(router.push).not.toHaveBeenCalled(); // opening the link joins nothing
    await user.click(screen.getByRole("button", { name: "הצטרפות לרשימה" }));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/lists/1/share"));
    expect(readRegistry().joined.map((j) => j.id)).toEqual([1]);
  });

  it("says a revoked or expired link cannot be used", async () => {
    server.use(
      http.post(`${API_BASE_URL}/lists/accept/:token`, () =>
        HttpResponse.json({}, { status: 410 }),
      ),
    );
    const user = userEvent.setup();
    render(<AcceptInvite token="old-token" />);
    await user.click(screen.getByRole("button", { name: "הצטרפות לרשימה" }));
    expect(await screen.findByTestId("accept-error")).toHaveTextContent("פג תוקפו");
    expect(router.push).not.toHaveBeenCalled();
  });
});

describe("shared list screen, polling mode (not signed in, mock)", () => {
  it("shows the items and the members, with the owner and a pending invite", async () => {
    await api("/me/lists", "POST", WEEK);
    await api("/me/lists/1/share", "POST", { role: "editor" });
    render(<SharedListScreen listId={1} />);
    expect(await screen.findByTestId("shared-name")).toHaveTextContent("הקנייה השבועית");
    const items = await screen.findAllByTestId("shared-item");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("חלב טרי 3%, 1 ליטר");
    expect(screen.getByTestId("sync-state")).toHaveAttribute("data-mode", "polling");
    const members = await screen.findAllByTestId("member");
    expect(members.map((m) => m.textContent)).toEqual([
      expect.stringContaining("הבעלים של הרשימה"),
      expect.stringContaining("הזמנה ממתינה"),
    ]);
    expect(screen.getByText(/המיקום וההעדפות של כל אחת נשארים אצלה/)).toBeInTheDocument();
  });

  it("changes a quantity optimistically and saves it through the API", async () => {
    await api("/me/lists", "POST", WEEK);
    const user = userEvent.setup();
    render(<SharedListScreen listId={1} />);
    const first = (await screen.findAllByTestId("shared-item"))[0]!;
    await user.click(within(first).getByRole("button", { name: /הוסיפי כמות/ }));
    await waitFor(() =>
      expect(within(screen.getAllByTestId("shared-item")[0]!).getByRole("group")).toHaveTextContent(
        "3",
      ),
    );
    const saved = (await api("/me/lists/1", "GET")) as { items: Array<{ quantity: string }> };
    expect(saved.items[0]!.quantity).toBe("3");
  });

  it("puts the list back and says so when a save fails", async () => {
    await api("/me/lists", "POST", WEEK);
    server.use(
      http.put(`${API_BASE_URL}/me/lists/:id`, () => HttpResponse.json({}, { status: 500 })),
    );
    const user = userEvent.setup();
    render(<SharedListScreen listId={1} />);
    const first = (await screen.findAllByTestId("shared-item"))[0]!;
    await user.click(within(first).getByRole("button", { name: /הסרת/ }));
    expect(await screen.findByTestId("shared-message")).toHaveTextContent("החזרנו את הרשימה");
    expect(screen.getAllByTestId("shared-item")).toHaveLength(2);
  });

  it("says when the list is not there or not yours", async () => {
    render(<SharedListScreen listId={404} />);
    expect(await screen.findByTestId("shared-error")).toHaveTextContent("לא נמצאה");
  });
});

describe("shared list screen, realtime mode (signed in with Supabase)", () => {
  type Payload = {
    eventType: string;
    new?: Record<string, unknown>;
    old?: Record<string, unknown>;
  };

  function fakeSupabase(opts: { failWrites?: boolean } = {}) {
    let handler: (p: Payload) => void = () => undefined;
    const filters: unknown[] = [];
    const writes: Array<{ op: string; value?: unknown; id?: unknown }> = [];
    const channel = {
      on: (_type: string, filter: unknown, cb: (p: Payload) => void) => {
        filters.push(filter);
        handler = cb;
        return channel;
      },
      subscribe: (cb: (s: string) => void) => {
        cb("SUBSCRIBED");
        return channel;
      },
    };
    const error = opts.failWrites ? { message: "denied" } : null;
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
        update: (value: unknown) => ({
          eq: async (_c: string, id: unknown) => {
            writes.push({ op: "update", value, id });
            return { error };
          },
        }),
        delete: () => ({
          eq: async (_c: string, id: unknown) => {
            writes.push({ op: "delete", id });
            return { error };
          },
        }),
        insert: (value: Record<string, unknown>) => ({
          select: () => ({
            single: async () => {
              writes.push({ op: "insert", value });
              return { data: { ...value, id: 5000 }, error };
            },
          }),
        }),
      })),
    };
    return {
      client: client as unknown as SupabaseClient,
      raw: client,
      emit: (p: Payload) => handler(p),
      filters,
      writes,
    };
  }

  async function renderRealtime(opts?: { failWrites?: boolean }) {
    await api("/me/lists", "POST", WEEK);
    const fake = fakeSupabase(opts);
    setSupabaseForTests(fake.client);
    render(
      <AuthProvider>
        <SharedListScreen listId={1} />
      </AuthProvider>,
    );
    await screen.findAllByTestId("shared-item");
    await waitFor(() =>
      expect(screen.getByTestId("sync-state")).toHaveAttribute("data-mode", "realtime"),
    );
    await waitFor(() => expect(screen.getByTestId("sync-state")).toHaveTextContent("בזמן אמת"));
    return fake;
  }

  it("subscribes to list_items of this list and applies other people's inserts, edits and deletes", async () => {
    const fake = await renderRealtime();
    expect(fake.filters).toEqual([
      { event: "*", schema: "public", table: "list_items", filter: "list_id=eq.1" },
    ]);

    act(() =>
      fake.emit({
        eventType: "INSERT",
        new: { id: 77, canonical_id: 1008, input_text: "ביצים", quantity: 12, sort: 5 },
      }),
    );
    expect(await screen.findByText("ביצים")).toBeInTheDocument();
    expect(screen.getAllByTestId("shared-item")).toHaveLength(3);

    act(() =>
      fake.emit({
        eventType: "UPDATE",
        new: {
          id: 1001,
          canonical_id: 1001,
          input_text: "חלב טרי 3%, 1 ליטר",
          quantity: 6,
          sort: 0,
        },
      }),
    );
    await waitFor(() =>
      expect(within(screen.getAllByTestId("shared-item")[0]!).getByRole("group")).toHaveTextContent(
        "6",
      ),
    );

    act(() => fake.emit({ eventType: "DELETE", old: { id: 77 } }));
    await waitFor(() => expect(screen.getAllByTestId("shared-item")).toHaveLength(2));

    // Replaying the same insert (a reconnect) does not duplicate the item.
    act(() =>
      fake.emit({
        eventType: "INSERT",
        new: { id: 1002, canonical_id: 1004, input_text: "רסק עגבניות", quantity: 1, sort: 1 },
      }),
    );
    expect(screen.getAllByTestId("shared-item")).toHaveLength(2);
  });

  it("writes straight to list_items, optimistically, as the signed-in user", async () => {
    const fake = await renderRealtime();
    const user = userEvent.setup();
    const first = screen.getAllByTestId("shared-item")[0]!;
    await user.click(within(first).getByRole("button", { name: /הוסיפי כמות/ }));
    expect(within(screen.getAllByTestId("shared-item")[0]!).getByRole("group")).toHaveTextContent(
      "3",
    );
    await waitFor(() =>
      expect(fake.writes).toContainEqual({ op: "update", value: { quantity: 3 }, id: 1001 }),
    );

    await user.click(
      within(screen.getAllByTestId("shared-item")[1]!).getByRole("button", { name: /הסרת/ }),
    );
    expect(screen.getAllByTestId("shared-item")).toHaveLength(1);
    await waitFor(() => expect(fake.writes).toContainEqual({ op: "delete", id: 1002 }));
  });

  it("rolls the optimistic change back when row-level security refuses the write", async () => {
    const fake = await renderRealtime({ failWrites: true });
    const user = userEvent.setup();
    await user.click(
      within(screen.getAllByTestId("shared-item")[0]!).getByRole("button", { name: /הסרת/ }),
    );
    expect(await screen.findByTestId("shared-message")).toHaveTextContent("החזרנו את הרשימה");
    expect(screen.getAllByTestId("shared-item")).toHaveLength(2);
    expect(fake.writes).toHaveLength(1);
  });
});

describe("share my own list", () => {
  it("creates the shared copy from the device's list once, then opens it", async () => {
    window.localStorage.setItem(
      "sc-list-v1",
      JSON.stringify({
        version: 1,
        name: "הקנייה השבועית",
        flexDefaults: {},
        updatedAt: null,
        items: [
          {
            id: "r1",
            inputText: "חלב",
            canonical: {
              canonical_id: 1001,
              display_name_he: "חלב טרי 3%, 1 ליטר",
              taxonomy_id: "dairy.milk",
              base_unit: "100ml",
            },
            candidates: [],
            quantity: 2,
            unit: null,
            isWeighed: false,
            flexLevel: "any_brand",
            allow: [],
            exactItemId: null,
            needsConfirmation: false,
            notFound: false,
            confidence: 1,
          },
        ],
      }),
    );
    const { resetListStoreForTests } = await import("@/state/list");
    resetListStoreForTests();
    const user = userEvent.setup();
    render(<SharedListScreen listId="mine" />);
    await user.click(await screen.findByRole("button", { name: "יצירת רשימה משותפת" }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/lists/1/share"));
    expect(readRegistry().ownedListId).toBe(1);
    const created = (await api("/me/lists/1", "GET")) as {
      items: Array<{ input_text: string; quantity: string }>;
    };
    expect(created.items).toMatchObject([{ input_text: "חלב טרי 3%, 1 ליטר", quantity: "2" }]);
  });

  it("has nothing to share from an empty list", async () => {
    const { resetListStoreForTests } = await import("@/state/list");
    resetListStoreForTests();
    render(<SharedListScreen listId="mine" />);
    expect(await screen.findByText(/הרשימה ריקה, ואין מה לשתף/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "יצירת רשימה משותפת" })).toBeNull();
  });
});
