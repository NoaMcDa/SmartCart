/** The mock's list routes behave like the API's: id-stable PUT, per-item routes, item versions. */
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { API_BASE_URL } from "@/api/config";
import { resetMeMock } from "./handlers";
import { server } from "./node";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => resetMeMock());

type Row = { id: number; input_text: string; quantity: string; sort: number; updated_at: string };

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

describe("PUT /me/lists/{id} keeps ids", () => {
  it("updates named items in place, adds the rest, removes the missing, and leaves unchanged versions", async () => {
    const [milk, bread, eggs] = await seed();
    const put = await call("/me/lists/1", "PUT", {
      name: "x",
      items: [
        { id: bread!.id, input_text: "לחם", quantity: 1 }, // moved up, same content
        { id: milk!.id, input_text: "חלב", quantity: 3 }, // changed
        { input_text: "גבינה" }, // new
      ],
    });
    const items = put.body.items as Row[];
    expect(items.map((i) => i.input_text)).toEqual(["לחם", "חלב", "גבינה"]);
    expect(items[0]!.id).toBe(bread!.id);
    expect(items[1]!.id).toBe(milk!.id);
    expect(items[1]!.updated_at).not.toBe(milk!.updated_at);
    expect([eggs!.id, milk!.id, bread!.id]).not.toContain(items[2]!.id);
    // A second PUT of the same content changes no version.
    const again = await call("/me/lists/1", "PUT", {
      name: "x",
      items: items.map((i) => ({ id: i.id, input_text: i.input_text, quantity: i.quantity })),
    });
    expect((again.body.items as Row[]).map((i) => i.updated_at)).toEqual(
      items.map((i) => i.updated_at),
    );
  });
});

describe("per-item routes", () => {
  it("add, patch, delete, with versions and 409", async () => {
    const [milk] = await seed();
    const added = await call("/me/lists/1/items", "POST", { input_text: "גבינה" });
    expect(added.status).toBe(201);
    expect(added.body).toMatchObject({ sort: 3, quantity: "1", checked: false });

    const patched = await call(`/me/lists/1/items/${milk!.id}`, "PATCH", { checked: true });
    expect(patched.body.checked).toBe(true);
    expect(patched.body.updated_at).not.toBe(milk!.updated_at);
    // A no-op keeps the version.
    const noop = await call(`/me/lists/1/items/${milk!.id}`, "PATCH", { checked: true });
    expect(noop.body.updated_at).toBe(patched.body.updated_at);

    const stale = await call(`/me/lists/1/items/${milk!.id}`, "PATCH", {
      checked: false,
      expected_updated_at: milk!.updated_at,
    });
    expect(stale.status).toBe(409);
    expect(stale.body.current).toEqual(patched.body);
    // The version matches to the millisecond, as in the API.
    const ms = new Date(patched.body.updated_at).toISOString();
    expect(
      (
        await call(`/me/lists/1/items/${milk!.id}`, "PATCH", {
          checked: false,
          expected_updated_at: ms,
        })
      ).status,
    ).toBe(200);

    const current = (await call(`/me/lists/1/items/${milk!.id}`, "PATCH", {})).body;
    const staleDelete = await call(
      `/me/lists/1/items/${milk!.id}?expected_updated_at=${encodeURIComponent(milk!.updated_at)}`,
      "DELETE",
    );
    expect(staleDelete.status).toBe(409);
    const ok = await call(
      `/me/lists/1/items/${milk!.id}?expected_updated_at=${encodeURIComponent(current.updated_at)}`,
      "DELETE",
    );
    expect(ok.status).toBe(204);
    expect((await call(`/me/lists/1/items/${milk!.id}`, "DELETE")).status).toBe(404);
    expect((await call("/me/lists/9/items", "POST", {})).status).toBe(404);
  });

  it("never hands out the id of a deleted item again", async () => {
    await seed();
    const last = (await call("/me/lists/1/items", "POST", { input_text: "a" })).body as Row;
    await call(`/me/lists/1/items/${last.id}`, "DELETE");
    const next = (await call("/me/lists/1/items", "POST", { input_text: "b" })).body as Row;
    expect(next.id).toBeGreaterThan(last.id);
  });
});
