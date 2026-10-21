/**
 * Per-item writes of a shared list (polling mode): the merge rule when the API answers 409 with
 * the item as another person left it. Against the MSW mock of the per-item routes, which keeps a
 * version (`updated_at`) per item and checks `expected_updated_at` like the API.
 */
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import { resetMeMock } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { MAX_MERGE_ATTEMPTS, mergeVerdict, writeItem } from "./itemWrites";
import { itemsOf, type SharedItem } from "./listSync";
import type { QueuedEdit } from "./offlineQueue";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => resetMeMock());

type Row = { id: number; quantity: string; checked: boolean; updated_at: string };

async function api(path: string, method: string, body?: unknown) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return res.status === 204 ? null : res.json();
}

const WEEK = {
  name: "הקנייה",
  is_recurring: false,
  items: [
    { canonical_id: 1001, input_text: "חלב", quantity: 2 },
    { canonical_id: 1004, input_text: "רסק", quantity: 1 },
  ],
};
const MILK = 1001; // list 1, first item (the mock numbers items list id * 1000 + n)

async function seed(): Promise<Row> {
  await api("/me/lists", "POST", WEEK);
  return (await api("/me/lists/1", "GET")).items[0];
}

const item = (over: Partial<SharedItem>): SharedItem => ({
  id: MILK,
  canonicalId: 1001,
  name: "חלב",
  quantity: 2,
  flexLevel: "any_brand",
  confirmed: true,
  checked: false,
  sort: 0,
  updatedAt: null,
  version: "v2",
  ...over,
});

describe("mergeVerdict: does the person's edit still make sense on the item as it is now", () => {
  const tick: QueuedEdit = {
    kind: "checked",
    itemId: MILK,
    checked: true,
    from: false,
    base: "v1",
  };
  const qty: QueuedEdit = { kind: "quantity", itemId: MILK, quantity: 3, from: 2, base: "v1" };

  it("is already done when the item has the value the person wanted", () => {
    expect(mergeVerdict(tick, item({ checked: true }))).toBe("already");
    expect(mergeVerdict(qty, item({ quantity: 3 }))).toBe("already");
  });

  it("is sent again when somebody changed another field, not the one the person edited", () => {
    expect(mergeVerdict(tick, item({ quantity: 5 }))).toBe("reapply"); // checked is still false
    expect(mergeVerdict(qty, item({ checked: true }))).toBe("reapply"); // quantity is still 2
  });

  it("gives way when somebody changed the same field to something else", () => {
    expect(mergeVerdict(qty, item({ quantity: 5 }))).toBe("superseded");
    // The person unticked (it was ticked); somebody else only changed the quantity.
    const untick: QueuedEdit = { kind: "checked", itemId: MILK, checked: false, from: true };
    expect(mergeVerdict(untick, item({ checked: true, quantity: 9 }))).toBe("reapply");
  });

  it("keeps an item somebody changed when the person removed it", () => {
    expect(mergeVerdict({ kind: "remove", itemId: MILK, base: "v1" }, item({}))).toBe("superseded");
  });

  it("without what the person saw (an edit queued by an older version) sends the edit again", () => {
    const old: QueuedEdit = { kind: "quantity", itemId: MILK, quantity: 3 };
    expect(mergeVerdict(old, item({ quantity: 5 }))).toBe("reapply");
  });
});

