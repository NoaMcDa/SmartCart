/**
 * Recipe to list (issue #71, UI half): scaling `/parse-recipe` rows to the servings the person
 * wants, and turning the lines nothing matched into "not found" rows.
 *
 * `/parse-recipe` returns rows for `servings` portions. The stepper in the recipe sheet changes the
 * target; quantities are scaled here, so changing portions never costs a request.
 */
import type { ParsedRow } from "@/api/client";

export const MIN_SERVINGS = 1;
export const MAX_SERVINGS = 24;

/**
 * Quantity of one row for `to` servings when it is `row.quantity` for `from`.
 * - Weighed goods (kg) scale smoothly and round to 50 g.
 * - Anything bought by the piece or pack rounds up to a whole one: half a pack cannot be bought,
 *   and a recipe that needs 1.5 packs needs 2.
 */
export function scaledQuantity(row: ParsedRow, from: number, to: number): number {
  const parsed = Number.parseFloat(row.quantity);
  const base = Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
  if (from === to || from <= 0) return base;
  const raw = (base * to) / from;
  if (row.is_weighed || row.unit === "kg") return Math.max(0.05, Math.round(raw * 20) / 20);
  return Math.max(1, Math.ceil(raw - 1e-9));
}

/** The rows for `to` servings, ready for `listActions.add`. */
export function scaleRows(rows: ParsedRow[], from: number, to: number): ParsedRow[] {
  return rows.map((row) => ({ ...row, quantity: String(scaledQuantity(row, from, to)) }));
}

/** A recipe line nothing matched, as the "לא זוהו" row the list builder already knows how to edit. */
export function unresolvedRow(text: string): ParsedRow {
  return {
    input_text: text,
    canonical: null,
    confidence: 0,
    needs_confirmation: true,
    not_found: true,
    candidates: [],
    quantity: "1",
    flex_level: "any_brand",
    is_weighed: false,
  };
}
