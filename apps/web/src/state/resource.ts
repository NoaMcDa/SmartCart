/**
 * A keyed async cache read through useSyncExternalStore. Screens ask for a key; the first reader
 * starts the request, every reader of the same key shares the result, and moving between the
 * results and the substitution card does not refetch.
 */
import { useEffect, useSyncExternalStore } from "react";

export type Resource<T> =
  | { status: "idle" }
  | { status: "loading"; data?: T }
  | { status: "success"; data: T }
  | { status: "error"; error: unknown; data?: T };

const IDLE = { status: "idle" } as const;

export function createResourceCache<I, T>(fetcher: (input: I) => Promise<T>, maxEntries = 20) {
  const entries = new Map<string, Resource<T>>();
  const listeners = new Set<() => void>();
  const emit = () => listeners.forEach((l) => l());

  function set(key: string, value: Resource<T>) {
    entries.delete(key);
    entries.set(key, value);
    while (entries.size > maxEntries) {
      const oldest = entries.keys().next().value;
      if (oldest === undefined) break;
      entries.delete(oldest);
    }
    emit();
  }

  function load(key: string, input: I, force = false) {
    const current = entries.get(key);
    if (!force && current && current.status !== "error") return;
    set(key, { status: "loading", data: current && "data" in current ? current.data : undefined });
    fetcher(input).then(
      (data) => set(key, { status: "success", data }),
      (error: unknown) => set(key, { status: "error", error }),
    );
  }

  function get(key: string | null): Resource<T> {
    return (key && entries.get(key)) || IDLE;
  }

  function subscribe(l: () => void) {
    listeners.add(l);
    return () => {
      listeners.delete(l);
    };
  }

  /** Read (and start loading) `input` under `key`; null key = nothing to load yet. */
  function useResource(key: string | null, input: I | null) {
    const value = useSyncExternalStore(
      subscribe,
      () => get(key),
      () => IDLE,
    );
    useEffect(() => {
      if (key && input !== null) load(key, input);
      // input is described by key
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [key]);
    return {
      ...value,
      reload: () => {
        if (key && input !== null) load(key, input, true);
      },
    };
  }

  return {
    useResource,
    load,
    get,
    clear: () => {
      entries.clear();
      emit();
    },
  };
}
