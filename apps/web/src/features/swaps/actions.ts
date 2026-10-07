/**
 * Apply, undo and dismiss for the smart cart (issue #45). A swap is never applied by itself: it
 * changes the flexibility of the list rows for that product only after a tap, and the tap is
 * reversible. Both outcomes are labeling signals for the catalog (D5), sent through the same
 * `/feedback/substitution` route the substitution card uses.
 */
import { substitutionFeedback, type FlexLevel, type SwapSuggestion } from "@/api/client";
import {
  reportSwapApplied,
  reportSwapDismissed,
  reportSwapUndone,
} from "@/features/consent/betaEvents";
import { getListState, listActions } from "@/state/list";
import {
  getSwapsState,
  recordApplied,
  recordDismissed,
  removeApplied,
  savingOf,
  swapKey,
  type AppliedSwap,
  type SwapOrigin,
} from "./swapState";

/** The verdict for each outcome: apply = accepted, undo = kept_original, dismiss = not_good. */
function signal(
  swap: {
    canonicalId: number;
    fromItemId: number;
    toItemId: number;
    flexLevel: FlexLevel;
    confidence: number | null;
  },
  verdict: "accepted" | "kept_original" | "not_good",
): void {
  substitutionFeedback({
    canonical_id: swap.canonicalId,
    original_item_id: swap.fromItemId,
    substitute_item_id: swap.toItemId,
    verdict,
    source: "swap",
    flex_level: swap.flexLevel,
    match_confidence: swap.confidence,
  }).catch(() => {
    // A lost signal changes nothing for the shopper.
  });
}

const originOf = (swap: SwapSuggestion): SwapOrigin => ({
  canonicalId: swap.canonical_id,
  fromItemId: swap.from_item_id,
  toItemId: swap.to_item_id,
  flexLevel: swap.flex_level,
  confidence: swap.confidence ?? null,
});

/** Sets the product's rows to the swap's level, remembering how they were. Returns the entry, or null when the list has no such row. */
export function applySwap(swap: SwapSuggestion): AppliedSwap | null {
  const rows = getListState().items.filter(
    (it) => it.canonical?.canonical_id === swap.canonical_id,
  );
  if (rows.length === 0) return null;
  const entry: AppliedSwap = {
    key: swapKey(swap),
    name: swap.to_display_name_he,
    saving: savingOf(swap),
    rows: rows.map((r) => ({
      rowId: r.id,
      flexLevel: r.flexLevel,
      allow: [...r.allow],
      exactItemId: r.exactItemId,
    })),
    at: new Date().toISOString(),
    origin: originOf(swap),
  };
  for (const r of rows) {
    listActions.setFlex(r.id, { level: swap.flex_level, allow: r.allow, remember: false });
  }
  recordApplied(entry);
  signal(originOf(swap), "accepted");
  reportSwapApplied(swap.flex_level, entry.saving);
  return entry;
}

/**
 * Puts every row back as it was before the swap, tells the catalog the shopper kept the original
 * (`kept_original`, source "swap") and reports `swap_undone`. The swap is offered again afterwards.
 */
export function undoSwap(key: string): boolean {
  const entry = getSwapsState().applied.find((a) => a.key === key);
  if (!entry) return false;
  const present = new Set(getListState().items.map((i) => i.id));
  for (const snap of entry.rows) {
    if (!present.has(snap.rowId)) continue; // the row was removed meanwhile
    listActions.setFlex(snap.rowId, { level: snap.flexLevel, allow: snap.allow, remember: false });
    if (snap.flexLevel === "exact" && snap.exactItemId !== null) {
      const row = getListState().items.find((i) => i.id === snap.rowId);
      if (row?.canonical) listActions.keepOriginal(row.canonical.canonical_id, snap.exactItemId);
    }
  }
  removeApplied(key);
  if (entry.origin) signal(entry.origin, "kept_original");
  reportSwapUndone(entry.origin?.flexLevel ?? null);
  return true;
}

/** Hides the suggestion until its saving changes materially (`isMaterialChange`); survives a reload. */
export function dismissSwap(swap: SwapSuggestion): void {
  recordDismissed(swap);
  signal(originOf(swap), "not_good");
  reportSwapDismissed(swap.flex_level);
}
