/**
 * A poll of the shared list that started before the person's edit and ends after it (polling mode):
 * the older answer must not take the tick back off the screen.
 */
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import { resetMeMock } from "@/mocks/handlers";
import { resetPhase2Mock } from "@/mocks/handlers.phase2";
import { server } from "@/mocks/node";
import { resetQueueForTests } from "./offlineQueue";
import { SharedListScreen } from "./SharedListScreen";
import { POLL_MS } from "./useSharedList";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  vi.useRealTimers();
});
afterAll(() => server.close());
beforeEach(() => {
  resetMeMock();
  resetPhase2Mock();
  window.localStorage.clear();
  resetQueueForTests();
});

async function api(path: string, method: string, body?: unknown) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return res.json();
}

const box = (n: number) =>
  within(screen.getAllByTestId("shared-item")[n]!).getByRole("checkbox") as HTMLInputElement;

it("keeps a tick made while an older poll was still being answered", async () => {
  await api("/me/lists", "POST", {
    name: "x",
    is_recurring: false,
    items: [{ canonical_id: 1001, input_text: "חלב טרי", quantity: 1, flex_level: "any_brand" }],
  });
  const before = await api("/me/lists/1", "GET"); // the list as the slow poll will report it

  // Only the poll timer is faked: the rest of the test runs in real time.
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  const user = userEvent.setup();
  render(<SharedListScreen listId={1} />);
  await screen.findAllByTestId("shared-item");

  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  let polls = 0;
  server.use(
    http.get(`${API_BASE_URL}/me/lists/1`, async () => {
      polls += 1;
      await held;
      return HttpResponse.json(before);
    }),
  );
  act(() => {
    vi.advanceTimersByTime(POLL_MS); // the poll starts and waits for the server
  });
  // `waitFor` polls with setInterval, which is faked here; wait on the real clock instead.
  await act(async () => {
    await new Promise((r) => setTimeout(r, 100));
  });
  expect(polls).toBe(1);

  await user.click(box(0)); // the person ticks the item meanwhile
  await waitFor(() => expect(box(0)).toBeChecked());

  release(); // the older answer arrives last
  await act(async () => {
    await new Promise((r) => setTimeout(r, 50));
  });
  expect(box(0)).toBeChecked();
});
