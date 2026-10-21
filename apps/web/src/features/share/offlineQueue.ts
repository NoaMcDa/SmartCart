/**
 * Edits to a shared list made while the device has no connection (issue #101).
 *
 * Each edit is applied to the screen at once and appended here, in `localStorage` under
 * `sc-shared-queue-v1` (kept in memory when storage is blocked). When the connection is back the
 * queue is replayed against the freshest copy of the list (`applyEdits`) and then emptied. While
 * it is not empty the screen shows "ממתין לסנכרון".
 *
 * Edits are coalesced so the queue stays small and a replay cannot do something the person never
 * meant: the latest quantity or checked value of an item wins, a removal drops the earlier edits of
 * that item, and an edit to an item added while offline folds into its "add". Edits to an item
 * somebody else deleted meanwhile do nothing. The queue holds item ids, quantities and the names
 * of items the person added: no location, no profile, no prices.
 *
 * An edit of an existing item also remembers what the person saw when making it: `base`, the item's
 * version (`updated_at`), and `from`, the value of the field they changed. The replay sends `base`
 * as the precondition of the per-item write; when the item changed meanwhile the server answers 409
 * with its current row and `itemWrites.ts` decides, from `from`, whether the edit still makes sense.
 */
import { useSyncExternalStore } from "react";
import { ApiError } from "@/api/client";
import { readJson, writeJson } from "@/state/storage";
import type { SharedItem } from "./listSync";

export const SHARED_QUEUE_KEY = "sc-shared-queue-v1";
/** More than this many pending edits for one list drops the oldest, so a long outage cannot fill storage. */
export const MAX_QUEUED_EDITS = 200;

/** What the person saw when they made the edit; absent on edits queued before this existed. */
type Seen = { base?: string | null };

export type QueuedEdit =
  | ({ kind: "quantity"; itemId: number; quantity: number; from?: number } & Seen)
  | ({ kind: "checked"; itemId: number; checked: boolean; from?: boolean } & Seen)
  | ({ kind: "remove"; itemId: number } & Seen)
  /** `itemId` is a negative placeholder until the server gives the row its real id. */
  | { kind: "add"; itemId: number; canonicalId: number | null; name: string; quantity: number };

type Stored = { version: 1; lists: Record<string, QueuedEdit[]> };

const EMPTY: Stored = { version: 1, lists: {} };
const listeners = new Set<() => void>();
let snapshot: Stored | null = null;
// One stable array per list, so `useSyncExternalStore` sees no change when nothing changed.
const NONE: ReadonlyArray<QueuedEdit> = [];

function isEdit(raw: unknown): raw is QueuedEdit {
  if (!raw || typeof raw !== "object") return false;
  const e = raw as Record<string, unknown>;
  if (typeof e.itemId !== "number" || !Number.isFinite(e.itemId)) return false;
  if (e.base !== undefined && e.base !== null && typeof e.base !== "string") return false;
  switch (e.kind) {
    case "quantity":
      return (
        typeof e.quantity === "number" &&
        e.quantity > 0 &&
        (e.from === undefined || typeof e.from === "number")
      );
    case "checked":
      return (
        typeof e.checked === "boolean" && (e.from === undefined || typeof e.from === "boolean")
      );
    case "remove":
      return true;
    case "add":
      return (
        typeof e.name === "string" &&
        typeof e.quantity === "number" &&
        e.quantity > 0 &&
        (e.canonicalId === null || typeof e.canonicalId === "number")
      );
    default:
      return false;
  }
}

function sanitize(raw: unknown): Stored {
  if (!raw || typeof raw !== "object") return EMPTY;
  const s = raw as Partial<Stored>;
  if (s.version !== 1 || !s.lists || typeof s.lists !== "object") return EMPTY;
  const lists: Record<string, QueuedEdit[]> = {};
  for (const [id, edits] of Object.entries(s.lists)) {
    const clean = (Array.isArray(edits) ? edits : []).filter(isEdit).slice(-MAX_QUEUED_EDITS);
    if (clean.length > 0) lists[id] = clean;
  }
  return { version: 1, lists };
}

let watching = false;

/**
 * Another tab changed the queue (it replayed it, or added edits), or the data was deleted: read it
 * again instead of writing this tab's older copy over it, which would replay edits twice or bring
 * back what "delete my data" removed.
 */
