import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "@/mocks/node";
import { getListState, resetListStoreForTests } from "@/state/list";
import { ScanScreen } from "./ScanScreen";
import { readScanLog, scanStats } from "./scanLog";

const FOUND = "5901234123457";
const NOT_FOUND = "5901234000000"; // valid check digit, ends 0000: the mock has no product for it

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
});
afterEach(() => {
  vi.unstubAllGlobals();
  delete (window as unknown as { BarcodeDetector?: unknown }).BarcodeDetector;
  Object.defineProperty(navigator, "mediaDevices", { value: undefined, configurable: true });
});

async function renderScreen() {
  const user = userEvent.setup();
  render(<ScanScreen />);
  // The store picker fills from /stores/nearest; the nearest store (שופרסל דיל, 1.1 km) is chosen.
  await waitFor(() => expect(screen.getByTestId("scan-store")).toHaveValue("103"));
  return user;
}

async function lookupManually(user: ReturnType<typeof userEvent.setup>, code: string) {
  await user.type(screen.getByRole("textbox", { name: /ברקוד \(13 ספרות/ }), code);
  await user.click(screen.getByRole("button", { name: "חיפוש" }));
}

describe("scan screen: manual entry and the result card", () => {
  it("shows here, cheapest nearby and the labeled cheaper substitute, each with its update time", async () => {
    const user = await renderScreen();
    await lookupManually(user, FOUND);

    const card = await screen.findByTestId("scan-result");
    expect(within(card).getByRole("heading", { level: 2 })).toHaveTextContent(
      "רסק עגבניות אסם 260 ג'",
    );
    expect(within(card).getByTestId("scan-here")).toHaveTextContent(/כאן.*₪\s14\.90/);
    expect(within(card).getByTestId("scan-cheapest")).toHaveTextContent(/₪\s11\.50/);
    expect(within(card).getByTestId("scan-cheapest")).toHaveTextContent("אושר עד");
    const sub = within(card).getByTestId("scan-substitute");
    expect(sub).toHaveTextContent(/₪\s8\.90/);
    expect(sub.querySelector('[data-variant="substitute"]')).toHaveTextContent("תחליף");
    expect(within(card).getByTestId("scan-reason")).toHaveTextContent("למה זה תחליף");
    expect(sub).toHaveTextContent(/זול ב-/); // unit price difference (D6)
    for (const row of ["scan-here", "scan-cheapest", "scan-substitute"]) {
      expect(within(card).getByTestId(row).querySelector("time[datetime]")).not.toBeNull();
    }
    expect(card).toHaveTextContent("המחיר הקובע הוא בקופה");
    // Every price is an LTR island.
    for (const price of within(card).getAllByText(/₪/)) {
      expect(price.closest('[dir="ltr"]')).not.toBeNull();
    }
  });

  it("marks the distance of a town-centre store as approximate, in the store choice and on the card", async () => {
    const user = await renderScreen();
    const select = screen.getByTestId("scan-store");
    const options = within(select)
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(options).toContain('יוחננוף · מודיעין · כ־3.6 ק"מ · מיקום משוער');
    expect(options).toContain('שופרסל דיל · מודיעין · 1.1 ק"מ');

    await user.selectOptions(select, "104");
    await lookupManually(user, FOUND);
    const card = await screen.findByTestId("scan-result");
    const here = within(within(card).getByTestId("scan-here")).getByTestId("scan-distance");
    expect(here).toHaveTextContent('כ־3.6 ק"מ · מיקום משוער');
    expect(here).toHaveAttribute("data-approximate", "true");
    const cheapest = within(within(card).getByTestId("scan-cheapest")).getByTestId("scan-distance");
    expect(cheapest).toHaveTextContent('5.1 ק"מ');
    expect(cheapest).not.toHaveTextContent("משוער");
  });

  it("adds the canonical product with the chosen quantity and the category's level", async () => {
    const user = await renderScreen();
    await lookupManually(user, FOUND);
    const card = await screen.findByTestId("scan-result");
    await user.click(within(card).getByRole("button", { name: /הוסיפי כמות של/ }));
    await user.click(within(card).getByRole("button", { name: "הוסיפי לרשימה" }));
    expect(await within(card).findByTestId("scan-added")).toBeInTheDocument();
    const rows = getListState().items;
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ quantity: 2, flexLevel: "any_brand" });
    expect(rows[0]!.canonical).toMatchObject({ canonical_id: 1004 });
  });

  it("flags a shelf price that differs from ours and offers to report it", async () => {
    const user = await renderScreen();
    await lookupManually(user, FOUND);
    const card = await screen.findByTestId("scan-result");
    expect(within(card).queryByTestId("scan-gap")).toBeNull();
    await user.type(within(card).getByLabelText(/המחיר שראית על המדף/), "12.90");
    const gap = within(card).getByTestId("scan-gap");
    expect(gap).toHaveTextContent(/₪\s12\.90/);
    expect(gap).toHaveTextContent(/₪\s14\.90/);
    expect(within(gap).getByRole("button", { name: /דווחי על פער/ })).toBeInTheDocument();
    await user.clear(within(card).getByLabelText(/המחיר שראית על המדף/));
    await user.type(within(card).getByLabelText(/המחיר שראית על המדף/), "14.90");
    expect(within(card).queryByTestId("scan-gap")).toBeNull();
  });

  it("shows a not-found state with report-a-gap and manual entry, never a guess", async () => {
    const user = await renderScreen();
    await lookupManually(user, NOT_FOUND);
    const state = await screen.findByTestId("scan-notfound");
    expect(state).toHaveTextContent("לא מצאנו את הברקוד הזה");
    expect(state).toHaveTextContent("לא ננחש מוצר");
    expect(within(state).getByRole("button", { name: /דווחי על פער/ })).toBeInTheDocument();
    expect(screen.queryByTestId("scan-result")).toBeNull();
    expect(screen.queryByRole("button", { name: "הוסיפי לרשימה" })).toBeNull();
    // The manual field is still there to try another code.
    expect(screen.getByRole("textbox", { name: /ברקוד \(13 ספרות/ })).toBeInTheDocument();
    expect(getListState().items).toHaveLength(0);
  });

  it("rejects a typo before asking the server", async () => {
    const user = await renderScreen();
    await lookupManually(user, "5901234123450"); // wrong check digit
    expect(await screen.findByText(/לא מרכיבות ברקוד תקין/)).toBeInTheDocument();
    expect(screen.queryByTestId("scan-loading")).toBeNull();
    expect(screen.queryByTestId("scan-result")).toBeNull();
  });

  it("logs success and time to result without a barcode or a location", async () => {
    const user = await renderScreen();
    await lookupManually(user, FOUND);
    await screen.findByTestId("scan-result");
    const log = readScanLog();
    expect(log).toMatchObject({ attempts: 1, found: 1, notFound: 0, failed: 0 });
    expect(log.byInput).toEqual({ camera: 0, manual: 1 });
    expect(scanStats(log).successRate).toBe(1);
    const stored = window.localStorage.getItem("sc-scan-log-v1") ?? "";
    expect(stored).not.toContain(FOUND);
    expect(stored).not.toMatch(/lat|lon/);
  });
});

