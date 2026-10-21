/**
 * Cancelling a recipe read (issue #71): "ביטול" while the recipe is being read closes the sheet for
 * good. The answer that arrives later is dropped: the next time the sheet opens it is the empty
 * form, not the recipe of the attempt the person gave up on, and the button is not stuck on
 * "קוראים...".
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, expect, it } from "vitest";
import { API_BASE_URL } from "@/api/config";
import { ListBuilder } from "@/features/list/ListBuilder";
import { parseRow } from "@/mocks/parseRow";
import { server } from "@/mocks/node";
import { resetListStoreForTests } from "@/state/list";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
});

it("an answer that arrives after cancel does not reopen as the person's recipe", async () => {
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  let answered = false;
  server.use(
    http.post(`${API_BASE_URL}/parse-recipe`, async () => {
      await held;
      answered = true;
      return HttpResponse.json({
        title: "סלט",
        servings: 2,
        items: [parseRow("שמן זית")],
        unresolved: [],
      });
    }),
  );
  const user = userEvent.setup();
  render(<ListBuilder />);
  await user.click(await screen.findByTestId("recipe-open"));
  let dialog = screen.getByRole("dialog", { name: "מתכון לרשימה" });
  await waitFor(() => expect(dialog).toContainElement(document.activeElement as HTMLElement));
  await user.click(within(dialog).getByLabelText("המתכון או רשימת המצרכים"));
  await user.paste("שמן זית");
  await user.click(screen.getByTestId("recipe-read"));
  await user.click(within(dialog).getByRole("button", { name: "ביטול" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  release();
  await waitFor(() => expect(answered).toBe(true));

  await user.click(screen.getByTestId("recipe-open"));
  dialog = screen.getByRole("dialog", { name: "מתכון לרשימה" });
  expect(screen.queryByTestId("recipe-title")).not.toBeInTheDocument();
  expect(screen.getByTestId("recipe-read")).toBeEnabled();
  expect(screen.queryAllByTestId("list-row")).toHaveLength(0);
});
