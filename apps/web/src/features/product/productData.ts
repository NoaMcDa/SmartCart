import type { CompareResponse, PricedItem, StoreResult } from "@/api/client";
import { perUnitLabel } from "@/lib/attributes";

export type Variant = {
  /** Chain item name, the variant's identity. */
  name: string;
  /** Effective price per unit (100 g, 100 ml, unit or kg), ILS. */
  unitPrice: number;
  /** "ל-100 מ"ל", 'לק"ג', "לביצה". */
  unitLabel: string;
  isEstimated: boolean;
  isSubstitute: boolean;
  storeCount: number;
  cheapestStore: string;
};

export type StoreRow = {
  store: StoreResult;
  item: PricedItem;
  /** Price of one pack (or one kg) after promos, ILS. */
  effective: number;
  shelf: number;
};

export function unitLabel(uom: string): string {
  return perUnitLabel(uom);
}

/** The canonical's lines in a compare result, one per store, cheapest effective price first. */
export function storeRows(compare: CompareResponse, canonicalId: number): StoreRow[] {
  const rows: StoreRow[] = [];
  for (const store of compare.stores) {
    const item = store.items.find((i) => i.canonical_id === canonicalId);
    if (!item) continue;
    const qty = Number(item.quantity) || 1;
    rows.push({
      store,
      item,
      effective: Number(item.line_total) / qty,
      shelf: Number(item.shelf_price),
    });
  }
  return rows.sort((a, b) => a.effective - b.effective || a.store.distance_m - b.store.distance_m);
}

/** Variants (distinct chain items) ranked by unit price, ascending (D6). */
export function variantsOf(rows: ReadonlyArray<StoreRow>): Variant[] {
  const byName = new Map<string, StoreRow[]>();
  for (const row of rows) {
    const list = byName.get(row.item.display_name_he) ?? [];
    list.push(row);
    byName.set(row.item.display_name_he, list);
  }
  const variants: Variant[] = [];
  for (const [name, list] of byName) {
    const best = [...list].sort(
      (a, b) => Number(a.item.effective_unit_price) - Number(b.item.effective_unit_price),
    )[0]!;
    variants.push({
      name,
      unitPrice: Number(best.item.effective_unit_price),
      unitLabel: unitLabel(best.item.uom),
      isEstimated: list.some((r) => r.item.is_estimated),
      isSubstitute: list.every((r) => r.item.is_substitute),
      storeCount: list.length,
      cheapestStore: best.store.chain_name,
    });
  }
  return variants.sort((a, b) => a.unitPrice - b.unitPrice || a.name.localeCompare(b.name, "he"));
}

/** "היום 06:40" for today's prices, "06.10 06:40" otherwise (Israel time). */
export function formatUpdated(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  const tz = "Asia/Jerusalem";
  const day = (x: Date) => x.toLocaleDateString("en-CA", { timeZone: tz });
  const time = d.toLocaleTimeString("he-IL", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: tz,
  });
  if (day(d) === day(now)) return `היום ${time}`;
  const date = d.toLocaleDateString("he-IL", { day: "2-digit", month: "2-digit", timeZone: tz });
  return `${date.replace(/\//g, ".")} ${time}`;
}
