/**
 * The account copy of the person's habits: only while signed in, merged both ways on sign-in, sent
 * after changes, never created for an empty document, and never touched for an anonymous visitor.
 */
import { render, waitFor } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { PersonalData } from "@/api/client";
import { setApiToken } from "@/features/auth/apiAuth";
import { mockPersonal, resetPersonalMock, seedPersonalMock } from "@/mocks/handlers.personal";
import { server } from "@/mocks/node";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import { PersonalSync } from "./PersonalSync";
import { EMPTY_DOC } from "./personalDoc";
import { getPersonal, personalActions, resetPersonalStoreForTests } from "./personalState";
import { COTTAGE, MILK, daysAgo, doc, regularDoc, signal, trip } from "./fixtures";

let authStatus: "signed-in" | "signed-out" = "signed-in";
vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({
    status: authStatus,
    email: "a@b.co",
    configured: true,
    openSignIn: () => {},
    signOut: async () => {},
  }),
}));

type Seen = { method: string; path: string };
const seen: Seen[] = [];
const toApi = (d: typeof EMPTY_DOC) => d as unknown as PersonalData;

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  server.events.removeAllListeners();
});
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetPersonalStoreForTests();
  resetPersonalMock();
  setApiToken("test-token");
  authStatus = "signed-in";
  seen.length = 0;
  server.events.on("request:start", ({ request }) => {
    seen.push({ method: request.method, path: new URL(request.url).pathname });
  });
});

const puts = () => seen.filter((s) => s.method === "PUT" && s.path === "/me/personal");
const personalCalls = () => seen.filter((s) => s.path === "/me/personal");

describe("anonymous", () => {
  it("makes no request at all, however much is recorded", async () => {
    authStatus = "signed-out";
    personalActions.recordTrip({ kind: "finished", lines: [{ ref: MILK, quantity: 1 }] });
    render(<PersonalSync />);
    personalActions.recordSignal("dairy.milk", "kept_brand");
    personalActions.setPrefs({ value_packs: true });
    await new Promise((r) => setTimeout(r, 1200)); // longer than the push delay
    expect(seen).toEqual([]);
    expect(mockPersonal()).toBeNull();
  });
});

describe("signed in", () => {
  it("sends the device's habits to an account that has none", async () => {
    personalActions.recordTrip({
      kind: "finished",
      lines: [
        { ref: MILK, quantity: 2 },
        { ref: COTTAGE, quantity: 1 },
      ],
    });
    render(<PersonalSync />);
    await waitFor(() => expect(mockPersonal()).not.toBeNull());
    expect(mockPersonal()!.trips).toHaveLength(1);
    expect(mockPersonal()!.refs).toHaveLength(2);
    expect(puts()).toHaveLength(1);
  });

  it("brings the account's habits to a device that has none, without writing them back", async () => {
    seedPersonalMock(toApi(regularDoc()));
    render(<PersonalSync />);
    await waitFor(() => expect(getPersonal().trips).toHaveLength(7));
    await new Promise((r) => setTimeout(r, 1200));
    expect(puts()).toEqual([]);
  });

  it("merges both sides when each has its own, and both end up with the union", async () => {
    const onAccount = doc({ trips: [trip(9, [[MILK]])], signals: [signal(5, "dairy.milk")] }, [
      MILK,
    ]);
    seedPersonalMock(toApi(onAccount));
    personalActions.recordTrip({ kind: "finished", lines: [{ ref: COTTAGE, quantity: 1 }] });
    render(<PersonalSync />);
    await waitFor(() => expect(mockPersonal()!.trips).toHaveLength(2));
    expect(getPersonal().trips).toHaveLength(2);
    expect(getPersonal().signals).toHaveLength(1);
    expect(mockPersonal()!.signals).toHaveLength(1);
    const refIds = (mockPersonal()!.refs ?? []).map((r) => r.canonical_id).sort();
    expect(refIds).toEqual([MILK.canonical_id, COTTAGE.canonical_id].sort());
  });

  it("never creates a document for an empty history with the default preferences", async () => {
    render(<PersonalSync />);
    await new Promise((r) => setTimeout(r, 1200));
    expect(puts()).toEqual([]);
    expect(mockPersonal()).toBeNull();
  });

  it("a preference change alone is worth storing", async () => {
    personalActions.setPrefs({ value_packs: true });
    render(<PersonalSync />);
    await waitFor(() => expect(mockPersonal()?.prefs?.value_packs).toBe(true));
  });

  it("the newer preferences win, in both directions", async () => {
    seedPersonalMock(
      toApi({ ...EMPTY_DOC, prefs: { learn: false, value_packs: true, updated_at: daysAgo(0) } }),
    );
    personalActions.setPrefs(
      { learn: true, value_packs: false },
      new Date(Date.now() - 5 * 86_400_000),
    );
    render(<PersonalSync />);
    await waitFor(() => expect(getPersonal().prefs.learn).toBe(false));
    expect(getPersonal().prefs.value_packs).toBe(true);
  });

  it("sends a change made after sign-in, once, after a pause", async () => {
    render(<PersonalSync />);
    await new Promise((r) => setTimeout(r, 100));
    personalActions.recordTrip({ kind: "finished", lines: [{ ref: MILK, quantity: 1 }] });
    personalActions.recordSignal("dairy.milk", "kept_brand");
    expect(puts()).toEqual([]); // not at once
    await waitFor(() => expect(puts()).toHaveLength(1), { timeout: 4000 });
    expect(mockPersonal()!.trips).toHaveLength(1);
    expect(mockPersonal()!.signals).toHaveLength(1);
    await new Promise((r) => setTimeout(r, 1200));
    expect(puts()).toHaveLength(1);
  });

  it("clearing what was learned empties the account copy as well", async () => {
    seedPersonalMock(toApi(regularDoc()));
    render(<PersonalSync />);
    await waitFor(() => expect(getPersonal().trips).toHaveLength(7));
    personalActions.clearLearned();
    await waitFor(() => expect(mockPersonal()!.trips).toEqual([]), { timeout: 4000 });
  });

  it("stays on the device when the API is down, and does not throw", async () => {
    server.use(
      http.get(`${API_BASE_URL}/me/personal`, () => HttpResponse.json({}, { status: 500 })),
    );
    personalActions.recordTrip({ kind: "finished", lines: [{ ref: MILK, quantity: 1 }] });
    render(<PersonalSync />);
    await new Promise((r) => setTimeout(r, 300));
    expect(getPersonal().trips).toHaveLength(1);
    expect(puts()).toEqual([]);
  });

  it("does not send what the account already holds", async () => {
    const same = regularDoc();
    seedPersonalMock(toApi(same));
    personalActions.replace(same);
    render(<PersonalSync />);
    await new Promise((r) => setTimeout(r, 1200));
    expect(personalCalls().every((c) => c.method === "GET")).toBe(true);
  });

  it("stops sending after sign-out", async () => {
    const view = render(<PersonalSync />);
    await new Promise((r) => setTimeout(r, 100));
    authStatus = "signed-out";
    view.rerender(<PersonalSync />);
    personalActions.recordTrip({ kind: "finished", lines: [{ ref: MILK, quantity: 1 }] });
    await new Promise((r) => setTimeout(r, 1200));
    expect(puts()).toEqual([]);
  });
});
