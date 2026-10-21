/**
 * Answers that arrive after the person moved on (issue #39): the camera permission prompt that is
 * answered after "עצירת המצלמה" or after leaving the screen must not turn the camera on, and a slow
 * lookup must not replace the result of a newer one.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import { API_BASE_URL } from "@/api/config";
import { server } from "@/mocks/node";
import { resetListStoreForTests } from "@/state/list";
import { ScanScreen } from "./ScanScreen";

const FOUND = "5901234123457";
const OTHER = "5901234123006"; // valid EAN-13 (check digit 6)

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  Object.defineProperty(navigator, "mediaDevices", { value: undefined, configurable: true });
});
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
});

/** A camera whose permission prompt is answered when `allow()` is called. */
function pendingCamera() {
  const stopTrack = vi.fn();
  const stream = { getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream;
  let allow: () => void = () => {};
  const getUserMedia = vi.fn(
    () =>
      new Promise<MediaStream>((resolve) => {
        allow = () => resolve(stream);
      }),
  );
  Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia }, configurable: true });
  return { stopTrack, getUserMedia, allow: () => allow() };
}

async function renderScreen() {
  const user = userEvent.setup();
  const view = render(<ScanScreen />);
  await waitFor(() => expect(screen.getByTestId("scan-store")).toHaveValue("103"));
  return { user, view };
}

it("a permission granted after 'stop the camera' is released at once, not shown", async () => {
  const cam = pendingCamera();
  const { user } = await renderScreen();
  await user.click(screen.getByRole("button", { name: "הפעלת המצלמה" }));
  expect(await screen.findByTestId("scan-video")).toBeInTheDocument(); // "opening the camera"
  await user.click(screen.getByRole("button", { name: "עצירת המצלמה" }));
  expect(screen.queryByTestId("scan-video")).not.toBeInTheDocument();

  cam.allow(); // the person taps "allow" on the browser prompt only now
  await waitFor(() => expect(cam.stopTrack).toHaveBeenCalled());
  expect(screen.queryByTestId("scan-video")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "הפעלת המצלמה" })).toBeEnabled();
});

it("a permission granted after leaving the screen does not leave the camera on", async () => {
  const cam = pendingCamera();
  const { user, view } = await renderScreen();
  await user.click(screen.getByRole("button", { name: "הפעלת המצלמה" }));
  await screen.findByTestId("scan-video");
  view.unmount();
  cam.allow();
  await waitFor(() => expect(cam.stopTrack).toHaveBeenCalled());
});

it("a slow lookup does not replace the result of the code typed after it", async () => {
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  server.use(
    http.get(`${API_BASE_URL}/items/barcode/${FOUND}`, async () => {
      await held;
      return HttpResponse.json({
        barcode: FOUND,
        found: false,
      });
    }),
    http.get(`${API_BASE_URL}/items/barcode/${OTHER}`, () =>
      HttpResponse.json({ barcode: OTHER, found: false }),
    ),
  );
  const { user } = await renderScreen();
  const field = screen.getByRole("textbox", { name: /ברקוד \(13 ספרות/ });
  await user.type(field, FOUND);
  await user.click(screen.getByRole("button", { name: "חיפוש" }));
  await user.clear(field);
  await user.type(field, OTHER);
  await user.click(screen.getByRole("button", { name: "חיפוש" }));
  const state = await screen.findByTestId("scan-notfound");
  expect(state).toHaveTextContent(OTHER);

  release(); // the first answer arrives last
  await new Promise((r) => setTimeout(r, 50));
  expect(screen.getByTestId("scan-notfound")).toHaveTextContent(OTHER);
  expect(screen.getByTestId("scan-notfound")).not.toHaveTextContent(FOUND);
});
