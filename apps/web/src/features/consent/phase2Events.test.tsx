/**
 * Phase 2 events fired by the share and alert screens (issue #101): `list_shared` when an invite
 * is created, `share_accepted` on the accept page, `alert_created` on alert creation. The scan and
 * swap events are tested next to their screens. Payloads carry a role, a level or a source only.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import { AlertMe } from "@/features/alerts/AlertMe";
import { AcceptInvite } from "@/features/share/AcceptInvite";
import { ShareSheet } from "@/features/share/ShareSheet";
import { resetMeMock } from "@/mocks/handlers";
import { resetPhase2Mock } from "@/mocks/handlers.phase2";
import { server } from "@/mocks/node";

const track = vi.hoisted(() => vi.fn());
vi.mock("@/features/seo/track", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/seo/track")>()),
  trackEvent: track,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  resetMeMock();
  resetPhase2Mock();
  window.localStorage.clear();
  track.mockClear();
});

async function seedList() {
  await fetch(`${API_BASE_URL}/me/lists`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name: "הקנייה השבועית", is_recurring: false, items: [] }),
  });
}

describe("shared lists", () => {
  it("list_shared carries the role of the invite that was created, once per invite", async () => {
    await seedList();
    const user = userEvent.setup();
    render(<ShareSheet open onClose={() => {}} listId={1} />);
    await user.click(screen.getByRole("radio", { name: "צפייה בלבד" }));
    await user.click(screen.getByRole("button", { name: "יצירת קישור הזמנה" }));
    await screen.findByLabelText(/קישור הזמנה/);
    expect(track.mock.calls).toEqual([["list_shared", { role: "viewer" }]]);
    // The link itself never goes into an event.
    expect(JSON.stringify(track.mock.calls)).not.toMatch(/inv-|accept|http/);
  });

  it("no list_shared when the invite could not be created", async () => {
    server.use(
      http.post(`${API_BASE_URL}/me/lists/:id/share`, () => HttpResponse.json({}, { status: 403 })),
    );
    const user = userEvent.setup();
    render(<ShareSheet open onClose={() => {}} listId={1} />);
    await user.click(screen.getByRole("button", { name: "יצירת קישור הזמנה" }));
    await screen.findByRole("alert");
    expect(track).not.toHaveBeenCalled();
  });

  it("share_accepted is sent when joining worked, with no token and no list id", async () => {
    await seedList();
    const user = userEvent.setup();
    render(<AcceptInvite token="inv-1-abc" />);
    expect(track).not.toHaveBeenCalled(); // opening the link reports nothing
    await user.click(screen.getByRole("button", { name: "הצטרפות לרשימה" }));
    await waitFor(() => expect(track).toHaveBeenCalledTimes(1));
    expect(track.mock.calls[0]).toEqual(["share_accepted"]);
    expect(JSON.stringify(track.mock.calls)).not.toContain("inv-1-abc");
  });

  it("no share_accepted for an expired link", async () => {
    server.use(
      http.post(`${API_BASE_URL}/lists/accept/:token`, () =>
        HttpResponse.json({}, { status: 410 }),
      ),
    );
    const user = userEvent.setup();
    render(<AcceptInvite token="old-token" />);
    await user.click(screen.getByRole("button", { name: "הצטרפות לרשימה" }));
    await screen.findByTestId("accept-error");
    expect(track).not.toHaveBeenCalled();
  });
});

describe("price alerts", () => {
  it("alert_created carries the level and the source, never the product or the threshold", async () => {
    const user = userEvent.setup();
    render(<AlertMe canonicalId={1001} name="חלב טרי 3%" unitLabel="ל-100 מ״ל" />);
    await user.click(screen.getByRole("radio", { name: "תחליף קרוב" }));
    await user.type(screen.getByRole("textbox"), "0.55");
    await user.click(screen.getByRole("button", { name: /יצירת התראה|התריעי/ }));
    await waitFor(() => expect(track).toHaveBeenCalledTimes(1));
    expect(track.mock.calls[0]).toEqual([
      "alert_created",
      { source: "product", flex_level: "close" },
    ]);
    expect(JSON.stringify(track.mock.calls)).not.toMatch(/1001|0\.55|חלב/);
  });

  it("no alert_created when the API refuses the alert", async () => {
    server.use(
      http.post(`${API_BASE_URL}/me/alerts`, () => HttpResponse.json({}, { status: 402 })),
    );
    const user = userEvent.setup();
    render(<AlertMe canonicalId={1001} name="חלב טרי 3%" unitLabel="ל-100 מ״ל" />);
    await user.type(screen.getByRole("textbox"), "0.55");
    await user.click(screen.getByRole("button", { name: /יצירת התראה|התריעי/ }));
    await screen.findByText(/הגעת למספר ההתראות/);
    expect(track).not.toHaveBeenCalled();
  });
});