describe("writeItem against the per-item routes", () => {
  it("writes with the version the person saw, and answers the saved row", async () => {
    const milk = await seed();
    const seen: string[] = [];
    server.events.on("request:start", async ({ request }) => {
      if (request.method === "PATCH") seen.push(await request.clone().text());
    });
    const out = await writeItem(1, {
      kind: "checked",
      itemId: milk.id,
      checked: true,
      from: false,
      base: milk.updated_at,
    });
    server.events.removeAllListeners();
    expect(out).toMatchObject({ saved: true, superseded: false });
    expect(out.item).toMatchObject({ id: milk.id, checked: true });
    expect(out.item!.version).not.toBe(milk.updated_at); // the item has a new version
    expect(JSON.parse(seen[0]!)).toEqual({ checked: true, expected_updated_at: milk.updated_at });
  });

  it("sends the version back exactly as the server wrote it, microseconds and all", async () => {
    const milk = await seed();
    expect(milk.updated_at).toMatch(/\.\d{6}Z$/); // the mock, like the API, keeps microseconds
    // Another person changed nothing: the stored string matches itself.
    const out = await writeItem(1, {
      kind: "quantity",
      itemId: milk.id,
      quantity: 4,
      from: 2,
      base: milk.updated_at,
    });
    expect(out).toMatchObject({ saved: true });
  });

  it("an edit on an item somebody changed in another field is sent again and both changes stay", async () => {
    const milk = await seed();
    await api(`/me/lists/1/items/${milk.id}`, "PATCH", { quantity: 5 }); // somebody else
    const out = await writeItem(1, {
      kind: "checked",
      itemId: milk.id,
      checked: true,
      from: false,
      base: milk.updated_at, // stale
    });
    expect(out).toMatchObject({ saved: true, superseded: false });
    expect(out.item).toMatchObject({ quantity: 5, checked: true });
    const now = (await api("/me/lists/1", "GET")).items[0];
    expect([now.quantity, now.checked]).toEqual(["5", true]);
  });

  it("an edit somebody else already made is not written again and says nothing", async () => {
    const milk = await seed();
    await api(`/me/lists/1/items/${milk.id}`, "PATCH", { checked: true });
    const out = await writeItem(1, {
      kind: "checked",
      itemId: milk.id,
      checked: true,
      from: false,
      base: milk.updated_at,
    });
    expect(out).toMatchObject({ saved: false, superseded: false });
    expect(out.item).toMatchObject({ checked: true });
  });

  it("the same field changed by somebody else wins, and the person is told", async () => {
    const milk = await seed();
    const theirs = await api(`/me/lists/1/items/${milk.id}`, "PATCH", { quantity: 5 });
    const out = await writeItem(1, {
      kind: "quantity",
      itemId: milk.id,
      quantity: 3,
      from: 2,
      base: milk.updated_at,
    });
    expect(out).toMatchObject({ saved: false, superseded: true });
    expect(out.item).toMatchObject({ quantity: 5, version: theirs.updated_at });
    expect((await api("/me/lists/1", "GET")).items[0].quantity).toBe("5"); // untouched by us
  });

  it("a removal of an item somebody changed keeps the item", async () => {
    const milk = await seed();
    await api(`/me/lists/1/items/${milk.id}`, "PATCH", { checked: true });
    const out = await writeItem(1, { kind: "remove", itemId: milk.id, base: milk.updated_at });
    expect(out).toMatchObject({ saved: false, superseded: true });
    expect(out.item).toMatchObject({ id: milk.id });
    expect((await api("/me/lists/1", "GET")).items).toHaveLength(2);
    // On the current version the same removal goes through.
    const again = await writeItem(1, { kind: "remove", itemId: milk.id, base: out.item!.version });
    expect(again).toEqual({ item: null, saved: true, superseded: false });
    expect((await api("/me/lists/1", "GET")).items).toHaveLength(1);
  });

  it("an item somebody removed: removing it again is done, editing it is dropped with a note", async () => {
    const milk = await seed();
    await api(`/me/lists/1/items/${milk.id}`, "DELETE");
    expect(await writeItem(1, { kind: "remove", itemId: milk.id, base: milk.updated_at })).toEqual({
      item: null,
      saved: false,
      superseded: false,
    });
    expect(
      await writeItem(1, {
        kind: "checked",
        itemId: milk.id,
        checked: true,
        from: false,
        base: milk.updated_at,
      }),
    ).toEqual({ item: null, saved: false, superseded: true });
  });

  it("an edit without a version is applied whatever the item looks like", async () => {
    const milk = await seed();
    await api(`/me/lists/1/items/${milk.id}`, "PATCH", { quantity: 5 });
    const out = await writeItem(1, { kind: "quantity", itemId: milk.id, quantity: 3 });
    expect(out).toMatchObject({ saved: true });
    expect(out.item).toMatchObject({ quantity: 3 });
  });

  it("gives up, with the note, when the item keeps changing under it", async () => {
    const milk = await seed();
    let calls = 0;
    server.use(
      http.patch(`${API_BASE_URL}/me/lists/:id/items/:itemId`, () => {
        calls += 1;
        return HttpResponse.json(
          {
            detail: "changed",
            current: {
              ...milk,
              quantity: "2",
              checked: false,
              flex_level: "any_brand",
              confirmed: true,
              sort: 0,
              updated_at: `2030-01-01T00:00:0${calls}.000000Z`,
            },
          },
          { status: 409 },
        );
      }),
    );
    const out = await writeItem(1, {
      kind: "checked",
      itemId: milk.id,
      checked: true,
      from: false,
      base: milk.updated_at,
    });
    expect(calls).toBe(MAX_MERGE_ATTEMPTS);
    expect(out).toMatchObject({ saved: false, superseded: true });
  });

  it("lets a refusal or a lost connection through for the caller to tell apart", async () => {
    const milk = await seed();
    server.use(
      http.patch(`${API_BASE_URL}/me/lists/:id/items/:itemId`, () =>
        HttpResponse.json({}, { status: 403 }),
      ),
    );
    await expect(
      writeItem(1, { kind: "checked", itemId: milk.id, checked: true }),
    ).rejects.toMatchObject({ status: 403 });
    server.use(
      http.patch(`${API_BASE_URL}/me/lists/:id/items/:itemId`, () => HttpResponse.error()),
    );
    await expect(
      writeItem(1, { kind: "checked", itemId: milk.id, checked: true }),
    ).rejects.toBeInstanceOf(TypeError);
  });

  it("adds an item with POST and answers the saved row with its id and version", async () => {
    await seed();
    const out = await writeItem(1, {
      kind: "add",
      itemId: -5,
      canonicalId: 1008,
      name: "ביצים",
      quantity: 2,
    });
    expect(out.saved).toBe(true);
    expect(out.item).toMatchObject({ name: "ביצים", quantity: 2, sort: 2 });
    expect(out.item!.id).toBeGreaterThan(0);
    expect(out.item!.version).toMatch(/Z$/);
    expect(itemsOf((await api("/me/lists/1", "GET")) as never).map((i) => i.name)).toEqual([
      "חלב",
      "רסק",
      "ביצים",
    ]);
  });

  it("sends the add's client id, so sending the same add again returns the saved row", async () => {
    await seed();
    const bodies: unknown[] = [];
    server.events.on("request:start", async ({ request }) => {
      if (request.method === "POST" && request.url.endsWith("/items")) {
        bodies.push(await request.clone().json());
      }
    });
    const add: QueuedEdit = {
      kind: "add",
      itemId: -5,
      canonicalId: 1008,
      name: "ביצים",
      quantity: 2,
      clientId: "0f6a6f0e-7c0b-4a39-a1a5-5d52e3a1b001",
    };
    const first = await writeItem(1, add);
    const again = await writeItem(1, add);
    server.events.removeAllListeners();
    expect(bodies).toMatchObject([
      { client_id: "0f6a6f0e-7c0b-4a39-a1a5-5d52e3a1b001" },
      { client_id: "0f6a6f0e-7c0b-4a39-a1a5-5d52e3a1b001" },
    ]);
    expect(again.item).toEqual(first.item);
    expect(((await api("/me/lists/1", "GET")) as { items: unknown[] }).items).toHaveLength(3);
  });

  it("an add queued before the key existed is sent without one", async () => {
    await seed();
    const add: QueuedEdit = { kind: "add", itemId: -5, canonicalId: 1008, name: "x", quantity: 1 };
    await writeItem(1, add);
    await writeItem(1, add);
    expect(((await api("/me/lists/1", "GET")) as { items: unknown[] }).items).toHaveLength(4);
  });
});