describe("scan screen: camera", () => {
  it("explains the permission before asking and keeps manual entry when it is denied", async () => {
    const getUserMedia = vi.fn(() =>
      Promise.reject(Object.assign(new Error("no"), { name: "NotAllowedError" })),
    );
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia },
      configurable: true,
    });
    const user = await renderScreen();
    expect(getUserMedia).not.toHaveBeenCalled(); // nothing is asked on load
    expect(screen.getByText(/לא נשמרות תמונות/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "הפעלת המצלמה" }));
    expect(await screen.findByTestId("scan-camera-error")).toHaveTextContent("הגישה למצלמה נחסמה");
    expect(screen.getByRole("textbox", { name: /ברקוד \(13 ספרות/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ניסיון נוסף" })).toBeInTheDocument();
    expect(readScanLog().failed).toBe(1);
  });

  it("reads a code from the camera with a stubbed detector, stops the camera and shows the result", async () => {
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
      detect = () => Promise.resolve([{ rawValue: FOUND }]);
    };
    const user = await renderScreen();
    await user.click(screen.getByRole("button", { name: "הפעלת המצלמה" }));
    expect(await screen.findByTestId("scan-video")).toBeInTheDocument();
    const card = await screen.findByTestId("scan-result", undefined, { timeout: 3000 });
    expect(within(card).getByTestId("scan-substitute")).toHaveTextContent(/₪\s8\.90/);
    expect(stopTrack).toHaveBeenCalled(); // the camera is off once a code is read
    expect(screen.queryByTestId("scan-video")).toBeNull();
    expect(readScanLog().byInput.camera).toBe(1);
  });
});
