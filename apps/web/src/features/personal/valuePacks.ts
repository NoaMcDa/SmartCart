/**
 * Large-family value packs (phase 3): with "prefer value packs" on, the list builder points out
 * where a larger pack of the same product has a lower unit price. Display and a one-tap quantity
 * change only: it reads `/compare` and changes no pricing rule.
 *
 * How the larger pack is found. Within one canonical product (eggs, pitas, toilet paper: counted
 * in units) a store can carry several shelf packs, and `/compare` already picks the cheapest
 * line for the quantity asked (`docs/optimizer.md`, "Offers for the quantity asked"). So a pack
 * that is cheaper per unit but dearer in total shows up only at a bigger quantity. This asks
 * twice, for the list's quantities and for five times them (a family stocking up), and reports a
 * pack when, at the cheapest store for the current quantity:
 *
 * - both lines are exact or any-brand matches (never a substitute: nothing is swapped silently),
 * - the larger line is a different shelf item holding at least 25% more units,
 * - its unit price is at least 5% lower, in the same unit.
 *
 * Applying raises the row's quantity to what covers one of the larger packs, so the next
 * `/compare` picks that pack by its own rule. The person is told it is more than they listed.
 */
import { useMemo } from "react";
import {
  compare,
  type BasketItemInput,
  type CompareInput,
  type CompareResponse,
} from "@/api/client";
import type { PricedItem, StoreResult } from "@/api/client";
import { buildCompareInput } from "@/state/comparison";
import { basketItems, type ListItem } from "@/state/list";
import { createResourceCache } from "@/state/resource";
import type { ShopperContext } from "@/state/shopper";
import { dayIndex, type PersonalDoc } from "./personalDoc";

/** The probe asks for this many times the listed quantity. */
export const FAMILY_FACTOR = 5;
export const MIN_LARGER_RATIO = 1.25;
export const MIN_UNIT_SAVING = 0.05;
/** A dismissed value pack comes back after this many days. */
export const VALUE_PACK_SNOOZE_DAYS = 30;

export type PackSide = {
  itemId: number;
  name: string;
  packUnits: number;
  /** Per unit, in `uom`. */
  unitPrice: number;
  shelfPrice: number;
  updatedAt: string;
};

export type ValuePack = {
  canonicalId: number;
  store: { id: number; name: string; chain: string };
  uom: string;
  current: PackSide;
  larger: PackSide;
  /** How much cheaper per unit the larger pack is, as a whole percent. */
  unitSavingPct: number;
  /** The quantity (in the list's own packs) that covers one larger pack. */
  quantityToSet: number;
  quantity: number;
};

