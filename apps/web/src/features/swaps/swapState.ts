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

/** What undo needs to tell the catalog "kept the original". Older stored entries may lack it. */
export type SwapOrigin = {
  canonicalId: number;
  fromItemId: number;
  toItemId: number;
  flexLevel: FlexLevel;
  confidence: number | null;
};

export type AppliedSwap = {
  key: string;
  name: string;
  saving: number;
  rows: RowSnapshot[];
  at: string;
  origin?: SwapOrigin;
};

export type SwapsState = {
  version: 1;
  /** swap key -> the saving (ILS) when it was dismissed. */
  dismissed: Record<string, number>;
  applied: AppliedSwap[];
};

const EMPTY: SwapsState = { version: 1, dismissed: {}, applied: [] };

/** Dismissals and applied swaps are kept for the most recent N only, so the key never grows without bound. */
export const MAX_DISMISSED = 200;
export const MAX_APPLIED = 20;

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
  const applied = (Array.isArray(s.applied) ? s.applied : [])
    .filter(
      (a): a is AppliedSwap =>
        Boolean(a) &&
        typeof a.key === "string" &&
        typeof a.name === "string" &&
        Array.isArray(a.rows),
    )
    .map((a) => ({ ...a, origin: sanitizeOrigin(a.origin) }));
  return { version: 1, ...capped(dismissed, applied) };
}

const LEVELS: ReadonlySet<string> = new Set(["exact", "any_brand", "close"]);

function sanitizeOrigin(raw: unknown): SwapOrigin | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  const o = raw as Partial<SwapOrigin>;
  if (
    typeof o.canonicalId !== "number" ||
    typeof o.fromItemId !== "number" ||
    typeof o.toItemId !== "number" ||
    typeof o.flexLevel !== "string" ||
    !LEVELS.has(o.flexLevel)
  ) {
    return undefined;
  }
  return {
    canonicalId: o.canonicalId,
    fromItemId: o.fromItemId,
    toItemId: o.toItemId,
    flexLevel: o.flexLevel,
    confidence: typeof o.confidence === "number" ? o.confidence : null,
  };
}

/** Keeps the newest entries (object keys keep insertion order, the applied list is oldest first). */
function capped(dismissed: Record<string, number>, applied: AppliedSwap[]) {
  const keys = Object.keys(dismissed);
  const keep =
    keys.length > MAX_DISMISSED
      ? Object.fromEntries(keys.slice(-MAX_DISMISSED).map((k) => [k, dismissed[k] as number]))
      : dismissed;
  return { dismissed: keep, applied: applied.slice(-MAX_APPLIED) };
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

/**
 * Remembers the dismissal with the saving at that moment. Dismissing again after the swap came
 * back replaces the saving, so the new price is the one a later change is measured against.
 */
export function recordDismissed(swap: SwapSuggestion): void {
  const state = load();
  const key = swapKey(swap);
  const dismissed = { ...state.dismissed };
  delete dismissed[key]; // re-insert last, so it is the newest when the list is capped
  dismissed[key] = savingOf(swap);
  set({ ...state, ...capped(dismissed, state.applied) });
}

/** An applied swap is no longer "dismissed": applying overrides an earlier dismissal. */
export function recordApplied(entry: AppliedSwap): void {
  const state = load();
  const dismissed = { ...state.dismissed };
  delete dismissed[entry.key];
  set({
    ...state,
    ...capped(dismissed, [...state.applied.filter((a) => a.key !== entry.key), entry]),
  });
}

export function removeApplied(key: string): void {
  const state = load();
  set({ ...state, applied: state.applied.filter((a) => a.key !== key) });
}

/**
 * The applied swaps that can still be undone: at least one of the rows it changed is still on the
 * list. A swap whose rows were all deleted has nothing left to restore.
 */
export function undoableSwaps(
  state: SwapsState,
  presentRowIds: ReadonlySet<string>,
): AppliedSwap[] {
  return state.applied.filter((a) => a.rows.some((r) => presentRowIds.has(r.rowId)));
}

// The "swap undone" note outlives the card: undoing changes the list, the results reload, and the
// card is rebuilt, so the note cannot live in the card's own state. Memory only, not persisted.
let undoneName: string | null = null;

/** Name of the swap the shopper just undid, until the next apply or a reload. */
export function useUndoneName(): string | null {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => {
        listeners.delete(l);
      };
    },
    () => undoneName,
    () => null,
  );
}

export function setUndoneName(name: string | null): void {
  undoneName = name;
  listeners.forEach((l) => l());
}

/** Test helper. */
export function resetSwapsForTests(): void {
  snapshot = null;
  undoneName = null;
}
