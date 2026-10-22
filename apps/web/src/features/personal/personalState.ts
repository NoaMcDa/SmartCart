/**
 * The personalization store (phase 3): the person's own habits on this device, in localStorage
 * under `sc-personal-v1`, read by the list builder and the profile through `usePersonal()`.
 *
 * Local first and local only until the person is signed in: nothing here makes a request.
 * `PersonalSync` (signed in only) mirrors the document to `/me/personal`. Recording stops when the
 * person turns learning off (`prefs.learn`), and "clear what was learned" and "delete my data"
 * empty it. The key is in `CORE_DATA_KEYS`, so deleting the data removes it and the export holds
 * it.
 */
import { useSyncExternalStore } from "react";
import type { CanonicalRef } from "@/api/client";
import { readJson, removeKey, writeJson } from "@/state/storage";
import {
  EMPTY_DOC,
  LIMITS,
  normalizeDoc,
  sanitizeDoc,
  type Dismissal,
  type DismissalKind,
  type PersonalDoc,
  type SignalKind,
  type Trip,
  type TripKind,
} from "./personalDoc";

export const PERSONAL_KEY = "sc-personal-v1";

type Snapshot = { doc: PersonalDoc; hydrated: boolean };

const SERVER_SNAPSHOT: Snapshot = { doc: EMPTY_DOC, hydrated: false };
let snapshot: Snapshot | null = null;
const listeners = new Set<() => void>();

function load(): Snapshot {
  if (!snapshot) snapshot = { doc: sanitizeDoc(readJson(PERSONAL_KEY, null)), hydrated: true };
  return snapshot;
}

function emit() {
  for (const l of listeners) l();
}

function onStorage(e: StorageEvent) {
  // `key` is null when another tab cleared all of localStorage.
  if (e.key !== null && e.key !== PERSONAL_KEY) return;
  snapshot = { doc: sanitizeDoc(readJson(PERSONAL_KEY, null)), hydrated: true };
  emit();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (listeners.size === 1 && typeof window !== "undefined") {
    window.addEventListener("storage", onStorage);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && typeof window !== "undefined") {
      window.removeEventListener("storage", onStorage);
    }
  };
}

export function getPersonal(): PersonalDoc {
  return load().doc;
}

function commit(next: PersonalDoc): PersonalDoc {
  snapshot = { doc: next, hydrated: true };
  writeJson(PERSONAL_KEY, next);
  emit();
  return next;
}

/** Test helper: forget the in-memory snapshot so the next read goes back to storage. */
export function resetPersonalStoreForTests() {
  snapshot = null;
}

export function usePersonal(): Snapshot {
  return useSyncExternalStore(subscribe, load, () => SERVER_SNAPSHOT);
}

const rand = () =>
  typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID().replace(/-/g, "").slice(0, 12)
    : Math.random().toString(36).slice(2, 14).padEnd(12, "0");

const newId = (prefix: string) => `${prefix}-${Date.now().toString(36)}${rand()}`;

export type TripInput = {
  kind: TripKind;
  /** Product and the quantity taken; a product appears once (the first wins). */
  lines: ReadonlyArray<{ ref: CanonicalRef; quantity: number }>;
  at?: Date;
};

export const personalActions = {
  /**
   * Records a finished trip or a cleared list. Does nothing while learning is off, or when no
   * line has a usable product and quantity. Returns whether anything was recorded.
   */
  recordTrip(input: TripInput): boolean {
    const current = load().doc;
    if (!current.prefs.learn) return false;
    const seen = new Set<number>();
    const lines: Trip["lines"] = [];
    const refs = new Map<number, CanonicalRef>();
    for (const { ref, quantity } of input.lines) {
      if (seen.has(ref.canonical_id)) continue;
      if (!Number.isFinite(quantity) || quantity <= 0 || quantity > 1000) continue;
      seen.add(ref.canonical_id);
      lines.push({ canonical_id: ref.canonical_id, quantity: Math.round(quantity * 1000) / 1000 });
      refs.set(ref.canonical_id, ref);
    }
    if (lines.length === 0) return false;
    const at = (input.at ?? new Date()).toISOString();
    const trip: Trip = {
      id: newId("t"),
      at,
      kind: input.kind,
      lines: lines.slice(0, LIMITS.linesPerTrip),
    };
    commit(
      normalizeDoc(
        {
          ...current,
          refs: [...refs.values(), ...current.refs],
          trips: [...current.trips, trip],
        },
        input.at,
      ),
    );
    return true;
  },

  /** One more time an exact brand was kept or a substitute turned down in a category. */
  recordSignal(taxonomyId: string, kind: SignalKind, at: Date = new Date()): boolean {
    const current = load().doc;
    if (!current.prefs.learn || !taxonomyId || taxonomyId.length > 60) return false;
    commit(
      normalizeDoc(
        {
          ...current,
          signals: [
            ...current.signals,
            { id: newId("s"), at: at.toISOString(), taxonomy_id: taxonomyId, kind },
          ],
        },
        at,
      ),
    );
    return true;
  },

  /** "Not now": hides a suggestion until its own rule brings it back (see `habits.ts`). */
  dismiss(kind: DismissalKind, key: string, at: Date = new Date()): void {
    const current = load().doc;
    const next: Dismissal = { kind, key, at: at.toISOString() };
    commit(normalizeDoc({ ...current, dismissals: [...current.dismissals, next] }, at));
  },

  /** Takes a dismissal back (the undo of a dismissal). */
  undismiss(kind: DismissalKind, key: string): void {
    const current = load().doc;
    commit({
      ...current,
      dismissals: current.dismissals.filter((d) => !(d.kind === kind && d.key === key)),
    });
  },

  setPrefs(patch: { learn?: boolean; value_packs?: boolean }, now: Date = new Date()): void {
    const current = load().doc;
    commit({
      ...current,
      prefs: { ...current.prefs, ...patch, updated_at: now.toISOString() },
    });
  },

  /** Forgets everything learned (trips, signals, dismissals); the preferences stay. */
  clearLearned(): void {
    const current = load().doc;
    commit({ ...EMPTY_DOC, prefs: current.prefs });
  },

  /** Replaces the whole document (the merge result of a sync). */
  replace(doc: PersonalDoc): void {
    commit(doc);
  },

  /** Removes the key itself (used by tests; "delete my data" removes it through `clearLocalData`). */
  wipe(): void {
    removeKey(PERSONAL_KEY);
    snapshot = { doc: EMPTY_DOC, hydrated: true };
    emit();
  },
};
