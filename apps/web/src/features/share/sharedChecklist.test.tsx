/**
 * Per-item "checked" on a shared list, and edits made without a connection (issue #101): the
 * checkbox is saved through the list's `checked` field, other members see it, and an edit that
 * cannot be sent waits in localStorage with "ממתין לסנכרון" until the connection is back.
 */
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
import { queuedEdits, resetQueueForTests, SHARED_QUEUE_KEY } from "./offlineQueue";
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

type SavedList = { items: Array<{ input_text: string; quantity: string; checked: boolean }> };

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
    { canonical_id: 1001, input_text: "חלב טרי", quantity: 2, flex_level: "any_brand" },
    { canonical_id: 1004, input_text: "רסק עגבניות", quantity: 1, flex_level: "close" },
  ],
};

const saved = () => api("/me/lists/1", "GET") as Promise<SavedList>;
const box = (n: number) =>
  within(screen.getAllByTestId("shared-item")[n]!).getByRole("checkbox") as HTMLInputElement;

function setOnline(value: boolean) {
  vi.spyOn(navigator, "onLine", "get").mockReturnValue(value);
}

describe("a checkbox per item, saved on the list item", () => {
  it("ticks an item, strikes it through, saves `checked` and shows it again on the next visit", async () => {
    await api("/me/lists", "POST", WEEK);
    const user = userEvent.setup();
    const first = render(<SharedListScreen listId={1} />);
    await screen.findAllByTestId("shared-item");
    expect(box(0)).not.toBeChecked();
    expect(box(0)).toHaveAccessibleName("סימון חלב טרי כנאסף");

    await user.click(box(0));
    expect(box(0)).toBeChecked(); // at once, before the save returns
    expect(screen.getAllByTestId("shared-item")[0]).toHaveAttribute("data-checked", "true");
    expect(screen.getAllByTestId("shared-item")[1]).toHaveAttribute("data-checked", "false");
    await waitFor(async () =>
      expect((await saved()).items.map((i) => i.checked)).toEqual([true, false]),
    );
    expect(screen.queryByTestId("pending-sync")).toBeNull();

    first.unmount();
    render(<SharedListScreen listId={1} />);
    await screen.findAllByTestId("shared-item");
    expect(box(0)).toBeChecked();
    expect(box(1)).not.toBeChecked();

    await user.click(box(0));
    await waitFor(async () => expect((await saved()).items[0]!.checked).toBe(false));
  });

  it("another member's tick arrives through the poll without a reload", async () => {
    await api("/me/lists", "POST", WEEK);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      render(<SharedListScreen listId={1} />);
      await screen.findAllByTestId("shared-item");
      expect(box(1)).not.toBeChecked();
      const list = (await saved()) as SavedList & { name: string };
      await api("/me/lists/1", "PUT", {
        name: list.name,
        is_recurring: false,
        items: list.items.map((i, n) => ({
          canonical_id: n === 0 ? 1001 : 1004,
          input_text: i.input_text,
          quantity: Number(i.quantity),
          checked: n === 1,
        })),
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(4500);
      });
      await waitFor(() => expect(box(1)).toBeChecked());
    } finally {
      vi.useRealTimers();
    }
  });

  it("a refused save puts the checkbox back and says so", async () => {
    await api("/me/lists", "POST", WEEK);
    server.use(
      http.put(`${API_BASE_URL}/me/lists/:id`, () => HttpResponse.json({}, { status: 500 })),
    );
    const user = userEvent.setup();
    render(<SharedListScreen listId={1} />);
    await screen.findAllByTestId("shared-item");
    await user.click(box(0));
    expect(await screen.findByTestId("shared-message")).toHaveTextContent("החזרנו את הרשימה");
    expect(box(0)).not.toBeChecked();
    expect(screen.queryByTestId("pending-sync")).toBeNull(); // a refusal is not queued
    expect(queuedEdits(1)).toEqual([]);
  });
});

