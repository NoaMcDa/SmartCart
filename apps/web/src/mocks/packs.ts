/**
 * The mock's reading of the quantity asked for a counted product (eggs, canonical 1009): a store
 * carries a 12-pack and a tray of 30, and, like `/compare` (`docs/optimizer.md`, "Offers for the
 * quantity asked"), the line is the cheapest way to buy that many: whole packs of each, the
 * lower total wins, a tie goes to the smaller pack. So one tray (2.5 packs of 12) beats five
 * 12-packs at the same time as a single 12-pack beats a tray for one pack. Every other line stays
 * as the fixtures have it.
 *
 * Used by the value-pack tests and the e2e specs; the real API chooses from the stores' real
 * offers.
 */
import type { BasketItemInput, CompareResponse, PricedItem, StoreResult } from "@/api/client";

const EGGS = 1009;
const PER_QUANTITY = 12; // eggs in one list quantity (the canonical's typical pack)
const TRAY = 30;
/** The tray costs this many times the 12-pack: about 15% cheaper per egg. */
const TRAY_FACTOR = 2.15;

const agorot = (v: string | number) => Math.round(Number(v) * 100);
const money = (a: number) => (a / 100).toFixed(2);

function eggLine(line: PricedItem, quantity: number): PricedItem {
  const shelf12 = agorot(line.shelf_price);
  const options = [
    { units: 12, shelf: shelf12, tray: false },
    { units: TRAY, shelf: Math.round(shelf12 * TRAY_FACTOR), tray: true },
  ].map((o) => {
    const packs = Math.ceil((quantity * PER_QUANTITY) / o.units - 1e-9);
    return { ...o, packs, total: packs * o.shelf };
  });
  const best = options.reduce((a, b) => (b.total < a.total ? b : a));
  return {
    ...line,
    item_id: best.tray ? line.item_id + 50_000 : line.item_id,
    display_name_he: best.tray ? "ביצים L, מגש 30 יחידות" : line.display_name_he,
    quantity: String(quantity),
    packs: String(best.packs),
    pack_units: String(best.units),
    shelf_price: money(best.shelf),
    effective_unit_price: money(Math.round(best.shelf / best.units)),
    uom: "ביצה",
    line_total: money(best.total),
    is_substitute: false,
    original_item_id: null,
    original_here: null,
    tags: [],
  };
}

function priceStore(store: StoreResult, quantity: number): StoreResult {
  const items = store.items.map((l) => (l.canonical_id === EGGS ? eggLine(l, quantity) : l));
  const total = items.reduce((sum, l) => sum + agorot(l.line_total), 0);
  return { ...store, items, total: money(total) };
}

export function applyPacksToCompare(
  res: CompareResponse,
  items: ReadonlyArray<BasketItemInput>,
): CompareResponse {
  const eggs = items.find((i) => i.canonical_id === EGGS);
  if (!eggs) return res;
  const quantity = Number(eggs.quantity);
  if (!(quantity > 0)) return res;
  return { ...res, stores: res.stores.map((s) => priceStore(s, quantity)) };
}
