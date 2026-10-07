import type { CanonicalRef } from "@/api/client";
import { listActions } from "@/state/list";

/**
 * Adds a canonical product to the shared list (W4b `listActions`) with a quantity. The flexibility
 * level is the one the list resolves for the product's category: the user's remembered default,
 * then the smart default (D4), then "any brand". Adding the same product again adds up.
 */
export function addCanonicalToList(canonical: CanonicalRef, name: string, quantity: number): void {
  listActions.add([
    {
      input_text: name,
      canonical,
      confidence: 1,
      needs_confirmation: false,
      not_found: false,
      candidates: [],
      quantity: String(quantity),
      flex_level: "any_brand",
      is_weighed: false,
    },
  ]);
}
