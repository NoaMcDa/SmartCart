/**
 * Joining or leaving the beta while the person signs out (or another account takes over): the
 * answer of the request that was on its way belongs to the old session and must not be written as
 * the shared membership, where the next sign-in would read it as its own.
 */
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import { resetBetaMock, setBetaMockMember } from "@/mocks/handlers.beta";
import { server } from "@/mocks/node";
import { resetTrackingForTests } from "@/features/seo/track";
import { BetaJoin } from "./BetaJoin";
import { getBetaState, resetBetaState } from "./betaState";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({
    status: "signed-out",
    email: null,
    configured: false,
    openSignIn: () => {},
    signOut: async () => {},
  }),
}));

beforeAll(() => server.listen({ onUnhandledFrame: "bypass" }));
afterAll(() => server.close());
beforeEach(() => {
  localStorage.clear();
  resetTrackingForTests();
  resetBetaMock();
  resetBetaState();
});
afterEach(() => server.resetHandlers());

function hold() {
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { held, release };
}

/** Lets the answer that was held reach the component. */
const settle = () =>
  act(async () => {
    await new Promise((r) => setTimeout(r, 50));
  });

it("does not keep a membership that was joined for a session that signed out meanwhile", async () => {
  const { held, release } = hold();
  server.use(
    http.post(`${API_BASE_URL}/beta/join`, async () => {
      await held;
      return HttpResponse.json({ member: true, segment: "kosher" });
    }),
  );
  const user = userEvent.setup();
  render(<BetaJoin code="BETA-KOSHER" />);
  await user.click(await screen.findByTestId("beta-join"));
  await waitFor(() => expect(screen.getByTestId("beta-join")).toBeDisabled());

  act(() => resetBetaState()); // sign-out: the shared answer is forgotten
  release();
  await settle();
  expect(getBetaState()).toMatchObject({ status: "unknown", member: false, segment: null });
});

it("does not mark the next session as 'left' when the leave of the old one ends after the sign-out", async () => {
  setBetaMockMember("kosher");
  const { held, release } = hold();
  server.use(
    http.delete(`${API_BASE_URL}/me/beta`, async () => {
      await held;
      return HttpResponse.json({ ok: true, id: null });
    }),
  );
  const user = userEvent.setup();
  render(<BetaJoin code="BETA-KOSHER" />);
  await user.click(await screen.findByTestId("beta-leave"));
  await user.click(screen.getByTestId("beta-leave-confirm"));

  act(() => resetBetaState());
  release();
  await screen.findByTestId("beta-left"); // the request ended
  await settle();
  expect(getBetaState().status).toBe("unknown");
});

it("still records the answer when nothing changed meanwhile", async () => {
  const user = userEvent.setup();
  render(<BetaJoin code="BETA-KOSHER" />);
  await user.click(await screen.findByTestId("beta-join"));
  await screen.findByTestId("beta-member");
  expect(getBetaState()).toMatchObject({ status: "ready", member: true, segment: "kosher" });
});
