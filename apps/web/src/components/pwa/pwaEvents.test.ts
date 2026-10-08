import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushEvents, resetTrackingForTests, setTrackingConsent } from "@/features/seo/track";
import {
  INSTALLED_KEY,
  PUSH_OPENED_MESSAGE,
  reportInstalled,
  resetPwaEventsForTests,
  startPwaEvents,
} from "./pwaEvents";

const fetchMock = vi.fn(
  async (_url: string, _init?: RequestInit) => new Response(JSON.stringify({ ok: true })),
);

async function sentEvents(): Promise<{ name: string; props: Record<string, unknown> }[]> {
  await flushEvents();
  return fetchMock.mock.calls.flatMap(
    ([, init]) => (JSON.parse(init!.body as string) as { events: never[] }).events,
  );
}

function standalone(on: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: on && query.includes("standalone"),
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    })),
  );
}

const ANDROID_UA =
  "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/126.0 Mobile Safari/537.36";

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NEXT_PUBLIC_BETA_EVENTS", "1");
  vi.spyOn(navigator, "userAgent", "get").mockReturnValue(ANDROID_UA);
  localStorage.clear();
  resetTrackingForTests();
  resetPwaEventsForTests();
  fetchMock.mockClear();
  standalone(false);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("pwa_installed", () => {
  it("is sent on appinstalled with the coarse platform, once", async () => {
    setTrackingConsent(true);
    const stop = startPwaEvents();
    window.dispatchEvent(new Event("appinstalled"));
    window.dispatchEvent(new Event("appinstalled"));
    const events = await sentEvents();
    expect(events).toEqual([
      expect.objectContaining({ name: "pwa_installed", props: { platform: "android" } }),
    ]);
    expect(localStorage.getItem(INSTALLED_KEY)).toBe("1");
    stop();
  });

  it("is sent on the first standalone launch and not on the next one", async () => {
    setTrackingConsent(true);
    standalone(true);
    startPwaEvents()();
    expect((await sentEvents()).map((e) => e.name)).toEqual(["pwa_installed"]);

    fetchMock.mockClear();
    resetPwaEventsForTests(); // a new page load
    startPwaEvents()();
    expect(await sentEvents()).toEqual([]);
  });

  it("is not sent from a normal browser tab", async () => {
    setTrackingConsent(true);
    startPwaEvents()();
    expect(await sentEvents()).toEqual([]);
    expect(localStorage.getItem(INSTALLED_KEY)).toBeNull();
  });

  it("respects the consent gate: nothing before consent, counted when it is given, nothing when declined", async () => {
    standalone(true);
    const stop = startPwaEvents();
    expect(reportInstalled()).toBe(false);
    expect(localStorage.getItem(INSTALLED_KEY)).toBeNull(); // not marked, so a later launch counts
    expect(await sentEvents()).toEqual([]);

    setTrackingConsent(true); // the person accepts on this very launch
    expect((await sentEvents()).map((e) => e.name)).toEqual(["pwa_installed"]);
    stop();

    localStorage.clear();
    resetTrackingForTests();
    resetPwaEventsForTests();
    fetchMock.mockClear();
    setTrackingConsent(false);
    startPwaEvents()();
    window.dispatchEvent(new Event("appinstalled"));
    expect(await sentEvents()).toEqual([]);
  });

  it("sends nothing outside a beta build", async () => {
    vi.stubEnv("NEXT_PUBLIC_BETA_EVENTS", "");
    setTrackingConsent(true);
    standalone(true);
    startPwaEvents()();
    window.dispatchEvent(new Event("appinstalled"));
    expect(await sentEvents()).toEqual([]);
  });

  it("stops listening when cleaned up", async () => {
    setTrackingConsent(true);
    startPwaEvents()();
    window.dispatchEvent(new Event("appinstalled"));
    expect(await sentEvents()).toEqual([]);
  });
});

describe("push_opened", () => {
  function fakeServiceWorker() {
    const listeners = new Set<(e: MessageEvent) => void>();
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: {
        addEventListener: (_t: string, fn: (e: MessageEvent) => void) => listeners.add(fn),
        removeEventListener: (_t: string, fn: (e: MessageEvent) => void) => listeners.delete(fn),
      },
    });
    return (data: unknown) => listeners.forEach((fn) => fn({ data } as MessageEvent));
  }

  afterEach(() => {
    Reflect.deleteProperty(navigator, "serviceWorker");
  });

  it("turns the worker's message into the event, with the platform", async () => {
    setTrackingConsent(true);
    const post = fakeServiceWorker();
    const stop = startPwaEvents();
    post({ type: PUSH_OPENED_MESSAGE });
    post({ type: "something-else" });
    post("sc-push-opened");
    post(null);
    expect(await sentEvents()).toEqual([
      expect.objectContaining({ name: "push_opened", props: { platform: "android" } }),
    ]);
    stop();
  });

  it("respects the consent gate", async () => {
    setTrackingConsent(false);
    const post = fakeServiceWorker();
    const stop = startPwaEvents();
    post({ type: PUSH_OPENED_MESSAGE });
    expect(await sentEvents()).toEqual([]);
    stop();
  });
});
