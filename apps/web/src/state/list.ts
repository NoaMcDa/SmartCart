/**
 * The shopping list: parsed rows with quantity and flexibility, plus the user's remembered
 * category defaults (flex_defaults by taxonomy id). Persisted in localStorage under LIST_KEY and
 * restored on reload; every storage access is wrapped so a private window still works in memory.
 *
 * The reducer (`listReducer`) is pure and unit tested; `useList()` and the action helpers wrap it
 * in a tiny external store shared by every screen (list builder, results, substitution card,
 * and W5's profile flexibility defaults through `useFlexDefaults`).
 */
import { useSyncExternalStore } from "react";
import type { BasketItemInput, CanonicalRef, FlexLevel, ParsedRow } from "@/api/client";
import { isFlexLevel, resolveFlexLevel, type FlexDefaults } from "./flex";
import { readJson, writeJson } from "./storage";

export const LIST_KEY = "sc-list-v1";

export type ListItem = {
  id: string;
  /** What the user typed for this row. */
  inputText: string;
  canonical: CanonicalRef | null;
  /** Alternatives offered while the row needs confirmation. */
  candidates: CanonicalRef[];
  quantity: number;
  /** "kg" when the user gave a weight. */
  unit: "kg" | null;
  isWeighed: boolean;
  flexLevel: FlexLevel;
  /** Soft attributes the user allows to differ (flexibility sheet checkboxes). */
  allow: string[];
  /** The barcode to keep when the user chose "keep the original" on a substitute. */
  exactItemId: number | null;
  needsConfirmation: boolean;
  notFound: boolean;
  confidence: number;
};

export type ListState = {
  version: 1;
  name: string;
  items: ListItem[];
  /** taxonomy id -> level, written by "remember this for all <category>". */
  flexDefaults: FlexDefaults;
  updatedAt: string | null;
};

export const EMPTY_LIST: ListState = {
  version: 1,
  name: "הקנייה השבועית",
  items: [],
  flexDefaults: {},
  updatedAt: null,
};

export type FlexChoice = {
  level: FlexLevel;
  allow: string[];
  /** Store the level as the default for the item's category and apply it to its rows. */
  remember: boolean;
};

export type ListAction =
  | { type: "add"; rows: ParsedRow[]; ids?: string[] }
  | { type: "setQuantity"; id: string; quantity: number }
  | { type: "setFlex"; id: string; choice: FlexChoice }
  | { type: "confirm"; id: string; canonical?: CanonicalRef }
  | { type: "remove"; id: string }
  | { type: "clear" }
  | { type: "keepOriginal"; canonicalId: number; originalItemId: number | null }
  | { type: "setFlexDefault"; taxonomyId: string; level: FlexLevel | null }
  | { type: "replace"; state: ListState };

let idCounter = 0;
export function newId(): string {
  idCounter += 1;
  const rand =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID().slice(0, 8)
      : Math.random().toString(36).slice(2, 10);
  return `r${Date.now().toString(36)}${idCounter}${rand}`;
}

function toQuantity(raw: string | number | undefined): number {
  const n = typeof raw === "number" ? raw : Number.parseFloat(raw ?? "1");
  return Number.isFinite(n) && n > 0 ? n : 1;
}

/** A parsed row as a list item, with the flexibility level resolved (user, smart, server). */
export function itemFromRow(row: ParsedRow, defaults: FlexDefaults, id = newId()): ListItem {
  const canonical = row.not_found ? null : (row.canonical ?? null);
  return {
    id,
    inputText: row.input_text,
    canonical,
    candidates: row.candidates ?? [],
    quantity: toQuantity(row.quantity),
    unit: row.unit ?? null,
    isWeighed: Boolean(row.is_weighed),
    flexLevel: resolveFlexLevel(canonical?.taxonomy_id, defaults, row.flex_level),
    allow: [],
    exactItemId: null,
    needsConfirmation: Boolean(row.needs_confirmation) && !row.not_found && canonical !== null,
    notFound: Boolean(row.not_found) || canonical === null,
    confidence: row.confidence,
  };
}

const round3 = (n: number) => Math.round(n * 1000) / 1000;

function touch(state: ListState, patch: Partial<ListState>): ListState {
  return { ...state, ...patch, updatedAt: new Date().toISOString() };
}

