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
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  getList,
  listMembers,
  updateList,
  type ListMember,
  type CanonicalRef,
} from "@/api/client";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { useAuth } from "@/features/auth/AuthProvider";
import { getSupabase } from "@/features/auth/supabaseClient";
import {
  applyChange,
  changeFromPayload,
  itemFromRow,
  itemsOf,
  serverBody,
  type SharedItem,
} from "./listSync";

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
  const [message, setMessage] = useState<string | null>(null);
  const itemsRef = useRef<SharedItem[]>([]);
  const nameRef = useRef("");
  const inflight = useRef(0);
  const tempId = useRef(0);

  const commit = useCallback((next: SharedItem[]) => {
    itemsRef.current = next;
    setItems(next);
  }, []);

  const load = useCallback(async () => {
    try {
      ensureApiAuth();
      const list = await getList(listId);
      nameRef.current = list.name;
      setName(list.name);
      commit(itemsOf(list));
      setStatus("ready");
    } catch (err) {
      setStatus((prev) => (prev === "ready" ? prev : statusOf(err)));
    }
  }, [listId, commit]);

  // First read, and a new one whenever the sync mode changes (signing in mid-session).
  useEffect(() => {
    if (waiting) return;
    void load();
  }, [load, mode, waiting]);

  // Polling fallback.
  useEffect(() => {
    if (mode !== "polling" || waiting) return;
    const timer = setInterval(() => {
      if (inflight.current === 0 && status === "ready") void load();
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [mode, waiting, status, load]);

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
          if (change) commit(applyChange(itemsRef.current, change));
        },
      )
      .subscribe((s) => {
        const ok = s === "SUBSCRIBED";
        setLive(ok);
        // After (re)connecting, read the list again: it merges whatever happened while offline.
        if (ok) void load();
      });
    return () => {
      setLive(false);
      void supabase.removeChannel(channel);
    };
  }, [supabase, listId, commit, load]);

  // Members refresh slowly in both modes.
  useEffect(() => {
    if (waiting) return;
    let cancelled = false;
    const read = () =>
      listMembers(listId).then(
        (m) => {
          if (!cancelled) setMembers(m);
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
  }, [listId, waiting]);

  const rollback = useCallback(
    (previous: SharedItem[], text: string) => {
      commit(previous);
      setMessage(text);
    },
    [commit],
  );

  /** Applies `next` optimistically and persists it; `write` is the realtime-mode write. */
  const persist = useCallback(
    async (
      next: SharedItem[],
      write: (client: NonNullable<typeof supabase>) => PromiseLike<{ error: unknown }>,
    ) => {
      const previous = itemsRef.current;
      commit(next);
      setMessage(null);
      inflight.current += 1;
      try {
        if (supabase) {
          const { error } = await write(supabase);
          if (error) throw error;
        } else {
          ensureApiAuth();
          const saved = await updateList(listId, serverBody(nameRef.current, next));
          commit(itemsOf(saved));
        }
      } catch {
        rollback(previous, "השינוי לא נשמר, אז החזרנו את הרשימה למה שהיה. נסי שוב.");
      } finally {
        inflight.current -= 1;
      }
    },
    [supabase, listId, commit, rollback],
  );

  const setQuantity = useCallback(
    (id: number, quantity: number) => {
      if (quantity <= 0) return Promise.resolve();
      const next = itemsRef.current.map((i) => (i.id === id ? { ...i, quantity } : i));
      return persist(next, (c) => c.from("list_items").update({ quantity }).eq("id", id));
    },
    [persist],
  );

  const remove = useCallback(
    (id: number) => {
      const next = itemsRef.current.filter((i) => i.id !== id);
      return persist(next, (c) => c.from("list_items").delete().eq("id", id));
    },
    [persist],
  );

  const add = useCallback(
    async (canonical: CanonicalRef) => {
      const existing = itemsRef.current.find((i) => i.canonicalId === canonical.canonical_id);
      if (existing) return setQuantity(existing.id, existing.quantity + 1);
      tempId.current -= 1;
      const draft = itemFromRow({
        id: tempId.current,
        canonical_id: canonical.canonical_id,
        input_text: canonical.display_name_he,
        quantity: 1,
        flex_level: "any_brand",
        sort: itemsRef.current.length,
      })!;
      const next = [...itemsRef.current, draft];
      if (!supabase) return persist(next, () => Promise.resolve({ error: null }));
      const previous = itemsRef.current;
      commit(next);
      setMessage(null);
      inflight.current += 1;
      try {
        const { data: user } = await supabase.auth.getUser();
        const { data, error } = await supabase
          .from("list_items")
          .insert({
            list_id: listId,
            user_id: user.user?.id,
            canonical_id: canonical.canonical_id,
            input_text: canonical.display_name_he,
            quantity: 1,
            flex_level: "any_brand",
            sort: draft.sort,
          })
          .select()
          .single();
        if (error || !data) throw error ?? new Error("no row");
        const saved = itemFromRow(data as Parameters<typeof itemFromRow>[0]);
        // Swap the draft for the real row; the Realtime INSERT for the same id is then an update.
        if (saved) {
          commit(
            applyChange(
              itemsRef.current.filter((i) => i.id !== draft.id),
              { type: "upsert", item: saved },
            ),
          );
        }
      } catch {
        rollback(previous, "הפריט לא נוסף. נסי שוב.");
      } finally {
        inflight.current -= 1;
      }
    },
    [supabase, listId, persist, setQuantity, commit, rollback],
  );

  const refreshMembers = useCallback(async () => {
    try {
      setMembers(await listMembers(listId));
    } catch {
      /* owner-only; ignore */
    }
  }, [listId]);

  return {
    status,
    name,
    items,
    members,
    mode,
    live,
    message,
    setQuantity,
    remove,
    add,
    refreshMembers,
    reload: load,
  };
}