describe("edits without a connection", () => {
  it("keeps a failed send on screen, shows ממתין לסנכרון, and sends it when the browser is online again", async () => {
    await api("/me/lists", "POST", WEEK);
    const user = userEvent.setup();
    render(<SharedListScreen listId={1} />);
    await screen.findAllByTestId("shared-item");

    // The connection drops: the PUT cannot reach the server.
    server.use(http.put(`${API_BASE_URL}/me/lists/:id`, () => HttpResponse.error()));
    await user.click(box(0));
    await user.click(
      within(screen.getAllByTestId("shared-item")[1]!).getByRole("button", { name: /הוסיפי כמות/ }),
    );
    expect(await screen.findByTestId("pending-sync")).toHaveTextContent("ממתין לסנכרון");
    expect(screen.getByTestId("pending-sync")).toHaveTextContent("2");
    expect(box(0)).toBeChecked(); // still what the person did
    expect(within(screen.getAllByTestId("shared-item")[1]!).getByRole("group")).toHaveTextContent(
      "2",
    );
    expect(screen.queryByTestId("shared-message")).toBeNull(); // not an error
    expect(JSON.parse(window.localStorage.getItem(SHARED_QUEUE_KEY)!).lists["1"]).toHaveLength(2);
    expect((await saved()).items.map((i) => i.checked)).toEqual([false, false]); // server unchanged

    // Back online.
    server.resetHandlers();
    await act(async () => {
      window.dispatchEvent(new Event("online"));
    });
    await waitFor(() => expect(screen.queryByTestId("pending-sync")).toBeNull());
    const after = await saved();
    expect(after.items.map((i) => [i.checked, i.quantity])).toEqual([
      [true, "2"],
      [false, "2"],
    ]);
    expect(queuedEdits(1)).toEqual([]);
    expect(box(0)).toBeChecked();
  });

  it("does not even try while the browser says it is offline, and replays in order afterwards", async () => {
    await api("/me/lists", "POST", WEEK);
    const user = userEvent.setup();
    render(<SharedListScreen listId={1} />);
    await screen.findAllByTestId("shared-item");

    let puts = 0;
    const count = ({ request }: { request: Request }) => {
      if (request.method === "PUT") puts += 1;
    };
    server.events.on("request:start", count);
    setOnline(false);
    await user.click(box(1));
    await user.click(box(1)); // ticked and unticked again: the queue holds the last value only
    await user.click(box(0));
    expect(puts).toBe(0);
    expect(screen.getByTestId("pending-sync")).toHaveTextContent("2");

    setOnline(true);
    await act(async () => {
      window.dispatchEvent(new Event("online"));
    });
    await waitFor(() => expect(screen.queryByTestId("pending-sync")).toBeNull());
    expect(puts).toBe(1); // one PUT for the whole queue
    expect((await saved()).items.map((i) => i.checked)).toEqual([true, false]);
    server.events.removeListener("request:start", count);
  });

  it("an item added offline appears at once and is on the server after the replay", async () => {
    await api("/me/lists", "POST", WEEK);
    const user = userEvent.setup();
    render(<SharedListScreen listId={1} />);
    await screen.findAllByTestId("shared-item");

    // Search works (it is a read), the save does not: the connection drops after the search.
    await user.type(screen.getByLabelText("הוספת פריט לרשימה המשותפת"), "ביצים");
    await user.click(screen.getByRole("button", { name: "חיפוש" }));
    const hit = await screen.findByRole("button", { name: /הוספי: / });
    server.use(http.put(`${API_BASE_URL}/me/lists/:id`, () => HttpResponse.error()));
    await user.click(hit);
    expect(await screen.findByTestId("pending-sync")).toBeInTheDocument();
    expect(screen.getAllByTestId("shared-item")).toHaveLength(3);
    expect(queuedEdits(1)).toMatchObject([{ kind: "add", quantity: 1 }]);
    expect((await saved()).items).toHaveLength(2);

    server.resetHandlers();
    await act(async () => {
      window.dispatchEvent(new Event("online"));
    });
    await waitFor(() => expect(screen.queryByTestId("pending-sync")).toBeNull());
    expect((await saved()).items).toHaveLength(3);
    expect(screen.getAllByTestId("shared-item")).toHaveLength(3);
  });

  it("a queue left from an earlier visit is sent as soon as the list has loaded", async () => {
    await api("/me/lists", "POST", WEEK);
    window.localStorage.setItem(
      SHARED_QUEUE_KEY,
      JSON.stringify({
        version: 1,
        lists: { "1": [{ kind: "checked", itemId: 1002, checked: true }] },
      }),
    );
    resetQueueForTests();
    render(<SharedListScreen listId={1} />);
    await screen.findAllByTestId("shared-item");
    await waitFor(async () => expect((await saved()).items[1]!.checked).toBe(true));
    await waitFor(() => expect(screen.queryByTestId("pending-sync")).toBeNull());
    expect(box(1)).toBeChecked();
  });

  it("an edit to an item somebody else removed meanwhile is dropped quietly", async () => {
    await api("/me/lists", "POST", WEEK);
    window.localStorage.setItem(
      SHARED_QUEUE_KEY,
      JSON.stringify({
        version: 1,
        lists: { "1": [{ kind: "quantity", itemId: 999, quantity: 7 }] },
      }),
    );
    resetQueueForTests();
    render(<SharedListScreen listId={1} />);
    await screen.findAllByTestId("shared-item");
    await waitFor(() => expect(queuedEdits(1)).toEqual([]));
    expect((await saved()).items.map((i) => i.quantity)).toEqual(["2", "1"]);
  });
});