function watchOtherTabs() {
  if (watching || typeof window === "undefined") return;
  watching = true;
  window.addEventListener("storage", (e) => {
    if (e.key !== null && e.key !== SHARED_QUEUE_KEY) return;
    snapshot = null;
    listeners.forEach((l) => l());
  });
}

function load(): Stored {
  watchOtherTabs();
  if (!snapshot) snapshot = sanitize(readJson(SHARED_QUEUE_KEY, null));
  return snapshot;
}

function save(lists: Record<string, QueuedEdit[]>) {
  snapshot = { version: 1, lists };
  writeJson(SHARED_QUEUE_KEY, snapshot);
  listeners.forEach((l) => l());
}

/** The pending edits of one list, oldest first. */
export function queuedEdits(listId: number): ReadonlyArray<QueuedEdit> {
  return load().lists[String(listId)] ?? NONE;
}

export function queuedCount(listId: number): number {
  return queuedEdits(listId).length;
}

/** How many edits are waiting for this list; re-renders when it changes. */
export function useQueuedCount(listId: number): number {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => {
        listeners.delete(l);
      };
    },
    () => queuedCount(listId),
    () => 0,
  );
}

/**
 * A newer edit of the same field takes the place of an older one, but what the person saw is what
 * they saw before the first of them: the version and the value the server had.
 */
function keepFirstSeen<T extends QueuedEdit>(edit: T, earlier: QueuedEdit | undefined): T {
  if (!earlier || earlier.kind === "add") return edit;
  const seen: { base?: string | null; from?: number | boolean } = {};
  if (earlier.base !== undefined) seen.base = earlier.base;
  if ("from" in earlier && earlier.from !== undefined) seen.from = earlier.from;
  return { ...edit, ...seen };
}

/** Pure: the queue after `edit`, with the coalescing rules above. */
export function coalesce(queue: ReadonlyArray<QueuedEdit>, edit: QueuedEdit): QueuedEdit[] {
  const mine = (e: QueuedEdit) => e.itemId === edit.itemId;
  switch (edit.kind) {
    case "quantity": {
      if (queue.some((e) => e.kind === "add" && mine(e))) {
        return queue.map((e) =>
          e.kind === "add" && mine(e) ? { ...e, quantity: edit.quantity } : e,
        );
      }
      const earlier = queue.find((e) => e.kind === "quantity" && mine(e));
      return [
        ...queue.filter((e) => !(e.kind === "quantity" && mine(e))),
        keepFirstSeen(edit, earlier),
      ];
    }
    case "checked": {
      const earlier = queue.find((e) => e.kind === "checked" && mine(e));
      return [
        ...queue.filter((e) => !(e.kind === "checked" && mine(e))),
        keepFirstSeen(edit, earlier),
      ];
    }
    case "remove": {
      const addedOffline = queue.some((e) => e.kind === "add" && mine(e));
      const rest = queue.filter((e) => !mine(e));
      // An item that never reached the server needs no removal at all.
      return addedOffline ? rest : [...rest, edit];
    }
    case "add":
      return [...queue.filter((e) => !(e.kind === "add" && mine(e))), edit];
  }
}

/**
 * Appends an edit (coalescing it with what is already waiting) and persists the queue. While the
 * queue is being replayed the head must not move, so `append` adds the edit as it is.
 */
export function enqueueEdit(
  listId: number,
  edit: QueuedEdit,
  options: { append?: boolean } = {},
): void {
  const state = load();
  const key = String(listId);
  const current = state.lists[key] ?? [];
  const next = (options.append ? [...current, edit] : coalesce(current, edit)).slice(
    -MAX_QUEUED_EDITS,
  );
  save({ ...state.lists, [key]: next });
}

/** Removes the first `count` edits (the ones just sent), keeping any made while sending. */
export function dropFirstEdits(listId: number, count: number): void {
  const state = load();
  const key = String(listId);
  const rest = (state.lists[key] ?? []).slice(count);
  const lists = { ...state.lists };
  if (rest.length > 0) lists[key] = rest;
  else delete lists[key];
  save(lists);
}

