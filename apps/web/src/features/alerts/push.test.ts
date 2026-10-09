import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import { server } from "@/mocks/node";
import { parseThreshold } from "./threshold";
import { trackEvent } from "@/features/seo/track";
import { enablePush, pushSupport, urlBase64ToUint8Array } from "./push";

vi.mock("@/features/seo/track", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/seo/track")>()),
  trackEvent: vi.fn(),
}));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const KEY =
  "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U";

describe("alert thresholds", () => {
  it("reads what people type", () => {
    expect(parseThreshold("8.9")).toBe(8.9);
    expect(parseThreshold("8,90")).toBe(8.9);
    expect(parseThreshold("₪ 9")).toBe(9);
    expect(parseThreshold("")).toBeNull();
    expect(parseThreshold("0")).toBeNull();
    expect(parseThreshold("-3")).toBeNull();
    expect(parseThreshold("abc")).toBeNull();
    expect(parseThreshold("100000")).toBeNull();
  });
});

describe("VAPID key", () => {
  it("decodes URL-safe base64 to the 65 bytes of an uncompressed P-256 key", () => {
    const bytes = urlBase64ToUint8Array(KEY);
    expect(bytes).toHaveLength(65);
    expect(bytes[0]).toBe(4);
  });
});

describe("push feature detection", () => {
  const w = window as unknown as Record<string, unknown>;
  const nav = navigator as unknown as Record<string, unknown>;
  const saved: Record<string, PropertyDescriptor | undefined> = {};

  function stub(target: object, key: string, value: unknown) {
    saved[key] ??= Object.getOwnPropertyDescriptor(target, key);
    Object.defineProperty(target, key, { value, configurable: true, writable: true });
  }

  afterEach(() => {
    for (const [key, desc] of Object.entries(saved)) {
      for (const target of [window, navigator] as object[]) {
        if (desc) Object.defineProperty(target, key, desc);
        else delete (target as Record<string, unknown>)[key];
      }
    }
  });

  it("is unsupported without the Push API, and says how iOS gets it", () => {
    expect(pushSupport(KEY)).toBe("unsupported"); // jsdom has none of the three
    stub(navigator, "userAgent", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)");
    expect(pushSupport(KEY)).toBe("ios-install");
  });

  it("needs the VAPID key even where the browser could do push", () => {
    stub(nav, "serviceWorker", {});
    stub(w, "PushManager", class {});
    stub(w, "Notification", { permission: "default" });
    expect(pushSupport("")).toBe("no-key");
    expect(pushSupport(KEY)).toBe("supported");
  });

  describe("enablePush", () => {
    let subscribe: ReturnType<typeof vi.fn>;
    beforeEach(() => {
      subscribe = vi.fn(() =>
        Promise.resolve({
          toJSON: () => ({
            endpoint: "https://push.example/abc",
            keys: { p256dh: "P", auth: "A" },
          }),
        }),
      );
      stub(nav, "serviceWorker", {
        getRegistration: () =>
          Promise.resolve({
            pushManager: { getSubscription: () => Promise.resolve(null), subscribe },
          }),
      });
      stub(w, "PushManager", class {});
      stub(w, "Notification", { permission: "default" });
    });

    it("asks only now, subscribes with the key and stores the subscription", async () => {
      stub(w, "Notification", {
        permission: "default",
        requestPermission: () => Promise.resolve("granted"),
      });
      let body: unknown;
      server.use(
        http.post(`${API_BASE_URL}/me/push-subscriptions`, async ({ request }) => {
          body = await request.json();
          return HttpResponse.json({ ok: true, id: 1 }, { status: 201 });
        }),
      );
      await expect(enablePush(KEY)).resolves.toEqual({ ok: true });
      expect(subscribe).toHaveBeenCalledWith(
        expect.objectContaining({
          userVisibleOnly: true,
          applicationServerKey: expect.any(Uint8Array),
        }),
      );
      expect(body).toMatchObject({ endpoint: "https://push.example/abc", p256dh: "P", auth: "A" });
    });

    it("reports push_opt_in with the platform when the permission becomes granted through our flow", async () => {
      vi.mocked(trackEvent).mockClear();
      stub(w, "Notification", {
        permission: "default",
        requestPermission: () => Promise.resolve("granted"),
      });
      server.use(
        http.post(`${API_BASE_URL}/me/push-subscriptions`, () =>
          HttpResponse.json({ ok: true, id: 1 }, { status: 201 }),
        ),
      );
      await enablePush(KEY);
      expect(vi.mocked(trackEvent).mock.calls.filter(([n]) => n === "push_opt_in")).toHaveLength(1);
      expect(trackEvent).toHaveBeenCalledWith("push_opt_in", {
        platform: expect.stringMatching(/^(ios|android|desktop|other)$/),
      });
    });

    it("reports push_prompt_shown right before the browser is asked, once, with the platform", async () => {
      vi.mocked(trackEvent).mockClear();
      const order: string[] = [];
      vi.mocked(trackEvent).mockImplementation((name) => {
        order.push(String(name));
      });
      stub(w, "Notification", {
        permission: "default",
        requestPermission: () => {
          order.push("requestPermission");
          return Promise.resolve("denied");
        },
      });
      await enablePush(KEY);
      expect(order).toEqual(["push_prompt_shown", "requestPermission"]);
      expect(trackEvent).toHaveBeenCalledWith("push_prompt_shown", {
        platform: expect.stringMatching(/^(ios|android|desktop|other)$/),
      });
      vi.mocked(trackEvent).mockReset();
    });

    it("does not report push_prompt_shown when no prompt can appear (already granted or blocked, or no key)", async () => {
      vi.mocked(trackEvent).mockClear();
      stub(w, "Notification", {
        permission: "denied",
        requestPermission: () => Promise.resolve("denied"),
      });
      await enablePush(KEY);
      await enablePush("");
      expect(trackEvent).not.toHaveBeenCalledWith("push_prompt_shown", expect.anything());
    });

    it("does not report push_opt_in for a denied or an already granted permission", async () => {
      vi.mocked(trackEvent).mockClear();
      stub(w, "Notification", {
        permission: "default",
        requestPermission: () => Promise.resolve("denied"),
      });
      await enablePush(KEY);
      stub(w, "Notification", {
        permission: "granted",
        requestPermission: () => Promise.resolve("granted"),
      });
      server.use(
        http.post(`${API_BASE_URL}/me/push-subscriptions`, () =>
          HttpResponse.json({ ok: true, id: 1 }, { status: 201 }),
        ),
      );
      await enablePush(KEY);
      expect(trackEvent).not.toHaveBeenCalledWith("push_opt_in", expect.anything());
    });

    it("handles a denied permission without subscribing or breaking", async () => {
      stub(w, "Notification", {
        permission: "default",
        requestPermission: () => Promise.resolve("denied"),
      });
      await expect(enablePush(KEY)).resolves.toEqual({ ok: false, reason: "denied" });
      expect(subscribe).not.toHaveBeenCalled();
    });

    it("reports a server failure as an error, not an exception", async () => {
      stub(w, "Notification", {
        permission: "default",
        requestPermission: () => Promise.resolve("granted"),
      });
      server.use(
        http.post(`${API_BASE_URL}/me/push-subscriptions`, () =>
          HttpResponse.json({ detail: "x" }, { status: 500 }),
        ),
      );
      await expect(enablePush(KEY)).resolves.toEqual({ ok: false, reason: "error" });
    });

    it("does nothing without a key", async () => {
      await expect(enablePush("")).resolves.toEqual({ ok: false, reason: "no-key" });
    });
  });
});
