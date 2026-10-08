"use client";

import { api, type ChainOnline } from "@/api/client";
import { createResourceCache } from "@/state/resource";

/**
 * `GET /chains/online`, fetched once and shared by every card on the screen. The list is small and
 * public (the API caches it for an hour). A failed request leaves the status at "error": the cards
 * then show no handoff action, and the results are not affected in any way.
 */
const cache = createResourceCache<true, ChainOnline[]>(async () => {
  const { data, response } = await api.GET("/chains/online");
  if (data === undefined || !response.ok) throw new Error(`chains/online ${response.status}`);
  return data;
});

const KEY = "chains-online";

/** The chains, or null while loading, on an error, or before the first request. */
export function useChainsOnline(): ChainOnline[] | null {
  const resource = cache.useResource(KEY, true);
  return resource.status === "success" ? resource.data : null;
}

export function clearChainsOnlineCache() {
  cache.clear();
}
