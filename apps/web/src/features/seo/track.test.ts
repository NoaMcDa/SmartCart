import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  flushEvents,
  getSessionId,
  getTrackingConsent,
  isTrackingAvailable,
  isTrackingEnabled,
  resetTrackingForTests,
  setAuthTokenProvider,
  setTrackingConsent,
  subscribeTrackingConsent,
  trackEvent,
} from "./track";

const fetchMock = vi.fn(
  async (_url: string, _init?: RequestInit) => new Response(JSON.stringify({ ok: true })),
);

function sent(): {
  events: { name: string; props: Record<string, unknown>; session_id: string }[];
} {
  return JSON.parse(fetchMock.mock.calls.at(-1)![1]!.body as string);
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NEXT_PUBLIC_BETA_EVENTS", "1");
  localStorage.clear();
  resetTrackingForTests();
  // Opt-in: every test below that expects a send starts from "the person accepted".
  setTrackingConsent(true);
  fetchMock.mockClear();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("trackEvent", () => {
  it("does nothing unless beta events are switched on at build time", async () => {
    vi.stubEnv("NEXT_PUBLIC_BETA_EVENTS", "");
    expect(isTrackingEnabled()).toBe(false);
    trackEvent("list_pasted", { item_count: 5 });
    await vi.advanceTimersByTimeAsync(5000);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(localStorage.getItem("sc-session")).toBeNull();
  });

  it("batches events into one POST /events after two seconds", async () => {
    trackEvent("app_opened", { surface: "web" });
    trackEvent("list_pasted", { item_count: 9 });
    trackEvent("split_viewed");
    expect(fetchMock).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(2000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://api.test/events");
    expect(init!.method).toBe("POST");
    expect(init!.keepalive).toBe(true);
    const body = sent();
    expect(body.events.map((e) => e.name)).toEqual(["app_opened", "list_pasted", "split_viewed"]);
    expect(body.events[1]?.props).toEqual({ item_count: 9 });
    expect(body.events[2]?.props).toEqual({});
  });

  it("sends only what the caller passed: a session id, no user id, no free text", async () => {
    trackEvent("substitution_verdict", { flex_level: "close", verdict: "not_good" });
    await flushEvents();
    const [event] = sent().events;
    expect(Object.keys(event!).sort()).toEqual(["name", "props", "session_id"]);
    expect(event!.session_id).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
  });

  it("flushes at once when 50 events are queued", async () => {
    for (let i = 0; i < 50; i++) trackEvent("flex_changed", { flex_level: "exact" });
    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(sent().events).toHaveLength(50);
  });

  it("flushes when the page is hidden", async () => {
    trackEvent("gap_reported");
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
  });

  it("adds the access token when a provider is registered", async () => {
    setAuthTokenProvider(() => "jwt-abc");
    trackEvent("app_opened");
    await flushEvents();
    const init = fetchMock.mock.calls[0]![1]!;
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer jwt-abc");
  });

  it("never throws when the network fails", async () => {
    fetchMock.mockRejectedValueOnce(new Error("offline"));
    trackEvent("app_opened");
    await expect(flushEvents()).resolves.toBeUndefined();
  });
});

describe("session id and consent", () => {
  it("keeps one random id in localStorage", () => {
    const first = getSessionId();
    expect(first).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(getSessionId()).toBe(first);
    expect(localStorage.getItem("sc-session")).toBe(first);
  });

  it("replaces a stored id that is not a valid token", () => {
    localStorage.setItem("sc-session", "a b c");
    expect(getSessionId()).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
  });

  it("works when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const id = getSessionId();
    expect(id).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(getSessionId()).toBe(id);
    vi.restoreAllMocks();
  });

  it("stops after opting out and drops what was queued", async () => {
    trackEvent("app_opened");
    setTrackingConsent(false);
    expect(isTrackingEnabled()).toBe(false);
    await vi.advanceTimersByTimeAsync(5000);
    expect(fetchMock).not.toHaveBeenCalled();
    trackEvent("app_opened");
    await vi.advanceTimersByTimeAsync(5000);
    expect(fetchMock).not.toHaveBeenCalled();
    setTrackingConsent(true);
    expect(isTrackingEnabled()).toBe(true);
  });

  it("is opt-in: nothing is queued or sent until the consent screen was accepted", async () => {
    localStorage.clear();
    resetTrackingForTests();
    expect(getTrackingConsent()).toBe("unset");
    expect(isTrackingEnabled()).toBe(false);
    trackEvent("list_pasted", { item_count: 3 });
    await vi.advanceTimersByTimeAsync(5000);
    await flushEvents();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(localStorage.getItem("sc-session")).toBeNull();
  });

  it("sends nothing after the consent screen was declined, and drops what was queued", async () => {
    trackEvent("list_pasted", { item_count: 3 });
    setTrackingConsent(false);
    expect(getTrackingConsent()).toBe("declined");
    expect(localStorage.getItem("sc-events-consent")).toBe("0");
    for (const name of [
      "app_opened",
      "list_pasted",
      "results_shown",
      "substitutions_shown",
      "substitution_verdict",
      "flex_changed",
      "split_viewed",
      "gap_reported",
    ] as const) {
      // Props are irrelevant here: the call must be a no-op.
      (trackEvent as (n: string, p?: object) => void)(name, {});
    }
    await vi.advanceTimersByTimeAsync(5000);
    await flushEvents();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("stores the answer and tells subscribers", () => {
    const listener = vi.fn();
    const off = subscribeTrackingConsent(listener);
    setTrackingConsent(false);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(getTrackingConsent()).toBe("declined");
    setTrackingConsent(true);
    expect(getTrackingConsent()).toBe("granted");
    expect(localStorage.getItem("sc-events-consent")).toBe("1");
    off();
    setTrackingConsent(false);
    expect(listener).toHaveBeenCalledTimes(2);
  });

  it("keeps the answer in memory when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    setTrackingConsent(false);
    expect(getTrackingConsent()).toBe("declined");
    expect(isTrackingEnabled()).toBe(false);
    vi.restoreAllMocks();
  });

  it("is not available at all without the build flag or with Do Not Track", () => {
    expect(isTrackingAvailable()).toBe(true);
    vi.stubEnv("NEXT_PUBLIC_BETA_EVENTS", "");
    expect(isTrackingAvailable()).toBe(false);
    vi.stubEnv("NEXT_PUBLIC_BETA_EVENTS", "1");
    Object.defineProperty(navigator, "doNotTrack", { value: "1", configurable: true });
    expect(isTrackingAvailable()).toBe(false);
    Reflect.deleteProperty(navigator, "doNotTrack");
  });

  it("respects Do Not Track", () => {
    Object.defineProperty(navigator, "doNotTrack", { value: "1", configurable: true });
    expect(isTrackingEnabled()).toBe(false);
    Reflect.deleteProperty(navigator, "doNotTrack");
    expect(isTrackingEnabled()).toBe(true);
  });
});