const num = (v: string | number | null | undefined): number | null => {
  if (v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

function side(line: PricedItem, packUnits: number, unitPrice: number): PackSide {
  return {
    itemId: line.item_id,
    name: line.display_name_he,
    packUnits,
    unitPrice,
    shelfPrice: num(line.shelf_price) ?? 0,
    updatedAt: line.price_valid_from,
  };
}

/** The value pack for one product at one store, or null when the rules above do not hold. */
export function findValuePack(
  base: PricedItem,
  probe: PricedItem,
  store: Pick<StoreResult, "store_id" | "store_name" | "chain_name">,
  rowQuantity: number,
): ValuePack | null {
  if (base.canonical_id !== probe.canonical_id || base.item_id === probe.item_id) return null;
  if (base.is_substitute || probe.is_substitute) return null;
  if (base.uom !== probe.uom) return null;
  const baseUnits = num(base.pack_units);
  const probeUnits = num(probe.pack_units);
  const baseUnit = num(base.effective_unit_price);
  const probeUnit = num(probe.effective_unit_price);
  if (!baseUnits || !probeUnits || !baseUnit || !probeUnit) return null;
  if (probeUnits < baseUnits * MIN_LARGER_RATIO) return null;
  if (probeUnit > baseUnit * (1 - MIN_UNIT_SAVING)) return null;
  // Units one list quantity stands for, from the line itself (12 eggs per quantity).
  const packs = num(base.packs);
  const asked = num(base.quantity);
  if (!packs || !asked) return null;
  const perQuantity = (packs * baseUnits) / asked;
  const quantityToSet = Math.ceil((probeUnits / perQuantity) * 2) / 2;
  if (!(quantityToSet > rowQuantity) || quantityToSet > 1000) return null;
  return {
    canonicalId: base.canonical_id,
    store: { id: store.store_id, name: store.store_name, chain: store.chain_name },
    uom: base.uom,
    current: side(base, baseUnits, baseUnit),
    larger: side(probe, probeUnits, probeUnit),
    unitSavingPct: Math.round((1 - probeUnit / baseUnit) * 100),
    quantityToSet,
    quantity: rowQuantity,
  };
}

/** The rows that can have a larger pack: a resolved product counted in units, not exact, not weighed. */
export function packEligibleRows(items: ReadonlyArray<ListItem>): ListItem[] {
  return items.filter(
    (it) =>
      it.canonical !== null &&
      !it.notFound &&
      !it.needsConfirmation &&
      it.flexLevel !== "exact" &&
      !it.isWeighed &&
      it.unit !== "kg" &&
      it.canonical.base_unit === "unit",
  );
}

/** The two `/compare` requests: the list's quantities, and the family-size probe. */
export function packRequests(
  rows: ReadonlyArray<ListItem>,
  shopper: ShopperContext,
): { base: CompareInput; probe: CompareInput } | null {
  const basket: BasketItemInput[] = basketItems({ items: [...packEligibleRows(rows)] });
  if (basket.length === 0) return null;
  const probeBasket = basket.map((b) => ({
    ...b,
    quantity: Math.min(1000, Number(b.quantity) * FAMILY_FACTOR),
  }));
  const base = buildCompareInput(basket, shopper);
  const probe = buildCompareInput(probeBasket, shopper);
  return base && probe ? { base, probe } : null;
}

/** Value packs from the two responses, one per product, at the cheapest store for the current quantity. */
export function valuePacksFrom(
  base: CompareResponse,
  probe: CompareResponse,
  rows: ReadonlyArray<ListItem>,
): ValuePack[] {
  const quantities = new Map<number, number>();
  for (const b of basketItems({ items: [...packEligibleRows(rows)] })) {
    quantities.set(b.canonical_id, Number(b.quantity));
  }
  const out: ValuePack[] = [];
  for (const [canonicalId, quantity] of quantities) {
    let cheapest: { store: StoreResult; line: PricedItem; total: number } | null = null;
    for (const store of base.stores) {
      const line = store.items.find((l) => l.canonical_id === canonicalId);
      const total = num(line?.line_total);
      if (!line || total === null || line.is_substitute) continue;
      if (!cheapest || total < cheapest.total) cheapest = { store, line, total };
    }
    if (!cheapest) continue;
    const probeStore = probe.stores.find((s) => s.store_id === cheapest!.store.store_id);
    const probeLine = probeStore?.items.find((l) => l.canonical_id === canonicalId);
    if (!probeLine) continue;
    const pack = findValuePack(cheapest.line, probeLine, cheapest.store, quantity);
    if (pack) out.push(pack);
  }
  return out.sort((a, b) => b.unitSavingPct - a.unitSavingPct || a.canonicalId - b.canonicalId);
}

/** Hides a pack the person dismissed in the last 30 days. */
export function visibleValuePacks(
  packs: ReadonlyArray<ValuePack>,
  doc: Pick<PersonalDoc, "dismissals">,
  now: Date,
): ValuePack[] {
  const today = dayIndex(now.toISOString());
  return packs.filter((p) => {
    const d = doc.dismissals.find(
      (x) => x.kind === "value_pack" && x.key === String(p.canonicalId),
    );
    return !d || today - dayIndex(d.at) >= VALUE_PACK_SNOOZE_DAYS;
  });
}

// ---------------------------------------------------------------------------------------------
// Hook

const cache = createResourceCache<CompareInput, CompareResponse>(compare, 8);

export function useValuePacks(
  rows: ReadonlyArray<ListItem>,
  shopper: ShopperContext | null,
  enabled: boolean,
): { packs: ValuePack[]; loading: boolean } {
  const requests = useMemo(
    () => (enabled && shopper ? packRequests(rows, shopper) : null),
    [enabled, shopper, rows],
  );
  const baseKey = requests ? JSON.stringify(requests.base) : null;
  const probeKey = requests ? JSON.stringify(requests.probe) : null;
  const base = cache.useResource(baseKey, requests?.base ?? null);
  const probe = cache.useResource(probeKey, requests?.probe ?? null);
  const baseData = "data" in base ? base.data : undefined;
  const probeData = "data" in probe ? probe.data : undefined;
  const packs = useMemo(
    () =>
      baseData && probeData && base.status === "success" && probe.status === "success"
        ? valuePacksFrom(baseData, probeData, rows)
        : [],
    [baseData, probeData, base.status, probe.status, rows],
  );
  return {
    packs,
    loading: Boolean(requests) && (base.status === "loading" || probe.status === "loading"),
  };
}

export function clearValuePackCache(): void {
  cache.clear();
}
