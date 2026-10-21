import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readJson, readRaw, removeKey, resetStorageMemoryForTests, writeJson } from "./storage";
import { PROFILE_KEY, readShopper, saveShopperProfile, shopperFromStored } from "./shopper";

beforeEach(() => {
  window.localStorage.clear();
  resetStorageMemoryForTests();
});
afterEach(() => {
  vi.restoreAllMocks();
});

/** A browser whose storage refuses writes (quota, some private windows). */
function blockWrites() {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new DOMException("quota", "QuotaExceededError");
  });
}

describe("storage helpers when storage misbehaves", () => {
  it("keeps a refused write in memory for the page view and reports it", () => {
    blockWrites();
    expect(writeJson("k", { a: 1 })).toBe(false);
    expect(readJson("k", null)).toEqual({ a: 1 });
    expect(readRaw("k")).toBe('{"a":1}');
  });

  it("a later successful write replaces the in-memory copy", () => {
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementationOnce(() => {
      throw new Error("blocked");
    });
    writeJson("k", 1);
    spy.mockRestore();
    expect(writeJson("k", 2)).toBe(true);
    expect(window.localStorage.getItem("k")).toBe("2");
    expect(readJson("k", null)).toBe(2);
  });

  it("removeKey forgets the in-memory copy", () => {
    blockWrites();
    writeJson("k", 1);
    removeKey("k");
    expect(readJson("k", "none")).toBe("none");
  });

  it("another tab's change to the key wins over the in-memory copy", () => {
    blockWrites();
    writeJson("k", "mine");
    vi.restoreAllMocks();
    window.localStorage.setItem("k", JSON.stringify("theirs"));
    window.dispatchEvent(new StorageEvent("storage", { key: "k" }));
    expect(readJson("k", null)).toBe("theirs");
  });

  it("survives a throwing getItem, garbage JSON and a non-JSON value", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    expect(readJson("k", "fallback")).toBe("fallback");
    expect(readRaw("k")).toBeNull();
    vi.restoreAllMocks();
    window.localStorage.setItem("k", "{not json");
    expect(readJson("k", "fallback")).toBe("fallback");
  });
});

describe("shopper profile in a window that refuses storage writes", () => {
  it("keeps what onboarding saved for the comparison of this page view", () => {
    blockWrites();
    saveShopperProfile({ neighborhood_lat: 32.085, neighborhood_lon: 34.782, radius_m: 9000 });
    const ctx = readShopper();
    expect(ctx.lat).toBe(32.085);
    expect(ctx.radiusM).toBe(9000);
    expect(ctx.usingDefaults).toBe(false);
  });

  it("builds on a stored profile that is garbage instead of spreading it", () => {
    window.localStorage.setItem(PROFILE_KEY, JSON.stringify("abc"));
    saveShopperProfile({ radius_m: 3000 });
    expect(JSON.parse(window.localStorage.getItem(PROFILE_KEY)!)).toEqual({ radius_m: 3000 });
  });
});

describe("shopperFromStored with damaged data", () => {
  it.each([5, "x", [1, 2], true])("treats %j as nothing stored", (bad) => {
    const ctx = shopperFromStored(bad as never, false);
    expect(ctx.usingDefaults).toBe(true);
    expect(ctx.radiusM).toBe(5000);
  });

  it("ignores a location that is not a real coordinate", () => {
    const nan = shopperFromStored({ neighborhood_lat: Number.NaN, neighborhood_lon: 35 }, false);
    const far = shopperFromStored({ neighborhood_lat: 400, neighborhood_lon: 35 }, false);
    expect(nan.lat).toBe(31.898);
    expect(far.lat).toBe(31.898);
  });

  it("never lets a negative travel cost turn a trip into a saving", () => {
    const ctx = shopperFromStored({ cost_per_km: "-3", extra_stop_value: "-10" }, false);
    expect(ctx.costPerKm).toBe(0);
    expect(ctx.extraStopValue).toBe(0);
  });
});
