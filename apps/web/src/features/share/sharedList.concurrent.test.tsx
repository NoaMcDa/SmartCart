/**
 * Two people editing the same shared list in polling mode (no Supabase client: the mock and local
 * development). Before per-item writes every edit was a whole-list PUT built from the last poll, so
 * two edits within one poll interval overwrote each other. Now each edit is one write to its item,
 * carrying the version the person saw: nothing is lost, and when both changed the same field the
 * later write wins and the one who lost is told.
 *
 * "Another person" is a direct call to the mock API while this screen still shows the list as of
 * its last read, which is exactly the situation between two polls.
 */
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
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

type Row = { id: number; input_text: string; quantity: string; checked: boolean };

async function api(path: string, method: string, body?: unknown) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return res.status === 204 ? null : res.json();
}

const WEEK = {
  name: "הקנייה השבועית",
  is_recurring: false,
  items: [
    { canonical_id: 1001, input_text: "חלב טרי", quantity: 2 },
    { canonical_id: 1004, input_text: "רסק עגבניות", quantity: 1 },
    { canonical_id: 1008, input_text: "ביצים", quantity: 12 },
  ],
};
const MILK = 1001;
const PASTE = 1002;
const EGGS = 1003;

const saved = async () => (await api("/me/lists/1", "GET")).items as Row[];
const rows = () => screen.getAllByTestId("shared-item");
const box = (n: number) => within(rows()[n]!).getByRole("checkbox") as HTMLInputElement;
const qty = (n: number) => within(rows()[n]!).getByRole("group");
const plus = (n: number) => within(rows()[n]!).getByRole("button", { name: /הוסיפי כמות/ });

async function open() {
  await api("/me/lists", "POST", WEEK);
  const user = userEvent.setup();
  render(<SharedListScreen listId={1} />);
  await screen.findAllByTestId("shared-item");
  return user;
}

