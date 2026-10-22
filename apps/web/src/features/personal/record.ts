/**
 * The call sites that feed the personalization store: a finished shopping trip (store mode),
 * a cleared list (the list builder), and the moments a person keeps an exact brand or turns a
 * substitute down. Each is a no-op while learning is off (`personalActions` checks) and none
 * makes a request: everything stays on the device until `PersonalSync` mirrors it, signed in.
 */
import type { CanonicalRef } from "@/api/client";
import { getListState, type ListItem } from "@/state/list";
import { personalActions, getPersonal } from "./personalState";
import type { SignalKind } from "./personalDoc";

/** A cleared list is one shop's worth of evidence only when it was a real list. */
export const MIN_LIST_LINES = 3;

function knownRefs(): Map<number, CanonicalRef> {
  const refs = new Map<number, CanonicalRef>();
  for (const r of getPersonal().refs) refs.set(r.canonical_id, r);
  for (const it of getListState().items) {
    if (it.canonical) refs.set(it.canonical.canonical_id, it.canonical);
  }
  return refs;
}

/**
 * "סיימתי": the lines the person ticked off are a finished trip. With nothing ticked the plan's
 * lines are recorded as a list instead (weaker evidence: it counts only until a finished trip of
 * the same day covers it), because "finish" without a tick is not proof of what was bought.
 */
export function recordFinishedShop(
  items: ReadonlyArray<{ canonicalId: number; quantity: string; checked: boolean }>,
  at: Date = new Date(),
): boolean {
  const refs = knownRefs();
  const ticked = items.filter((i) => i.checked);
  const source = ticked.length > 0 ? ticked : items;
  const lines = source.flatMap((i) => {
    const ref = refs.get(i.canonicalId);
    const quantity = Number(i.quantity);
    return ref && quantity > 0 ? [{ ref, quantity }] : [];
  });
  return personalActions.recordTrip({
    kind: ticked.length > 0 ? "finished" : "list",
    lines,
    at,
  });
}

/** The list builder's "clear": the recognized rows of a list of at least three are a past list. */
export function recordClearedList(items: ReadonlyArray<ListItem>, at: Date = new Date()): boolean {
  const lines = items.flatMap((it) =>
    it.canonical && !it.notFound ? [{ ref: it.canonical, quantity: it.quantity }] : [],
  );
  if (lines.length < MIN_LIST_LINES) return false;
  return personalActions.recordTrip({ kind: "list", lines, at });
}

/**
 * A brand signal for the category of a product on the list: the exact brand was kept (the original
 * kept over a substitute, an undone swap, "exact" chosen in the flexibility sheet) or a substitute
 * was turned down ("not a good substitute", a dismissed swap).
 */
export function recordBrandSignal(canonicalId: number, kind: SignalKind): boolean {
  const row = getListState().items.find((i) => i.canonical?.canonical_id === canonicalId);
  const taxonomy = row?.canonical?.taxonomy_id;
  return taxonomy ? personalActions.recordSignal(taxonomy, kind) : false;
}
