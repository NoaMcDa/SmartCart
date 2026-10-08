/**
 * The phase 3 mock routes through the typed client: the shapes the lead checks against
 * services/api (`POST /me/spend`, `GET /me/spend?month=`, `POST /parse-recipe`).
 */
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { ApiError, getSpend, parseRecipe, postSpend, type SpendEntry } from "@/api/client";
import { mockSpendEntries, resetPhase3Mock } from "./handlers.phase3";
import { server } from "./node";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(resetPhase3Mock);

const entry = (over: Partial<SpendEntry> = {}): SpendEntry => ({
  id: "a1",
  date: "2026-10-08",
  store_id: 101,
  store_name: "רמי לוי · מודיעין",
  total: 371.4,
  item_count: 9,
  plan: "split",
  ...over,
});

describe("POST /me/spend and GET /me/spend", () => {
  it("stores an entry and returns it", async () => {
    expect(await postSpend(entry())).toEqual(entry());
    expect(mockSpendEntries()).toEqual([entry()]);
  });

  it("is idempotent on the id", async () => {
    await postSpend(entry());
    await postSpend(entry({ total: 400 }));
    expect(mockSpendEntries()).toHaveLength(1);
    expect(mockSpendEntries()[0]!.total).toBe(400);
  });

  it("lists a month with its total and the budget (null in the mock)", async () => {
    await postSpend(entry({ id: "a", date: "2026-10-02", total: 100.1 }));
    await postSpend(entry({ id: "b", date: "2026-10-20", total: 200.2 }));
    await postSpend(entry({ id: "c", date: "2026-09-30", total: 999 }));
    const res = await getSpend("2026-10");
    expect(Object.keys(res).sort()).toEqual(["budget", "entries", "month", "total"]);
    expect(res.month).toBe("2026-10");
    expect(res.entries.map((e) => e.id)).toEqual(["a", "b"]);
    expect(res.total).toBe(300.3);
    expect(res.budget).toBeNull();
    expect((await getSpend("2026-08")).entries).toEqual([]);
  });

  it("rejects a malformed entry and a malformed month with 422", async () => {
    await expect(postSpend(entry({ date: "8.10.2026" }))).rejects.toMatchObject({ status: 422 });
    await expect(postSpend(entry({ plan: "triple" as never }))).rejects.toBeInstanceOf(ApiError);
    await expect(getSpend("2026-13")).rejects.toMatchObject({ status: 422 });
    expect(mockSpendEntries()).toEqual([]);
  });
});

describe("POST /parse-recipe", () => {
  it("reads pasted text into parse-list rows, with the lines it could not match", async () => {
    const res = await parseRecipe({
      text: "פסטה ברוטב עגבניות\n500 גרם פסטה\n2 רסק עגבניות\nחופן בזיליקום",
    });
    expect(Object.keys(res).sort()).toEqual(["items", "servings", "title", "unresolved"]);
    expect(res.title).toBe("פסטה ברוטב עגבניות");
    expect(res.servings).toBe(4);
    expect(res.items.map((r) => [r.input_text, r.quantity])).toEqual([
      ["פסטה", "1"],
      ["2 רסק עגבניות", "2"],
    ]);
    // Rows have the /parse-list shape.
    expect(res.items[0]).toMatchObject({
      canonical: { canonical_id: expect.any(Number) },
      not_found: false,
      confidence: expect.any(Number),
    });
    expect(res.unresolved).toEqual(["חופן בזיליקום"]);
  });

  it("reads the servings the recipe states, and scales to the ones asked for", async () => {
    const stated = await parseRecipe({ text: "מתכון ל-6 מנות\n2 רסק עגבניות" });
    expect(stated.servings).toBe(6);
    const asked = await parseRecipe({ text: "2 רסק עגבניות\nפסטה\n3 מנות", servings: 6 });
    expect(asked.servings).toBe(6);
    expect(asked.items[0]!.quantity).toBe("4"); // 2 for 3 servings -> 4 for 6
  });

  it("reads a URL (a fixed recipe in the mock)", async () => {
    const res = await parseRecipe({ url: "https://example.com/pasta" });
    expect(res.title).toBe("פסטה ברוטב עגבניות");
    expect(res.items.length).toBeGreaterThan(2);
    expect(res.unresolved.length).toBeGreaterThan(0);
  });

  it("422 without text or url, and for a url that is not http(s)", async () => {
    await expect(parseRecipe({})).rejects.toMatchObject({ status: 422 });
    await expect(parseRecipe({ url: "javascript:alert(1)" })).rejects.toMatchObject({
      status: 422,
    });
  });
});
