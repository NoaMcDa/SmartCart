// @vitest-environment node
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { compare, optimize, parseList, search } from "@/api/client";
import { WEEKLY_BASKET } from "./fixtures";
import { server } from "./node";

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const location = { lat: 31.899, lon: 35.007, radius_m: 5000 };
const items = WEEKLY_BASKET.map((b) => ({ ...b, quantity: b.quantity }));

const sum = (xs: string[]) => xs.reduce((a, x) => a + Math.round(Number(x) * 100), 0) / 100;

describe("mock API (typed client + MSW handlers)", () => {
  it("/parse-list parses Hebrew quantities and flags ambiguous rows", async () => {
    const res = await parseList({ text: "חלב, 2 רסק עגבניות, סלמון, שמן זית, קולה זירו" });
    const [milk, paste, salmon, oil, unknown] = res.rows;
    expect(milk?.canonical?.display_name_he).toBe("חלב טרי 3%, 1 ליטר");
    expect(paste).toMatchObject({ quantity: "2", needs_confirmation: false });
    expect(paste?.canonical?.taxonomy_id).toBe("pantry.tomato_paste");
    expect(salmon?.is_weighed).toBe(true);
    expect(oil?.needs_confirmation).toBe(true);
    expect(oil?.candidates?.length).toBeGreaterThan(1);
    expect(unknown).toMatchObject({ not_found: true, canonical: null });
  });

  it("/compare returns the artboard stores, totals equal to their line items, complete baskets first", async () => {
    const res = await compare({ items, location, home_store_id: 103 });
    expect(res.home_store_total).toBe("446.00");
    const byName = Object.fromEntries(res.stores.map((s) => [s.store_name, s]));
    expect(byName["רמי לוי · מודיעין"]?.total).toBe("389.00");
    expect(byName["רמי לוי · מודיעין"]?.saving_vs_home).toBe("57.00");
    expect(byName["רמי לוי · מודיעין"]?.missing).toEqual([1002]);
    expect(byName["שופרסל דיל · מודיעין"]?.total).toBe("446.00");
    for (const s of res.stores) expect(sum(s.items.map((i) => i.line_total))).toBe(Number(s.total));
    const firstIncomplete = res.stores.findIndex((s) => s.missing.length > 0);
    expect(res.stores.slice(firstIncomplete).every((s) => s.missing.length > 0)).toBe(true);
    expect(res.disclaimer_he).toBe("המחיר הקובע הוא בקופה.");
  });

  it("/optimize returns single ₪389, split ₪371 and the home store ₪446 as minimum effort", async () => {
    const res = await optimize({
      items,
      location,
      home_store_id: 103,
      travel: { mode: "car", extra_stop_value: 25 },
    });
    expect(res.single.total).toBe("389.00");
    expect(res.single.breakdown?.net_saving).toBe("57.00");
    expect(res.single.recommended).toBe(true);
    expect(res.split?.total).toBe("371.00");
    expect(res.split?.stores.map((s) => s.item_ids.length)).toEqual([6, 3]);
    expect(res.split?.breakdown).toEqual({
      basket_saving: "75.00",
      travel_cost: "9.00",
      extra_stop_cost: "25.00",
      net_saving: "41.00",
    });
    expect(res.minimum_effort?.total).toBe("446.00");
  });

  it("/optimize drops the split when it does not beat min_split_saving", async () => {
    const res = await optimize({
      items,
      location,
      home_store_id: 103,
      travel: { extra_stop_value: 50 },
      min_split_saving: 25,
    });
    expect(res.split).toBeNull();
  });

  it("/compare answers 422 on an empty basket", async () => {
    await expect(compare({ items: [], location })).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
    });
  });

  it("/search finds by Hebrew substring", async () => {
    const res = await search("סויה");
    expect(res.hits[0]?.canonical.display_name_he).toBe("משקה סויה ללא סוכר, 1 ליטר");
  });
});
