"use client";

/**
 * A shared list that stays in step across devices (issue #34).
 *
 * Signed in with Supabase configured ("realtime" mode): the items are read through the API once,
 * then kept current by a Supabase Realtime subscription on `list_items` filtered to this list;
 * edits go straight to `list_items` (row-level security lets only members through) and are applied
 * optimistically, then confirmed or rolled back. Otherwise ("polling" mode, mock and local
 * development): the list is read from `GET /me/lists/{id}` every few seconds and edits are sent as
 * a `PUT`, so two browsers still see each other. Merge rule: see `listSync.ts`.
 *
 * Offline (issue #101): an edit that fails because there is no connection is kept on screen and
 * queued in localStorage (`offlineQueue.ts`); the queue is replayed when the browser reports it is
 * online again, when the next poll or reconnect succeeds, and on the next visit. A server refusal
 * still rolls the edit back. The owner's member list changes optimistically too: revoking an
 * invite or removing a member disappears at once and comes back if the call fails.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  getList,
  listMembers,
  removeMember,
  revokeShareById,
  updateList,
  type ListMember,
  type CanonicalRef,
} from "@/api/client";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { useAuth } from "@/features/auth/AuthProvider";
import { getSupabase } from "@/features/auth/supabaseClient";
import type { ShareMessageKey } from "@/i18n/messages/share";
import {
  applyChange,
  changeFromPayload,
  itemFromRow,
  itemsOf,
  serverBody,
  type SharedItem,
} from "./listSync";
import {
  applyEdit,
  applyEdits,
  clearEdits,
  dropFirstEdits,
  enqueueEdit,
  isNetworkFailure,
  placeholderId,
  queuedEdits,
  useQueuedCount,
  type QueuedEdit,
} from "./offlineQueue";

export const POLL_MS = 4000;
const MEMBERS_MS = 10000;

export type SyncMode = "realtime" | "polling";
export type LoadStatus = "loading" | "ready" | "not-found" | "forbidden" | "error";

function statusOf(err: unknown): LoadStatus {
  if (err instanceof ApiError) {
    if (err.status === 404) return "not-found";
    if (err.status === 401 || err.status === 403) return "forbidden";
  }
  return "error";
}

type Supabase = NonNullable<ReturnType<typeof getSupabase>>;

/** Which row a member or invite is, whatever refreshes replace the object. */
const memberKey = (m: ListMember) =>
  m.share_id != null ? `s${m.share_id}` : `u${m.user_id ?? ""}`;

/** The hook raises message keys (`shareMessages`); the screen translates them, so a language
 * switch changes a message that is already showing. */
const REFUSED = "msgRefused" satisfies ShareMessageKey;

