/**
 * Cancelling a photo before its request starts (#61, #68): "ביטול" or closing the sheet while the
 * photo is still being prepared sends nothing, reports nothing and adds nothing. The preparation is
 * held open here so the cancel lands before the upload, as on a slow phone.
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import { resetImageConsentForTests, setImageConsent } from "@/features/consent/imageConsent";
import { ListBuilder } from "@/features/list/ListBuilder";
import { trackEvent } from "@/features/seo/track";
import { server } from "@/mocks/node";
import { getListState, resetListStoreForTests } from "@/state/list";

let release: () => void = () => {};

vi.mock("./imageFile", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./imageFile")>();
  return {
    ...actual,
    prepareImage: async (file: File) => {
      await new Promise<void>((resolve) => {
        release = resolve;
      });
      return file;
    },
  };
});

vi.mock("@/features/seo/track", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/seo/track")>()),
  trackEvent: vi.fn(),
}));

let requests: string[];

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.events.removeAllListeners();
  cleanup();
});
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetImageConsentForTests();
  resetListStoreForTests();
  vi.mocked(trackEvent).mockClear();
  requests = [];
  server.events.on("request:start", ({ request }) => {
    if (request.url.endsWith("/parse-image")) requests.push(request.url);
  });
});

async function pickWhilePreparing() {
  setImageConsent(true);
  const user = userEvent.setup();
  render(<ListBuilder />);
  await user.click(await screen.findByTestId("photo-open"));
  await user.click(screen.getByTestId("photo-list-file"));
  fireEvent.change(screen.getByTestId("photo-input-file"), {
    target: { files: [new File([new Uint8Array(2000)], "photo.jpg", { type: "image/jpeg" })] },
  });
  await screen.findByTestId("photo-reading");
  return user;
}

/** Lets the held preparation finish, then gives any upload it would start time to run. */
async function finishPreparing() {
  release();
  await new Promise((resolve) => setTimeout(resolve, 50));
}

function imageParsedCalls() {
  return vi.mocked(trackEvent).mock.calls.filter(([name]) => name === "image_parsed");
}

it("'ביטול' while the photo is prepared sends no request and stays on the choices", async () => {
  const user = await pickWhilePreparing();
  await user.click(screen.getByTestId("photo-cancel"));
  await finishPreparing();
  expect(requests).toEqual([]);
  expect(imageParsedCalls()).toEqual([]);
  expect(screen.getByTestId("photo-list-camera")).toBeVisible();
  expect(screen.queryByTestId("photo-reading")).not.toBeInTheDocument();
  expect(getListState().items).toEqual([]);
});

it("closing the page while the photo is prepared sends no request", async () => {
  await pickWhilePreparing();
  cleanup();
  await finishPreparing();
  expect(requests).toEqual([]);
  expect(imageParsedCalls()).toEqual([]);
});
