import { describe, expect, it } from "vitest";
import { createResourceCache } from "./resource";

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const tick = () => new Promise((r) => setTimeout(r, 0));

describe("createResourceCache", () => {
  it("a slow older response does not overwrite the newer one after a reload", async () => {
    const calls = [deferred<string>(), deferred<string>()];
    let n = 0;
    const cache = createResourceCache<string, string>(() => calls[n++]!.promise);
    cache.load("k", "in");
    cache.load("k", "in", true); // the user pressed retry while the first was slow
    calls[1]!.resolve("new");
    await tick();
    calls[0]!.resolve("old");
    await tick();
    expect(cache.get("k")).toEqual({ status: "success", data: "new" });
  });

  it("an old failure cannot replace a newer success either", async () => {
    const calls = [deferred<string>(), deferred<string>()];
    let n = 0;
    const cache = createResourceCache<string, string>(() => calls[n++]!.promise);
    cache.load("k", "in");
    cache.load("k", "in", true);
    calls[1]!.resolve("fresh");
    await tick();
    calls[0]!.reject(new Error("late"));
    await tick();
    expect(cache.get("k")).toEqual({ status: "success", data: "fresh" });
  });

  it("a response that lands after clear() does not come back", async () => {
    const d = deferred<string>();
    const cache = createResourceCache<string, string>(() => d.promise);
    cache.load("k", "in");
    cache.clear();
    d.resolve("stale");
    await tick();
    expect(cache.get("k")).toEqual({ status: "idle" });
  });

  it("keeps the previous data visible while a reload runs", async () => {
    const first = deferred<string>();
    const second = deferred<string>();
    const queue = [first, second];
    const cache = createResourceCache<string, string>(() => queue.shift()!.promise);
    cache.load("k", "in");
    first.resolve("a");
    await tick();
    cache.load("k", "in", true);
    expect(cache.get("k")).toEqual({ status: "loading", data: "a" });
    second.resolve("b");
    await tick();
    expect(cache.get("k")).toEqual({ status: "success", data: "b" });
  });
});
