import type { GapReportRequest } from "@/api/client";

/** What the screen knows about the price being reported. Everything except the store is optional. */
export type GapContext = {
  storeId: number;
  storeName: string;
  canonicalId?: number | null;
  itemId?: number | null;
  itemName?: string | null;
  /** The price the user was shown, ILS. */
  shownPrice?: number | string | null;
  /** When that price was valid from (ISO), shown next to it and sent along. */
  priceUpdatedAt?: string | null;
};

export type GapReason = "price_differs" | "wrong_product" | "promo_wrong";

export const GAP_REASONS: ReadonlyArray<{ value: GapReason; label: string }> = [
  { value: "price_differs", label: "המחיר שונה" },
  { value: "wrong_product", label: "מוצר לא נכון" },
  { value: "promo_wrong", label: "מבצע חסר או שגוי" },
];

const NOTE_MAX = 500;

/**
 * Builds the /feedback/gap body. The API has fields for store, item, shown and actual price and a
 * note, but none for the reason or the time of the price, so those travel as a machine-readable
 * tail on the note ("#reason=..., #shown_at=...") that the quality gates can parse. The user's
 * own text comes first and is cut so the whole note stays within the API limit of 500.
 */
export function buildGapRequest(
  context: GapContext,
  input: { reason: GapReason | null; actualPrice: string; note: string },
): GapReportRequest {
  const tail = [
    input.reason ? `#reason=${input.reason}` : null,
    context.priceUpdatedAt ? `#shown_at=${context.priceUpdatedAt}` : null,
  ]
    .filter(Boolean)
    .join(" ");
  const text = input.note.trim().slice(0, Math.max(0, NOTE_MAX - tail.length - 1));
  const note = [text, tail].filter(Boolean).join(" ") || null;
  const actual = Number.parseFloat(input.actualPrice.replace(/[^\d.,]/g, "").replace(",", "."));
  const shown =
    context.shownPrice === undefined || context.shownPrice === null
      ? null
      : Number(context.shownPrice);
  return {
    store_id: context.storeId,
    canonical_id: context.canonicalId ?? null,
    item_id: context.itemId ?? null,
    shown_price: shown !== null && Number.isFinite(shown) ? shown : null,
    actual_price: Number.isFinite(actual) && actual >= 0 ? actual : null,
    note,
  };
}