export function useSharedList(listId: number) {
  const auth = useAuth();
  const supabase = auth.status === "signed-in" ? getSupabase() : null;
  const mode: SyncMode = supabase ? "realtime" : "polling";
  const waiting = auth.configured && auth.status === "loading";

  const [status, setStatus] = useState<LoadStatus>("loading");
  const [name, setName] = useState("");
  const [items, setItems] = useState<SharedItem[]>([]);
  const [members, setMembers] = useState<ListMember[]>([]);
  const [live, setLive] = useState(false);
  const [message, setMessage] = useState<ShareMessageKey | null>(null);
  const pending = useQueuedCount(listId);
  const itemsRef = useRef<SharedItem[]>([]);
  const membersRef = useRef<ListMember[]>([]);
  const nameRef = useRef("");
  const inflight = useRef(0);
  const memberOps = useRef(0);
  const flushing = useRef(false);

  const commit = useCallback((next: SharedItem[]) => {
    itemsRef.current = next;
    setItems(next);
  }, []);

  const commitMembers = useCallback((next: ListMember[]) => {
    membersRef.current = next;
    setMembers(next);
  }, []);

  /** What the person should see: the server's list with their still-queued edits on top. */
  const withQueue = useCallback(
    (server: SharedItem[]) => applyEdits(server, queuedEdits(listId)),
    [listId],
  );

  const load = useCallback(async () => {
    try {
      ensureApiAuth();
      const list = await getList(listId);
      nameRef.current = list.name;
      setName(list.name);
      commit(withQueue(itemsOf(list)));
      setStatus("ready");
    } catch (err) {
      setStatus((prev) => (prev === "ready" ? prev : statusOf(err)));
    }
  }, [listId, commit, withQueue]);

  /** Writes one edit to Supabase (realtime mode). Returns the saved row for an add. */
  const writeRealtime = useCallback(
    async (client: Supabase, change: QueuedEdit): Promise<SharedItem | null> => {
      if (change.kind === "add") {
        const { data: user } = await client.auth.getUser();
        const { data, error } = await client
          .from("list_items")
          .insert({
            list_id: listId,
            user_id: user.user?.id,
            canonical_id: change.canonicalId,
            input_text: change.name,
            quantity: change.quantity,
            flex_level: "any_brand",
            sort: itemsRef.current.find((i) => i.id === change.itemId)?.sort ?? 0,
          })
          .select()
          .single();
        if (error || !data) throw error ?? new Error("no row");
        return itemFromRow(data as Parameters<typeof itemFromRow>[0]);
      }
      const table = client.from("list_items");
      const { error } =
        change.kind === "quantity"
          ? await table.update({ quantity: change.quantity }).eq("id", change.itemId)
          : change.kind === "checked"
            ? await table.update({ checked: change.checked }).eq("id", change.itemId)
            : await table.delete().eq("id", change.itemId);
      if (error) throw error;
      return null;
    },
    [listId],
  );

  /**
   * Replays the queue, oldest first, once the connection is back. Polling mode reads the list,
   * lays the edits on it and writes it whole; realtime mode writes each edit. A failure that is
   * still "no connection" keeps the rest for the next try; anything the server refuses is dropped
   * and the list is read again, with a note.
   */
  const flush = useCallback(async () => {
    if (flushing.current || inflight.current > 0) return;
    if (queuedEdits(listId).length === 0) return;
    if (typeof navigator !== "undefined" && navigator.onLine === false) return;
    flushing.current = true;
    inflight.current += 1;
    let refused = false;
    try {
      ensureApiAuth();
      // Edits made while this runs are queued behind the ones being sent, so go round again.
      for (let round = 0; round < 5; round++) {
        const edits = queuedEdits(listId);
        if (edits.length === 0) break;
        if (supabase) {
          // An item added offline has a placeholder id; later edits of it use the real id.
          const realIds = new Map<number, number>();
          for (const original of edits) {
            const change = {
              ...original,
              itemId: realIds.get(original.itemId) ?? original.itemId,
            };
            try {
              const saved = await writeRealtime(supabase, change);
              if (saved && original.kind === "add") realIds.set(original.itemId, saved.id);
            } catch (err) {
              if (isNetworkFailure(err)) throw err;
              refused = true;
            }
            dropFirstEdits(listId, 1);
          }
        } else {
          const server = await getList(listId);
          const merged = applyEdits(itemsOf(server), edits);
          await updateList(listId, serverBody(server.name, merged));
          dropFirstEdits(listId, edits.length);
        }
      }
    } catch (err) {
      if (!isNetworkFailure(err)) {
        clearEdits(listId);
        refused = true;
      }
    } finally {
      inflight.current -= 1;
      flushing.current = false;
    }
    if (refused) setMessage("msgPartial");
    if (queuedEdits(listId).length === 0) await load();
  }, [listId, supabase, writeRealtime, load]);

  // First read, and a new one whenever the sync mode changes (signing in mid-session).
  useEffect(() => {
    if (waiting) return;
    void load();
  }, [load, mode, waiting]);

  // The browser says it is online again: replay what was queued. A leftover queue from an earlier
  // visit is replayed as soon as the list has loaded.
  useEffect(() => {
    if (waiting) return;
    const onOnline = () => void flush();
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, [flush, waiting]);

  useEffect(() => {
    if (status === "ready") void flush();
  }, [status, flush]);

  // Polling fallback; a poll tick also retries a queue that `online` did not get through.
  useEffect(() => {
    if (mode !== "polling" || waiting) return;
    const timer = setInterval(() => {
      if (inflight.current !== 0 || status !== "ready") return;
      if (queuedEdits(listId).length > 0) void flush();
      else void load();
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [mode, waiting, status, load, flush, listId]);

  // Realtime subscription.
  useEffect(() => {
    if (!supabase) return;
    const channel = supabase
      .channel(`list-items-${listId}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "list_items", filter: `list_id=eq.${listId}` },
        (payload) => {
          const change = changeFromPayload(payload as Parameters<typeof changeFromPayload>[0]);
          if (change) commit(withQueue(applyChange(itemsRef.current, change)));
        },
      )
      .subscribe((s) => {
        const ok = s === "SUBSCRIBED";
        setLive(ok);
        // After (re)connecting, replay what was queued, then read the list again: it merges
        // whatever happened while offline.
        if (ok) void flush().then(() => load());
      });
    return () => {
      setLive(false);
      void supabase.removeChannel(channel);
    };
  }, [supabase, listId, commit, load, flush, withQueue]);

  // Members refresh slowly in both modes, but not while an optimistic change is in flight.
  useEffect(() => {
    if (waiting) return;
    let cancelled = false;
    const read = () =>
      listMembers(listId).then(
        (m) => {
          if (!cancelled && memberOps.current === 0) commitMembers(m);
        },
        () => {
          // Only the owner can read members; a member simply sees none.
        },
      );
    void read();
    const timer = setInterval(read, MEMBERS_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [listId, waiting, commitMembers]);

  /**
   * One edit: shown at once, then sent. No connection (or edits already waiting, to keep their
   * order) queues it; a refusal from the server undoes it with a message.
   */
  const edit = useCallback(
    async (change: QueuedEdit, failure: ShareMessageKey = REFUSED) => {
      const previous = itemsRef.current;
      const next = applyEdit(previous, change);
      commit(next);
      setMessage(null);
      const offline = typeof navigator !== "undefined" && navigator.onLine === false;
      if (offline || queuedEdits(listId).length > 0 || flushing.current) {
        enqueueEdit(listId, change, { append: flushing.current });
        return;
      }
      inflight.current += 1;
      try {
        if (supabase) {
          const saved = await writeRealtime(supabase, change);
          // Swap the draft for the real row; the Realtime INSERT for the same id is then an update.
          if (saved && change.kind === "add") {
            commit(
              applyChange(
                itemsRef.current.filter((i) => i.id !== change.itemId),
                { type: "upsert", item: saved },
              ),
            );
          }
        } else {
          ensureApiAuth();
          const saved = await updateList(listId, serverBody(nameRef.current, next));
          commit(withQueue(itemsOf(saved)));
        }
      } catch (err) {
        if (isNetworkFailure(err)) {
          enqueueEdit(listId, change);
        } else {
          commit(previous);
          setMessage(failure);
        }
      } finally {
        inflight.current -= 1;
      }
    },
    [supabase, listId, commit, writeRealtime, withQueue],
  );

  const setQuantity = useCallback(
    (id: number, quantity: number) => {
      if (quantity <= 0) return Promise.resolve();
      return edit({ kind: "quantity", itemId: id, quantity });
    },
    [edit],
  );

  const setChecked = useCallback(
    (id: number, checked: boolean) => edit({ kind: "checked", itemId: id, checked }),
    [edit],
  );

  const remove = useCallback((id: number) => edit({ kind: "remove", itemId: id }), [edit]);

  const add = useCallback(
    async (canonical: CanonicalRef) => {
      const existing = itemsRef.current.find((i) => i.canonicalId === canonical.canonical_id);
      if (existing) return setQuantity(existing.id, existing.quantity + 1);
      return edit(
        {
          kind: "add",
          itemId: placeholderId(),
          canonicalId: canonical.canonical_id,
          name: canonical.display_name_he,
          quantity: 1,
        },
        "msgAddFailed",
      );
    },
    [edit, setQuantity],
  );

  const refreshMembers = useCallback(async () => {
    try {
      commitMembers(await listMembers(listId));
    } catch {
      /* owner-only; ignore */
    }
  }, [listId, commitMembers]);

  /**
   * Optimistic removal of a member or a pending invite: it leaves the list now, comes back in the
   * same place when the call fails, and the member list is read again either way.
   */
  const dropMember = useCallback(
    async (target: ListMember, call: () => Promise<void>, failure: ShareMessageKey) => {
      const key = memberKey(target);
      const index = membersRef.current.findIndex((m) => memberKey(m) === key);
      if (index < 0) return;
      memberOps.current += 1;
      setMessage(null);
      commitMembers(membersRef.current.filter((m) => memberKey(m) !== key));
      try {
        ensureApiAuth();
        await call();
      } catch {
        if (!membersRef.current.some((m) => memberKey(m) === key)) {
          const back = [...membersRef.current];
          back.splice(Math.min(index, back.length), 0, target);
          commitMembers(back);
        }
        setMessage(failure);
      } finally {
        memberOps.current -= 1;
      }
      if (memberOps.current === 0) await refreshMembers();
    },
    [commitMembers, refreshMembers],
  );

  /** Cancels an invite nobody accepted yet: `DELETE /me/lists/{id}/shares/{share_id}`. */
  const revokeInvite = useCallback(
    (invite: ListMember) => {
      const shareId = invite.share_id;
      if (shareId == null) return Promise.resolve();
      return dropMember(invite, () => revokeShareById(listId, shareId), "msgRevokeFailed");
    },
    [dropMember, listId],
  );

  /** Takes a member off the list, through the share row when the API gave one, else the user id. */
  const removeListMember = useCallback(
    (member: ListMember) => {
      const { share_id: shareId, user_id: userId } = member;
      if (shareId == null && !userId) return Promise.resolve();
      return dropMember(
        member,
        () => (shareId != null ? revokeShareById(listId, shareId) : removeMember(listId, userId!)),
        "msgRemoveFailed",
      );
    },
    [dropMember, listId],
  );

  return {
    status,
    name,
    items,
    members,
    mode,
    live,
    message,
    /** Edits waiting for a connection ("ממתין לסנכרון"). */
    pending,
    setQuantity,
    setChecked,
    remove,
    add,
    refreshMembers,
    revokeInvite,
    removeListMember,
    reload: load,
  };
}
