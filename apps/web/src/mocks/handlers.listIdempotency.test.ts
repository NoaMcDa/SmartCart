/** The mock's per-item routes behave like the API's: idempotent add, and the list's own updated_at. */
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { API_BASE_URL } from "@/api/config";
import { resetMeMock } from "./handlers";
import { server } from "./node";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => resetMeMock());

type Row = { id: number; input_text: string; client_id: string | null };

async function call(path: string, method: string, body?: unknown) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return { status: res.status, body: res.status === 204 ? null : await res.json() };
}

const seed = async () =>
  (
    await call("/me/lists", "POST", {
      name: "x",
      items: [{ input_text: "חלב", quantity: 2 }, { input_text: "לחם" }, { input_text: "ביצים" }],
    })
  ).body.items as Row[];

describe("idempotent add", () => {
  it("a repeat of an add with the same client_id answers 200 with the stored item", async () => {
    await seed();
    const body = { input_text: "גבינה", client_id: "5b0a8a8e-33c3-4f0e-9d5b-0d1f6b2a7c11" };
    const first = await call("/me/lists/1/items", "POST", body);
    const again = await call("/me/lists/1/items", "POST", { ...body, input_text: "אחר" });
    expect([first.status, again.status]).toEqual([201, 200]);
    expect(again.body).toEqual(first.body);
    expect(first.body.client_id).toBe(body.client_id);
    expect(((await call("/me/lists/1", "GET")).body.items as Row[]).length).toBe(4);
  });

  it("without a client_id every POST adds", async () => {
    await seed();
    expect((await call("/me/lists/1/items", "POST", { input_text: "a" })).status).toBe(201);
    expect((await call("/me/lists/1/items", "POST", { input_text: "a" })).status).toBe(201);
    expect(((await call("/me/lists/1", "GET")).body.items as Row[]).length).toBe(5);
  });

  it("PUT ignores a client_id in the body and keeps the one a kept item has", async () => {
    await seed();
    const kept = (
      await call("/me/lists/1/items", "POST", { input_text: "גבינה", client_id: "key-1" })
    ).body as Row;
    const put = await call("/me/lists/1", "PUT", {
      name: "x",
      items: [
        { id: kept.id, input_text: "גבינה", client_id: "other" },
        { input_text: "חדש", client_id: "key-2" },
      ],
    });
    expect((put.body.items as Row[]).map((i) => i.client_id)).toEqual(["key-1", null]);
  });
});

describe("the list's own updated_at follows its items", () => {
  const stamp = async () => (await call("/me/lists/1", "GET")).body.updated_at as string;
  const later = () => new Promise((r) => setTimeout(r, 5));

  it("moves when an item is added, changed or removed, and not for a change that changes nothing", async () => {
    const [milk] = await seed();
    let last = await stamp();
    await later();
    const added = (await call("/me/lists/1/items", "POST", { input_text: "גבינה" })).body as Row;
    expect(Date.parse(await stamp())).toBeGreaterThan(Date.parse(last));

    last = await stamp();
    await later();
    await call(`/me/lists/1/items/${milk!.id}`, "PATCH", { checked: false }); // nothing changes
    expect(await stamp()).toBe(last);
    await call(`/me/lists/1/items/${milk!.id}`, "PATCH", { checked: true });
    expect(Date.parse(await stamp())).toBeGreaterThan(Date.parse(last));

    last = await stamp();
    await later();
    await call(`/me/lists/1/items/${added.id}`, "DELETE");
    expect(Date.parse(await stamp())).toBeGreaterThan(Date.parse(last));
  });
});
