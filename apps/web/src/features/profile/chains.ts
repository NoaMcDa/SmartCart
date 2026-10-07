/**
 * Chains the app knows by name (docs/decisions.md D13: the ten phase 0 chains). `id` is a slug, and
 * `apiId` is the chain id the API stores (the GS1 company prefix the transparency files carry), which
 * `GET /stores/nearest` takes. The slugs also match the chain_id values of the mock compare
 * fixtures; the API's `StoreResult.chain_id` is whatever it stores, so matching a compare result
 * also falls back to the Hebrew chain name.
 * Logos are deliberately text badges (a letter and the name): no real logos or trademarks.
 */
export type Chain = {
  id: string;
  /** Hebrew display name, also the club name sent in `clubs` (matches the API's club_name). */
  name: string;
  /** Single letter for the badge. */
  letter: string;
  /** The API's chain id, for `GET /stores/nearest?chain_id=`. */
  apiId: string;
};

export const CHAINS: ReadonlyArray<Chain> = [
  { id: "shufersal", name: "שופרסל", letter: "ש", apiId: "7290027600007" },
  { id: "rami_levy", name: "רמי לוי", letter: "ר", apiId: "7290058140886" },
  { id: "victory", name: "ויקטורי", letter: "ו", apiId: "7290696200003" },
  { id: "yeinot_bitan", name: "יינות ביתן", letter: "י", apiId: "7290055700007" },
  { id: "hazi_hinam", name: "חצי חינם", letter: "ח", apiId: "7290700100008" },
  { id: "tiv_taam", name: "טיב טעם", letter: "ט", apiId: "7290873255550" },
  { id: "osher_ad", name: "אושר עד", letter: "א", apiId: "7290103152017" },
  { id: "yochananof", name: "יוחננוף", letter: "י", apiId: "7290803800003" },
  { id: "machsanei_hashuk", name: "מחסני השוק", letter: "מ", apiId: "7290661400001" },
  { id: "king_store", name: "קינג סטור", letter: "ק", apiId: "7290058108879" },
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
 * The API takes `home_store_id` (a store), onboarding asks for a chain. Picking a chain resolves
 * the store with `GET /stores/nearest` (`adoptNearestHomeStore` in profileState.ts). This is the
 * fallback for when that lookup fails: the nearest store of the chosen chain in a compare result.
 * Returns null when the chain has no store in the result.
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