export function listReducer(state: ListState, action: ListAction): ListState {
  switch (action.type) {
    case "add": {
      const items = [...state.items];
      action.rows.forEach((row, i) => {
        const item = itemFromRow(row, state.flexDefaults, action.ids?.[i]);
        // The same confident product twice adds up instead of making a second row.
        const existing =
          item.canonical && !item.needsConfirmation
            ? items.findIndex(
                (it) =>
                  it.canonical?.canonical_id === item.canonical?.canonical_id &&
                  !it.needsConfirmation &&
                  it.unit === item.unit,
              )
            : -1;
        if (existing >= 0) {
          const prev = items[existing]!;
          items[existing] = { ...prev, quantity: round3(prev.quantity + item.quantity) };
        } else {
          items.push(item);
        }
      });
      return touch(state, { items });
    }
    case "setQuantity":
      return touch(state, {
        items: state.items.map((it) =>
          it.id === action.id && action.quantity > 0
            ? { ...it, quantity: round3(action.quantity) }
            : it,
        ),
      });
    case "setFlex": {
      const target = state.items.find((it) => it.id === action.id);
      if (!target) return state;
      const { level, allow, remember } = action.choice;
      const taxonomy = target.canonical?.taxonomy_id;
      const flexDefaults =
        remember && taxonomy ? { ...state.flexDefaults, [taxonomy]: level } : state.flexDefaults;
      const items = state.items.map((it) => {
        if (it.id === action.id) {
          return {
            ...it,
            flexLevel: level,
            allow: level === "exact" ? [] : [...allow],
            exactItemId: level === "exact" ? it.exactItemId : null,
          };
        }
        if (remember && taxonomy && it.canonical?.taxonomy_id === taxonomy) {
          return {
            ...it,
            flexLevel: level,
            exactItemId: level === "exact" ? it.exactItemId : null,
          };
        }
        return it;
      });
      return touch(state, { items, flexDefaults });
    }
    case "confirm":
      return touch(state, {
        items: state.items.map((it) => {
          if (it.id !== action.id) return it;
          const canonical = action.canonical ?? it.canonical;
          const changed = canonical?.canonical_id !== it.canonical?.canonical_id;
          return {
            ...it,
            canonical,
            candidates: [],
            needsConfirmation: false,
            confidence: 1,
            flexLevel: changed
              ? resolveFlexLevel(canonical?.taxonomy_id, state.flexDefaults, it.flexLevel)
              : it.flexLevel,
          };
        }),
      });
    case "remove":
      return touch(state, { items: state.items.filter((it) => it.id !== action.id) });
    case "clear":
      return touch(state, { items: [] });
    case "keepOriginal":
      return touch(state, {
        items: state.items.map((it) =>
          it.canonical?.canonical_id === action.canonicalId
            ? { ...it, flexLevel: "exact", allow: [], exactItemId: action.originalItemId }
            : it,
        ),
      });
    case "setFlexDefault": {
      const flexDefaults = { ...state.flexDefaults };
      if (action.level) flexDefaults[action.taxonomyId] = action.level;
      else delete flexDefaults[action.taxonomyId];
      return touch(state, { flexDefaults });
    }
    case "replace":
      return action.state;
  }
}

/** The rows the API can price: resolved canonicals, duplicates merged. */
export function basketItems(state: Pick<ListState, "items">): BasketItemInput[] {
  const byCanonical = new Map<number, BasketItemInput>();
  for (const it of state.items) {
    if (!it.canonical || it.notFound) continue;
    const id = it.canonical.canonical_id;
    const prev = byCanonical.get(id);
    if (prev) {
      prev.quantity = round3(Number(prev.quantity) + it.quantity);
      continue;
    }
    byCanonical.set(id, {
      canonical_id: id,
      quantity: it.quantity,
      flex_level: it.flexLevel,
      ...(it.flexLevel === "exact" && it.exactItemId ? { exact_item_id: it.exactItemId } : {}),
    });
  }
  return [...byCanonical.values()];
}

/** Group rows by department, in order of first appearance; unrecognized rows come last. */
export function groupByDepartment(items: ListItem[]): Array<{ name: string; items: ListItem[] }> {
  const groups = new Map<string, ListItem[]>();
  for (const it of items) {
    if (it.notFound) continue;
    const name = it.canonical?.category_path_he?.[0] ?? "שונות";
    const list = groups.get(name) ?? [];
    list.push(it);
    groups.set(name, list);
  }
  return [...groups.entries()].map(([name, list]) => ({ name, items: list }));
}

