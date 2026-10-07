import { API_MOCK } from "@/api/config";

/**
 * Chains the app knows by name (docs/decisions.md D13: the ten phase 0 chains). The ids for the
 * first five match the chain_id values of the mock API fixtures; the API's real chain ids are
 * whatever `StoreResult.chain_id` carries, so matching also falls back to the Hebrew chain name.
 * Logos are deliberately text badges (a letter and the name): no real logos or trademarks.
 */
export type Chain = {
  id: string;
  /** Hebrew display name, also the club name sent in `clubs` (matches the API's club_name). */
  name: string;
  /** Single letter for the badge. */
  letter: string;
};

export const CHAINS: ReadonlyArray<Chain> = [
  { id: "shufersal", name: "שופרסל", letter: "ש" },
  { id: "rami_levy", name: "רמי לוי", letter: "ר" },
  { id: "victory", name: "ויקטורי", letter: "ו" },
  { id: "yeinot_bitan", name: "יינות ביתן", letter: "י" },
  { id: "hazi_hinam", name: "חצי חינם", letter: "ח" },
  { id: "tiv_taam", name: "טיב טעם", letter: "ט" },
  { id: "osher_ad", name: "אושר עד", letter: "א" },
  { id: "yochananof", name: "יוחננוף", letter: "י" },
  { id: "machsanei_hashuk", name: "מחסני השוק", letter: "מ" },
  { id: "king_store", name: "קינג סטור", letter: "ק" },
];

export function chainById(id: string | null | undefined): Chain | undefined {
  return id ? CHAINS.find((c) => c.id === id) : undefined;
}

/** Club names are chain names; the API matches `clubs` against the promo's club_name. */
export function clubLabel(name: string): string {
  return `מועדון ${name}`;
}

type StoreLike = { store_id: number; chain_id: string; chain_name: string; distance_m: number };

/**
 * The API takes `home_store_id` (a store), onboarding asks for a chain. Until the API offers a
 * "nearest store of chain X" lookup, the home store is the nearest store of the chosen chain in a
 * compare result. Returns null when the chain has no store in the result.
 */
export function resolveHomeStoreId(
  homeChainId: string | null,
  stores: ReadonlyArray<StoreLike>,
): number | null {
  const chain = chainById(homeChainId);
  if (!chain) return null;
  const matches = stores.filter(
    (s) =>
      s.chain_id === chain.id || s.chain_name === chain.name || s.chain_name.startsWith(chain.name),
  );
  const nearest = [...matches].sort((a, b) => a.distance_m - b.distance_m)[0];
  return nearest ? nearest.store_id : null;
}

/** Store ids of the mock API fixtures, one per chain (src/mocks/fixtures.ts). */
const MOCK_STORE_IDS: Record<string, number> = {
  rami_levy: 101,
  osher_ad: 102,
  shufersal: 103,
  yochananof: 104,
  victory: 105,
};

/**
 * With the API mock on, a chain resolves to its fixture store right away. Against the real API
 * there is no "nearest store of chain X" lookup yet (request to services/api), so this is null
 * and the id is adopted from a compare result later (`adoptHomeStore`).
 */
export function mockStoreIdFor(chainId: string | null): number | null {
  return API_MOCK && chainId ? (MOCK_STORE_IDS[chainId] ?? null) : null;
}
