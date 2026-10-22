import { describe, expect, it } from "vitest";
import type { BasketItemInput, CompareResponse, PricedItem } from "@/api/client";
import { compareFixture } from "@/mocks/fixtures";
import { applyPacksToCompare } from "@/mocks/packs";
import { itemFromRow, type ListItem } from "@/state/list";
import { parseRow } from "@/mocks/parseRow";
import { readShopper } from "@/state/shopper";
import {
  FAMILY_FACTOR,
  VALUE_PACK_SNOOZE_DAYS,
  findValuePack,
  packEligibleRows,
  packRequests,
  valuePacksFrom,
  visibleValuePacks,
} from "./valuePacks";
import { NOW, dismissal, doc } from "./fixtures";

const SHOPPER = readShopper();

const row = (text: string, quantity = 1, patch: Partial<ListItem> = {}): ListItem => ({
  ...itemFromRow({ ...parseRow(text), quantity: String(quantity) }, {}),
  ...patch,
});

const priced = (q: number): CompareResponse =>
  applyPacksToCompare(compareFixture(103), [{ canonical_id: 1009, quantity: q }]);

const eggsLine = (res: CompareResponse, storeId: number): PricedItem =>
  res.stores.find((s) => s.store_id === storeId)!.items.find((l) => l.canonical_id === 1009)!;

describe("the mock's pack choice (what findValuePack reads)", () => {
  it("sells a 12-pack for one pack and a tray of 30 for a big quantity", () => {
    const one = eggsLine(priced(1), 103);
    expect(one).toMatchObject({ pack_units: "12", packs: "1", shelf_price: "15.90" });
    const family = eggsLine(priced(5), 103);
    expect(family).toMatchObject({ pack_units: "30", packs: "2" });
    expect(Number(family.effective_unit_price)).toBeLessThan(Number(one.effective_unit_price));
  });

  it("does not touch a basket without eggs", () => {
    const res = compareFixture(103);
    expect(applyPacksToCompare(res, [{ canonical_id: 1001, quantity: 1 }])).toBe(res);
  });
});

describe("findValuePack", () => {
  const store = { store_id: 103, store_name: "שופרסל דיל · מודיעין", chain_name: "שופרסל" };
  const base = eggsLine(priced(1), 103);
  const probe = eggsLine(priced(5), 103);

  it("reports a different, larger pack with a lower unit price, and the quantity that buys one", () => {
    const pack = findValuePack(base, probe, store, 1)!;
    expect(pack.larger.packUnits).toBe(30);
    expect(pack.current.packUnits).toBe(12);
    expect(pack.unitSavingPct).toBeGreaterThanOrEqual(5);
    expect(pack.larger.unitPrice).toBeLessThan(pack.current.unitPrice);
    expect(pack.quantityToSet).toBe(2.5); // 30 eggs = 2.5 quantities of 12
    expect(pack.store).toEqual({ id: 103, name: "שופרסל דיל · מודיעין", chain: "שופרסל" });
    expect(pack.larger.updatedAt).toBe(probe.price_valid_from);
  });

  it("is null for the same shelf item", () => {
    expect(findValuePack(base, base, store, 1)).toBeNull();
  });

  it("never suggests a substitute, on either side", () => {
    expect(findValuePack({ ...base, is_substitute: true }, probe, store, 1)).toBeNull();
    expect(findValuePack(base, { ...probe, is_substitute: true }, store, 1)).toBeNull();
  });

  it("needs a pack at least 25% larger", () => {
    expect(findValuePack(base, { ...probe, pack_units: "14" }, store, 1)).toBeNull();
    expect(findValuePack(base, { ...probe, pack_units: "15" }, store, 1)).not.toBeNull();
  });

  it("needs a unit price at least 5% lower", () => {
    const dear = {
      ...probe,
      effective_unit_price: (Number(base.effective_unit_price) * 0.96).toFixed(2),
    };
    expect(findValuePack(base, dear, store, 1)).toBeNull();
    const cheap = {
      ...probe,
      effective_unit_price: (Number(base.effective_unit_price) * 0.9).toFixed(2),
    };
    expect(findValuePack(base, cheap, store, 1)).not.toBeNull();
  });

  it("needs the same unit of measure", () => {
    expect(findValuePack(base, { ...probe, uom: "100 ג'" }, store, 1)).toBeNull();
  });

  it("needs the counts and the pack data the quantity is worked out from", () => {
    expect(findValuePack({ ...base, pack_units: null }, probe, store, 1)).toBeNull();
    expect(findValuePack(base, { ...probe, pack_units: null }, store, 1)).toBeNull();
    expect(findValuePack({ ...base, packs: null }, probe, store, 1)).toBeNull();
  });

  it("is null when the list already asks for that many", () => {
    expect(findValuePack(base, probe, store, 3)).toBeNull();
  });

  it("is null for another product", () => {
    expect(findValuePack(base, { ...probe, canonical_id: 1001 }, store, 1)).toBeNull();
  });
});