describe("two people editing within one poll interval", () => {
  it("different items: both edits are kept (the old whole-list PUT lost one)", async () => {
    const user = await open();
    // The other person ticks the eggs and changes the paste while this screen is not yet refreshed.
    await api(`/me/lists/1/items/${EGGS}`, "PATCH", { checked: true });
    await api(`/me/lists/1/items/${PASTE}`, "PATCH", { quantity: 4 });

    await user.click(box(0)); // this person ticks the milk from a stale view
    await waitFor(async () =>
      expect((await saved()).map((r) => r.checked)).toEqual([true, false, true]),
    );
    expect((await saved()).map((r) => r.quantity)).toEqual(["2", "4", "12"]); // theirs survived
    expect(screen.queryByTestId("shared-message")).toBeNull();
    // The rows keep their ids: nothing was deleted and recreated.
    expect((await saved()).map((r) => r.id)).toEqual([MILK, PASTE, EGGS]);
  });

  it("the same item, different fields: both changes stay and nobody is told anything", async () => {
    const user = await open();
    await api(`/me/lists/1/items/${MILK}`, "PATCH", { quantity: 5 }); // the other person

    await user.click(box(0)); // ticks the milk, believing the quantity is 2
    await waitFor(async () =>
      expect((await saved())[0]).toMatchObject({ checked: true, quantity: "5" }),
    );
    await waitFor(() => expect(qty(0)).toHaveTextContent("5")); // this screen shows theirs too
    expect(box(0)).toBeChecked();
    expect(screen.queryByTestId("shared-message")).toBeNull();
    expect(queuedEdits(1)).toEqual([]);
  });

  it("the same field of the same item: the later write wins, and the one who lost is told quietly", async () => {
    const user = await open();
    await api(`/me/lists/1/items/${MILK}`, "PATCH", { quantity: 7 }); // the other person got there first

    await user.click(plus(0)); // this person's 2 -> 3, made on a stale view
    expect(await screen.findByTestId("shared-message")).toHaveTextContent("מישהי אחרת שינתה");
    expect((await saved())[0]!.quantity).toBe("7"); // theirs is kept, ours did not overwrite it
    await waitFor(() => expect(qty(0)).toHaveTextContent("7"));
    expect(queuedEdits(1)).toEqual([]);
    expect(screen.queryByTestId("pending-sync")).toBeNull();
  });

  it("the other person wanted the same thing: nothing to say", async () => {
    const user = await open();
    await api(`/me/lists/1/items/${MILK}`, "PATCH", { checked: true });
    await user.click(box(0));
    await waitFor(() => expect(box(0)).toBeChecked());
    expect((await saved())[0]!.checked).toBe(true);
    expect(screen.queryByTestId("shared-message")).toBeNull();
  });

  it("removing an item the other person just changed keeps it, with the note", async () => {
    const user = await open();
    await api(`/me/lists/1/items/${EGGS}`, "PATCH", { quantity: 6 });
    await user.click(within(rows()[2]!).getByRole("button", { name: /הסרת/ }));
    expect(await screen.findByTestId("shared-message")).toHaveTextContent("מישהי אחרת שינתה");
    expect(await saved()).toHaveLength(3);
    await waitFor(() => expect(rows()).toHaveLength(3));
    expect(qty(2)).toHaveTextContent("6");
  });

  it("an item the other person removed disappears, and the tick on it says why it did not stick", async () => {
    const user = await open();
    await api(`/me/lists/1/items/${PASTE}`, "DELETE");
    await user.click(box(1));
    expect(await screen.findByTestId("shared-message")).toHaveTextContent("מישהי אחרת שינתה");
    await waitFor(() => expect(rows()).toHaveLength(2));
    expect((await saved()).map((r) => r.id)).toEqual([MILK, EGGS]);
  });

  it("an item added by the other person is not touched by this person's edit, and shows up", async () => {
    const user = await open();
    const theirs = (await api("/me/lists/1/items", "POST", {
      input_text: "גבינה",
      quantity: 1,
    })) as Row;
    await user.click(box(0));
    await waitFor(async () => expect((await saved())[0]!.checked).toBe(true));
    expect((await saved()).map((r) => r.id)).toContain(theirs.id); // a whole-list PUT deleted it
    expect(await saved()).toHaveLength(4);
  });

  it("two quick taps on the same item do not conflict with each other", async () => {
    const user = await open();
    await user.click(plus(1));
    await user.click(plus(1));
    await user.click(plus(1));
    await waitFor(async () => expect((await saved())[1]!.quantity).toBe("4"));
    await waitFor(() => expect(queuedEdits(1)).toEqual([]));
    expect(qty(1)).toHaveTextContent("4");
    expect(screen.queryByTestId("shared-message")).toBeNull();
  });

  it("the poll brings the other person's change in, and a tick after it is on the new version", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      await api("/me/lists", "POST", WEEK);
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<SharedListScreen listId={1} />);
      await screen.findAllByTestId("shared-item");
      await api(`/me/lists/1/items/${MILK}`, "PATCH", { quantity: 9 });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(4500);
      });
      await waitFor(() => expect(qty(0)).toHaveTextContent("9"));
      const bodies: unknown[] = [];
      server.events.on("request:start", async ({ request }) => {
        if (request.method === "PATCH") bodies.push(await request.clone().json());
      });
      await user.click(box(0));
      await waitFor(async () =>
        expect((await saved())[0]).toMatchObject({ checked: true, quantity: "9" }),
      );
      server.events.removeAllListeners();
      expect(bodies).toHaveLength(1); // one write, no conflict round trip
      expect(screen.queryByTestId("shared-message")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("edits made offline, replayed per item", () => {
  function setOnline(value: boolean) {
    vi.spyOn(navigator, "onLine", "get").mockReturnValue(value);
  }

  it("replays each edit on its own item and merges with what happened meanwhile", async () => {
    const user = await open();
    setOnline(false);
    await user.click(box(0)); // tick the milk
    await user.click(plus(1)); // paste 1 -> 2
    await user.click(within(rows()[2]!).getByRole("button", { name: /הסרת/ })); // remove the eggs
    expect(screen.getByTestId("pending-sync")).toHaveTextContent("3");
    expect(queuedEdits(1).map((e) => e.kind)).toEqual(["checked", "quantity", "remove"]);
    // What the queue remembers: the version and value the person saw.
    expect(queuedEdits(1)[0]).toMatchObject({ kind: "checked", from: false });
    expect(typeof (queuedEdits(1)[0] as { base?: string }).base).toBe("string");

    // Meanwhile the other person changed the milk's quantity and the paste's quantity.
    await api(`/me/lists/1/items/${MILK}`, "PATCH", { quantity: 3 });
    await api(`/me/lists/1/items/${PASTE}`, "PATCH", { quantity: 5 });

    setOnline(true);
    await act(async () => {
      window.dispatchEvent(new Event("online"));
    });
    await waitFor(() => expect(screen.queryByTestId("pending-sync")).toBeNull());
    const after = await saved();
    // The tick went through on top of their quantity; our paste quantity lost to theirs (same
    // field); the eggs were removed (nobody touched them).
    expect(after.map((r) => [r.id, r.checked, r.quantity])).toEqual([
      [MILK, true, "3"],
      [PASTE, false, "5"],
    ]);
    expect(await screen.findByTestId("shared-message")).toHaveTextContent("מישהי אחרת שינתה");
    expect(queuedEdits(1)).toEqual([]);
    await waitFor(() => expect(rows()).toHaveLength(2));
    expect(qty(1)).toHaveTextContent("5");
  });

  it("an item added offline and ticked offline is saved once, then ticked on its real row", async () => {
    const user = await open();
    await user.type(screen.getByLabelText("הוספת פריט לרשימה המשותפת"), "קוטג");
    await user.click(screen.getByRole("button", { name: "חיפוש" }));
    const hit = await screen.findByRole("button", { name: /הוספי: / });
    setOnline(false);
    await user.click(hit);
    await waitFor(() => expect(rows()).toHaveLength(4));
    await user.click(box(3));
    expect(queuedEdits(1).map((e) => e.kind)).toEqual(["add", "checked"]);

    setOnline(true);
    await act(async () => {
      window.dispatchEvent(new Event("online"));
    });
    await waitFor(() => expect(screen.queryByTestId("pending-sync")).toBeNull());
    const after = await saved();
    expect(after).toHaveLength(4);
    expect(after[3]).toMatchObject({ checked: true });
    expect(after[3]!.id).toBeGreaterThan(0);
    await waitFor(() => expect(box(3)).toBeChecked());
    expect(rows()).toHaveLength(4);
  });
});
