/**
 * Things that happen while `/parse-list` is being answered: typing goes on, or the dictation sheet
 * is closed. Neither may lose what the person typed or add rows they gave up on.
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, expect, it } from "vitest";
import { API_BASE_URL } from "@/api/config";
import { parseRow } from "@/mocks/parseRow";
import { server } from "@/mocks/node";
import { getListState, resetListStoreForTests } from "@/state/list";
import {
  FakeRecognizer,
  installFakeSpeech,
  removeFakeSpeech,
} from "../../../tests/unit/fakeSpeech";
import { ListBuilder } from "./ListBuilder";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  removeFakeSpeech();
});
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
});

/** A /parse-list that answers when `release()` is called, with one milk row. */
function holdParse() {
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  server.use(
    http.post(`${API_BASE_URL}/parse-list`, async () => {
      await held;
      return HttpResponse.json({ rows: [parseRow("חלב")] });
    }),
  );
  return release;
}

it("keeps what was typed while the first line was being read", async () => {
  const release = holdParse();
  const user = userEvent.setup();
  render(<ListBuilder />);
  const box = await screen.findByLabelText("הוסיפי פריטים לרשימה");
  await user.type(box, "חלב{Enter}");
  // The person goes on typing the next item while the list is being read.
  await user.type(box, "ביצים");
  release();
  await waitFor(() => expect(getListState().items).toHaveLength(1));
  await waitFor(() => expect(screen.queryByText("מזהה פריטים…")).not.toBeInTheDocument());
  expect(box).toHaveValue("ביצים");
});

it("clears the box when nothing was typed meanwhile", async () => {
  const release = holdParse();
  const user = userEvent.setup();
  render(<ListBuilder />);
  const box = await screen.findByLabelText("הוסיפי פריטים לרשימה");
  await user.type(box, "חלב{Enter}");
  release();
  await waitFor(() => expect(getListState().items).toHaveLength(1));
  expect(box).toHaveValue("");
});

it("a dictated list whose sheet was closed meanwhile adds no rows", async () => {
  installFakeSpeech();
  const release = holdParse();
  const user = userEvent.setup();
  render(<ListBuilder />);
  await user.click(await screen.findByTestId("voice-open"));
  await user.click(screen.getByTestId("voice-start"));
  act(() => {
    FakeRecognizer.last().begin();
    FakeRecognizer.last().hear({ text: "חלב" });
    FakeRecognizer.last().finish();
  });
  await user.click(screen.getByTestId("voice-add"));
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  release();
  // Give the answer time to land; the list must stay empty.
  await act(async () => {
    await new Promise((r) => setTimeout(r, 50));
  });
  expect(getListState().items).toHaveLength(0);
});
