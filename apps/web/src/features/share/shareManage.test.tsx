import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import { resetMeMock } from "@/mocks/handlers";
import { resetPhase2Mock } from "@/mocks/handlers.phase2";
import { server } from "@/mocks/node";
import { ShareSheet } from "./ShareSheet";
import { SharedListScreen } from "./SharedListScreen";
import { setOwnedListId } from "./sharedLists";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  resetMeMock();
  resetPhase2Mock();
  window.localStorage.clear();
});

async function seedList() {
  await fetch(`${API_BASE_URL}/me/lists`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      name: "הקנייה השבועית",
      is_recurring: false,
      items: [
        {
          canonical_id: 1001,
          input_text: "חלב",
          quantity: 1,
          flex_level: "any_brand",
          confirmed: true,
        },
      ],
    }),
  });
}

describe("revoking an invite link", () => {
  it("cancels the link in the API and says it can no longer be used", async () => {
    await seedList();
    let revoked: string | null = null;
    server.use(
      http.delete(`${API_BASE_URL}/me/lists/:id/share/:token`, ({ params }) => {
        revoked = `${params.id}/${params.token}`;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    render(<ShareSheet open onClose={() => {}} listId={1} />);
    await user.click(screen.getByRole("button", { name: "יצירת קישור הזמנה" }));
    const link = (await screen.findByLabelText(/קישור הזמנה/)) as HTMLInputElement;
    const token = link.value.split("/").pop();
    await user.click(screen.getByRole("button", { name: "ביטול הקישור" }));
    expect(await screen.findByTestId("invite-revoked")).toHaveTextContent("הקישור בוטל");
    expect(revoked).toBe(`1/${token}`);
    expect(screen.queryByTestId("invite")).toBeNull();
    // A new link can be made again.
    expect(screen.getByRole("button", { name: "יצירת קישור הזמנה" })).toBeInTheDocument();
  });

  it("does not show an old link when the sheet is opened again (it may have been cancelled meanwhile)", async () => {
    await seedList();
    const user = userEvent.setup();
    const view = render(<ShareSheet open onClose={() => {}} listId={1} />);
    await user.click(screen.getByRole("button", { name: "יצירת קישור הזמנה" }));
    await screen.findByLabelText(/קישור הזמנה/);
    view.rerender(<ShareSheet open={false} onClose={() => {}} listId={1} />);
    expect(screen.queryByRole("dialog")).toBeNull();
    view.rerender(<ShareSheet open onClose={() => {}} listId={1} />);
    expect(screen.queryByTestId("invite")).toBeNull();
    expect(screen.getByRole("button", { name: "יצירת קישור הזמנה" })).toBeInTheDocument();
  });
});

describe("removing a member", () => {
  const members = [
    { user_id: "owner-1", role: "editor", accepted_at: "2026-10-01T00:00:00Z", is_owner: true },
    { user_id: "member-9", role: "viewer", accepted_at: "2026-10-02T00:00:00Z", is_owner: false },
    { user_id: null, role: "editor", accepted_at: null, is_owner: false },
  ];

  it("offers removal to the owner for joined members only, and refreshes the list", async () => {
    await seedList();
    setOwnedListId(1);
    let now = [...members];
    const removed: string[] = [];
    server.use(
      http.get(`${API_BASE_URL}/me/lists/:id/members`, () => HttpResponse.json(now)),
      http.delete(`${API_BASE_URL}/me/lists/:id/members/:member`, ({ params }) => {
        removed.push(String(params.member));
        now = now.filter((m) => m.user_id !== params.member);
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    render(<SharedListScreen listId={1} />);
    const rows = await screen.findAllByTestId("member");
    expect(rows).toHaveLength(3);
    expect(within(rows[0]!).queryByRole("button")).toBeNull(); // the owner
    expect(within(rows[2]!).queryByRole("button")).toBeNull(); // a pending invite
    await user.click(within(rows[1]!).getByRole("button", { name: /הסרת חברה מהרשימה/ }));
    await waitFor(() => expect(screen.getAllByTestId("member")).toHaveLength(2));
    expect(removed).toEqual(["member-9"]);
  });

  it("shows no removal to someone who is not the owner", async () => {
    await seedList();
    server.use(http.get(`${API_BASE_URL}/me/lists/:id/members`, () => HttpResponse.json(members)));
    render(<SharedListScreen listId={1} />);
    await screen.findAllByTestId("member");
    expect(screen.queryByRole("button", { name: /הסרת חברה/ })).toBeNull();
  });
});

describe("lists shared with me", () => {
  it("lists them next to my own and links each to its page", async () => {
    server.use(
      http.get(`${API_BASE_URL}/me/shared-lists`, () =>
        HttpResponse.json([
          {
            id: 31,
            name: "קניות של אמא",
            is_recurring: false,
            items: [],
            created_at: "2026-10-01T00:00:00Z",
            updated_at: "2026-10-01T00:00:00Z",
          },
        ]),
      ),
    );
    render(<SharedListScreen listId="mine" />);
    const card = await screen.findByTestId("shared-with-me");
    expect(within(card).getByRole("link", { name: "קניות של אמא" })).toHaveAttribute(
      "href",
      "/lists/31/share",
    );
  });

  it("shows nothing when none are shared", async () => {
    server.use(http.get(`${API_BASE_URL}/me/shared-lists`, () => HttpResponse.json([])));
    render(<SharedListScreen listId="mine" />);
    await screen.findByText(/הרשימה ריקה, ואין מה לשתף/);
    expect(screen.queryByTestId("shared-with-me")).toBeNull();
  });
});

describe("revoking a pending invite, removing a member (optimistic)", () => {
  const owner = {
    user_id: "owner-1",
    role: "editor",
    accepted_at: "2026-10-01T00:00:00Z",
    is_owner: true,
    share_id: null,
  };
  const pending = {
    user_id: null,
    role: "editor",
    accepted_at: null,
    is_owner: false,
    share_id: 7,
  };
  const joined = {
    user_id: "member-9",
    role: "viewer",
    accepted_at: "2026-10-02T00:00:00Z",
    is_owner: false,
    share_id: 8,
  };

  it("shows revoke on a pending invite only, calls DELETE shares/{share_id}, and drops it at once", async () => {
    await seedList();
    setOwnedListId(1);
    let now = [owner, pending, joined];
    const deleted: string[] = [];
    let release: () => void = () => undefined;
    const gate = new Promise<void>((r) => (release = r));
    server.use(
      http.get(`${API_BASE_URL}/me/lists/:id/members`, () => HttpResponse.json(now)),
      http.delete(`${API_BASE_URL}/me/lists/:id/shares/:shareId`, async ({ params }) => {
        deleted.push(`${params.id}/${params.shareId}`);
        await gate; // the answer is slow: the row must already be gone
        now = now.filter((m) => String(m.share_id) !== params.shareId);
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    render(<SharedListScreen listId={1} />);
    const rows = await screen.findAllByTestId("member");
    expect(rows).toHaveLength(3);
    expect(within(rows[0]!).queryByRole("button")).toBeNull();
    expect(within(rows[2]!).queryByRole("button", { name: /ביטול הזמנה/ })).toBeNull();
    await user.click(within(rows[1]!).getByRole("button", { name: /ביטול הזמנה ממתינה/ }));
    await waitFor(() => expect(screen.getAllByTestId("member")).toHaveLength(2));
    expect(screen.queryByText("הזמנה ממתינה")).toBeNull();
    release();
    await waitFor(() => expect(deleted).toEqual(["1/7"]));
    await waitFor(() => expect(screen.getAllByTestId("member")).toHaveLength(2));
  });

  it("puts the invite back in the same place and says so when the API refuses", async () => {
    await seedList();
    setOwnedListId(1);
    server.use(
      http.get(`${API_BASE_URL}/me/lists/:id/members`, () =>
        HttpResponse.json([owner, pending, joined]),
      ),
      http.delete(`${API_BASE_URL}/me/lists/:id/shares/:shareId`, () =>
        HttpResponse.json({}, { status: 500 }),
      ),
    );
    const user = userEvent.setup();
    render(<SharedListScreen listId={1} />);
    const rows = await screen.findAllByTestId("member");
    await user.click(within(rows[1]!).getByRole("button", { name: /ביטול הזמנה ממתינה/ }));
    expect(await screen.findByTestId("shared-message")).toHaveTextContent("ההזמנה לא בוטלה");
    const after = screen.getAllByTestId("member");
    expect(after).toHaveLength(3);
    expect(after[1]).toHaveTextContent("הזמנה ממתינה");
  });

  it("removes a joined member through the share row and rolls back when it fails", async () => {
    await seedList();
    setOwnedListId(1);
    const deleted: string[] = [];
    let fail = true;
    server.use(
      http.get(`${API_BASE_URL}/me/lists/:id/members`, () => HttpResponse.json([owner, joined])),
      http.delete(`${API_BASE_URL}/me/lists/:id/shares/:shareId`, ({ params }) => {
        deleted.push(String(params.shareId));
        return fail
          ? HttpResponse.json({}, { status: 500 })
          : new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    render(<SharedListScreen listId={1} />);
    let rows = await screen.findAllByTestId("member");
    await user.click(within(rows[1]!).getByRole("button", { name: /הסרת חברה מהרשימה/ }));
    expect(await screen.findByTestId("shared-message")).toHaveTextContent("החברה לא הוסרה");
    expect(screen.getAllByTestId("member")).toHaveLength(2);

    fail = false;
    rows = screen.getAllByTestId("member");
    await user.click(within(rows[1]!).getByRole("button", { name: /הסרת חברה מהרשימה/ }));
    await waitFor(() => expect(deleted).toEqual(["8", "8"]));
  });

  it("the mock API keeps the share id and removes the row it names", async () => {
    await seedList();
    const res = await fetch(`${API_BASE_URL}/me/lists/1/share`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ role: "viewer" }),
    });
    expect(res.status).toBe(201);
    const members = (await (await fetch(`${API_BASE_URL}/me/lists/1/members`)).json()) as Array<{
      share_id: number | null;
    }>;
    expect(members.map((m) => m.share_id)).toEqual([null, 1]);
    const del = (await fetch(`${API_BASE_URL}/me/lists/1/shares/1`, { method: "DELETE" })).status;
    expect(del).toBe(204);
    const again = (await fetch(`${API_BASE_URL}/me/lists/1/shares/1`, { method: "DELETE" })).status;
    expect(again).toBe(404);
    const after = (await (await fetch(`${API_BASE_URL}/me/lists/1/members`)).json()) as unknown[];
    expect(after).toHaveLength(1);
  });
});
