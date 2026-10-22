/**
 * The personalization document: what the app learns from the person's own lists and finished
 * shopping trips, plus two preferences (phase 3). Pure functions only; the store is
 * `personalState.ts`, the account copy is `PersonalSync.tsx`.
 *
 * The shape is the API's `PersonalData` (`PUT /me/personal`), so the device copy and the account
 * copy are the same document and a merge never needs a translation. Everything is bounded: the
 * device keeps at most 40 trips of 60 lines each, 200 product references, 100 brand signals and 200
 * dismissals, and nothing older than 400 days. Nothing here is a price, a store, a location or free
 * text: product ids and quantities, the Hebrew and Arabic names of the products the person's own
 * list already held, category ids, dates and counts.
 */
import type { CanonicalRef } from "@/api/client";
import { israelDate } from "@/features/budget/month";

export const LIMITS = {
  trips: 40,
  linesPerTrip: 60,
  refs: 200,
  signals: 100,
  dismissals: 200,
  retentionDays: 400,
  /** The API refuses a body over 256 KB; the document is trimmed to stay well under it. */
  maxBytes: 200 * 1024,
} as const;

export type TripKind = "finished" | "list";
export type TripLine = { canonical_id: number; quantity: number };
export type Trip = { id: string; at: string; kind: TripKind; lines: TripLine[] };
export type SignalKind = "kept_brand" | "rejected_substitute";
export type Signal = { id: string; at: string; taxonomy_id: string; kind: SignalKind };
export type DismissalKind = "buy_again" | "brand_default" | "value_pack";
export type Dismissal = { kind: DismissalKind; key: string; at: string };
export type Prefs = { learn: boolean; value_packs: boolean; updated_at: string | null };

export type PersonalDoc = {
  version: 1;
  prefs: Prefs;
  refs: CanonicalRef[];
  trips: Trip[];
  signals: Signal[];
  dismissals: Dismissal[];
};

export const DEFAULT_PREFS: Prefs = { learn: true, value_packs: false, updated_at: null };

export const EMPTY_DOC: PersonalDoc = {
  version: 1,
  prefs: DEFAULT_PREFS,
  refs: [],
  trips: [],
  signals: [],
  dismissals: [],
};

// ---------------------------------------------------------------------------------------------
// Days

const MS_PER_DAY = 86_400_000;

/** Days since 1970-01-01 of the Israel calendar date of `iso`; NaN for text that is not a time. */
export function dayIndex(iso: string): number {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return Number.NaN;
  const [y, m, d] = israelDate(new Date(t)).split("-").map(Number) as [number, number, number];
  return Math.round(Date.UTC(y, m - 1, d) / MS_PER_DAY);
}

// ---------------------------------------------------------------------------------------------
// Validation of what comes back from storage or from the account

const KINDS_TRIP = new Set<string>(["finished", "list"]);
const KINDS_SIGNAL = new Set<string>(["kept_brand", "rejected_substitute"]);
const KINDS_DISMISSAL = new Set<string>(["buy_again", "brand_default", "value_pack"]);
const BASE_UNITS = new Set<string>(["100g", "100ml", "unit", "kg"]);
const ID = /^[A-Za-z0-9_-]{6,64}$/;

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;
const isTime = (v: unknown): v is string => typeof v === "string" && Number.isFinite(Date.parse(v));
const text = (v: unknown, max: number): string | null =>
  typeof v === "string" && v.length > 0 && v.length <= max ? v : null;

