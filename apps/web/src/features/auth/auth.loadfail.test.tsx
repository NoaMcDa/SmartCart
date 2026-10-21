/**
 * Sign-in when things go wrong: the Supabase library cannot be fetched (offline, a flaky
 * connection) or a call to it fails. Nothing may wait forever for a session that is not coming,
 * the sheet must not stay busy, and a failed library load must be tried again on the next call.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { SupabaseClient } from "@supabase/supabase-js";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const loadSupabase = vi.hoisted(() => vi.fn());
vi.mock("./supabaseClient", () => ({
  isSupabaseConfigured: () => true,
  loadSupabase,
  getSupabase: () => null,
  setSupabaseForTests: () => {},
}));

import { AuthProvider, useAuth } from "./AuthProvider";
import { setApiToken } from "./apiAuth";

function Probe() {
  const a = useAuth();
  return (
    <div>
      <span data-testid="status">{a.status}</span>
      <button onClick={a.openSignIn}>open</button>
    </div>
  );
}

beforeEach(() => {
  setApiToken(null);
  loadSupabase.mockReset();
});
afterEach(() => vi.restoreAllMocks());

describe("when the Supabase library cannot be loaded", () => {
  it("the app is signed out instead of 'loading' for ever", async () => {
    loadSupabase.mockRejectedValue(new Error("ChunkLoadError"));
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    expect(screen.getByTestId("status")).toHaveTextContent("loading");
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("signed-out"));
  });

  it("the sheet says the code could not be sent, is not left busy, and works on the next try", async () => {
    // The provider's own load fails; then the sheet's first load fails; then the library is back.
    const otp = vi.fn(async () => ({ error: null }));
    const client = { auth: { signInWithOtp: otp } } as unknown as SupabaseClient;
    loadSupabase
      .mockRejectedValueOnce(new Error("ChunkLoadError"))
      .mockRejectedValueOnce(new Error("ChunkLoadError"))
      .mockResolvedValue(client);
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await user.click(screen.getByText("open"));
    const dialog = await screen.findByRole("dialog", { name: "התחברות" });
    await waitFor(() => expect(dialog).toContainElement(document.activeElement as HTMLElement));
    await user.type(screen.getByLabelText("אימייל"), "noa@example.com");
    await user.click(screen.getByRole("button", { name: "שליחת קוד" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("לא הצלחנו לשלוח קוד");
    expect(screen.getByRole("button", { name: "שליחת קוד" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "שליחת קוד" }));
    await waitFor(() => expect(otp).toHaveBeenCalledTimes(1));
    expect(await screen.findByLabelText("קוד אימות")).toBeInTheDocument();
  });

  it("a verification that throws is reported and does not leave the button busy; Arabic digits are read", async () => {
    const verifyOtp = vi
      .fn()
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValue({ error: new Error("wrong") });
    const client = {
      auth: {
        signInWithOtp: vi.fn(async () => ({ error: null })),
        verifyOtp,
        getSession: vi.fn(async () => ({ data: { session: null } })),
        onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
      },
    } as unknown as SupabaseClient;
    loadSupabase.mockResolvedValue(client);
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await user.click(screen.getByText("open"));
    const dialog = await screen.findByRole("dialog", { name: "התחברות" });
    await waitFor(() => expect(dialog).toContainElement(document.activeElement as HTMLElement));
    await user.type(screen.getByLabelText("אימייל"), "noa@example.com");
    await user.click(screen.getByRole("button", { name: "שליחת קוד" }));
    await user.type(await screen.findByLabelText("קוד אימות"), "١٢٣٤٥٦");
    await user.click(screen.getByRole("button", { name: "כניסה" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("לא הצלחנו לאמת את הקוד");
    expect(screen.getByRole("button", { name: "כניסה" })).toBeEnabled();
    expect(verifyOtp).toHaveBeenCalledWith({
      email: "noa@example.com",
      token: "123456",
      type: "email",
    });
    await user.click(screen.getByRole("button", { name: "כניסה" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("הקוד שגוי");
  });
});
