// @vitest-environment node
/**
 * The push and notificationclick handlers of public/sw.js (issue #23), run in a vm with a fake
 * service-worker scope: what the notification says, where a tap goes, and that a payload can never
 * send the user to another site.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";
import { describe, expect, it, vi } from "vitest";

const SW = readFileSync(
  join(fileURLToPath(new URL("../../..", import.meta.url)), "public/sw.js"),
  "utf8",
);
const ORIGIN = "https://smartcart.example";

type Handler = (event: Record<string, unknown>) => void;

function loadWorker(
  windows: Array<{
    url: string;
    focus: () => Promise<void>;
    navigate?: (u: string) => Promise<void>;
  }> = [],
) {
  const handlers: Record<string, Handler> = {};
  const shown: Array<{ title: string; options: Record<string, unknown> }> = [];
  const openWindow = vi.fn(() => Promise.resolve());
  const self = {
    location: { origin: ORIGIN },
    addEventListener: (type: string, fn: Handler) => {
      handlers[type] = fn;
    },
    registration: {
      showNotification: (title: string, options: Record<string, unknown>) => {
        shown.push({ title, options });
        return Promise.resolve();
      },
    },
    clients: {
      matchAll: () => Promise.resolve(windows),
      openWindow,
      claim: () => Promise.resolve(),
    },
    skipWaiting: () => Promise.resolve(),
  };
  runInNewContext(SW, {
    self,
    URL,
    Promise,
    Set,
    Date,
    Intl,
    Error,
    caches: {},
    fetch: () => Promise.reject(new Error("offline")),
  });
  return { handlers, shown, openWindow };
}

async function push(payload: unknown, raw = false) {
  const worker = loadWorker();
  let done: Promise<unknown> = Promise.resolve();
  worker.handlers.push!({
    data: raw
      ? {
          json: () => {
            throw new Error("bad");
          },
          text: () => String(payload),
        }
      : { json: () => payload },
    waitUntil: (p: Promise<unknown>) => {
      done = p;
    },
  });
  await done;
  return worker.shown[0]!;
}

describe("push handler", () => {
  it("shows product, store, price, the time of the price and the checkout wording, in Hebrew RTL", async () => {
    const n = await push({
      title: "ירידת מחיר: משקה סויה",
      product: "משקה סויה ללא סוכר, 1 ליטר",
      store: "יוחננוף · מודיעין",
      price: "8.90",
      updated_at: "2026-10-07T03:40:00Z",
      url: "/product/1003?name=%D7%A1%D7%95%D7%99%D7%94",
      tag: "alert-5",
    });
    expect(n.title).toBe("ירידת מחיר: משקה סויה");
    const body = String(n.options.body);
    expect(body).toContain("משקה סויה ללא סוכר, 1 ליטר");
    expect(body).toContain("יוחננוף · מודיעין");
    expect(body).toContain("₪ 8.90");
    expect(body).toContain("07.10 06:40"); // Israel time, not UTC
    expect(body).toContain("המחיר הקובע הוא בקופה.");
    expect(n.options).toMatchObject({ lang: "he", dir: "rtl", tag: "alert-5" });
    expect(n.options.data).toEqual({ url: "/product/1003?name=%D7%A1%D7%95%D7%99%D7%94" });
  });

  it("uses a ready-made body when the server sends one, and a plain default when it sends nothing", async () => {
    expect((await push({ title: "x", body: "גוף מוכן" })).options.body).toBe("גוף מוכן");
    const empty = await push({});
    expect(empty.title).toContain("ירידת מחיר");
    expect(String(empty.options.body)).toContain("המחיר הקובע הוא בקופה.");
    expect(empty.options.data).toEqual({ url: "/alerts" });
  });

  it("survives a payload that is not JSON", async () => {
    const n = await push("טקסט רגיל", true);
    expect(n.options.body).toBe("טקסט רגיל");
  });

  it("never links to another site", async () => {
    const n = await push({ url: "https://evil.example/phish" });
    expect(n.options.data).toEqual({ url: "/alerts" });
  });
});

describe("notificationclick", () => {
  function click(worker: ReturnType<typeof loadWorker>, url: string) {
    let done: Promise<unknown> = Promise.resolve();
    const close = vi.fn();
    worker.handlers.notificationclick!({
      notification: { close, data: { url } },
      waitUntil: (p: Promise<unknown>) => {
        done = p;
      },
    });
    return { close, done: () => done };
  }

  it("closes the notification and opens the product when no window is open", async () => {
    const worker = loadWorker();
    const { close, done } = click(worker, "/product/1003?name=x");
    await done();
    expect(close).toHaveBeenCalled();
    expect(worker.openWindow).toHaveBeenCalledWith("/product/1003?name=x");
  });

  it("focuses an open window and sends it to the product", async () => {
    const focus = vi.fn(() => Promise.resolve());
    const navigate = vi.fn(() => Promise.resolve());
    const worker = loadWorker([{ url: `${ORIGIN}/compare`, focus, navigate }]);
    await click(worker, "/product/1003").done();
    expect(focus).toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith("/product/1003");
    expect(worker.openWindow).not.toHaveBeenCalled();
  });

  it("ignores a stored link that points off-site", async () => {
    const worker = loadWorker();
    await click(worker, "https://evil.example/").done();
    expect(worker.openWindow).toHaveBeenCalledWith("/alerts");
  });
});
