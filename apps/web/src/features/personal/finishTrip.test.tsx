/**
 * "סיימתי" in store mode feeds "my usual" and "buy again" (phase 3): the ticked lines are a
 * finished trip, nothing ticked is only a list, and nothing is recorded while learning is off.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { clearLastResultCache } from "@/features/split/lastResult";
import { StoreMode } from "@/features/store/StoreMode";
import { buildSession, clearSession, startSession } from "@/features/store/session";
import { lastResultFixture, weeklyListState } from "@/mocks/lastResult";
import { server } from "@/mocks/node";
import { clearComparisonCache } from "@/state/comparison";
import { resetListStoreForTests } from "@/state/list";
import { getPersonal, personalActions, resetPersonalStoreForTests } from "./personalState";

vi.mock("@/features/seo/track", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/seo/track")>()),
  trackEvent: vi.fn(),
}));
const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(""),
}));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const result = lastResultFixture();
const rami = result.compare!.stores.find((s) => s.store_id === 101)!;

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem("sc-list-v1", JSON.stringify(weeklyListState()));
  resetListStoreForTests();
  resetPersonalStoreForTests();
  clearComparisonCache();
  clearLastResultCache();
  clearSession();
  push.mockClear();
  startSession(buildSession(rami, result, { overhead: 0 }));
});

async function finish(user: ReturnType<typeof userEvent.setup>, tick: number) {
  render(<StoreMode />);
  const boxes = await screen.findAllByRole("checkbox");
  for (const box of boxes.slice(0, tick)) await user.click(box);
  await user.click(screen.getByTestId("finish"));
  await user.click(screen.getByTestId("finish-confirm"));
}

describe("finishing a shop", () => {
  it("records what was ticked as a finished trip, with the quantities, on the device", async () => {
    await finish(userEvent.setup(), 2);
    const trips = getPersonal().trips;
    expect(trips).toHaveLength(1);
    expect(trips[0]!.kind).toBe("finished");
    expect(trips[0]!.lines).toHaveLength(2);
    for (const line of trips[0]!.lines) expect(line.quantity).toBeGreaterThan(0);
    // The products came from the list: their names are kept to draw "my usual" later.
    expect(getPersonal().refs).toHaveLength(2);
    expect(push).toHaveBeenCalledWith("/");
  });

  it("with nothing ticked, records the plan as a list, never as a finished trip", async () => {
    await finish(userEvent.setup(), 0);
    expect(getPersonal().trips).toHaveLength(1);
    expect(getPersonal().trips[0]!.kind).toBe("list");
    expect(getPersonal().trips[0]!.lines).toHaveLength(8);
  });

  it("records nothing while learning is off, and still finishes", async () => {
    personalActions.setPrefs({ learn: false });
    await finish(userEvent.setup(), 3);
    expect(getPersonal().trips).toEqual([]);
    expect(push).toHaveBeenCalledWith("/");
  });
});
