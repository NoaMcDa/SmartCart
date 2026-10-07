import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { SupabaseClient } from "@supabase/supabase-js";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthProvider";
import { getApiToken, setApiToken } from "./apiAuth";
import { isSupabaseConfigured, setSupabaseForTests } from "./supabaseClient";

type Listener = (event: string, session: unknown) => void;

function fakeSupabase(initialSession: unknown = null) {
  let listener: Listener = () => undefined;
  const auth = {
    getSession: vi.fn(async () => ({ data: { session: initialSession } })),
    onAuthStateChange: vi.fn((cb: Listener) => {
      listener = cb;
      return { data: { subscription: { unsubscribe: vi.fn() } } };
    }),
    signInWithOtp: vi.fn(async () => ({ error: null })),
    verifyOtp: vi.fn(async () => {
      listener("SIGNED_IN", { access_token: "jwt-123", user: { email: "noa@example.com" } });
      return { error: null };
    }),
    signOut: vi.fn(async () => {
      listener("SIGNED_OUT", null);
      return { error: null };
    }),
  };
  return { client: { auth } as unknown as SupabaseClient, auth };
}

function Probe() {
  const a = useAuth();
  return (
    <div>
      <span data-testid="status">{a.status}</span>
      <span data-testid="email">{a.email ?? ""}</span>
      <button onClick={a.openSignIn}>open</button>
      <button onClick={() => void a.signOut()}>out</button>
    </div>
  );
}

beforeEach(() => setApiToken(null));
afterEach(() => setSupabaseForTests(undefined));

describe("auth", () => {
  it("without Supabase variables it is signed out, with no token and no loading state", () => {
    setSupabaseForTests(null);
    expect(isSupabaseConfigured()).toBe(false);
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    expect(screen.getByTestId("status")).toHaveTextContent("signed-out");
    expect(getApiToken()).toBeNull();
  });

  it("email OTP: send the code, verify it, session token goes to the API wrapper, then sign out", async () => {
    const { client, auth } = fakeSupabase();
    setSupabaseForTests(client);
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("signed-out"));

    await user.click(screen.getByText("open"));
    const dialog = await screen.findByRole("dialog", { name: "התחברות" });
    // Bad email is rejected before any request.
    await user.type(screen.getByLabelText("אימייל"), "not-an-email");
    await user.click(screen.getByRole("button", { name: "שליחת קוד" }));
    expect(screen.getByRole("alert")).toHaveTextContent("לא נראית תקינה");
    expect(auth.signInWithOtp).not.toHaveBeenCalled();

    await user.clear(screen.getByLabelText("אימייל"));
    await user.type(screen.getByLabelText("אימייל"), "noa@example.com");
    await user.click(screen.getByRole("button", { name: "שליחת קוד" }));
    expect(auth.signInWithOtp).toHaveBeenCalledWith({
      email: "noa@example.com",
      options: { shouldCreateUser: true },
    });

    await user.type(await screen.findByLabelText("קוד אימות"), "123456");
    await user.click(screen.getByRole("button", { name: "כניסה" }));
    expect(auth.verifyOtp).toHaveBeenCalledWith({
      email: "noa@example.com",
      token: "123456",
      type: "email",
    });
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("signed-in"));
    expect(screen.getByTestId("email")).toHaveTextContent("noa@example.com");
    expect(getApiToken()).toBe("jwt-123");
    expect(dialog).not.toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByText("out"));
    });
    expect(auth.signOut).toHaveBeenCalled();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("signed-out"));
    expect(getApiToken()).toBeNull();
  });

  it("restores an existing session on load", async () => {
    const { client } = fakeSupabase({ access_token: "stored-jwt", user: { email: "a@b.co" } });
    setSupabaseForTests(client);
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("signed-in"));
    expect(getApiToken()).toBe("stored-jwt");
  });

  it("shows an error when the code is wrong", async () => {
    const { client, auth } = fakeSupabase();
    auth.verifyOtp.mockResolvedValueOnce({ error: { message: "bad" } } as never);
    setSupabaseForTests(client);
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await user.click(screen.getByText("open"));
    await user.type(await screen.findByLabelText("אימייל"), "noa@example.com");
    await user.click(screen.getByRole("button", { name: "שליחת קוד" }));
    await user.type(await screen.findByLabelText("קוד אימות"), "000000");
    await user.click(screen.getByRole("button", { name: "כניסה" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("הקוד שגוי");
    expect(getApiToken()).toBeNull();
  });
});
