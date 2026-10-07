"use client";

import { swapSuggestions, type CompareInput, type SwapSuggestionResponse } from "@/api/client";
import { createResourceCache } from "@/state/resource";

type SwapsRequest = { storeId: number; body: CompareInput };

const cache = createResourceCache<SwapsRequest, SwapSuggestionResponse>((r) =>
  swapSuggestions(r.storeId, r.body),
);

/**
 * `POST /optimize/swaps` for the list at one store. Shares its result between renders and screens;
 * the key covers the store and the exact request, so a changed list refetches.
 */
export function useSwaps(request: SwapsRequest | null) {
  return cache.useResource(
    request ? `${request.storeId}|${JSON.stringify(request.body)}` : null,
    request,
  );
}

export function clearSwapsCache() {
  cache.clear();
}