// ---------------------------------------------------------------------------------------------
// Validation of what comes back from storage (it may be stale, edited or from an older version).

function sanitizeItem(raw: unknown): ListItem | null {
  if (!raw || typeof raw !== "object") return null;
  const it = raw as Partial<ListItem>;
  if (typeof it.id !== "string" || typeof it.inputText !== "string") return null;
  return {
    id: it.id,
    inputText: it.inputText,
    canonical: it.canonical ?? null,
    candidates: Array.isArray(it.candidates) ? it.candidates : [],
    quantity: toQuantity(it.quantity),
    unit: it.unit === "kg" ? "kg" : null,
    isWeighed: Boolean(it.isWeighed),
    flexLevel: isFlexLevel(it.flexLevel) ? it.flexLevel : "any_brand",
    allow: Array.isArray(it.allow) ? it.allow.filter((a) => typeof a === "string") : [],
    exactItemId: typeof it.exactItemId === "number" ? it.exactItemId : null,
    needsConfirmation: Boolean(it.needsConfirmation),
    notFound: Boolean(it.notFound) || !it.canonical,
    confidence: typeof it.confidence === "number" ? it.confidence : 1,
  };
}

export function sanitizeState(raw: unknown): ListState {
  if (!raw || typeof raw !== "object") return EMPTY_LIST;
  const s = raw as Partial<ListState>;
  if (s.version !== 1) return EMPTY_LIST;
  const flexDefaults: FlexDefaults = {};
  for (const [k, v] of Object.entries(s.flexDefaults ?? {})) {
    if (isFlexLevel(v)) flexDefaults[k] = v;
  }
  return {
    version: 1,
    name: typeof s.name === "string" && s.name ? s.name : EMPTY_LIST.name,
    items: (Array.isArray(s.items) ? s.items : [])
      .map(sanitizeItem)
      .filter((x): x is ListItem => x !== null),
    flexDefaults,
    updatedAt: typeof s.updatedAt === "string" ? s.updatedAt : null,
  };
}

// ---------------------------------------------------------------------------------------------
// Store

type Snapshot = { state: ListState; hydrated: boolean };

const SERVER_SNAPSHOT: Snapshot = { state: EMPTY_LIST, hydrated: false };
let snapshot: Snapshot | null = null;
const listeners = new Set<() => void>();

function load(): Snapshot {
  if (!snapshot) snapshot = { state: sanitizeState(readJson(LIST_KEY, null)), hydrated: true };
  return snapshot;
}

function emit() {
  for (const l of listeners) l();
}

function onStorage(e: StorageEvent) {
  if (e.key !== LIST_KEY) return;
  snapshot = { state: sanitizeState(readJson(LIST_KEY, null)), hydrated: true };
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

export function getListState(): ListState {
  return load().state;
}

export function dispatch(action: ListAction): ListState {
  const next = listReducer(load().state, action);
  snapshot = { state: next, hydrated: true };
  writeJson(LIST_KEY, next);
  emit();
  return next;
}

/** Test helper: forget the in-memory snapshot so the next read goes back to storage. */
export function resetListStoreForTests() {
  snapshot = null;
}

export function useList(): Snapshot {
  return useSyncExternalStore(subscribe, load, () => SERVER_SNAPSHOT);
}

/** The user's remembered category defaults (Profile shows and edits them; W5). */
export function useFlexDefaults(): FlexDefaults {
  return useList().state.flexDefaults;
}

export const listActions = {
  add: (rows: ParsedRow[]) => dispatch({ type: "add", rows }),
  setQuantity: (id: string, quantity: number) => dispatch({ type: "setQuantity", id, quantity }),
  setFlex: (id: string, choice: FlexChoice) => dispatch({ type: "setFlex", id, choice }),
  confirm: (id: string, canonical?: CanonicalRef) => dispatch({ type: "confirm", id, canonical }),
  remove: (id: string) => dispatch({ type: "remove", id }),
  clear: () => dispatch({ type: "clear" }),
  keepOriginal: (canonicalId: number, originalItemId: number | null) =>
    dispatch({ type: "keepOriginal", canonicalId, originalItemId }),
  setFlexDefault: (taxonomyId: string, level: FlexLevel | null) =>
    dispatch({ type: "setFlexDefault", taxonomyId, level }),
};
