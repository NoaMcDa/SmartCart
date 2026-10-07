// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("API client with NEXT_PUBLIC_API_MOCK=1", () => {
  it("answers from the MSW handlers in process, without touching the network", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MOCK", "1");
    const networkFetch = vi.fn(() => Promise.reject(new Error("network used")));
    vi.stubGlobal("fetch", networkFetch);
    vi.resetModules();
    const { optimize, health } = await import("./client");

    await expect(health()).resolves.toEqual({ status: "ok", version: "0.1.0-mock" });
    const res = await optimize({
      items: [{ canonical_id: 1001, quantity: 2 }],
      location: { lat: 31.899, lon: 35.007 },
      home_store_id: 103,
    });
    expect(res.single.stores[0]?.store.store_name).toBe("רמי לוי · מודיעין");
    expect(res.minimum_effort?.total).toBe("446.00");
    expect(networkFetch).not.toHaveBeenCalled();
  });

  it("deleteMe and nearestStore are typed helpers over the phase 2 routes", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MOCK", "1");
    vi.resetModules();
    const { deleteMe, nearestStore } = await import("./client");
    await expect(deleteMe()).resolves.toMatchObject({ ok: true });
    const store = await nearestStore("7290058140886", 31.898, 35.01);
    expect(store).toMatchObject({ chain_name: "רמי לוי", store_id: 101 });
  });

  it("deleteMe throws ApiError on a failed response", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MOCK", "");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json({ detail: "boom" }, { status: 500 })),
    );
    vi.resetModules();
    const { deleteMe, ApiError } = await import("./client");
    await expect(deleteMe()).rejects.toBeInstanceOf(ApiError);
  });

  it("uses the network when the mock is off", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MOCK", "");
    const networkFetch = vi.fn(async () => Response.json({ status: "ok", version: "1.2.3" }));
    vi.stubGlobal("fetch", networkFetch);
    vi.resetModules();
    const { health } = await import("./client");
    await expect(health()).resolves.toEqual({ status: "ok", version: "1.2.3" });
    expect(networkFetch).toHaveBeenCalledOnce();
  });
});