describe("realtime mode", () => {
  function fakeSupabase(opts: { networkDown?: boolean } = {}) {
    let handler: (p: { eventType: string; new?: Record<string, unknown> }) => void = () =>
      undefined;
    const writes: Array<{ op: string; value?: unknown; id?: unknown }> = [];
    const state = { down: opts.networkDown ?? false };
    const channel = {
      on: (_t: string, _f: unknown, cb: typeof handler) => {
        handler = cb;
        return channel;
      },
      subscribe: (cb: (s: string) => void) => {
        cb("SUBSCRIBED");
        return channel;
      },
    };
    const result = () =>
      state.down ? { error: { message: "TypeError: Failed to fetch" } } : { error: null };
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
            if (!state.down) writes.push({ op: "update", value, id });
            return result();
          },
        }),
        delete: () => ({
          eq: async (_c: string, id: unknown) => {
            if (!state.down) writes.push({ op: "delete", id });
            return result();
          },
        }),
      })),
    };
    return {
      client: client as unknown as SupabaseClient,
      emit: (p: { eventType: string; new?: Record<string, unknown> }) => handler(p),
      writes,
      state,
    };
  }

  async function renderRealtime(opts?: { networkDown?: boolean }) {
    await api("/me/lists", "POST", WEEK);
    const fake = fakeSupabase(opts);
    setSupabaseForTests(fake.client);
    render(
      <AuthProvider>
        <SharedListScreen listId={1} />
      </AuthProvider>,
    );
    await screen.findAllByTestId("shared-item");
    await waitFor(() => expect(screen.getByTestId("sync-state")).toHaveTextContent("בזמן אמת"));
    return fake;
  }

  it("writes `checked` to list_items and shows a tick another member made", async () => {
    const fake = await renderRealtime();
    const user = userEvent.setup();
    await user.click(box(0));
    await waitFor(() =>
      expect(fake.writes).toContainEqual({ op: "update", value: { checked: true }, id: 1001 }),
    );
    act(() =>
      fake.emit({
        eventType: "UPDATE",
        new: {
          id: 1002,
          canonical_id: 1004,
          input_text: "רסק עגבניות",
          quantity: 1,
          sort: 1,
          checked: true,
        },
      }),
    );
    await waitFor(() => expect(box(1)).toBeChecked());
  });

  it("queues a write that failed for lack of a connection and replays it on reconnect", async () => {
    const fake = await renderRealtime({ networkDown: true });
    const user = userEvent.setup();
    await user.click(box(0));
    expect(await screen.findByTestId("pending-sync")).toBeInTheDocument();
    expect(box(0)).toBeChecked();
    expect(queuedEdits(1)).toEqual([{ kind: "checked", itemId: 1001, checked: true }]);

    fake.state.down = false;
    await act(async () => {
      window.dispatchEvent(new Event("online"));
    });
    await waitFor(() => expect(screen.queryByTestId("pending-sync")).toBeNull());
    expect(fake.writes).toContainEqual({ op: "update", value: { checked: true }, id: 1001 });
    expect(queuedEdits(1)).toEqual([]);
  });
});