/**
 * An item added offline reached the server and got its real id: removes the "add" (the first
 * edit, just sent) and gives the edits still waiting for that item (a tick, a quantity, a removal)
 * the real id (and, as what they were made on, the saved row's version), in one write. A flush that fails right after, or a reload, then retries those edits
 * against the real row instead of the placeholder, which no row has.
 */
export function completeAdd(
  listId: number,
  placeholder: number,
  realId: number,
  version: string | null = null,
): void {
  const state = load();
  const key = String(listId);
  const rest = (state.lists[key] ?? [])
    .slice(1)
    .map((e) =>
      e.itemId === placeholder
        ? { ...e, itemId: realId, ...(version && e.kind !== "add" ? { base: version } : {}) }
        : e,
    );
  const lists = { ...state.lists };
  if (rest.length > 0) lists[key] = rest;
  else delete lists[key];
  save(lists);
}

/**
 * An edit of an item was saved and the item has a new version: the edits still waiting for the same
 * item were made on the version before, which was this person's own earlier change, so they move on
 * to the new one (otherwise they would conflict with the edit that was just sent).
 */
export function rebaseEdits(listId: number, itemId: number, from: string | null, to: string): void {
  if (!from) return;
  const state = load();
  const key = String(listId);
  const queue = state.lists[key] ?? [];
  const stale = (e: QueuedEdit) => e.kind !== "add" && e.itemId === itemId && e.base === from;
  if (!queue.some(stale)) return;
  save({ ...state.lists, [key]: queue.map((e) => (stale(e) ? { ...e, base: to } : e)) });
}

export function clearEdits(listId: number): void {
  dropFirstEdits(listId, Number.MAX_SAFE_INTEGER);
}

/** Pure: one edit applied to a list of items. An edit to an item that is not there changes nothing. */
export function applyEdit(items: ReadonlyArray<SharedItem>, edit: QueuedEdit): SharedItem[] {
  switch (edit.kind) {
    case "quantity":
      return items.map((i) => (i.id === edit.itemId ? { ...i, quantity: edit.quantity } : i));
    case "checked":
      return items.map((i) => (i.id === edit.itemId ? { ...i, checked: edit.checked } : i));
    case "remove":
      return items.filter((i) => i.id !== edit.itemId);
    case "add": {
      if (items.some((i) => i.id === edit.itemId)) return [...items];
      const sort = items.reduce((max, i) => Math.max(max, i.sort), -1) + 1;
      return [
        ...items,
        {
          id: edit.itemId,
          canonicalId: edit.canonicalId,
          name: edit.name,
          quantity: edit.quantity,
          flexLevel: "any_brand",
          confirmed: true,
          checked: false,
          sort,
          updatedAt: null,
          version: null,
        },
      ];
    }
  }
}

export function applyEdits(
  items: ReadonlyArray<SharedItem>,
  edits: ReadonlyArray<QueuedEdit>,
): SharedItem[] {
  return edits.reduce<SharedItem[]>((acc, e) => applyEdit(acc, e), [...items]);
}

/**
 * Whether a failure means "no connection" (keep the edit and retry) rather than "the server said
 * no" (undo the edit and tell the person). Covers `fetch` rejecting, the browser reporting
 * offline, and the Supabase client's wrapped network errors.
 */
export function isNetworkFailure(err: unknown): boolean {
  if (err instanceof ApiError) return false;
  if (typeof navigator !== "undefined" && navigator.onLine === false) return true;
  if (err instanceof TypeError) return true;
  // The client gives up on a request that gets no answer (`REQUEST_TIMEOUT_MS`): a dead link.
  if (
    typeof err === "object" &&
    err !== null &&
    (err as { name?: unknown }).name === "TimeoutError"
  ) {
    return true;
  }
  const message =
    typeof err === "object" && err !== null && "message" in err
      ? String((err as { message: unknown }).message)
      : "";
  return /failed to fetch|networkerror|network request failed|load failed/i.test(message);
}

/** A negative placeholder id for an item added offline, unique across reloads. */
let placeholderSeq = 0;
export function placeholderId(): number {
  placeholderSeq += 1;
  return -(Date.now() * 1000 + (placeholderSeq % 1000));
}

/** Test helper: forget the in-memory copy (a reload) or everything. */
export function resetQueueForTests(): void {
  snapshot = null;
  placeholderSeq = 0;
}
