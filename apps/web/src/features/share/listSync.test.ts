import { describe, expect, it } from "vitest";
import type { ListItem } from "@/state/list";
import {
  applyChange,
  changeFromPayload,
  itemFromRow,
  itemsOf,
  serverBody,
  type SharedItem,
} from "./listSync";
import { localListToServer } from "./sharedLists";

const item = (over: Partial<SharedItem> & { id: number }): SharedItem => ({
  canonicalId: 1001,
  name: "חלב",
  quantity: 1,
  flexLevel: "any_brand",
  confirmed: true,
  sort: over.id,
  updatedAt: null,
  ...over,
});

describe("merge rule: per item, last write wins, nothing else touched", () => {
  const base = [item({ id: 1, name: "חלב" }), item({ id: 2, name: "ביצים", canonicalId: 1008 })];

  it("two people editing different items lose nothing", () => {
    const a = applyChange(base, {
      type: "upsert",
      item: item({ id: 1, name: "חלב", quantity: 3 }),
    });
    const b = applyChange(a, { type: "upsert", item: item({ id: 2, name: "ביצים", quantity: 2 }) });
    expect(b.map((i) => [i.id, i.quantity])).toEqual([
      [1, 3],
      [2, 2],
    ]);
  });

  it("two people editing the same item end with the latest change, whatever the order of the other fields", () => {
    const first = applyChange(base, {
      type: "upsert",
      item: item({ id: 1, quantity: 2, updatedAt: 1000 }),
    });
    const second = applyChange(first, {
      type: "upsert",
      item: item({ id: 1, quantity: 5, updatedAt: 2000 }),
    });
    expect(second.find((i) => i.id === 1)?.quantity).toBe(5);
    // The same two changes arriving in the other order give the same result: deterministic.
    const reversed = applyChange(
      applyChange(base, { type: "upsert", item: item({ id: 1, quantity: 5, updatedAt: 2000 }) }),
      { type: "upsert", item: item({ id: 1, quantity: 2, updatedAt: 1000 }) },
    );
    expect(reversed.find((i) => i.id === 1)?.quantity).toBe(5);
  });

  it("without timestamps the change that arrives last wins", () => {
    const a = applyChange(base, { type: "upsert", item: item({ id: 1, quantity: 2 }) });
    const b = applyChange(a, { type: "upsert", item: item({ id: 1, quantity: 4 }) });
    expect(b.find((i) => i.id === 1)?.quantity).toBe(4);
  });

  it("an insert that replays after a reconnect updates the item instead of duplicating it", () => {
    const again = applyChange(base, {
      type: "upsert",
      item: item({ id: 2, name: "ביצים", canonicalId: 1008 }),
    });
    expect(again).toHaveLength(2);
    const replayed = applyChange(again, { type: "upsert", item: item({ id: 3, name: "לחם" }) });
    expect(
      applyChange(replayed, { type: "upsert", item: item({ id: 3, name: "לחם" }) }),
    ).toHaveLength(3);
  });

  it("a delete removes only that item", () => {
    expect(applyChange(base, { type: "remove", id: 1 }).map((i) => i.id)).toEqual([2]);
    expect(applyChange(base, { type: "remove", id: 99 })).toHaveLength(2);
  });

  it("a full reload replaces the set", () => {
    expect(
      applyChange(base, { type: "replace", items: [item({ id: 7 })] }).map((i) => i.id),
    ).toEqual([7]);
  });
});

describe("rows and Realtime payloads", () => {
  it("reads a list_items row, with a name for items that have none", () => {
    expect(
      itemFromRow({
        id: "5",
        canonical_id: "1004",
        input_text: "  רסק עגבניות ",
        quantity: "2.5",
        flex_level: "close",
        sort: 3,
      }),
    ).toMatchObject({
      id: 5,
      canonicalId: 1004,
      name: "רסק עגבניות",
      quantity: 2.5,
      flexLevel: "close",
      sort: 3,
    });
    expect(itemFromRow({ id: 6, canonical_id: 1001, input_text: null })?.name).toBe(
      "מוצר מס' 1001",
    );
    expect(itemFromRow({ id: 7, flex_level: "weird", quantity: -1 })).toMatchObject({
      flexLevel: "any_brand",
      quantity: 1,
      name: "פריט",
    });
    expect(itemFromRow({})).toBeNull();
  });

  it("maps INSERT, UPDATE and DELETE", () => {
    expect(
      changeFromPayload({ eventType: "INSERT", new: { id: 1, input_text: "חלב" } }),
    ).toMatchObject({
      type: "upsert",
    });
    expect(changeFromPayload({ eventType: "UPDATE", new: { id: 1, quantity: 2 } })).toMatchObject({
      type: "upsert",
    });
    expect(changeFromPayload({ eventType: "DELETE", old: { id: 4 } })).toEqual({
      type: "remove",
      id: 4,
    });
    expect(changeFromPayload({ eventType: "DELETE", old: {} })).toBeNull();
  });

  it("reads a server list sorted, and writes it back whole", () => {
    const items = itemsOf({
      items: [
        {
          id: 2,
          sort: 1,
          canonical_id: 1002,
          confirmed: true,
          flex_level: "exact",
          input_text: "קוטג'",
          quantity: "1",
        },
        {
          id: 1,
          sort: 0,
          canonical_id: 1001,
          confirmed: true,
          flex_level: "any_brand",
          input_text: "חלב",
          quantity: "2",
        },
      ],
    });
    expect(items.map((i) => i.id)).toEqual([1, 2]);
    expect(serverBody("הקנייה", items)).toEqual({
      name: "הקנייה",
      is_recurring: false,
      items: [
        {
          canonical_id: 1001,
          input_text: "חלב",
          quantity: 2,
          flex_level: "any_brand",
          confirmed: true,
        },
        {
          canonical_id: 1002,
          input_text: "קוטג'",
          quantity: 1,
          flex_level: "exact",
          confirmed: true,
        },
      ],
    });
  });
});

describe("local list to server copy", () => {
  const row = (over: Partial<ListItem>): ListItem => ({
    id: "r1",
    inputText: "חלב",
    canonical: {
      canonical_id: 1001,
      display_name_he: "חלב טרי 3%, 1 ליטר",
      taxonomy_id: "dairy.milk",
      base_unit: "100ml",
    },
    candidates: [],
    quantity: 2,
    unit: null,
    isWeighed: false,
    flexLevel: "close",
    allow: [],
    exactItemId: null,
    needsConfirmation: false,
    notFound: false,
    confidence: 1,
    ...over,
  });

  it("sends names, quantities and levels for recognised rows only", () => {
    const body = localListToServer("הקנייה השבועית", [
      row({}),
      row({ id: "r2", notFound: true, canonical: null }),
      row({ id: "r3", needsConfirmation: true }),
    ]);
    expect(body.items).toEqual([
      {
        canonical_id: 1001,
        input_text: "חלב טרי 3%, 1 ליטר",
        quantity: 2,
        flex_level: "close",
        confirmed: true,
      },
      {
        canonical_id: 1001,
        input_text: "חלב טרי 3%, 1 ליטר",
        quantity: 2,
        flex_level: "close",
        confirmed: false,
      },
    ]);
    // Nothing about the person: no location, no preferences.
    expect(JSON.stringify(body)).not.toMatch(/lat|lon|radius|club|diet/);
  });
});
