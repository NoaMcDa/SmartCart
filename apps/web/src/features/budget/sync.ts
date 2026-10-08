/**
 * Optional sync of spend entries with the account (issue #70), for a signed-in user only. The
 * device copy (`sc-spend-v1`) is the source of truth the screens read; this module only
 *  - pushes entries that are `pending` with `POST /me/spend` (idempotent on the entry id), and
 *  - pulls months with `GET /me/spend?month=` and merges entries this device does not have.
 * An entry is `pending` only when it was recorded while signed in; shops recorded signed out stay
 * on the device. Every failure is swallowed: offline, a 401 or an API without the route leaves the
 * entry pending and the app working. Nothing here is sent to anyone else (D10, D11).
 */
import { getSpend, postSpend } from "@/api/client";
import { loadSpend, markSynced, mergeServerEntries } from "./spendState";

/** Sends every pending entry; returns how many the server accepted. */
export async function pushPendingSpend(): Promise<number> {
  const store = loadSpend();
  const byId = new Map(store.entries.map((e) => [e.id, e]));
  const accepted: string[] = [];
  for (const id of store.pending) {
    const entry = byId.get(id);
    if (!entry) continue;
    try {
      await postSpend(entry);
      accepted.push(id);
    } catch {
      break; // offline or signed out: keep the rest pending, try again next time
    }
  }
  if (accepted.length) markSynced(accepted);
  return accepted.length;
}

/** Merges the server's entries for `months` (`YYYY-MM`) into the device copy. */
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
