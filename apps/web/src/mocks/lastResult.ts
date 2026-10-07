/**
 * Fixtures for the split, map and store screens, built from the mock catalog: the weekly basket
 * compared in Modi'in with Shufersal as the home store, so the split is Rami Levy + Osher Ad with
 * net saving 41 (basket 75, travel 9, extra stop 25).
 * - `lastResultFixture()`: the assembled comparison (what `useComparison` returns), for pure tests.
 * - `weeklyListState()` and `shopperSeed()`: the persisted core state (`sc-list-v1`,
 *   `sc-profile-v1`) from which the screens build that comparison through the mock API. The
 *   Playwright specs seed these into localStorage.
 * Imports from the app are type-only so Playwright can load this file without the "@" alias.
 */
import type { LastResult } from "@/features/split/lastResult";
import type { ListState } from "@/state/list";
import {
  CATALOG,
  HOME_STORE_ID,
  WEEKLY_BASKET,
  canonicalRef,
  compareFixture,
  optimizeFixture,
} from "./fixtures";

export function lastResultFixture(overrides: Partial<LastResult> = {}): LastResult {
  return {
    version: 1,
    savedAt: "2026-10-07T04:00:00.000Z",
    listName: "הקנייה השבועית",
    location: { lat: 31.899, lon: 35.007, radius_m: 5000 },
    homeStoreId: HOME_STORE_ID,
    travel: { mode: "car", cost_per_km: 1.2, extra_stop_value: 25 },
    compare: compareFixture(HOME_STORE_ID),
    optimize: optimizeFixture({ homeStoreId: HOME_STORE_ID }),
    taxonomy: Object.fromEntries(
      Object.values(CATALOG).map((c) => [c.canonical_id, c.taxonomy_id]),
    ),
    ...overrides,
  };
}

/** The weekly basket as the core screens' persisted list (`sc-list-v1`). */
export function weeklyListState(): ListState {
  return {
    version: 1,
    name: "הקנייה השבועית",
    items: WEEKLY_BASKET.map((b) => {
      const c = canonicalRef(b.canonical_id);
      return {
        id: `seed-${b.canonical_id}`,
        inputText: c.display_name_he,
        canonical: c,
        candidates: [],
        quantity: b.quantity,
        unit: null,
        isWeighed: CATALOG[b.canonical_id]?.weighed === true,
        flexLevel: b.flex_level,
        allow: [],
        exactItemId: null,
        needsConfirmation: false,
        notFound: false,
        confidence: 1,
      };
    }),
    flexDefaults: {},
    updatedAt: null,
  };
}

/** The shopper context the comparison reads (`sc-profile-v1`): Modi'in, 5 km, home store 103. */
export function shopperSeed(over: Record<string, unknown> = {}) {
  return {
    neighborhood_lat: 31.897,
    neighborhood_lon: 35.01,
    city_label: "מודיעין-מכבים-רעות",
    radius_m: 5000,
    home_store_id: HOME_STORE_ID,
    clubs: [],
    travel_mode: "car",
    cost_per_km: "1.2",
    extra_stop_value: "25",
    ...over,
  };
}
