/**
 * Keyboard focus when a control leaves the page with its row: removing a row, answering the amber
 * question. Focus must land on something near, not fall back to the top of the page.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, expect, it } from "vitest";
import { parseRow } from "@/mocks/parseRow";
import { server } from "@/mocks/node";
import { listActions, resetListStoreForTests } from "@/state/list";
import { ListBuilder } from "./ListBuilder";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
});

const rows = () => screen.getAllByTestId("list-row");
const firstButton = (row: HTMLElement) => within(row).getAllByRole("button")[0]!;

it("removing a row moves focus to the next row's first control", async () => {
  listActions.add([parseRow("חלב"), parseRow("ביצים")]);
  const user = userEvent.setup();
  render(<ListBuilder />);
  const [first, second] = [rows()[0]!, rows()[1]!];
  await user.click(within(first).getByRole("button", { name: /הסרת/ }));
  await waitFor(() => expect(rows()).toHaveLength(1));
  await waitFor(() => expect(firstButton(second)).toHaveFocus());
});

it("removing the last row moves focus to the box where items are typed", async () => {
  listActions.add([parseRow("חלב")]);
  const user = userEvent.setup();
  render(<ListBuilder />);
  await user.click(within(rows()[0]!).getByRole("button", { name: /הסרת/ }));
  await waitFor(() => expect(screen.queryAllByTestId("list-row")).toHaveLength(0));
  await waitFor(() => expect(screen.getByRole("textbox")).toHaveFocus());
});

it("answering the amber question keeps focus in the row", async () => {
  listActions.add([parseRow("שמן זית")]);
  const user = userEvent.setup();
  render(<ListBuilder />);
  const row = rows()[0]!;
  await user.click(within(row).getByRole("button", { name: /כן/ }));
  await waitFor(() =>
    expect(within(row).queryByRole("group", { name: /אישור הפריט/ })).not.toBeInTheDocument(),
  );
  await waitFor(() => expect(firstButton(row)).toHaveFocus());
});

it("clearing the list moves focus to the typing box", async () => {
  listActions.add([parseRow("חלב"), parseRow("ביצים")]);
  const user = userEvent.setup();
  render(<ListBuilder />);
  await user.click(screen.getByRole("button", { name: "ניקוי הרשימה" }));
  await waitFor(() => expect(screen.getByRole("textbox")).toHaveFocus());
});
