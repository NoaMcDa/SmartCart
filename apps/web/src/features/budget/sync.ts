/**
 * Optional sync of spend entries with the account (issue #70), for a signed-in user only. The
 * device copy (`sc-spend-v1`) is the source of truth the screens read; this module only
 *  - pushes entries that are `pending` with `POST /me/spend` (201, the account assigns the id,
 *    kept as `server_id` so a later pull does not add the entry twice). Every POST carries the
 *    entry's `client_id`, made once and stored with it, so a retry after a lost response returns
 *    the stored entry instead of a duplicate;
 *  - pulls months with `GET /me/spend?month=` and merges entries this device does not have;
 *  - corrects an entry's total (`PUT /me/spend/{id}`) and deletes one (`DELETE /me/spend/{id}`).
 *    Both change the device copy first and roll it back when the account refuses.
 * An entry is `pending` only when it was recorded while signed in; shops recorded signed out stay
 * on the device. Pushing and pulling swallow every failure: offline, a 401 or an API without the
 * route leaves the entry pending and the app working. Nothing here is sent to anyone else (D10,
 * D11).
 */
import { ApiError, deleteSpend, getSpend, postSpend, updateSpend } from "@/api/client";
import {
  correctSpendTotal,
  ensureClientId,
  loadSpend,
  markSynced,
  mergeServerEntries,
  replaceSpendRow,
  restoreSpendRow,
  spendInput,
  validSpendTotal,
  type RemovedSpend,
} from "./spendState";

/** Sends every pending entry; returns how many the account accepted. */
export async function pushPendingSpend(): Promise<number> {
  let accepted = 0;
  for (const id of [...loadSpend().pending]) {
    // Read the entry again each time: it may have been corrected or deleted meanwhile.
    const entry = ensureClientId(id);
    if (!entry || !loadSpend().pending.includes(id)) continue;
    try {
      const saved = await postSpend(spendInput(entry));
      accepted += 1;
      // Recorded one by one: a failure later must not lose the ids of the ones that went through.
      markSynced([{ id, serverId: saved.id }]);
    } catch {
      break; // offline or signed out: keep the rest pending, try again next time
    }
  }
  return accepted;
}

/** Merges the account's entries for `months` (`YYYY-MM`) into the device copy. */
export async function pullSpendMonths(months: ReadonlyArray<string>): Promise<number> {
  const results = await Promise.allSettled(months.map((m) => getSpend(m)));
  let added = 0;
  for (const r of results) {
    if (r.status === "fulfilled") added += mergeServerEntries(r.value.entries);
  }
  return added;
}

/** Signed in: push what is pending, then pull the given months. */
export async function syncSpend(months: ReadonlyArray<string>): Promise<void> {
  await pushPendingSpend();
  await pullSpendMonths(months);
}

export type CorrectOutcome =
  /** Saved on the device, and on the account when the person is signed in and the entry is there. */
  | "ok"
  /** Not a valid amount: nothing changed. */
  | "invalid"
  /** The account refused: the old total is back on the device. */
  | "failed"
  /** The entry is gone. */
  | "missing";

/**
 * "תיקון הסכום": replaces an entry's total with the person's actual one. The device copy changes
 * at once; for a signed-in user whose entry is already on the account, `PUT /me/spend/{id}`
 * follows and the old total is restored if it fails. An entry still waiting to be sent goes out
 * with its corrected total.
 */
export async function correctSpend(
  id: string,
  rawTotal: unknown,
  signedIn: boolean,
): Promise<CorrectOutcome> {
  const total = validSpendTotal(rawTotal);
  if (total === null) return "invalid";
  const changed = correctSpendTotal(id, total);
  if (!changed) return "missing";
  const { before, after } = changed;
  if (!signedIn || after.server_id === undefined) return "ok";
  try {
    await updateSpend(after.server_id, spendInput(after));
    return "ok";
  } catch {
    replaceSpendRow(before);
    return "failed";
  }
}

/**
 * The account side of a delete, run after the undo window. The device copy was already removed by
 * `removeSpendRow`; if the account refuses, the entry is put back and this returns false. An
 * entry that never reached the account (or a signed-out user) has nothing to delete there.
 */
export async function commitSpendRemoval(
  removed: RemovedSpend,
  signedIn: boolean,
): Promise<boolean> {
  const serverId = removed.row.server_id;
  if (!signedIn || serverId === undefined) return true;
  try {
    await deleteSpend(serverId);
    return true;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return true; // already gone
    restoreSpendRow(removed);
    return false;
  }
}
