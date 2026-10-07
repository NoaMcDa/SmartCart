/**
 * Apply, undo and dismiss for the smart cart (issue #45). A swap is never applied by itself: it
 * changes the flexibility of the list rows for that product only after a tap, and the tap is
 * reversible. Both outcomes are labeling signals for the catalog (D5), sent through the same
 * `/feedback/substitution` route the substitution card uses.
 */
import { substitutionFeedback, type SwapSuggestion } from "@/api/client";
import { getListState, listActions } from "@/state/list";
import {
  getSwapsState,
  recordApplied,
  recordDismissed,
  removeApplied,
  savingOf,
  swapKey,
  type AppliedSwap,
} from "./swapState";

function signal(swap: SwapSuggestion, verdict: "accepted" | "not_good"): void {
  substitutionFeedback({
    canonical_id: swap.canonical_id,
    original_item_id: swap.from_item_id,
    substitute_item_id: swap.to_item_id,
    verdict,
    source: "swap",
    flex_level: swap.flex_level,
    match_confidence: swap.confidence ?? null,
  }).catch(() => {
    // A lost signal changes nothing for the shopper.
  });
}

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
  };
  for (const r of rows) {
    listActions.setFlex(r.id, { level: swap.flex_level, allow: r.allow, remember: false });
  }
  recordApplied(entry);
  signal(swap, "accepted");
  return entry;
}

/** Puts every row back as it was before the swap. */
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
  return true;
}

export function dismissSwap(swap: SwapSuggestion): void {
  recordDismissed(swap);
  signal(swap, "not_good");
}
