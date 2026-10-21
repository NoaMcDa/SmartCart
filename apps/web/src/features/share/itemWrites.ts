/**
 * One edit of a shared list written to the API, per item (polling mode), and what to do when the
 * item changed since the person saw it.
 *
 * Each write carries the item's version (`QueuedEdit.base`, the `updated_at` the person saw). When
 * somebody else changed the item meanwhile the API answers 409 with the item as it is now, and the
 * merge rule decides, per field and never for the whole list:
 *
 * - the item already has the value the person wanted: nothing to do, quietly;
 * - the field the person edited is still what they saw (somebody else changed another field, for
 *   example a quantity while this person ticked the box): the edit is sent again on the current
 *   version, quietly, and the other person's change stays;
 * - somebody else changed the same field to another value: their change stays and the person's
 *   edit is dropped, with a quiet note (`superseded`). Latest writer wins, as in realtime mode,
 *   but never silently for the one who lost;
 * - removing an item somebody changed meanwhile: the item stays (somebody just worked on it) with
 *   the same note. Removing an item somebody already removed, or editing one that is gone, is a 404:
 *   the first is done, the second is dropped with the note.
 *
 * An edit that keeps losing (three rounds of somebody changing the item again) is dropped with the
 * note too.
 */
import {
  ApiError,
  addListItem,
  conflictItem,
  deleteListItem,
  patchListItem,
  type ListItemPatch,
} from "@/api/client";
import { itemFromRow, type SharedItem } from "./listSync";
import type { QueuedEdit } from "./offlineQueue";

/** How many times an edit is sent again on a newer version before it is given up. */
export const MAX_MERGE_ATTEMPTS = 3;

export type WriteOutcome = {
  /** The item as the server has it after this write: the saved row, the row that won, or null when it is gone. */
  item: SharedItem | null;
  /** The person's edit was written (not dropped, not already there). */
  saved: boolean;
  /** The person's edit did not make it and the server's version stayed: tell them, quietly. */
  superseded: boolean;
};

export type Verdict = "already" | "reapply" | "superseded";

/** Pure: what to do with `edit` now that the server's row is `current`. */
export function mergeVerdict(edit: QueuedEdit, current: SharedItem): Verdict {
  switch (edit.kind) {
    case "checked":
      if (current.checked === edit.checked) return "already";
      return edit.from === undefined || current.checked === edit.from ? "reapply" : "superseded";
    case "quantity":
      if (current.quantity === edit.quantity) return "already";
      return edit.from === undefined || current.quantity === edit.from ? "reapply" : "superseded";
    case "remove":
      return "superseded";
    case "add":
      return "reapply";
  }
}

function patchOf(edit: QueuedEdit, base: string | null): ListItemPatch {
  const expected = base ? { expected_updated_at: base } : {};
  if (edit.kind === "quantity") return { quantity: edit.quantity, ...expected };
  if (edit.kind === "checked") return { checked: edit.checked, ...expected };
  return expected;
}

/**
 * Writes one queued edit. Throws what the API throws for anything but 404 and 409 (the caller tells
 * a lost connection from a refusal).
 */
export async function writeItem(listId: number, edit: QueuedEdit): Promise<WriteOutcome> {
  if (edit.kind === "add") {
    const row = await addListItem(listId, {
      canonical_id: edit.canonicalId,
      input_text: edit.name,
      quantity: edit.quantity,
      // A repeat of an add the server already saved answers with that row (200), not a second one.
      ...(edit.clientId ? { client_id: edit.clientId } : {}),
    });
    return { item: itemFromRow(row), saved: true, superseded: false };
  }

  let base = edit.base ?? null;
  let latest: SharedItem | null = null;
  for (let attempt = 0; attempt < MAX_MERGE_ATTEMPTS; attempt++) {
    try {
      if (edit.kind === "remove") {
        await deleteListItem(listId, edit.itemId, base);
        return { item: null, saved: true, superseded: false };
      }
      const row = await patchListItem(listId, edit.itemId, patchOf(edit, base));
      return { item: itemFromRow(row), saved: true, superseded: false };
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        // Gone: a removal is done; an edit of an item somebody removed has nothing to apply to.
        return { item: null, saved: false, superseded: edit.kind !== "remove" };
      }
      const row = conflictItem(err);
      const current = row ? itemFromRow(row) : null;
      if (!current) throw err;
      latest = current;
      const verdict = mergeVerdict(edit, current);
      if (verdict === "already") return { item: current, saved: false, superseded: false };
      if (verdict === "superseded") return { item: current, saved: false, superseded: true };
      base = current.version;
    }
  }
  return { item: latest, saved: false, superseded: true };
}
