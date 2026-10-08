/**
 * `/scan?code=<ean>` (docs/fullstack.md gap 5): the lookup runs from the URL without the camera,
 * as if the code had been typed into the manual field.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { API_BASE_URL } from "@/api/config";
import { server } from "@/mocks/node";
import { resetListStoreForTests } from "@/state/list";
import { ScanScreen } from "./ScanScreen";

let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(search),
}));

const track = vi.hoisted(() => vi.fn());
vi.mock("@/features/seo/track", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/seo/track")>()),
  trackEvent: track,
}));

const FOUND = "5901234123457";
const lookups: string[] = [];
const getUserMedia = vi.fn();

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  server.events.removeAllListeners();
  Object.defineProperty(navigator, "mediaDevices", { value: undefined, configurable: true });
});
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
  track.mockClear();
  getUserMedia.mockClear();
  lookups.length = 0;
  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia },
    configurable: true,
  });
  server.events.on("request:start", ({ request }) => {
    if (request.url.includes("/items/barcode/")) lookups.push(new URL(request.url).pathname);
  });
});

describe("/scan?code=", () => {
  it("looks the code up once the stores are known, with no camera", async () => {
    search = `code=${FOUND}`;
    render(<ScanScreen />);
    await screen.findByTestId("scan-result");
    expect(lookups).toEqual([`/items/barcode/${FOUND}`]);
    expect(getUserMedia).not.toHaveBeenCalled();
    // The code is also in the manual field, so it can be corrected.
    expect(screen.getByRole("textbox", { name: /ברקוד \(13 ספרות/ })).toHaveValue(FOUND);
    // The store the shopper is in was resolved before the lookup (the home store, 103).
    expect(screen.getByTestId("scan-store")).toHaveValue("103");
  });

  it("asks for the shopper's store in the lookup", async () => {
    search = `code=${FOUND}`;
    const queries: string[] = [];
    server.use(
      http.get(`${API_BASE_URL}/items/barcode/:barcode`, ({ request }) => {
        queries.push(new URL(request.url).search);
        return HttpResponse.json({}, { status: 404 });
      }),
    );
    render(<ScanScreen />);
    await waitFor(() => expect(queries).toHaveLength(1));
    expect(queries[0]).toContain("store_id=103");
  });

  it("is reported like a manual entry", async () => {
    search = `code=${FOUND}`;
    render(<ScanScreen />);
    await screen.findByTestId("scan-result");
    expect(track.mock.calls.map(([name, props]) => [name, props])).toEqual([
      ["scan_started", { engine: "manual" }],
      ["scan_completed", { outcome: "found", duration_ms: expect.any(Number), engine: "manual" }],
    ]);
  });

  it("a code that fails the check digit shows the manual-entry error and makes no request", async () => {
    search = "code=5901234123458";
    render(<ScanScreen />);
    expect(await screen.findByRole("alert")).toHaveTextContent("הספרות לא מרכיבות ברקוד תקין");
    await waitFor(() => expect(screen.getByTestId("scan-store")).toHaveValue("103"));
    expect(lookups).toEqual([]);
    expect(track).not.toHaveBeenCalled();
  });

  it("without a code the screen is as before: idle, camera card, nothing looked up", async () => {
    search = "";
    render(<ScanScreen />);
    await waitFor(() => expect(screen.getByTestId("scan-store")).toHaveValue("103"));
    expect(screen.getByRole("button", { name: "הפעלת המצלמה" })).toBeEnabled();
    expect(lookups).toEqual([]);
  });

  it("scanning another product afterwards works and the URL code is not looked up again", async () => {
    search = `code=${FOUND}`;
    const user = userEvent.setup();
    render(<ScanScreen />);
    await screen.findByTestId("scan-result");
    await user.click(screen.getByRole("button", { name: "סריקת מוצר נוסף" }));
    expect(lookups).toHaveLength(1);
    expect(screen.queryByTestId("scan-result")).not.toBeInTheDocument();
  });
});
