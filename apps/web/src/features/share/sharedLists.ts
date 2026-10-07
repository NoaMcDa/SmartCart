/**
 * What this device knows about shared lists (issue #34), in localStorage under `sc-shared-lists-v1`:
 * the server id of the list this device shared from the local list (so "share" opens the same list
 * next time), and the lists it joined through an invite link. Nothing here is a secret: the invite
 * token is never stored, and access is enforced by the API and row-level security.
 */
import type { ListItem } from "@/state/list";
import type { Schemas, ShoppingListInput } from "@/api/client";
import { readJson, writeJson } from "@/state/storage";

export const SHARED_LISTS_KEY = "sc-shared-lists-v1";

export type JoinedList = { id: number; name: string; joinedAt: string };

export type SharedRegistry = {
  version: 1;
  /** Server id of the list shared from this device's list, or null. */
  ownedListId: number | null;
  joined: JoinedList[];
};

const EMPTY: SharedRegistry = { version: 1, ownedListId: null, joined: [] };

export function readRegistry(): SharedRegistry {
  const raw = readJson<Partial<SharedRegistry> | null>(SHARED_LISTS_KEY, null);
  if (!raw || raw.version !== 1) return EMPTY;
  const joined = (Array.isArray(raw.joined) ? raw.joined : [])
    .filter(
      (j): j is JoinedList => Boolean(j) && typeof j.id === "number" && typeof j.name === "string",
    )
    .map((j) => ({ id: j.id, name: j.name.slice(0, 120), joinedAt: String(j.joinedAt ?? "") }));
  return {
    version: 1,
    ownedListId: typeof raw.ownedListId === "number" ? raw.ownedListId : null,
    joined,
  };
}

export function setOwnedListId(id: number | null): void {
  writeJson(SHARED_LISTS_KEY, { ...readRegistry(), ownedListId: id });
}

export function rememberJoined(list: { id: number; name: string }): void {
  const reg = readRegistry();
  const joined = [
    ...reg.joined.filter((j) => j.id !== list.id),
    { id: list.id, name: list.name, joinedAt: new Date().toISOString() },
  ];
  writeJson(SHARED_LISTS_KEY, { ...reg, joined });
}

/**
 * The server copy of the local list: confident rows only (an unrecognised row has nothing to
 * share), each with its Hebrew name so every member sees names without a catalog lookup. The
 * flexibility level travels with the item; members' own overrides are not shared (issue #34: the
 * chosen behaviour is per-item level, set by whoever last edited the item).
 */
export function localListToServer(name: string, items: ReadonlyArray<ListItem>): ShoppingListInput {
  const rows: Schemas["ListItemIn"][] = items
    .filter((it) => it.canonical && !it.notFound)
    .map((it) => ({
      canonical_id: it.canonical!.canonical_id,
      input_text: it.canonical!.display_name_he,
      quantity: it.quantity,
      flex_level: it.flexLevel,
      confirmed: !it.needsConfirmation,
    }));
  return { name, is_recurring: false, items: rows };
}
