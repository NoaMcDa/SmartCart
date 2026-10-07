import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { SupabaseClient } from "@supabase/supabase-js";
import { API_BASE_URL } from "@/api/config";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { setSupabaseForTests } from "@/features/auth/supabaseClient";
import { resetMeMock } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { resetListStoreForTests } from "@/state/list";
import { PrivacySection } from "./PrivacySection";
import { resetProfileCache } from "./profileState";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

/** A signed-in Supabase session, so the Privacy section calls the account routes. */
function signedIn() {
  const signOut = vi.fn(async () => ({ error: null }));
  const client = {
    auth: {
      getSession: vi.fn(async () => ({
        data: { session: { access_token: "jwt-1", user: { email: "noa@example.com" } } },
      })),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
      signOut,
    },
  } as unknown as SupabaseClient;
  setSupabaseForTests(client);
  return { signOut };
}

async function deleteEverything() {
  const user = userEvent.setup();
  render(
    <AuthProvider>
      <PrivacySection />
    </AuthProvider>,
  );
  await user.click(await screen.findByRole("button", { name: "מחקי את הנתונים שלי" }));
  await screen.findByText(/וגם מהחשבון/);
  await user.click(screen.getByTestId("confirm-delete"));
  return screen.findByTestId("delete-done");
}

beforeEach(() => {
  window.localStorage.clear();
  resetProfileCache();
  resetListStoreForTests();
  resetMeMock();
});
afterEach(() => setSupabaseForTests(undefined));

describe("account deletion in Profile (issues #30 and #55)", () => {
  it("calls DELETE /me with the token, confirms the account is gone, and shows no hosted-account notice", async () => {
    const { signOut } = signedIn();
    let auth: string | null = null;
    let calls = 0;
    server.use(
      http.delete(`${API_BASE_URL}/me`, ({ request }) => {
        calls += 1;
        auth = request.headers.get("authorization");
        return HttpResponse.json({ ok: true, id: null });
      }),
    );
    const done = await deleteEverything();
    expect(calls).toBe(1);
    expect(auth).toBe("Bearer jwt-1");
    expect(done).toHaveTextContent("החשבון עצמו, כולל כתובת האימייל, נמחק");
    expect(screen.queryByTestId("account-remains")).toBeNull();
    expect(signOut).toHaveBeenCalled();
  });

  it("shows the hosted-account notice only when DELETE /me fails, and still clears the device", async () => {
    signedIn();
    window.localStorage.setItem("sc-list-v1", "{}");
    server.use(http.delete(`${API_BASE_URL}/me`, () => HttpResponse.json({}, { status: 500 })));
    const done = await deleteEverything();
    expect(done).toHaveTextContent("הנתונים נמחקו מהמכשיר");
    expect(done).not.toHaveTextContent("כתובת האימייל, נמחק");
    expect(screen.getByTestId("account-remains")).toHaveTextContent("לא הצלחנו למחוק את החשבון");
    expect(window.localStorage.getItem("sc-list-v1")).toBeNull();
  });
});
