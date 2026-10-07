/**
 * The events /scan sends (issue #101): `scan_started` with the engine, `scan_completed` with the
 * outcome, the duration and the engine. `trackEvent` is replaced by a spy so each test sees exactly
 * the payload; the consent gate is covered in betaEvents.test.ts. No payload may carry a barcode, a
 * name or a price.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { API_BASE_URL } from "@/api/config";
import { server } from "@/mocks/node";
import { resetListStoreForTests } from "@/state/list";
import { outcomeOf, ScanScreen } from "./ScanScreen";

const track = vi.hoisted(() => vi.fn());
vi.mock("@/features/seo/track", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/seo/track")>()),
  trackEvent: track,
}));

const FOUND = "5901234123457";
const NOT_FOUND = "5901234000000";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  vi.unstubAllGlobals();
  delete (window as unknown as { BarcodeDetector?: unknown }).BarcodeDetector;
  Object.defineProperty(navigator, "mediaDevices", { value: undefined, configurable: true });
});
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
  track.mockClear();
});

const sent = () => track.mock.calls.map(([name, props]) => [name, props]);

async function renderScreen() {
  const user = userEvent.setup();
  const view = render(<ScanScreen />);
  await waitFor(() => expect(screen.getByTestId("scan-store")).toHaveValue("103"));
  return { user, ...view };
}

async function lookupManually(user: ReturnType<typeof userEvent.setup>, code: string) {
  await user.type(screen.getByRole("textbox", { name: /ברקוד \(13 ספרות/ }), code);
  await user.click(screen.getByRole("button", { name: "חיפוש" }));
}

function stubCamera(opts: { detects?: string } = {}) {
  const stopTrack = vi.fn();
  const stream = { getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream;
  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia: vi.fn(() => Promise.resolve(stream)) },
    configurable: true,
  });
  Object.defineProperty(HTMLMediaElement.prototype, "play", {
    value: () => Promise.resolve(),
    configurable: true,
  });
  (window as unknown as { BarcodeDetector: unknown }).BarcodeDetector = class {
    detect = () => Promise.resolve(opts.detects ? [{ rawValue: opts.detects }] : []);
  };
}

describe("outcome of a lookup", () => {
  const base = {
    barcode: FOUND,
    found: true,
    display_name_he: "x",
    canonical: null,
    here: null,
    cheapest_nearby: null,
    cheaper_substitute: null,
    generated_at: "2026-10-07T00:00:00Z",
    disclaimer_he: "",
  };
  it("is not_found for an unknown code, no_price for a known product without a price, else found", () => {
    expect(outcomeOf({ ...base, found: false })).toBe("not_found");
    expect(outcomeOf(base)).toBe("no_price");
    expect(
      outcomeOf({
        ...base,
        cheapest_nearby: { shelf_price: "1" } as never,
      }),
    ).toBe("found");
  });
});

describe("manual entry", () => {
  it("sends scan_started with engine manual and scan_completed found with a duration", async () => {
    const { user } = await renderScreen();
    await lookupManually(user, FOUND);
    await screen.findByTestId("scan-result");
    expect(sent()).toEqual([
      ["scan_started", { engine: "manual" }],
      ["scan_completed", { outcome: "found", duration_ms: expect.any(Number), engine: "manual" }],
    ]);
    const done = track.mock.calls[1]![1] as { duration_ms: number };
    expect(Number.isInteger(done.duration_ms)).toBe(true);
    expect(done.duration_ms).toBeGreaterThanOrEqual(0);
    // Nothing about the product, the code, the store or a price.
    const json = JSON.stringify(sent());
    expect(json).not.toContain(FOUND);
    expect(json).not.toMatch(/₪|price|barcode|store|רסק|אסם|lat|lon/i);
  });

  it("an unknown code is not_found", async () => {
    const { user } = await renderScreen();
    await lookupManually(user, NOT_FOUND);
    await screen.findByTestId("scan-notfound");
    expect(track.mock.calls.map(([n]) => n)).toEqual(["scan_started", "scan_completed"]);
    expect(track.mock.calls[1]![1]).toMatchObject({ outcome: "not_found", engine: "manual" });
    expect(JSON.stringify(sent())).not.toContain(NOT_FOUND);
  });

  it("a known product with no price anywhere is no_price", async () => {
    server.use(
      http.get(`${API_BASE_URL}/items/barcode/:barcode`, ({ params }) =>
        HttpResponse.json({
          barcode: params.barcode,
          found: true,
          display_name_he: "מוצר",
          canonical: null,
          here: null,
          cheapest_nearby: null,
          cheaper_substitute: null,
          generated_at: "2026-10-07T00:00:00Z",
          disclaimer_he: "המחיר הקובע הוא בקופה.",
        }),
      ),
    );
    const { user } = await renderScreen();
    await lookupManually(user, FOUND);
    await waitFor(() => expect(track).toHaveBeenCalledTimes(2));
    expect(track.mock.calls[1]![1]).toMatchObject({ outcome: "no_price" });
  });

  it("a failed lookup is error, and the retry is a new started and completed pair", async () => {
    let fail = true;
    server.use(
      http.get(`${API_BASE_URL}/items/barcode/:barcode`, () =>
        fail ? HttpResponse.json({}, { status: 500 }) : HttpResponse.json({}, { status: 404 }),
      ),
    );
    const { user } = await renderScreen();
    await lookupManually(user, FOUND);
    await screen.findByTestId("scan-error");
    expect(sent()).toEqual([
      ["scan_started", { engine: "manual" }],
      ["scan_completed", { outcome: "error", duration_ms: expect.any(Number), engine: "manual" }],
    ]);
    fail = false;
    track.mockClear();
    await user.click(screen.getByRole("button", { name: "נסי שוב" }));
    await waitFor(() => expect(track).toHaveBeenCalledTimes(2));
    expect(track.mock.calls.map(([n]) => n)).toEqual(["scan_started", "scan_completed"]);
  });

  it("a mistyped code never started a scan", async () => {
    const { user } = await renderScreen();
    await lookupManually(user, "5901234123450");
    await screen.findByText(/לא מרכיבות ברקוד תקין/);
    expect(track).not.toHaveBeenCalled();
  });
});

describe("camera", () => {
  it("a denied permission is started without an engine, then error", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      value: {
        getUserMedia: vi.fn(() =>
          Promise.reject(Object.assign(new Error("no"), { name: "NotAllowedError" })),
        ),
      },
      configurable: true,
    });
    const { user } = await renderScreen();
    await user.click(screen.getByRole("button", { name: "הפעלת המצלמה" }));
    await screen.findByTestId("scan-camera-error");
    expect(sent()).toEqual([
      ["scan_started", {}],
      ["scan_completed", { outcome: "error", duration_ms: expect.any(Number) }],
    ]);
  });

  it("reads a code with the native detector: started with engine native, completed found", async () => {
    stubCamera({ detects: FOUND });
    const { user } = await renderScreen();
    await user.click(screen.getByRole("button", { name: "הפעלת המצלמה" }));
    await screen.findByTestId("scan-result", undefined, { timeout: 3000 });
    expect(sent()).toEqual([
      ["scan_started", { engine: "native" }],
      ["scan_completed", { outcome: "found", duration_ms: expect.any(Number), engine: "native" }],
    ]);
    expect(JSON.stringify(sent())).not.toContain(FOUND);
  });

  it("stopping the camera before a code is read is cancelled, with the engine", async () => {
    stubCamera();
    const { user } = await renderScreen();
    await user.click(screen.getByRole("button", { name: "הפעלת המצלמה" }));
    await screen.findByTestId("scan-video");
    await waitFor(() => expect(track).toHaveBeenCalledWith("scan_started", { engine: "native" }));
    await user.click(screen.getByRole("button", { name: "עצירת המצלמה" }));
    expect(sent()).toEqual([
      ["scan_started", { engine: "native" }],
      [
        "scan_completed",
        { outcome: "cancelled", duration_ms: expect.any(Number), engine: "native" },
      ],
    ]);
  });

  it("leaving the screen while scanning is cancelled too, exactly once", async () => {
    stubCamera();
    const { user, unmount } = await renderScreen();
    await user.click(screen.getByRole("button", { name: "הפעלת המצלמה" }));
    await screen.findByTestId("scan-video");
    await waitFor(() => expect(track).toHaveBeenCalledWith("scan_started", { engine: "native" }));
    unmount();
    expect(track.mock.calls.filter(([n]) => n === "scan_completed")).toHaveLength(1);
    expect(track.mock.calls.at(-1)![1]).toMatchObject({ outcome: "cancelled" });
  });

  it("typing a code while the camera is on cancels the camera attempt and starts a manual one", async () => {
    stubCamera();
    const { user } = await renderScreen();
    await user.click(screen.getByRole("button", { name: "הפעלת המצלמה" }));
    await screen.findByTestId("scan-video");
    await waitFor(() => expect(track).toHaveBeenCalledWith("scan_started", { engine: "native" }));
    await lookupManually(user, FOUND);
    await screen.findByTestId("scan-result");
    expect(track.mock.calls.map(([n, p]) => [n, (p as { outcome?: string }).outcome])).toEqual([
      ["scan_started", undefined],
      ["scan_completed", "cancelled"],
      ["scan_started", undefined],
      ["scan_completed", "found"],
    ]);
  });
});
