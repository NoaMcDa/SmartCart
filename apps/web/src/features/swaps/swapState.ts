/**
 * Smart cart bookkeeping (issue #45): which swaps the shopper dismissed or applied, kept in
 * localStorage under `sc-swaps-v1` so a dismissed swap does not come back after a reload, and what
 * is needed to undo an applied one. Pure helpers decide what is still worth showing.
 */
import { useSyncExternalStore } from "react";
import type { FlexLevel, SwapSuggestion } from "@/api/client";
import { readJson, writeJson } from "@/state/storage";

export const SWAPS_KEY = "sc-swaps-v1";

/** What a list row looked like before a swap changed it. */
export type RowSnapshot = {
  rowId: string;
  flexLevel: FlexLevel;
  allow: string[];
  exactItemId: number | null;
};

export type AppliedSwap = {
  key: string;
  name: string;
  saving: number;
  rows: RowSnapshot[];
  at: string;
};

export type SwapsState = {
  version: 1;
  /** swap key -> the saving (ILS) when it was dismissed. */
  dismissed: Record<string, number>;
  applied: AppliedSwap[];
};

const EMPTY: SwapsState = { version: 1, dismissed: {}, applied: [] };

export const swapKey = (s: Pick<SwapSuggestion, "canonical_id" | "to_item_id">) =>
  `${s.canonical_id}:${s.to_item_id}`;

const cents = (n: number) => Math.round(n * 100) / 100;
export const savingOf = (s: Pick<SwapSuggestion, "saving">) =>
  cents(Number.parseFloat(s.saving) || 0);

/**
 * A dismissed swap stays hidden until its saving changes materially: by at least ₪1 and 25%. Prices
 * moving a few agorot does not bring back a suggestion the shopper already declined.
 */
export function isMaterialChange(before: number, now: number): boolean {
  const diff = Math.abs(now - before);
  return diff >= 1 && diff >= before * 0.25;
}

/** Swaps still worth offering: not applied, and not dismissed unless the saving moved a lot. */
export function visibleSwaps(
  swaps: ReadonlyArray<SwapSuggestion>,
  state: SwapsState,
): SwapSuggestion[] {
  const applied = new Set(state.applied.map((a) => a.key));
  return swaps.filter((s) => {
    const key = swapKey(s);
    if (applied.has(key)) return false;
    const was = state.dismissed[key];
    return was === undefined || isMaterialChange(was, savingOf(s));
  });
}

/**
 * "N swaps save you X": the sum over the visible swaps. The API gives non-overlapping swaps (one
 * per product), so adding them up cannot count a saving twice; the sum is in whole agorot.
 */
export function aggregate(swaps: ReadonlyArray<SwapSuggestion>): { count: number; total: number } {
  const agorot = swaps.reduce((sum, s) => sum + Math.round(savingOf(s) * 100), 0);
  return { count: swaps.length, total: agorot / 100 };
}

// ---------------------------------------------------------------------------------------------
// Store

function sanitize(raw: unknown): SwapsState {
  if (!raw || typeof raw !== "object") return EMPTY;
  const s = raw as Partial<SwapsState>;
  if (s.version !== 1) return EMPTY;
  const dismissed: Record<string, number> = {};
  for (const [k, v] of Object.entries(s.dismissed ?? {})) {
    if (typeof v === "number" && Number.isFinite(v)) dismissed[k] = v;
  }
  const applied = (Array.isArray(s.applied) ? s.applied : []).filter(
    (a): a is AppliedSwap =>
      Boolean(a) &&
      typeof a.key === "string" &&
      typeof a.name === "string" &&
      Array.isArray(a.rows),
  );
  return { version: 1, dismissed, applied };
}

let snapshot: SwapsState | null = null;
const listeners = new Set<() => void>();

function load(): SwapsState {
  if (!snapshot) snapshot = sanitize(readJson(SWAPS_KEY, null));
  return snapshot;
}

function set(next: SwapsState) {
  snapshot = next;
  writeJson(SWAPS_KEY, next);
  listeners.forEach((l) => l());
}

export function getSwapsState(): SwapsState {
  return load();
}

export function useSwapsState(): SwapsState {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => {
        listeners.delete(l);
      };
    },
    load,
    () => EMPTY,
  );
}

export function recordDismissed(swap: SwapSuggestion): void {
  const state = load();
  set({ ...state, dismissed: { ...state.dismissed, [swapKey(swap)]: savingOf(swap) } });
}

export function recordApplied(entry: AppliedSwap): void {
  const state = load();
  set({ ...state, applied: [...state.applied.filter((a) => a.key !== entry.key), entry] });
}

export function removeApplied(key: string): void {
  const state = load();
  set({ ...state, applied: state.applied.filter((a) => a.key !== key) });
}

/** Test helper. */
export function resetSwapsForTests(): void {
  snapshot = null;
}