function sanitizeRef(raw: unknown): CanonicalRef | null {
  if (!isObject(raw)) return null;
  const id = raw.canonical_id;
  const he = text(raw.display_name_he, 120);
  const tax = text(raw.taxonomy_id, 60);
  if (typeof id !== "number" || !Number.isInteger(id) || !he || !tax) return null;
  if (typeof raw.base_unit !== "string" || !BASE_UNITS.has(raw.base_unit)) return null;
  const ar = text(raw.display_name_ar, 120);
  const path = Array.isArray(raw.category_path_he)
    ? raw.category_path_he
        .filter((p): p is string => typeof p === "string" && p.length > 0 && p.length <= 80)
        .slice(0, 4)
    : [];
  return {
    canonical_id: id,
    display_name_he: he,
    display_name_ar: ar,
    taxonomy_id: tax,
    base_unit: raw.base_unit as CanonicalRef["base_unit"],
    category_path_he: path,
  };
}

function sanitizeTrip(raw: unknown): Trip | null {
  if (!isObject(raw) || typeof raw.id !== "string" || !ID.test(raw.id) || !isTime(raw.at))
    return null;
  if (typeof raw.kind !== "string" || !KINDS_TRIP.has(raw.kind) || !Array.isArray(raw.lines))
    return null;
  const lines: TripLine[] = [];
  const seen = new Set<number>();
  for (const l of raw.lines) {
    if (!isObject(l)) continue;
    const id = l.canonical_id;
    const q = l.quantity;
    if (typeof id !== "number" || !Number.isInteger(id) || seen.has(id)) continue;
    if (typeof q !== "number" || !Number.isFinite(q) || q <= 0 || q > 1000) continue;
    seen.add(id);
    lines.push({ canonical_id: id, quantity: q });
  }
  if (lines.length === 0) return null;
  return {
    id: raw.id,
    at: raw.at,
    kind: raw.kind as TripKind,
    lines: lines.slice(0, LIMITS.linesPerTrip),
  };
}

function sanitizeSignal(raw: unknown): Signal | null {
  if (!isObject(raw) || typeof raw.id !== "string" || !ID.test(raw.id) || !isTime(raw.at))
    return null;
  const tax = text(raw.taxonomy_id, 60);
  if (!tax || typeof raw.kind !== "string" || !KINDS_SIGNAL.has(raw.kind)) return null;
  return { id: raw.id, at: raw.at, taxonomy_id: tax, kind: raw.kind as SignalKind };
}

function sanitizeDismissal(raw: unknown): Dismissal | null {
  if (!isObject(raw) || !isTime(raw.at)) return null;
  const key = text(raw.key, 60);
  if (!key || typeof raw.kind !== "string" || !KINDS_DISMISSAL.has(raw.kind)) return null;
  return { kind: raw.kind as DismissalKind, key, at: raw.at };
}

function sanitizePrefs(raw: unknown): Prefs {
  if (!isObject(raw)) return DEFAULT_PREFS;
  return {
    learn: typeof raw.learn === "boolean" ? raw.learn : true,
    value_packs: typeof raw.value_packs === "boolean" ? raw.value_packs : false,
    updated_at: isTime(raw.updated_at) ? raw.updated_at : null,
  };
}

const list = <T>(raw: unknown, one: (x: unknown) => T | null): T[] =>
  (Array.isArray(raw) ? raw : []).map(one).filter((x): x is T => x !== null);

/** A usable document from stored or received JSON that may be old, edited or damaged. */
export function sanitizeDoc(raw: unknown, now: Date = new Date()): PersonalDoc {
  if (!isObject(raw) || raw.version !== 1) return EMPTY_DOC;
  return normalizeDoc(
    {
      version: 1,
      prefs: sanitizePrefs(raw.prefs),
      refs: list(raw.refs, sanitizeRef),
      trips: list(raw.trips, sanitizeTrip),
      signals: list(raw.signals, sanitizeSignal),
      dismissals: list(raw.dismissals, sanitizeDismissal),
    },
    now,
  );
}

// ---------------------------------------------------------------------------------------------
// Bounds

const byAt = <T extends { at: string }>(a: T, b: T) => Date.parse(a.at) - Date.parse(b.at);

function dedupeBy<T>(items: T[], key: (item: T) => string): T[] {
  const seen = new Set<string>();
  const out: T[] = [];
  for (const item of items) {
    const k = key(item);
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(item);
  }
  return out;
}

