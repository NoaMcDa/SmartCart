import { search } from "@/api/client";
import { departmentOf, loadSession, saveSession, type ShoppingSession } from "./session";

/**
 * Looks up the taxonomy department of items that have none, by searching the chain item's name
 * and taking the hit with the same canonical id. Runs once when shopping starts (online); on any
 * failure the item stays in "אחר" and the checklist still works. At most 5 requests at a time.
 */
export async function lookupDepartments(
  items: ReadonlyArray<{ canonicalId: number; name: string }>,
  concurrency = 5,
): Promise<Record<number, string>> {
  const found: Record<number, string> = {};
  const queue = [...items];
  async function worker() {
    for (let next = queue.shift(); next; next = queue.shift()) {
      try {
        const res = await search(next.name, 8);
        const hit = res.hits.find((h) => h.canonical.canonical_id === next.canonicalId);
        if (hit) found[next.canonicalId] = hit.canonical.taxonomy_id;
      } catch {
        /* offline or API down: leave the item in "אחר" */
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, queue.length) }, worker));
  return found;
}

/** Fills in departments for a stored session (once) and saves it. */
export async function resolveDepartments(session: ShoppingSession): Promise<void> {
  const missing = session.items.filter((i) => i.department === "other");
  const found = missing.length
    ? await lookupDepartments(missing.map((i) => ({ canonicalId: i.canonicalId, name: i.name })))
    : {};
  // Re-read: the user may have ticked items while the lookups ran, and those marks must survive.
  const current = loadSession();
  if (!current || current.storeId !== session.storeId) return;
  saveSession({
    ...current,
    departmentsResolved: true,
    items: current.items.map((i) =>
      i.department === "other" && found[i.canonicalId]
        ? { ...i, department: departmentOf(found[i.canonicalId]) }
        : i,
    ),
  });
}