describe("which rows and requests", () => {
  it("only a resolved, non-exact, non-weighed product counted in units is eligible", () => {
    const rows = [
      row("ביצים"), // counted in units
      row("חלב"), // per 100 ml
      row("עגבניות"), // weighed
      row("ביצים", 1, { flexLevel: "exact" }),
      row("ביצים", 1, { needsConfirmation: true }),
      row("משהו לא מוכר"),
    ];
    expect(packEligibleRows(rows)).toHaveLength(1);
    expect(packEligibleRows(rows)[0]!.canonical!.canonical_id).toBe(1009);
  });

  it("asks for the list's quantities and for five times them, only for the eligible rows", () => {
    const req = packRequests([row("ביצים", 2), row("חלב", 3)], SHOPPER)!;
    expect(req.base.items).toEqual([expect.objectContaining({ canonical_id: 1009, quantity: 2 })]);
    expect(req.probe.items).toEqual([
      expect.objectContaining({ canonical_id: 1009, quantity: 2 * FAMILY_FACTOR }),
    ]);
  });

  it("asks nothing when no row can have a larger pack", () => {
    expect(packRequests([row("חלב")], SHOPPER)).toBeNull();
    expect(packRequests([], SHOPPER)).toBeNull();
  });

  it("never asks for more than 1000", () => {
    const req = packRequests([row("ביצים", 900)], SHOPPER)!;
    expect((req.probe.items[0] as BasketItemInput).quantity).toBe(1000);
  });
});

describe("valuePacksFrom", () => {
  const rows = [row("ביצים", 1), row("חלב", 2)];

  it("finds the pack at the cheapest store for the current quantity", () => {
    const base = priced(1);
    const probe = priced(5);
    const packs = valuePacksFrom(base, probe, rows);
    expect(packs).toHaveLength(1);
    const cheapest = base.stores
      .map((s) => ({ s, line: s.items.find((l) => l.canonical_id === 1009)! }))
      .sort((a, b) => Number(a.line.line_total) - Number(b.line.line_total))[0]!;
    expect(packs[0]!.store.id).toBe(cheapest.s.store_id);
    expect(packs[0]!.canonicalId).toBe(1009);
    expect(packs[0]!.quantity).toBe(1);
  });

  it("finds nothing when the probe answers the same item (no larger pack at that quantity)", () => {
    const base = priced(1);
    expect(valuePacksFrom(base, base, rows)).toEqual([]);
  });

  it("finds nothing for a store the probe did not return", () => {
    const base = priced(1);
    const probe = { ...priced(5), stores: [] };
    expect(valuePacksFrom(base, probe, rows)).toEqual([]);
  });
});

describe("visibleValuePacks", () => {
  const packs = valuePacksFrom(priced(1), priced(5), [row("ביצים", 1)]);

  it("hides a pack dismissed in the last 30 days and shows it again after", () => {
    const key = String(packs[0]!.canonicalId);
    const recent = doc({ dismissals: [dismissal(VALUE_PACK_SNOOZE_DAYS - 1, "value_pack", key)] });
    expect(visibleValuePacks(packs, recent, NOW)).toEqual([]);
    const old = doc({ dismissals: [dismissal(VALUE_PACK_SNOOZE_DAYS, "value_pack", key)] });
    expect(visibleValuePacks(packs, old, NOW)).toEqual(packs);
  });

  it("another kind of dismissal for the same key does not hide it", () => {
    const key = String(packs[0]!.canonicalId);
    expect(
      visibleValuePacks(packs, doc({ dismissals: [dismissal(1, "buy_again", key)] }), NOW),
    ).toEqual(packs);
  });
});
