import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { resetMeMock } from "@/mocks/handlers";
import { resetPhase2Mock } from "@/mocks/handlers.phase2";
import { server } from "@/mocks/node";
import { API_BASE_URL } from "./config";
import {
  acceptShare,
  addPushSubscription,
  ApiError,
  createAlert,
  createList,
  deleteAlert,
  getList,
  listAlerts,
  listMembers,
  lookupBarcode,
  nearestStore,
  priceHistory,
  shareList,
  swapSuggestions,
  updateList,
} from "./client";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  resetMeMock();
  resetPhase2Mock();
});

describe("phase 2 typed helpers", () => {
  it("priceHistory: 90 days by default, a store or the chain base price", async () => {
    const base = await priceHistory(1001);
    expect(base).toMatchObject({ canonical_id: 1001, store_id: null, days: 90 });
    expect(base.points.length).toBeGreaterThan(20);
    expect(base.promos?.length).toBeGreaterThan(0);
    const store = await priceHistory(1001, { storeId: 103, days: 30 });
    expect(store).toMatchObject({ store_id: 103, days: 30 });
  });

  it("alerts: create, list, delete (204 is success)", async () => {
    const created = await createAlert({
      canonical_id: 1003,
      threshold_unit_price: "0.90",
      flex_level: "close",
    });
    expect(created).toMatchObject({ canonical_id: 1003, flex_level: "close", active: true });
    expect(await listAlerts()).toHaveLength(1);
    await expect(deleteAlert(created.id)).resolves.toBeUndefined();
    expect(await listAlerts()).toEqual([]);
  });

  it("alerts: a refusal throws ApiError with the status", async () => {
    server.use(
      http.post(`${API_BASE_URL}/me/alerts`, () =>
        HttpResponse.json({ detail: "limit" }, { status: 402 }),
      ),
    );
    await expect(createAlert({ canonical_id: 1, threshold_unit_price: 1 })).rejects.toMatchObject({
      name: "ApiError",
      status: 402,
    });
    server.use(
      http.delete(`${API_BASE_URL}/me/alerts/:id`, () => new HttpResponse(null, { status: 500 })),
    );
    await expect(deleteAlert(1)).rejects.toBeInstanceOf(ApiError);
  });

  it("push subscriptions", async () => {
    await expect(
      addPushSubscription({ endpoint: "e", p256dh: "p", auth: "a" }),
    ).resolves.toMatchObject({ ok: true });
  });

  it("lists: create, read, update; share, members, accept", async () => {
    const list = await createList({ name: "x", is_recurring: false, items: [] });
    expect((await getList(list.id)).name).toBe("x");
    const updated = await updateList(list.id, {
      name: "x",
      is_recurring: false,
      items: [
        {
          canonical_id: 1001,
          input_text: "חלב",
          quantity: 2,
          flex_level: "any_brand",
          confirmed: true,
        },
      ],
    });
    expect(updated.items).toHaveLength(1);
    const invite = await shareList(list.id, "viewer");
    expect(invite).toMatchObject({ list_id: list.id, role: "viewer" });
    expect(invite.url).toBe(`/lists/accept/${invite.token}`);
    const members = await listMembers(list.id);
    expect(members.map((m) => m.is_owner)).toEqual([true, false]);
    expect(members[1]).toMatchObject({ user_id: null, role: "viewer" });
    expect((await acceptShare(invite.token)).id).toBe(list.id);
  });

  it("lookupBarcode sends the place and the store", async () => {
    let query = "";
    server.use(
      http.get(`${API_BASE_URL}/items/barcode/:code`, ({ request }) => {
        query = new URL(request.url).search;
        return HttpResponse.json({
          barcode: "x",
          found: false,
          generated_at: "2026-10-07T00:00:00Z",
          disclaimer_he: "d",
        });
      }),
    );
    await lookupBarcode("5901234123457", { lat: 31.898, lon: 35.01, radiusM: 3000, storeId: 103 });
    expect(query).toContain("lat=31.898");
    expect(query).toContain("lon=35.01");
    expect(query).toContain("radius_m=3000");
    expect(query).toContain("store_id=103");
    const found = await lookupBarcode("5901234123457", { lat: 31.898, lon: 35.01, storeId: 103 });
    expect(found).toMatchObject({ found: false });
  });

  it("swapSuggestions and nearestStore", async () => {
    const swaps = await swapSuggestions(101, {
      items: [{ canonical_id: 1004, quantity: 2 }],
      location: { lat: 31.9, lon: 35 },
    });
    expect(swaps.store_id).toBe(101);
    expect(swaps.swaps.map((s) => s.saving)).toEqual(["5.00", "4.80", "1.20"]);
    expect(swaps.top_swap?.saving).toBe("5.00");
    expect((await nearestStore("7290058140886", 31.9, 35)).chain_name).toBe("רמי לוי");
  });
});
