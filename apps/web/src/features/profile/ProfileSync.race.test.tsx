/**
 * Signing out while the first upload of a profile is still in flight, then signing in again: the
 * old attempt must not mark the new session as loaded. Otherwise the first local change of the new
 * session is pushed before that account's stored profile has been read, over the top of it.
 */
import { act, render } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { API_BASE_URL } from "@/api/config";
import { resetMeMock } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { ProfileSync } from "./ProfileSync";
import { resetProfileCache, updateProfile } from "./profileState";

const auth = vi.hoisted(() => ({ status: "signed-in" as "signed-in" | "signed-out" }));
vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({
    status: auth.status,
    email: "a@b.co",
    configured: true,
    openSignIn: () => {},
    signOut: async () => {},
  }),
}));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  vi.useRealTimers();
});
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetProfileCache();
  resetMeMock();
  auth.status = "signed-in";
});

it("an upload that finishes after sign-out does not mark the next sign-in as loaded", async () => {
  let releaseFirst: () => void = () => {};
  const held = new Promise<void>((resolve) => {
    releaseFirst = resolve;
  });
  let puts = 0;
  let secondGet: () => void = () => {};
  const secondGetHeld = new Promise<void>((resolve) => {
    secondGet = resolve;
  });
  let gets = 0;
  server.use(
    http.get(`${API_BASE_URL}/me/profile`, async () => {
      gets += 1;
      if (gets === 2) await secondGetHeld; // the second account's profile is slow to arrive
      return HttpResponse.json({ exists: false });
    }),
    http.put(`${API_BASE_URL}/me/profile`, async () => {
      puts += 1;
      if (puts === 1) await held; // the first upload hangs
      return HttpResponse.json({ exists: true });
    }),
  );
  // A new element each time: React skips re-rendering the very same element object.
  const tree = () => (
    <ThemeProvider>
      <ProfileSync />
    </ThemeProvider>
  );
  const view = render(tree());
  await vi.waitFor(() => expect(puts).toBe(1)); // account A's first upload is on its way

  auth.status = "signed-out";
  view.rerender(tree());
  auth.status = "signed-in"; // account B signs in; its stored profile has not arrived yet
  view.rerender(tree());
  await vi.waitFor(() => expect(gets).toBe(2));

  await act(async () => {
    releaseFirst(); // A's upload finally ends
    await new Promise((r) => setTimeout(r, 50));
  });
  // A local change now must wait for B's own profile instead of being uploaded at once.
  act(() => {
    updateProfile({ radiusKm: 9 });
  });
  await new Promise((r) => setTimeout(r, 1200)); // longer than the 800 ms save pause
  expect(puts).toBe(1);

  await act(async () => {
    secondGet();
    await new Promise((r) => setTimeout(r, 50));
  });
});