/**
 * Applies every bound: nothing older than the retention window, the newest of each list up to its
 * limit, references only for products a kept trip names (the most recently used first when there
 * are too many), and finally the whole document under the byte budget by dropping the oldest
 * trips. Idempotent, and it never invents anything.
 */
export function normalizeDoc(doc: PersonalDoc, now: Date = new Date()): PersonalDoc {
  const today = dayIndex(now.toISOString());
  const fresh = (iso: string) => {
    const d = dayIndex(iso);
    return Number.isFinite(d) && today - d <= LIMITS.retentionDays;
  };
  let trips = dedupeBy([...doc.trips].filter((t) => fresh(t.at)).sort(byAt), (t) => t.id).slice(
    -LIMITS.trips,
  );
  const signals = dedupeBy(
    [...doc.signals].filter((s) => fresh(s.at)).sort(byAt),
    (s) => s.id,
  ).slice(-LIMITS.signals);
  // One dismissal per (kind, key): the latest.
  const latest = new Map<string, Dismissal>();
  for (const d of [...doc.dismissals].filter((d) => fresh(d.at)).sort(byAt)) {
    latest.set(`${d.kind}\u0000${d.key}`, d);
  }
  const dismissals = [...latest.values()].sort(byAt).slice(-LIMITS.dismissals);

  const build = (kept: Trip[]): PersonalDoc => {
    const lastUse = new Map<number, number>();
    kept.forEach((t, i) => t.lines.forEach((l) => lastUse.set(l.canonical_id, i)));
    const refs = dedupeBy(doc.refs, (r) => String(r.canonical_id))
      .filter((r) => lastUse.has(r.canonical_id))
      .sort((a, b) => (lastUse.get(b.canonical_id) ?? 0) - (lastUse.get(a.canonical_id) ?? 0))
      .slice(0, LIMITS.refs);
    return { version: 1, prefs: doc.prefs, refs, trips: kept, signals, dismissals };
  };

  let out = build(trips);
  while (out.trips.length > 1 && docBytes(out) > LIMITS.maxBytes) {
    trips = trips.slice(1);
    out = build(trips);
  }
  return out;
}

export function docBytes(doc: PersonalDoc): number {
  return new TextEncoder().encode(JSON.stringify(doc)).length;
}

/** The document has nothing learned in it (preferences aside). */
export function isEmptyHistory(doc: PersonalDoc): boolean {
  return doc.trips.length === 0 && doc.signals.length === 0 && doc.dismissals.length === 0;
}

// ---------------------------------------------------------------------------------------------
// Merge (device and account)

/**
 * The union of two documents: trips and signals by id, a dismissal per (kind, key) at its latest
 * time, references from either, and the preferences of whichever side changed them last (the
 * device wins a tie). Nothing is lost by syncing in either direction, and merging twice changes
 * nothing.
 */
export function mergeDocs(device: PersonalDoc, account: PersonalDoc, now: Date = new Date()) {
  const dev = Date.parse(device.prefs.updated_at ?? "") || 0;
  const acc = Date.parse(account.prefs.updated_at ?? "") || 0;
  return normalizeDoc(
    {
      version: 1,
      prefs: acc > dev ? account.prefs : device.prefs,
      refs: [...device.refs, ...account.refs],
      trips: [...device.trips, ...account.trips],
      signals: [...device.signals, ...account.signals],
      dismissals: [...device.dismissals, ...account.dismissals],
    },
    now,
  );
}

/** Same content, whatever the order: used to skip a push when nothing changed. */
export function docKey(doc: PersonalDoc): string {
  const ids = (xs: Array<{ id: string }>) => xs.map((x) => x.id).sort();
  return JSON.stringify([
    doc.prefs,
    ids(doc.trips),
    ids(doc.signals),
    doc.dismissals.map((d) => `${d.kind}:${d.key}:${d.at}`).sort(),
  ]);
}
